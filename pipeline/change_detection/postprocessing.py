"""Deterministic probability thresholding and binary-mask statistics."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np
from scipy import ndimage


CONNECTIVITY_8 = np.ones((3, 3), dtype=np.uint8)


@dataclass(frozen=True)
class PostprocessingConfig:
    threshold: float = 0.96
    min_component_area: int = 32
    morphology: str = "none"

    def __post_init__(self) -> None:
        if not np.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be finite and within [0, 1]")
        if self.min_component_area < 0:
            raise ValueError("min_component_area cannot be negative")
        if self.morphology not in {"none", "closing_3x3"}:
            raise ValueError(f"Unsupported morphology: {self.morphology}")


def threshold_probability(probability: np.ndarray, threshold: float) -> np.ndarray:
    values = np.asarray(probability)
    if values.ndim != 2 or values.size == 0:
        raise ValueError("probability must be a nonempty 2-D array")
    if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("probability must contain finite values in [0, 1]")
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and within [0, 1]")
    return (values >= threshold).astype(np.uint8)


def postprocess_probability(
    probability: np.ndarray,
    config: PostprocessingConfig,
    *,
    valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Threshold, remove small 8-connected components, optionally close, mask invalid."""
    result = threshold_probability(probability, config.threshold).astype(bool)
    if valid_mask is not None:
        valid = np.asarray(valid_mask, dtype=bool)
        if valid.shape != result.shape:
            raise ValueError("valid_mask shape must match probability")
        result &= valid
    if config.min_component_area and result.any():
        labels, count = ndimage.label(result, structure=CONNECTIVITY_8)
        sizes = np.bincount(labels.ravel(), minlength=count + 1)
        keep = sizes >= config.min_component_area
        keep[0] = False
        result = keep[labels]
    if config.morphology == "closing_3x3":
        result = ndimage.binary_closing(result, structure=CONNECTIVITY_8, border_value=0)
        if valid_mask is not None:
            result &= valid
    return result.astype(np.uint8)


def component_statistics(mask: np.ndarray, valid_mask: np.ndarray | None = None) -> dict:
    binary = np.asarray(mask)
    if binary.ndim != 2 or not np.isin(binary, (0, 1)).all():
        raise ValueError("mask must be a 2-D array containing only 0 and 1")
    valid = np.ones(binary.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask, dtype=bool)
    if valid.shape != binary.shape:
        raise ValueError("valid_mask shape must match mask")
    changed = binary.astype(bool) & valid
    labels, count = ndimage.label(changed, structure=CONNECTIVITY_8)
    sizes = np.bincount(labels.ravel(), minlength=count + 1)[1:].astype(np.int64)
    areas = sorted((int(value) for value in sizes), reverse=True)
    valid_count = int(valid.sum())
    changed_count = int(changed.sum())
    return {
        "total_pixels": int(binary.size),
        "valid_pixels": valid_count,
        "changed_pixels": changed_count,
        "changed_pixel_fraction": changed_count / valid_count if valid_count else 0.0,
        "changed_percentage": 100.0 * changed_count / valid_count if valid_count else 0.0,
        "connected_component_count": len(areas),
        "largest_component_pixels": areas[0] if areas else 0,
        "median_component_pixels": float(np.median(areas)) if areas else 0.0,
        "top_component_areas_pixels": areas[:10],
        "connectivity": 8,
    }


@dataclass(frozen=True)
class CandidateFilteringConfig:
    """Explicit, optional candidate filters; defaults preserve Phase 6 output."""

    enabled: bool = True
    min_valid_fraction: float | None = None
    reject_edge_components: bool = False
    edge_margin_pixels: int = 0
    scoring_enabled: bool = True

    def __post_init__(self) -> None:
        if self.min_valid_fraction is not None and (
            not np.isfinite(self.min_valid_fraction)
            or not 0 <= self.min_valid_fraction <= 1
        ):
            raise ValueError("min_valid_fraction must be null or within [0, 1]")
        if self.edge_margin_pixels < 0:
            raise ValueError("edge_margin_pixels cannot be negative")


def analyze_candidates(
    probability: np.ndarray,
    candidate_mask: np.ndarray,
    *,
    threshold: float,
    valid_mask: np.ndarray | None = None,
    config: CandidateFilteringConfig = CandidateFilteringConfig(),
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, int], dict[str, float]]:
    """Describe 8-connected candidates, optionally suppress components, and rank them.

    ``candidate_score`` is the component's mean BIT change-class probability.
    It ranks candidates for review; it is not a calibrated probability of true change.
    Component IDs follow scipy's stable row-major labeling.
    """
    values = np.asarray(probability)
    mask = np.asarray(candidate_mask)
    if values.ndim != 2 or mask.ndim != 2 or values.shape != mask.shape:
        raise ValueError("probability and candidate_mask must be matching 2-D arrays")
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and within [0, 1]")
    if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("probability must contain finite values in [0, 1]")
    if not np.isin(mask, (0, 1)).all():
        raise ValueError("candidate_mask must contain only 0 and 1")
    valid = np.ones(mask.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask, dtype=bool)
    if valid.shape != mask.shape:
        raise ValueError("valid_mask shape must match candidate_mask")

    extraction_started = perf_counter()
    labels, count = ndimage.label(mask.astype(bool), structure=CONNECTIVITY_8)
    output = mask.astype(np.uint8, copy=True)
    entries: list[dict[str, Any]] = []
    removed_components = removed_pixels = 0
    filtering_seconds = 0.0
    height, width = mask.shape
    for component_id in range(1, count + 1):
        rows, cols = np.where(labels == component_id)
        pix = values[rows, cols]
        valid_fraction = float(valid[rows, cols].mean()) if len(rows) else 0.0
        edge_distance = int(min(rows.min(), cols.min(), height - 1 - rows.max(), width - 1 - cols.max()))
        touches_edge = edge_distance <= config.edge_margin_pixels
        filter_started = perf_counter()
        reject_edge = config.enabled and config.reject_edge_components and touches_edge
        reject_validity = (
            config.enabled and config.min_valid_fraction is not None
            and valid_fraction < config.min_valid_fraction
        )
        area = int(len(rows))
        rejected = bool(reject_edge or reject_validity)
        if rejected:
            output[labels == component_id] = 0
            removed_components += 1
            removed_pixels += area
        filtering_seconds += perf_counter() - filter_started
        entry: dict[str, Any] = {
            "component_id": int(component_id),
            "area_pixels": area,
            "bbox_pixels": {
                "xmin": int(cols.min()), "ymin": int(rows.min()),
                "xmax_exclusive": int(cols.max()) + 1, "ymax_exclusive": int(rows.max()) + 1,
            },
            "centroid_pixels": {"x": float(cols.mean()), "y": float(rows.mean())},
            "mean_probability": float(pix.mean()),
            "maximum_probability": float(pix.max()),
            "median_probability": float(np.median(pix)),
            "probability_percentiles": {"p90": float(np.percentile(pix, 90)), "p95": float(np.percentile(pix, 95))},
            "fraction_above_threshold": float(np.mean(pix >= threshold)),
            "edge_distance_pixels": edge_distance,
            "touches_image_edge": bool(touches_edge),
            "valid_fraction": valid_fraction,
            "invalid_fraction": float(1.0 - valid_fraction),
            "candidate_score": None,
            "retained": not rejected,
            "rejection_reasons": [name for name, condition in (("image_edge", reject_edge), ("valid_fraction", reject_validity)) if condition],
        }
        entries.append(entry)

    extraction_seconds = perf_counter() - extraction_started - filtering_seconds
    scoring_started = perf_counter()
    if config.scoring_enabled:
        for entry in entries:
            entry["candidate_score"] = entry["mean_probability"]
    retained = [entry for entry in entries if entry["retained"]]
    if config.scoring_enabled:
        retained.sort(key=lambda entry: (-entry["candidate_score"], entry["component_id"]))
    else:
        retained.sort(key=lambda entry: entry["component_id"])
    for rank, entry in enumerate(retained, start=1):
        entry["rank"] = rank
    scoring_seconds = perf_counter() - scoring_started
    entries.sort(key=lambda entry: (not entry["retained"], entry.get("rank", float("inf")), entry["component_id"]))
    filtering = {
        "raw_component_count": int(count),
        "components_removed": removed_components,
        "components_retained": len(retained),
        "pixels_removed": removed_pixels,
        "pixels_retained": int(output.sum()),
    }
    return output, entries, filtering, {
        "candidate_extraction": max(0.0, extraction_seconds),
        "candidate_filtering": filtering_seconds,
        "candidate_scoring": scoring_seconds,
    }
