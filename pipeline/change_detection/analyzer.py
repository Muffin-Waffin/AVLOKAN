"""Application-level orchestration for reusable BIT change analysis."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from typing import Any
import uuid

import numpy as np
import rasterio
import yaml

from pipeline.change_detection.bit import BITDetector, BIT_MODEL_NAME
from pipeline.change_detection.postprocessing import (
    CandidateFilteringConfig,
    PostprocessingConfig,
    analyze_candidates,
    component_statistics,
    postprocess_probability,
    threshold_probability,
)
from pipeline.change_detection.inference import infer_pair_arrays
from pipeline.change_detection.temporal_pair import TemporalPair, TemporalPairError


@dataclass(frozen=True)
class ChangeAnalysisConfig:
    checkpoint: Path | None
    checkpoint_role: str = "explicit_checkpoint"
    checkpoint_sha256: str | None = None
    device: str = "auto"
    threshold: float = 0.96
    minimum_component_area: int = 32
    morphology: str = "none"
    candidate_filtering: CandidateFilteringConfig = CandidateFilteringConfig()
    output_directory: Path = Path("data/processed/change_analysis")
    save_probability: bool = True
    raw_mask_threshold: float = 0.50
    compute_temporal_embedding_similarity: bool = False
    remoteclip_checkpoint: Path = Path("models/remoteclip/RemoteCLIP-ViT-B-32.pt")

    @classmethod
    def load(cls, path: str | Path, *, checkpoint: str | Path | None = None) -> "ChangeAnalysisConfig":
        config_path = Path(path)
        if not config_path.is_file():
            raise FileNotFoundError(f"Change-analysis config does not exist: {config_path}")
        try:
            values = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid change-analysis YAML {config_path}: {exc}") from exc
        if not isinstance(values, dict):
            raise ValueError(f"Change-analysis config must contain a mapping: {config_path}")
        allowed = {
            "checkpoint", "checkpoint_role", "checkpoint_sha256", "device", "threshold", "minimum_component_area", "morphology",
            "quality_mask", "output_directory", "save_probability", "save_raw_mask",
            "save_final_mask", "raw_mask_threshold", "remoteclip_checkpoint",
            "compute_temporal_embedding_similarity",
            "candidate_filtering",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unknown change-analysis config keys: {sorted(unknown)}")
        if values.get("quality_mask", "nodata_and_nonfinite") != "nodata_and_nonfinite":
            raise ValueError("quality_mask currently supports only nodata_and_nonfinite")
        if values.get("save_raw_mask", True) is not True or values.get("save_final_mask", True) is not True:
            raise ValueError("raw and final masks are required outputs")
        checkpoint_value = checkpoint if checkpoint is not None else values.get("checkpoint")
        resolved = lambda value: (Path(value) if Path(value).is_absolute() else config_path.parent.parent / value)
        result = cls(
            checkpoint=resolved(checkpoint_value) if checkpoint_value else None,
            checkpoint_role=str(values.get("checkpoint_role", "explicit_checkpoint")),
            checkpoint_sha256=values.get("checkpoint_sha256"),
            device=str(values.get("device", "auto")),
            threshold=float(values.get("threshold", 0.96)),
            minimum_component_area=int(values.get("minimum_component_area", 32)),
            morphology=str(values.get("morphology", "none")),
            candidate_filtering=CandidateFilteringConfig(**values.get("candidate_filtering", {})),
            output_directory=resolved(values.get("output_directory", "data/processed/change_analysis")),
            save_probability=bool(values.get("save_probability", True)),
            raw_mask_threshold=float(values.get("raw_mask_threshold", 0.50)),
            compute_temporal_embedding_similarity=bool(values.get("compute_temporal_embedding_similarity", False)),
            remoteclip_checkpoint=resolved(values.get("remoteclip_checkpoint", "models/remoteclip/RemoteCLIP-ViT-B-32.pt")),
        )
        result.validate()
        return result

    def validate(self) -> None:
        if self.checkpoint is None:
            raise ValueError("A BIT checkpoint must be explicitly configured or passed with --checkpoint")
        if self.checkpoint_sha256 is not None and (
            len(self.checkpoint_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.checkpoint_sha256.lower())
        ):
            raise ValueError("checkpoint_sha256 must be a 64-character hexadecimal SHA-256")
        if not np.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be finite and within [0, 1]")
        if not np.isfinite(self.raw_mask_threshold) or not 0 <= self.raw_mask_threshold <= 1:
            raise ValueError("raw_mask_threshold must be finite and within [0, 1]")
        PostprocessingConfig(self.threshold, self.minimum_component_area, self.morphology)
        if not isinstance(self.candidate_filtering, CandidateFilteringConfig):
            raise ValueError("candidate_filtering must be a CandidateFilteringConfig")
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be one of: auto, cpu, cuda")


@dataclass(frozen=True)
class ChangeAnalysisResult:
    analysis_id: str
    timestamp: str
    pair_id: str
    t1_scene_id: str | None
    t2_scene_id: str | None
    t1_acquisition_timestamp: str
    t2_acquisition_timestamp: str
    sensor: str
    crs: str
    transform: tuple[float, ...]
    width: int
    height: int
    pixel_resolution: tuple[float, float]
    bounding_box: tuple[float, float, float, float]
    pixel_area_m2: float | None
    model_name: str
    checkpoint_path: str
    checkpoint_role: str
    checkpoint_sha256: str
    model_configuration: dict[str, Any] | None
    probability_raster: str | None
    raw_mask_raster: str
    final_mask_raster: str
    candidate_mask_raster: str
    candidates: list[dict[str, Any]]
    candidate_count: int
    filtering_statistics: dict[str, int]
    metadata_path: str
    threshold: float
    postprocessing: dict[str, Any]
    statistics: dict[str, Any]
    temporal_embedding_similarity: float | None
    timings_seconds: dict[str, float]
    provenance: dict[str, Any]


def _read_rgb_preview(path: Path):
    from PIL import Image
    from rasterio.enums import Resampling

    with rasterio.open(path) as src:
        data = src.read((3, 2, 1), out_shape=(3, 224, 224), resampling=Resampling.average, masked=True)
        values = np.asarray(data.filled(0), dtype=np.float32)
    rgb = np.rint(np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8)
    return Image.fromarray(np.moveaxis(rgb, 0, -1), mode="RGB")


def compare_temporal_embeddings(adapter, t1_path: Path, t2_path: Path) -> float:
    """Cosine similarity of normalized RemoteCLIP image embeddings for T1 and T2 previews."""
    embeddings = adapter.encode_images([_read_rgb_preview(t1_path), _read_rgb_preview(t2_path)])
    if embeddings.shape[0] != 2 or embeddings.ndim != 2:
        raise RuntimeError("RemoteCLIP did not return two temporal image embeddings")
    return float(np.clip(np.dot(embeddings[0], embeddings[1]), -1.0, 1.0))


def _spatial_pixel_area(crs_text: str, transform: rasterio.Affine) -> float | None:
    try:
        crs = rasterio.crs.CRS.from_string(crs_text)
        if not crs.is_projected:
            return None
        units, factor = crs.linear_units_factor
        if not units or not factor:
            return None
        map_area = abs(transform.a * transform.e - transform.b * transform.d)
        return float(map_area * factor * factor)
    except Exception:
        return None


class ChangeAnalyzer:
    """Reusable application wrapper around the repository's existing BIT implementation."""

    def __init__(self, config: ChangeAnalysisConfig):
        config.validate()
        self.config = config

    def analyze(self, pair: TemporalPair, config: ChangeAnalysisConfig | None = None) -> ChangeAnalysisResult:
        selected = config or self.config
        selected.validate()
        if pair.sensor.lower().replace("-", "") not in {"sentinel2", "s2"}:
            raise ValueError(f"Unsupported sensor {pair.sensor!r}; BIT application inputs currently require Sentinel-2")
        for name, path in (("T1", pair.t1_path), ("T2", pair.t2_path)):
            if not path.is_file():
                raise FileNotFoundError(f"{name} input raster is missing: {path}")
        with rasterio.open(pair.t1_path) as first, rasterio.open(pair.t2_path) as second:
            if first.count < 4 or second.count < 4:
                raise TemporalPairError("Sentinel-2 inputs must provide bands B02, B03, B04, B08 in that order")
            if first.dtypes[:4] != ("float32",) * 4 or second.dtypes[:4] != ("float32",) * 4:
                raise TemporalPairError("BIT Sentinel-2 inputs must be float32 surface reflectance")
            required_descriptions = ("B02", "B03", "B04", "B08")
            for source in (first, second):
                descriptions = tuple(source.descriptions[:4])
                if any(descriptions) and descriptions != required_descriptions:
                    raise TemporalPairError(
                        f"Band descriptions must be B02/B03/B04/B08 in order, got {descriptions}"
                    )
            if first.crs != second.crs or first.transform != second.transform:
                raise TemporalPairError("T1 and T2 CRS/transform changed after temporal-pair validation")
            if first.dtypes != second.dtypes or (first.width, first.height) != (second.width, second.height):
                raise TemporalPairError("T1 and T2 band types or dimensions do not match")
            grid_profile = first.profile.copy()
            t1_tags, t2_tags = first.tags(), second.tags()
            bounds = tuple(first.bounds)
            crs_text = first.crs.to_string()
            transform = first.transform

        timings = {"model_load": 0.0, "preprocessing": 0.0, "inference": 0.0, "postprocessing": 0.0,
                   "candidate_extraction": 0.0, "candidate_filtering": 0.0, "candidate_scoring": 0.0}
        started = perf_counter()
        load_started = perf_counter()
        detector = BITDetector(selected.checkpoint, device=selected.device)
        timings["model_load"] = perf_counter() - load_started
        if selected.checkpoint_sha256 and detector.checkpoint_sha256.lower() != selected.checkpoint_sha256.lower():
            raise RuntimeError(
                f"Configured checkpoint SHA-256 does not match {detector.checkpoint_path}: "
                f"expected {selected.checkpoint_sha256}, got {detector.checkpoint_sha256}"
            )

        analysis_id = uuid.uuid4().hex
        output_dir = Path(selected.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        probability_path = output_dir / f"{analysis_id}_probability.tif"
        raw_mask_path = output_dir / f"{analysis_id}_raw_mask.tif"
        final_mask_path = output_dir / f"{analysis_id}_mask.tif"
        metadata_path = output_dir / f"{analysis_id}_metadata.json"
        probability, valid, inference_timings = infer_pair_arrays(pair, detector)
        timings["preprocessing"] = inference_timings["preprocessing"]
        timings["inference"] = inference_timings["inference"]

        probability_profile = grid_profile.copy()
        probability_profile.update(count=1, dtype="float32", nodata=None, compress="deflate", predictor=3)
        mask_profile = grid_profile.copy()
        mask_profile.update(count=1, dtype="uint8", nodata=None, compress="deflate", predictor=2)
        if selected.save_probability:
            with rasterio.open(probability_path, "w", **probability_profile) as dst:
                dst.write(probability, 1)
                dst.update_tags(model=BIT_MODEL_NAME, checkpoint_sha256=detector.checkpoint_sha256,
                                pair_id=pair.pair_id, product="change_probability",
                                probability_semantics="softmax change-class probability")

        post_started = perf_counter()
        final_mask = postprocess_probability(
            probability,
            PostprocessingConfig(selected.threshold, selected.minimum_component_area, selected.morphology),
            valid_mask=valid,
        )
        raw_mask = threshold_probability(probability, selected.raw_mask_threshold)
        raw_mask[~valid] = 0
        final_mask, candidates, filtering_statistics, candidate_timings = analyze_candidates(
            probability, final_mask, threshold=selected.threshold, valid_mask=valid,
            config=selected.candidate_filtering,
        )
        timings.update(candidate_timings)
        for candidate in candidates:
            bbox = candidate["bbox_pixels"]
            corners = [
                transform @ (col, row)
                for col, row in (
                    (bbox["xmin"], bbox["ymin"]),
                    (bbox["xmax_exclusive"], bbox["ymin"]),
                    (bbox["xmin"], bbox["ymax_exclusive"]),
                    (bbox["xmax_exclusive"], bbox["ymax_exclusive"]),
                )
            ]
            center_x, center_y = transform @ (
                candidate["centroid_pixels"]["x"] + 0.5,
                candidate["centroid_pixels"]["y"] + 0.5,
            )
            candidate["bbox_coordinates"] = {
                "xmin": float(min(point[0] for point in corners)),
                "ymin": float(min(point[1] for point in corners)),
                "xmax": float(max(point[0] for point in corners)),
                "ymax": float(max(point[1] for point in corners)),
                "crs": crs_text,
            }
            candidate["centroid_coordinates"] = {"x": float(center_x), "y": float(center_y), "crs": crs_text}
        with rasterio.open(raw_mask_path, "w", **mask_profile) as dst:
            dst.write(raw_mask, 1)
            dst.update_tags(threshold=str(selected.raw_mask_threshold), values="0=no change, 1=change")
        with rasterio.open(final_mask_path, "w", **mask_profile) as dst:
            dst.write(final_mask, 1)
            dst.update_tags(threshold=str(selected.threshold), minimum_component_area=str(selected.minimum_component_area),
                            morphology=selected.morphology, connectivity="8", values="0=no change, 1=change")
        timings["postprocessing"] = perf_counter() - post_started
        stats = component_statistics(final_mask, valid)
        stats["candidate_count"] = filtering_statistics["components_retained"]
        stats["raw_candidate_component_count"] = filtering_statistics["raw_component_count"]
        pixel_area = _spatial_pixel_area(crs_text, transform)
        if pixel_area is not None:
            stats["changed_area_m2"] = stats["changed_pixels"] * pixel_area
        similarity = None
        if selected.compute_temporal_embedding_similarity:
            from pipeline.embeddings.remoteclip import RemoteCLIPAdapter
            adapter = RemoteCLIPAdapter(selected.remoteclip_checkpoint, device=selected.device)
            timings["model_load"] += float(adapter.load_seconds)
            embedding_preprocess_before = adapter.preprocessing_seconds
            embedding_inference_before = adapter.inference_seconds
            similarity = compare_temporal_embeddings(adapter, pair.t1_path, pair.t2_path)
            timings["preprocessing"] += adapter.preprocessing_seconds - embedding_preprocess_before
            timings["inference"] += adapter.inference_seconds - embedding_inference_before
        timings["total"] = perf_counter() - started
        provenance = {
            "source_files": {"T1": str(pair.t1_path), "T2": str(pair.t2_path)},
            "input_band_order": ["B02", "B03", "B04", "B08"],
            "model_band_order": ["B04", "B03", "B02"],
            "normalization": "reflectance clip [0,1], then map linearly to [-1,1]",
            "quality_mask": "intersection of source nodata and finite B04/B03/B02 pixels; invalid outputs encoded as zero",
            "checkpoint": str(detector.checkpoint_path),
            "checkpoint_role": selected.checkpoint_role,
            "checkpoint_sha256": detector.checkpoint_sha256,
            "threshold": selected.threshold,
            "raw_mask_threshold": selected.raw_mask_threshold,
            "postprocessing": {"minimum_component_area": selected.minimum_component_area,
                               "morphology": selected.morphology, "connectivity": 8,
                               "candidate_filtering": asdict(selected.candidate_filtering),
                               "candidate_score": "mean component BIT change-class probability; ranking only, not calibrated"},
            "calibration_note": "0.96 is the selected pooled OOF calibration threshold; not a universal probability calibration claim",
            "temporal_order": "supplied T1/T2 roles preserved; no automatic reordering",
        }
        result = ChangeAnalysisResult(
            analysis_id=analysis_id, timestamp=datetime.now(timezone.utc).isoformat(), pair_id=pair.pair_id,
            t1_scene_id=t1_tags.get("source_scene_id"), t2_scene_id=t2_tags.get("source_scene_id"),
            t1_acquisition_timestamp=t1_tags.get("acquisition_datetime", pair.t1_date.isoformat()),
            t2_acquisition_timestamp=t2_tags.get("acquisition_datetime", pair.t2_date.isoformat()),
            sensor=pair.sensor, crs=crs_text, transform=tuple(transform), width=pair.width, height=pair.height,
            pixel_resolution=pair.resolution, bounding_box=bounds, pixel_area_m2=pixel_area,
            model_name=BIT_MODEL_NAME, checkpoint_path=str(detector.checkpoint_path),
            checkpoint_role=selected.checkpoint_role,
            checkpoint_sha256=detector.checkpoint_sha256, model_configuration=detector.model_config,
            probability_raster=str(probability_path) if selected.save_probability else None,
            raw_mask_raster=str(raw_mask_path), final_mask_raster=str(final_mask_path),
            candidate_mask_raster=str(final_mask_path), candidates=candidates,
            candidate_count=filtering_statistics["components_retained"],
            filtering_statistics=filtering_statistics,
            metadata_path=str(metadata_path), threshold=selected.threshold,
            postprocessing={"minimum_component_area": selected.minimum_component_area,
                            "morphology": selected.morphology, "connectivity": 8,
                            "candidate_filtering": asdict(selected.candidate_filtering),
                            "candidate_score": "mean component BIT change-class probability; ranking only, not calibrated"},
            statistics=stats, temporal_embedding_similarity=similarity,
            timings_seconds={key: float(value) for key, value in timings.items()}, provenance=provenance,
        )
        metadata_path.write_text(json.dumps(asdict(result), indent=2, default=str), encoding="utf-8")
        return result
