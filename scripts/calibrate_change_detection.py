"""Inference-only OOF validation calibration for saved OSCD BIT probability maps.

This reads existing probability/ground-truth rasters only. It never loads a model,
checkpoint, source imagery, or official OSCD test location.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio
from scipy import ndimage


BASELINE_ROOT = PROJECT_ROOT / "data/processed/oscd_cv5_validation_baseline"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data/processed/oscd_cv5_validation_calibrated"
THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85,
              0.90, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99)
MIN_COMPONENT_AREAS = (0, 16, 32, 64, 128)
MORPHOLOGY_OPTIONS = ("none", "closing_3x3")
CONNECTIVITY_8 = np.ones((3, 3), dtype=np.uint8)


def postprocess_probability(
    probability: np.ndarray,
    *,
    threshold: float,
    min_component_area: int = 0,
    morphology: str = "none",
) -> np.ndarray:
    """Threshold, remove small 8-connected components, then optionally close 3x3."""
    source = np.asarray(probability)
    if source.ndim != 2 or source.size == 0:
        raise ValueError("probability must be a nonempty 2-D array")
    if not np.isfinite(source).all() or np.any((source < 0) | (source > 1)):
        raise ValueError("probability must contain finite values in [0, 1]")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    if min_component_area < 0:
        raise ValueError("min_component_area cannot be negative")
    if morphology not in MORPHOLOGY_OPTIONS:
        raise ValueError(f"Unsupported morphology: {morphology}")

    result = source >= threshold
    if min_component_area > 0 and result.any():
        labels, component_count = ndimage.label(result, structure=CONNECTIVITY_8)
        sizes = np.bincount(labels.ravel(), minlength=component_count + 1)
        keep = sizes >= min_component_area
        keep[0] = False
        result = keep[labels]
    if morphology == "closing_3x3":
        result = ndimage.binary_closing(result, structure=CONNECTIVITY_8, border_value=0)
    return np.asarray(result, dtype=np.uint8)


def confusion_metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float | int]:
    pred = np.asarray(prediction).astype(bool, copy=False)
    truth = np.asarray(target).astype(bool, copy=False)
    if pred.ndim != 2 or pred.shape != truth.shape:
        raise ValueError("prediction and target must be same-shaped 2-D arrays")
    tp = int(np.count_nonzero(pred & truth))
    fp = int(np.count_nonzero(pred & ~truth))
    fn = int(np.count_nonzero(~pred & truth))
    tn = int(np.count_nonzero(~pred & ~truth))
    total = int(truth.size)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1, "iou": iou,
        "predicted_changed_percent": 100.0 * (tp + fp) / total,
        "ground_truth_changed_percent": 100.0 * (tp + fn) / total,
        "total_pixels": total,
    }


def pooled_metrics(location_metrics: dict[str, dict]) -> dict:
    counts = {key: sum(int(row[key]) for row in location_metrics.values())
              for key in ("tp", "fp", "fn", "tn", "total_pixels")}
    tp, fp, fn, tn, total = (counts[key] for key in ("tp", "fp", "fn", "tn", "total_pixels"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        **counts, "precision": precision, "recall": recall, "f1": f1, "iou": iou,
        "predicted_changed_percent": 100.0 * (tp + fp) / total,
        "ground_truth_changed_percent": 100.0 * (tp + fn) / total,
    }


def select_global_configuration(rows: list[dict]) -> dict:
    """Max pooled F1; ties prefer less processing, then smaller area, then higher threshold."""
    if not rows:
        raise ValueError("configuration results cannot be empty")
    return max(rows, key=lambda row: (
        row["pooled"]["f1"],
        row["morphology"] == "none",
        -row["min_component_area"],
        row["threshold"],
    ))


def _load_oof_inputs(metrics_path: Path) -> tuple[dict[str, tuple[np.ndarray, np.ndarray, dict]], dict]:
    metadata = json.loads(metrics_path.read_text(encoding="utf-8"))
    aggregate_isolation = metadata.get("five_fold_oof_aggregate", {}).get("official_test_evaluated")
    if metadata.get("official_test_locations_touched") is not False or aggregate_isolation is not False:
        raise ValueError("Baseline artifact does not certify official-test isolation")
    scenes = {}
    for fold in metadata["folds"]:
        fold_id = int(fold["fold"])
        for location, paths in fold["artifacts"].items():
            if location in scenes:
                raise ValueError(f"Duplicate OOF location in baseline manifest: {location}")
            prob_path = Path(paths["probability"])
            gt_path = Path(paths["ground_truth"])
            # Also support baseline manifests written with absolute paths on another OS.
            if not prob_path.is_file():
                prob_path = BASELINE_ROOT / f"fold_{fold_id}" / location / f"{location}_probability.tif"
            if not gt_path.is_file():
                gt_path = BASELINE_ROOT / f"fold_{fold_id}" / location / f"{location}_ground_truth.tif"
            if not prob_path.is_file() or not gt_path.is_file():
                raise FileNotFoundError(f"Missing saved OOF map/mask for fold {fold_id} location {location}")
            with rasterio.open(prob_path) as src:
                probability = src.read(1)
                prob_grid = (src.width, src.height, src.count)
            with rasterio.open(gt_path) as src:
                target = src.read(1)
                target_grid = (src.width, src.height, src.count)
            if prob_grid != target_grid or probability.shape != target.shape:
                raise ValueError(f"Probability/ground-truth grid mismatch: {location}")
            if prob_grid[2] != 1 or not np.isfinite(probability).all():
                raise ValueError(f"Invalid probability raster for {location}")
            if np.any((probability < 0) | (probability > 1)) or not set(np.unique(target)) <= {0, 1}:
                raise ValueError(f"Invalid probability range or non-binary mask for {location}")
            scenes[location] = (probability.astype(np.float32, copy=False),
                                target.astype(np.uint8, copy=False),
                                {"fold": fold_id, "probability_path": str(prob_path),
                                 "ground_truth_path": str(gt_path)})
    if len(scenes) != 14:
        raise ValueError(f"Expected 14 OOF validation locations, found {len(scenes)}")
    return scenes, metadata


def run_calibration(
    baseline_root: Path = BASELINE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict:
    baseline_root, output_root = baseline_root.resolve(), output_root.resolve()
    metrics_path = baseline_root / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Missing OOF baseline metrics: {metrics_path}")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty calibration directory: {output_root}")
    scenes, baseline_metadata = _load_oof_inputs(metrics_path)

    baseline_by_location = {}
    for location, (probability, target, meta) in scenes.items():
        baseline_prediction = postprocess_probability(probability, threshold=0.50)
        # Ensure saved baseline prediction is exactly the advertised threshold result.
        pred_path = baseline_root / f"fold_{meta['fold']}" / location / f"{location}_prediction_threshold_0.50.tif"
        if pred_path.is_file():
            with rasterio.open(pred_path) as src:
                saved_prediction = src.read(1)
            if not np.array_equal(saved_prediction, baseline_prediction):
                raise ValueError(f"Saved baseline prediction differs from probability thresholding: {location}")
        baseline_by_location[location] = confusion_metrics(baseline_prediction, target)
    baseline_pooled = pooled_metrics(baseline_by_location)

    sweep_rows = []
    for morphology in MORPHOLOGY_OPTIONS:
        for area in MIN_COMPONENT_AREAS:
            for threshold in THRESHOLDS:
                per_location = {}
                for location, (probability, target, _) in scenes.items():
                    prediction = postprocess_probability(
                        probability, threshold=threshold,
                        min_component_area=area, morphology=morphology,
                    )
                    per_location[location] = confusion_metrics(prediction, target)
                row = {
                    "threshold": threshold,
                    "min_component_area": area,
                    "morphology": morphology,
                    "pooled": pooled_metrics(per_location),
                    "per_location": per_location,
                }
                sweep_rows.append(row)

    selected = select_global_configuration(sweep_rows)
    threshold_only = [row for row in sweep_rows
                      if row["min_component_area"] == 0 and row["morphology"] == "none"]
    best_threshold_f1 = max(threshold_only, key=lambda row: (row["pooled"]["f1"], row["threshold"]))
    best_threshold_iou = max(threshold_only, key=lambda row: (row["pooled"]["iou"], row["threshold"]))
    baseline_row = next(row for row in sweep_rows if row["threshold"] == 0.50
                        and row["min_component_area"] == 0 and row["morphology"] == "none")
    if baseline_row["pooled"] != baseline_pooled:
        raise RuntimeError("Baseline recomputation did not match the threshold-grid baseline")

    calibrated_metrics = selected["pooled"]
    metric_names = ("precision", "recall", "f1", "iou", "predicted_changed_percent")
    deltas = {}
    for name in metric_names:
        before, after = float(baseline_pooled[name]), float(calibrated_metrics[name])
        deltas[name] = {
            "baseline": before, "calibrated": after, "absolute_change": after - before,
            "relative_change_percent": (100.0 * (after - before) / abs(before)) if before else None,
            "unit": "percentage_points" if name == "predicted_changed_percent" else "fraction",
        }

    output_root.mkdir(parents=True, exist_ok=True)
    selected_masks = {
        location: postprocess_probability(
            probability, threshold=selected["threshold"],
            min_component_area=selected["min_component_area"],
            morphology=selected["morphology"],
        )
        for location, (probability, _, _) in scenes.items()
    }
    per_location_comparison = {}
    selected_mask_paths = {}
    for location, (probability, target, meta) in scenes.items():
        calibrated_prediction = selected_masks[location]
        calibrated_location = selected["per_location"][location]
        baseline_location = baseline_by_location[location]
        per_location_comparison[location] = {
            "fold": meta["fold"], "baseline": baseline_location,
            "calibrated": calibrated_location,
            "delta": {name: calibrated_location[name] - baseline_location[name]
                      for name in metric_names},
        }
        out_dir = output_root / f"fold_{meta['fold']}" / location
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{location}_calibrated_mask.tif"
        reference = Path(meta["ground_truth_path"])
        with rasterio.open(reference) as src:
            profile = src.profile.copy()
        profile.update(driver="GTiff", count=1, dtype="uint8", nodata=None,
                       compress="deflate", predictor=2)
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(calibrated_prediction, 1)
            dst.update_tags(spatial_reference_note=
                            "OSCD registered pixel grid; source has no meaningful CRS/geotransform")
        selected_mask_paths[location] = str(path)

    selection_summary = {
        "label": "OOF validation calibration",
        "threshold": selected["threshold"],
        "min_component_area": selected["min_component_area"],
        "morphology": selected["morphology"],
        "connectivity": 8,
        "selection_criterion": "maximum pooled OOF F1 across the predefined global grid",
        "tie_break": "prefer no morphology, then smaller component area, then higher threshold",
        "selected_pooled_metrics": calibrated_metrics,
        "selected_masks": selected_mask_paths,
    }
    summary = {
        "label": "OOF validation calibration",
        "baseline_source": str(metrics_path),
        "validation_locations": list(scenes),
        "official_oscd_test_evaluated": False,
        "primary_threshold_selection": "pooled OOF F1",
        "baseline_config": {"threshold": 0.50, "min_component_area": 0, "morphology": "none"},
        "baseline_metrics": baseline_pooled,
        "calibrated_config": selection_summary,
        "calibrated_metrics": calibrated_metrics,
        "absolute_relative_change": deltas,
        "threshold_only_best_f1": {
            "threshold": best_threshold_f1["threshold"], "pooled": best_threshold_f1["pooled"]},
        "threshold_only_best_iou": {
            "threshold": best_threshold_iou["threshold"], "pooled": best_threshold_iou["pooled"]},
        "threshold_iou_agree_with_f1": best_threshold_f1["threshold"] == best_threshold_iou["threshold"],
        "configuration_grid_count": len(sweep_rows),
        "method": {
            "thresholds": list(THRESHOLDS), "min_component_areas": list(MIN_COMPONENT_AREAS),
            "morphology_options": list(MORPHOLOGY_OPTIONS),
            "component_connectivity": 8,
            "operation_order": "threshold -> remove 8-connected components smaller than minimum area -> optional 3x3 closing",
            "morphology": "binary closing with a 3x3 all-ones structuring element; applied after component removal",
            "aggregation": "pixel-count pooled across all 14 OOF locations; one global configuration",
        },
    }
    (output_root / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_root / "per_location.json").write_text(json.dumps(per_location_comparison, indent=2), encoding="utf-8")
    (output_root / "selected_config.json").write_text(json.dumps(selection_summary, indent=2), encoding="utf-8")
    (output_root / "threshold_sweep.json").write_text(json.dumps({
        "label": "OOF validation calibration", "rows": sweep_rows,
        "threshold_only_best_f1": best_threshold_f1,
        "threshold_only_best_iou": best_threshold_iou,
        "selected_global_configuration": {
            "threshold": selected["threshold"],
            "min_component_area": selected["min_component_area"],
            "morphology": selected["morphology"],
            "pooled": selected["pooled"],
        },
    }, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, default=BASELINE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    result = run_calibration(args.baseline_dir, args.output_dir)
    print(json.dumps({
        "baseline": result["baseline_metrics"],
        "selected_config": result["calibrated_config"],
        "calibrated_metrics": result["calibrated_metrics"],
        "threshold_only_best_f1": result["threshold_only_best_f1"],
        "threshold_only_best_iou": result["threshold_only_best_iou"],
    }, indent=2))


if __name__ == "__main__":
    main()
