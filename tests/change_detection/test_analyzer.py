from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
import torch

from pipeline.change_detection.analyzer import (
    ChangeAnalysisConfig,
    ChangeAnalyzer,
    ChangeAnalysisResult,
    component_statistics,
)
from pipeline.change_detection.bit import BITDetector
from pipeline.change_detection.postprocessing import PostprocessingConfig, postprocess_probability
from pipeline.change_detection.temporal_pair import TemporalPair, TemporalPairError


def _write_source(path: Path, *, width: int = 12, height: int = 10, xoff: float = 500000) -> None:
    data = np.full((4, height, width), 3000, dtype=np.float32)
    with rasterio.open(path, "w", driver="GTiff", width=width, height=height, count=4,
                       dtype="float32", crs="EPSG:32643",
                       transform=from_origin(xoff, 2500000, 10, 10), nodata=-9999) as dst:
        dst.write(data)
        dst.set_band_description(1, "B02")
        dst.set_band_description(2, "B03")
        dst.set_band_description(3, "B04")
        dst.set_band_description(4, "B08")
        dst.update_tags(sensor="sentinel-2", source_scene_id=path.stem,
                        acquisition_datetime="2025-03-24T05:26:49Z")


@pytest.fixture
def pair_files(tmp_path):
    first, second = tmp_path / "t1.tif", tmp_path / "t2.tif"
    _write_source(first)
    _write_source(second)
    pair = TemporalPair.from_paths(tile_id="fixture", t1_path=first, t2_path=second,
                                   t1_date="2025-03-24", t2_date="2025-03-29")
    return first, second, pair


def test_configuration_load_requires_explicit_checkpoint_and_validates(tmp_path):
    cfg = tmp_path / "change.yaml"
    cfg.write_text("checkpoint: null\nthreshold: 0.96\nminimum_component_area: 32\nmorphology: none\n", encoding="utf-8")
    with pytest.raises(ValueError, match="explicitly configured"):
        ChangeAnalysisConfig.load(cfg)
    loaded = ChangeAnalysisConfig.load(cfg, checkpoint="models/example.pt")
    assert loaded.checkpoint == (tmp_path.parent / "models/example.pt")
    assert loaded.threshold == 0.96
    assert loaded.minimum_component_area == 32
    with pytest.raises(ValueError, match="threshold"):
        replace(loaded, threshold=1.1).validate()
    cfg.write_text(
        "checkpoint: demo.pt\ncandidate_filtering:\n  enabled: true\n  min_valid_fraction: 1.5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="min_valid_fraction"):
        ChangeAnalysisConfig.load(cfg)


def test_temporal_pair_validation_rejects_band_grid_and_date_issues(pair_files, tmp_path):
    first, second, _ = pair_files
    short = tmp_path / "short.tif"
    with rasterio.open(short, "w", driver="GTiff", width=11, height=10, count=4,
                       dtype="float32", crs="EPSG:32643",
                       transform=from_origin(500000, 2500000, 10, 10)) as dst:
        dst.write(np.ones((4, 10, 11), dtype=np.float32))
    with pytest.raises(TemporalPairError, match="dimensions"):
        TemporalPair.from_paths(tile_id="bad", t1_path=first, t2_path=short,
                                t1_date="2025-03-24", t2_date="2025-03-29")
    with pytest.raises(TemporalPairError, match="earlier"):
        TemporalPair.from_paths(tile_id="bad", t1_path=first, t2_path=second,
                                t1_date="2025-03-29", t2_date="2025-03-24")


def test_checkpoint_loading_accepts_verified_oscd_container():
    checkpoint = Path("models/bit/BIT_OSCD_CV5/fold_0/best_oscd_bit.pt")
    if not checkpoint.is_file():
        pytest.skip("local OSCD fold checkpoint is not present")
    detector = BITDetector(checkpoint, device="cpu")
    assert detector.checkpoint_sha256
    assert detector.model_config["cross_validation"]["fold"] == 0


def test_postprocessing_and_statistics_use_8_connectivity():
    probability = np.zeros((5, 5), dtype=np.float32)
    probability[0, 0] = probability[1, 1] = 0.99
    probability[4, 4] = 0.99
    final = postprocess_probability(probability, PostprocessingConfig(0.96, 2, "none"))
    assert final.dtype == np.uint8
    assert set(np.unique(final)) <= {0, 1}
    np.testing.assert_array_equal(final, np.eye(5, dtype=np.uint8)[:5] * np.array(
        [[1, 0, 0, 0, 0], [0, 1, 0, 0, 0], [0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]], dtype=np.uint8))
    stats = component_statistics(final)
    assert stats["total_pixels"] == 25
    assert stats["valid_pixels"] == 25
    assert stats["changed_pixels"] == 2
    assert stats["connected_component_count"] == 1
    assert stats["largest_component_pixels"] == 2


class _FakeDetector:
    def __init__(self, checkpoint_path, *, device):
        self.checkpoint_path = Path(checkpoint_path)
        self.checkpoint_sha256 = "test-checkpoint-hash"
        self.model_config = {"architecture": "test-double"}

    def predict(self, t1, t2, *, threshold, target_shape):
        probability = torch.zeros((1, *target_shape), dtype=torch.float32)
        probability[:, 2:5, 3:7] = 0.99
        return {"probability": probability}


def test_analyzer_writes_aligned_outputs_metadata_and_deterministic_pixels(pair_files, tmp_path, monkeypatch):
    _, _, pair = pair_files
    checkpoint = tmp_path / "explicit.pt"
    checkpoint.write_bytes(b"test")
    monkeypatch.setattr("pipeline.change_detection.analyzer.BITDetector", _FakeDetector)
    config = ChangeAnalysisConfig(checkpoint=checkpoint, device="cpu", output_directory=tmp_path / "out",
                                  threshold=0.96, minimum_component_area=1)
    first = ChangeAnalyzer(config).analyze(pair)
    second = ChangeAnalyzer(config).analyze(pair)
    assert isinstance(first, ChangeAnalysisResult)
    assert first.statistics["changed_pixels"] == 12
    assert first.statistics["connected_component_count"] == 1
    assert first.statistics["changed_area_m2"] == 1200
    assert first.temporal_embedding_similarity is None
    for path in (first.probability_raster, first.raw_mask_raster, first.final_mask_raster,
                 first.metadata_path):
        assert Path(path).is_file()
    with rasterio.open(first.probability_raster) as probability, \
            rasterio.open(first.raw_mask_raster) as raw_mask, \
            rasterio.open(first.final_mask_raster) as mask, \
            rasterio.open(pair.t1_path) as source:
        assert probability.dtypes == ("float32",)
        assert raw_mask.dtypes == mask.dtypes == ("uint8",)
        assert probability.shape == mask.shape == (pair.height, pair.width)
        assert probability.crs.to_string() == pair.crs
        assert tuple(probability.transform) == tuple(mask.transform) == tuple(source.transform)
        values = probability.read(1)
        assert np.isfinite(values).all() and values.min() >= 0 and values.max() <= 1
        assert set(np.unique(mask.read(1))) <= {0, 1}
        expected_raw = (values >= 0.50).astype(np.uint8)
        np.testing.assert_array_equal(raw_mask.read(1), expected_raw)
    with rasterio.open(first.final_mask_raster) as one, rasterio.open(second.final_mask_raster) as two:
        np.testing.assert_array_equal(one.read(1), two.read(1))
    assert first.statistics == second.statistics
    assert Path(first.metadata_path).read_text(encoding="utf-8").find("test-checkpoint-hash") >= 0


@pytest.mark.integration
def test_real_sentinel2_pair_change_analysis(tmp_path):
    root = Path(__file__).resolve().parents[2]
    config_path = root / "configs/change_detection.yaml"
    t1 = root / "data/processed/phase2_validation/s2_reflectance_512.tif"
    t2 = root / "data/processed/phase6_validation/s2_20250324_512.tif"
    if not config_path.is_file() or not t1.is_file() or not t2.is_file():
        pytest.skip("local Phase 6 configuration, checkpoint, or Sentinel-2 pair is absent")
    config = ChangeAnalysisConfig.load(config_path)
    if not config.checkpoint.is_file():
        pytest.skip("configured local BIT checkpoint is absent")
    if config.compute_temporal_embedding_similarity and not config.remoteclip_checkpoint.is_file():
        pytest.skip("configured local RemoteCLIP checkpoint is absent")
    assert config.checkpoint_role == "prototype_demo_checkpoint"
    pair = TemporalPair.from_paths(tile_id="phase6-validation", t1_path=t1, t2_path=t2,
                                   t1_date="2025-03-29T05:28:41.025Z",
                                   t2_date="2025-03-24T05:26:49.024000Z",
                                   allow_reversed_dates=True)
    config = replace(config, device="auto", output_directory=tmp_path)
    one = ChangeAnalyzer(config).analyze(pair)
    two = ChangeAnalyzer(config).analyze(pair)
    assert one.statistics == two.statistics
    assert one.temporal_embedding_similarity == pytest.approx(two.temporal_embedding_similarity, abs=1e-7)
    assert one.checkpoint_sha256 == config.checkpoint_sha256
    assert one.checkpoint_role == "prototype_demo_checkpoint"
    with rasterio.open(pair.t1_path) as source_t1, rasterio.open(pair.t2_path) as source_t2:
        valid = np.ones((pair.height, pair.width), dtype=bool)
        for source in (source_t1, source_t2):
            bands = source.read((3, 2, 1), masked=True)
            valid &= ~np.ma.getmaskarray(bands).any(axis=0) & np.isfinite(bands.filled(np.nan)).all(axis=0)
    with rasterio.open(one.probability_raster) as probability, \
            rasterio.open(one.raw_mask_raster) as raw_mask, \
            rasterio.open(one.final_mask_raster) as mask:
        array = probability.read(1)
        raw = raw_mask.read(1)
        final = mask.read(1)
        for output in (probability, raw_mask, mask):
            assert output.shape == (pair.height, pair.width)
            assert output.crs == probability.crs
            assert output.transform == probability.transform
        assert np.isfinite(array).all() and array.min() >= 0 and array.max() <= 1
        assert probability.dtypes == ("float32",)
        assert raw_mask.dtypes == mask.dtypes == ("uint8",)
        assert set(np.unique(raw)) <= {0, 1}
        assert set(np.unique(final)) <= {0, 1}
        assert np.array_equal(raw, (array >= 0.50).astype(np.uint8))
        with rasterio.open(two.probability_raster) as second_probability, \
                rasterio.open(two.raw_mask_raster) as second_raw, \
                rasterio.open(two.final_mask_raster) as second_mask:
            np.testing.assert_array_equal(array, second_probability.read(1))
            np.testing.assert_array_equal(raw, second_raw.read(1))
            np.testing.assert_array_equal(final, second_mask.read(1))
    metadata = json.loads(Path(one.metadata_path).read_text(encoding="utf-8"))
    assert metadata["checkpoint_sha256"] == config.checkpoint_sha256
    assert metadata["checkpoint_role"] == "prototype_demo_checkpoint"
    assert metadata["sensor"] == "sentinel-2"
    assert metadata["pair_id"] == pair.pair_id
    assert metadata["provenance"]["source_files"] == {"T1": str(t1), "T2": str(t2)}
    assert metadata["provenance"]["checkpoint"] == str(config.checkpoint)
    assert metadata["provenance"]["threshold"] == 0.96
    assert metadata["provenance"]["postprocessing"]["minimum_component_area"] == 32
    assert metadata["provenance"]["postprocessing"]["morphology"] == "none"
    assert metadata["provenance"]["postprocessing"]["connectivity"] == 8
    assert metadata["provenance"]["postprocessing"]["candidate_filtering"] == {
        "enabled": True, "min_valid_fraction": None, "reject_edge_components": False,
        "edge_margin_pixels": 0, "scoring_enabled": True,
    }
    assert metadata["candidate_count"] == metadata["filtering_statistics"]["components_retained"]
    assert metadata["candidate_mask_raster"] == metadata["final_mask_raster"]
    retained = [candidate for candidate in metadata["candidates"] if candidate["retained"]]
    assert [candidate["rank"] for candidate in retained] == list(range(1, len(retained) + 1))
    assert all(candidate["candidate_score"] == candidate["mean_probability"] for candidate in retained)
    assert all(candidate["centroid_coordinates"]["crs"] == metadata["crs"] for candidate in retained)
    assert all(metadata["timings_seconds"][key] >= 0 for key in (
        "candidate_extraction", "candidate_filtering", "candidate_scoring",
    ))
    actual_stats = component_statistics(final, valid)
    for key in ("total_pixels", "changed_pixels", "connected_component_count",
                "largest_component_pixels", "median_component_pixels"):
        assert metadata["statistics"][key] == actual_stats[key]
    assert all(value >= 0 for value in metadata["timings_seconds"].values())
    assert metadata["timings_seconds"]["model_load"] > 0
    assert metadata["timings_seconds"]["inference"] > 0
    assert one.temporal_embedding_similarity is not None
    assert -1.0 <= one.temporal_embedding_similarity <= 1.0
