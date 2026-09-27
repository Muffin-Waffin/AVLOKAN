"""Evaluate the saved best checkpoint for each OSCD location-CV fold.

Only the 14 official OSCD training locations are evaluated as their assigned
fold validation locations. The official OSCD test locations are never loaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio
import torch

from pipeline.change_detection.bit import BITArchitecture, BIT_CHECKPOINT_SHA256
from pipeline.change_detection.bit_alignment import align_bit_logits
from pipeline.change_detection.oscd_dataset import load_split_manifest
from pipeline.change_detection.oscd_training import (
    OSCDPatchDataset,
    load_training_config,
    make_location_folds,
    training_device,
)
from scripts.evaluate_oscd_bit import _aggregate, _measure, _save_panel, _write_geotiff


DEFAULT_CONFIG = PROJECT_ROOT / "configs/oscd_bit_training.yaml"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/processed/oscd_cv5_validation_baseline"
EXPECTED_VALIDATION = (
    ("bercy", "mumbai", "pisa"),
    ("abudhabi", "bordeaux", "rennes"),
    ("aguasclaras", "beihai", "hongkong"),
    ("cupertino", "nantes", "paris"),
    ("beirut", "saclay_e"),
)
EXPECTED_BEST = (
    (16, 1.1374972904),
    (10, 1.1203641241),
    (5, 1.0294453878),
    (17, 0.6688525188),
    (28, 0.9511334298),
)
THRESHOLDS = tuple(round(value / 100, 2) for value in range(5, 100, 5))


def probability_distribution(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("Probability distribution requires nonempty finite values")
    p90, p95 = np.percentile(values, (90, 95))
    return {
        "pixels": int(values.size), "mean": float(values.mean()),
        "median": float(np.median(values)), "p90": float(p90), "p95": float(p95),
        "fraction_ge_0_25": float(np.mean(values >= 0.25)),
        "fraction_ge_0_50": float(np.mean(values >= 0.50)),
        "fraction_ge_0_75": float(np.mean(values >= 0.75)),
    }


def discrimination_auc(probability: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    """Return tie-aware ROC-AUC and non-interpolated average precision (PR-AUC)."""
    scores = np.asarray(probability, dtype=np.float64).reshape(-1)
    labels = np.asarray(target, dtype=np.uint8).reshape(-1)
    if scores.size != labels.size or scores.size == 0 or not np.isfinite(scores).all():
        raise ValueError("AUC inputs must be equal-length, nonempty, and finite")
    positives = int(labels.sum())
    negatives = int(labels.size - positives)
    if positives == 0 or negatives == 0:
        return float("nan"), float("nan")

    order = np.argsort(scores, kind="mergesort")
    sorted_scores, sorted_labels = scores[order], labels[order]
    _, starts, counts = np.unique(sorted_scores, return_index=True, return_counts=True)
    positive_by_group = np.add.reduceat(sorted_labels, starts).astype(np.int64)
    # Mann-Whitney rank statistic with average ranks for tied scores.
    ranks = starts.astype(np.float64) + (counts.astype(np.float64) + 1.0) / 2.0
    roc_auc = float((np.sum(ranks * positive_by_group) - positives * (positives + 1) / 2)
                    / (positives * negatives))

    # Average precision: sum over unique descending score thresholds of
    # recall increment times precision at that threshold (step-wise PR area).
    cumulative_tp = np.cumsum(positive_by_group[::-1])
    cumulative_count = np.cumsum(counts[::-1])
    increments = positive_by_group[::-1] / positives
    precision_at_threshold = cumulative_tp / cumulative_count
    average_precision = float(np.sum(increments * precision_at_threshold))
    return roc_auc, average_precision


def _threshold_record(probability: np.ndarray, target: np.ndarray, threshold: float) -> dict:
    metrics = _measure(probability >= threshold, target)
    return {
        "threshold": threshold,
        "precision": metrics["precision"], "recall": metrics["recall"],
        "f1": metrics["f1"], "iou": metrics["iou"],
        "predicted_changed_percent": metrics["predicted_changed_percent"],
    }


def _best_threshold(records: list[dict]) -> dict:
    # Ties resolve to the higher threshold, deterministically and diagnostically only.
    return max(records, key=lambda row: (row["f1"], row["threshold"]))


def _read_dates(root: Path, location: str) -> list[str]:
    path = root / "Onera Satellite Change Detection dataset - Images" / location / "dates.txt"
    dates = [line.strip().split(":", 1)[-1].strip()
             for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(dates) != 2:
        raise RuntimeError(f"Expected two dates for {location}, got {dates}")
    return dates


def _evaluate_fold(
    fold_index: int, checkpoint_path: Path, container: dict, config: dict,
    validation_locations: tuple[str, ...], device: torch.device,
    output_root: Path, threshold: float,
) -> tuple[dict, dict[str, dict], dict[str, dict]]:
    data = config["data"]
    patch = config["patch"]
    dataset = OSCDPatchDataset(
        split="validation", locations=list(validation_locations),
        patch_size=int(patch["patch_size"]),
        patch_stride=int(patch.get("validation_stride", patch["patch_size"])),
        quantification_value=float(config["input"]["quantification_value"]),
        augmentation=False, seed=int(config["training"]["seed"]),
        root=data["root"], splits_path=data["splits"],
    )
    model = BITArchitecture()
    model.load_state_dict(container["model_state_dict"], strict=True)
    model.eval().to(device)

    scenes: dict[str, dict] = {}
    with torch.inference_mode():
        for index in range(len(dataset)):
            sample = dataset[index]
            metadata = sample["metadata"]
            location = metadata["location_id"]
            if location not in validation_locations:
                raise RuntimeError(f"Unexpected location in fold {fold_index}: {location}")
            if location not in scenes:
                reference = (Path(data["root"]) / "Onera Satellite Change Detection dataset - Images"
                             / location / "imgs_1_rect" / "B04.tif")
                with rasterio.open(reference) as source:
                    height, width = source.height, source.width
                scenes[location] = {
                    "reference": reference,
                    "probability": np.full((height, width), np.nan, dtype=np.float32),
                    "target": np.zeros((height, width), dtype=np.uint8),
                    "t1": np.zeros((height, width, 3), dtype=np.float32),
                    "t2": np.zeros((height, width, 3), dtype=np.float32),
                }
            row, col = int(metadata["row"]), int(metadata["col"])
            valid_h, valid_w = int(metadata["valid_height"]), int(metadata["valid_width"])
            t1 = sample["t1"].unsqueeze(0).to(device)
            t2 = sample["t2"].unsqueeze(0).to(device)
            logits = align_bit_logits(model(t1, t2), tuple(sample["target"].shape))
            probs = torch.softmax(logits.float(), dim=1)[0, 1, :valid_h, :valid_w].cpu().numpy()
            scene = scenes[location]
            destination = np.s_[row:row + valid_h, col:col + valid_w]
            if np.isfinite(scene["probability"][destination]).any():
                raise RuntimeError(f"Overlapping validation patches unexpectedly found for {location}")
            scene["probability"][destination] = probs
            scene["target"][destination] = sample["target"][:valid_h, :valid_w].numpy().astype(np.uint8)
            scene["t1"][destination] = ((sample["t1"][:, :valid_h, :valid_w].permute(1, 2, 0).numpy() + 1) / 2)
            scene["t2"][destination] = ((sample["t2"][:, :valid_h, :valid_w].permute(1, 2, 0).numpy() + 1) / 2)

    if set(scenes) != set(validation_locations):
        raise RuntimeError(f"Fold {fold_index} did not produce exactly its validation roster")

    location_metrics: dict[str, dict] = {}
    location_diagnostics: dict[str, dict] = {}
    artifacts: dict[str, dict] = {}
    fold_sweep: dict[str, dict] = {}
    for location in validation_locations:
        scene = scenes[location]
        probability, target = scene["probability"], scene["target"]
        if not np.isfinite(probability).all() or not np.isin(target, (0, 1)).all():
            raise RuntimeError(f"Incomplete probability map or invalid mask for {location}")
        prediction = probability >= threshold
        metrics = _measure(prediction, target)
        roc_auc, pr_auc = discrimination_auc(probability, target)
        location_metrics[location] = {**metrics, "roc_auc": roc_auc, "pr_auc_average_precision": pr_auc}
        changed, unchanged = target.astype(bool), ~target.astype(bool)
        location_diagnostics[location] = {
            "changed_probability": probability_distribution(probability[changed]),
            "unchanged_probability": probability_distribution(probability[unchanged]),
            "roc_auc": roc_auc, "pr_auc_average_precision": pr_auc,
            "dates": _read_dates(Path(data["root"]), location),
            "registered_pixel_grid": {
                "height": int(target.shape[0]), "width": int(target.shape[1]),
                "crs": None, "geotransform": None,
            },
        }
        sweep = [_threshold_record(probability, target, value) for value in THRESHOLDS]
        fold_sweep[location] = {"thresholds": sweep, "best_f1_diagnostic": _best_threshold(sweep)}

        loc_dir = output_root / f"fold_{fold_index}" / location
        loc_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "probability": loc_dir / f"{location}_probability.tif",
            "prediction": loc_dir / f"{location}_prediction_threshold_{threshold:.2f}.tif",
            "ground_truth": loc_dir / f"{location}_ground_truth.tif",
            "panel": loc_dir / f"{location}_panel.png",
        }
        _write_geotiff(paths["probability"], probability, scene["reference"], dtype="float32", predictor=3)
        _write_geotiff(paths["prediction"], prediction.astype(np.uint8), scene["reference"], dtype="uint8", predictor=2)
        _write_geotiff(paths["ground_truth"], target, scene["reference"], dtype="uint8", predictor=2)
        _save_panel(paths["panel"], scene["t1"], scene["t2"], target, probability, prediction)
        artifacts[location] = {key: str(path) for key, path in paths.items()}

        # Exact Fold 0 comparability check against the previously saved evaluator output.
        if fold_index == 0:
            old_path = PROJECT_ROOT / "data/processed/oscd_fold0_validation" / location / f"{location}_probability.tif"
            if old_path.is_file():
                with rasterio.open(old_path) as old:
                    old_map = old.read(1)
                if old_map.shape != probability.shape:
                    raise RuntimeError(f"Fold 0 comparison map has a different grid: {location}")
                max_delta = float(np.max(np.abs(old_map - probability)))
                location_diagnostics[location]["max_abs_difference_from_previous_fold0_map"] = max_delta
                if max_delta > 1e-7:
                    raise RuntimeError(f"Fold 0 inference differs from saved baseline for {location}: {max_delta}")

    aggregate = _aggregate(location_metrics)
    fold_target = np.concatenate([scenes[name]["target"].reshape(-1) for name in validation_locations])
    fold_probability = np.concatenate([scenes[name]["probability"].reshape(-1) for name in validation_locations])
    fold_sweep_records = [
        {"threshold": value, **_measure(fold_probability >= value, fold_target)}
        for value in THRESHOLDS
    ]
    fold_record = {
        "fold": fold_index, "locations": list(validation_locations),
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        "epoch": int(container["epoch"]),
        "saved_validation_metrics": container["validation_metrics"],
        "per_location": location_metrics,
        "aggregates": aggregate,
        "total_predicted_changed_percent": aggregate["micro"]["predicted_changed_percent"],
        "total_ground_truth_changed_percent": aggregate["micro"]["ground_truth_changed_percent"],
        "threshold_sweep": {
            "locations": fold_sweep,
            "pooled_fold_thresholds": fold_sweep_records,
            "best_f1_diagnostic": _best_threshold([
                {**row, "predicted_changed_percent": row["predicted_changed_percent"]}
                for row in fold_sweep_records
            ]),
            "note": "Diagnostic only; does not select or change the system threshold.",
        },
        "artifacts": artifacts,
    }
    return fold_record, location_diagnostics, location_metrics


def evaluate(config_path: Path, output_dir: Path, *, device_name: str = "auto", threshold: float = 0.5) -> dict:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be within [0,1]")
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty output directory: {output_dir}")
    config_path = config_path.resolve()
    template = load_training_config(config_path)
    data = template["data"]
    manifest = load_split_manifest(data["root"], data["splits"])
    folds = make_location_folds(manifest["official_train"], manifest["test"],
                                n_splits=5, seed=42)
    actual_rosters = tuple(tuple(fold["validation"]) for fold in folds)
    if actual_rosters != EXPECTED_VALIDATION:
        raise RuntimeError(f"Fold validation roster mismatch: {actual_rosters}")
    official_test = set(manifest["test"])
    if set().union(*(set(roster) for roster in actual_rosters)) & official_test:
        raise RuntimeError("Official test location leaked into fold validation roster")

    device = training_device(device_name)
    fold_results, all_diagnostics, all_location_metrics = [], {}, {}
    checkpoint_root = PROJECT_ROOT / template["output"]["checkpoint_directory"]
    for fold_index, roster in enumerate(EXPECTED_VALIDATION):
        checkpoint = checkpoint_root / f"fold_{fold_index}" / "best_oscd_bit.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Missing fold {fold_index} best checkpoint: {checkpoint}")
        container = torch.load(checkpoint, map_location="cpu", weights_only=False)
        run_config = container.get("config")
        if not isinstance(run_config, dict):
            raise ValueError(f"Checkpoint has no saved config: {checkpoint}")
        if run_config.get("cross_validation", {}).get("fold") != fold_index:
            raise ValueError(f"Checkpoint fold metadata mismatch: {checkpoint}")
        if run_config.get("cross_validation", {}).get("seed") != 42:
            raise ValueError(f"Checkpoint seed mismatch: {checkpoint}")
        if container.get("base_checkpoint_sha256") != BIT_CHECKPOINT_SHA256:
            raise ValueError(f"Checkpoint base BIT provenance mismatch: {checkpoint}")
        if not isinstance(container.get("validation_metrics"), dict) or "total" not in container["validation_metrics"]:
            raise ValueError(f"Checkpoint lacks validation-selection metrics: {checkpoint}")
        expected_epoch, expected_loss = EXPECTED_BEST[fold_index]
        metadata_match = (int(container["epoch"]) == expected_epoch
                          and abs(float(container["validation_metrics"]["total"]) - expected_loss) <= 1e-8)
        # The saved artifact remains authoritative as the best checkpoint, but preserve any
        # conflict with the user-provided training-log summary for the report.
        if tuple(roster) != tuple(folds[fold_index]["validation"]):
            raise RuntimeError(f"Checkpoint validation roster cannot be verified: fold {fold_index}")
        fold_record, diagnostics, location_metrics = _evaluate_fold(
            fold_index, checkpoint, container, run_config, roster, device, output_dir, threshold,
        )
        fold_record["provided_best_record_match"] = metadata_match
        fold_record["provided_best_record"] = {"epoch": expected_epoch, "validation_loss": expected_loss}
        if not metadata_match:
            fold_record["artifact_discrepancy"] = (
                "Saved best checkpoint metadata differs from supplied training-log summary; "
                "evaluated the existing best_oscd_bit.pt artifact selected by saved validation loss."
            )
        fold_results.append(fold_record)
        all_diagnostics.update(diagnostics)
        all_location_metrics.update(location_metrics)
        print(f"Completed fold {fold_index}: checkpoint epoch={container['epoch']}, "
              f"validation_loss={container['validation_metrics']['total']:.10f}", flush=True)

    if set(all_location_metrics) != set(manifest["official_train"]):
        raise RuntimeError("Out-of-fold evaluation did not cover exactly the 14 official training locations")
    pooled = _aggregate(all_location_metrics)
    overall = {
        "locations_evaluated": len(all_location_metrics),
        "official_test_evaluated": False,
        "micro": pooled["micro"], "macro": pooled["macro"],
        "threshold": threshold,
        "threshold_convention": "change probability >= threshold",
        "probability_auc_aggregation": "per-location ROC-AUC and average precision; no pooled AUC",
        "fold_macro_mean": {
            metric: float(np.mean([fold["aggregates"]["macro"][metric] for fold in fold_results]))
            for metric in ("precision", "recall", "f1", "iou")
        },
    }
    result = {
        "title": "OSCD five-fold location-level out-of-fold baseline evaluation",
        "config": str(config_path), "seed": 42, "device": str(device),
        "model": "BIT fine-tuned from verified official LEVIR checkpoint",
        "input_bands": template["input"]["bands"],
        "normalization": template["input"]["normalization"],
        "patch": {"size": template["patch"]["patch_size"],
                  "training_stride": template["patch"]["patch_stride"],
                  "validation_stride": template["patch"]["validation_stride"]},
        "threshold": threshold, "folds": fold_results,
        "five_fold_oof_aggregate": overall,
        "per_location_diagnostics": all_diagnostics,
        "official_test_locations_touched": False,
        "notes": [
            "AUC outputs are discrimination/separation diagnostics, not calibration metrics.",
            "PR-AUC is reported as non-interpolated average precision with tie-grouped thresholds.",
            "OSCD registered images have no meaningful CRS/geotransform; outputs preserve pixel dimensions and identity registered grid only.",
            "Fold-specific best-F1 thresholds are diagnostics and do not replace the primary 0.50 threshold.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    result = evaluate(args.config, args.output_dir, device_name=args.device, threshold=args.threshold)
    print(json.dumps({"output_dir": str(args.output_dir.resolve()),
                      "folds": [{"fold": f["fold"], "epoch": f["epoch"],
                                 "micro": f["aggregates"]["micro"],
                                 "macro": f["aggregates"]["macro"]} for f in result["folds"]],
                      "five_fold_oof_aggregate": result["five_fold_oof_aggregate"]}, indent=2))


if __name__ == "__main__":
    main()
