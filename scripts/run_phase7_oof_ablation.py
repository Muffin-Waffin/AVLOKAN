"""Evaluate the fixed Phase 7 image-edge candidate filter on existing OSCD OOF maps."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.change_detection.postprocessing import (  # noqa: E402
    CandidateFilteringConfig,
    PostprocessingConfig,
    analyze_candidates,
    postprocess_probability,
)


def _metrics(prediction: np.ndarray, truth: np.ndarray) -> dict[str, float | int]:
    pred, actual = prediction.astype(bool), truth.astype(bool)
    tp = int(np.count_nonzero(pred & actual))
    fp = int(np.count_nonzero(pred & ~actual))
    fn = int(np.count_nonzero(~pred & actual))
    tn = int(np.count_nonzero(~pred & ~actual))
    total = tp + fp + fn + tn
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
        "predicted_change_fraction": (tp + fp) / total if total else 0.0,
        "predicted_change_percent": 100 * (tp + fp) / total if total else 0.0,
        "total_pixels": total,
    }


def run() -> dict:
    baseline_dir = ROOT / "data/processed/oscd_cv5_validation_baseline"
    metrics_path = baseline_dir / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Existing OSCD OOF metrics are required: {metrics_path}")
    source_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    locations: dict[str, dict] = {}
    for fold in source_metrics["folds"]:
        for location in fold["locations"]:
            scene_dir = baseline_dir / f"fold_{fold['fold']}" / location
            with rasterio.open(scene_dir / f"{location}_probability.tif") as src:
                probability = src.read(1)
            with rasterio.open(scene_dir / f"{location}_ground_truth.tif") as src:
                truth = src.read(1).astype(bool)
            if probability.shape != truth.shape:
                raise ValueError(f"OOF probability and label dimensions differ for {location}")
            baseline = postprocess_probability(
                probability, PostprocessingConfig(0.96, 32, "none")
            )
            edge_mask, _, removed, _ = analyze_candidates(
                probability, baseline, threshold=0.96,
                config=CandidateFilteringConfig(
                    enabled=True, reject_edge_components=True, edge_margin_pixels=0,
                    scoring_enabled=False,
                ),
            )
            locations[location] = {
                "fold": int(fold["fold"]),
                "baseline": _metrics(baseline, truth),
                "baseline_plus_image_edge_suppression": _metrics(edge_mask, truth),
                "filtering": removed,
            }

    pooled: dict[str, dict] = {}
    for key in ("baseline", "baseline_plus_image_edge_suppression"):
        combined = {
            metric: sum(scene[key][metric] for scene in locations.values())
            for metric in ("tp", "fp", "fn", "tn", "total_pixels")
        }
        tp, fp, fn = combined["tp"], combined["fp"], combined["fn"]
        combined.update({
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
            "iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
            "predicted_change_fraction": (tp + fp) / combined["total_pixels"],
            "predicted_change_percent": 100 * (tp + fp) / combined["total_pixels"],
        })
        pooled[key] = combined

    artifact = {
        "experiment": "Phase 7 fixed image-border component suppression ablation",
        "source_probability_maps": str(metrics_path.relative_to(ROOT)),
        "source_label": "existing five-fold OSCD OOF; maps and evaluation artifacts read-only",
        "locations_count": len(locations),
        "baseline_configuration": {
            "threshold": 0.96, "minimum_component_area": 32,
            "morphology": "none", "connectivity": 8,
        },
        "candidate_filter": {
            "name": "exclude_components_touching_outermost_raster_row_or_column",
            "margin_pixels": 0,
            "quality_or_tile_seam_data_available": False,
        },
        "limitations": [
            "OOF files do not provide quality-mask or tile-seam metadata.",
            "Image-border contact is only a fixed exploratory filter and is not active by default.",
            "OOF validation results do not establish generalization to arbitrary scenes.",
        ],
        "pooled": pooled,
        "per_location": locations,
    }
    output_dir = ROOT / "data/processed/phase7_candidate_filtering"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "oof_image_edge_ablation.json"
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps({"artifact": str(output_path), "pooled": pooled}, indent=2))
    return artifact


if __name__ == "__main__":
    run()
