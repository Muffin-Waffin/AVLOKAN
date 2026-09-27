"""Fold 0 screening ablation initialized from its existing best OSCD checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio
import torch
import yaml

from pipeline.change_detection.bit import BITArchitecture, BIT_CHECKPOINT_SHA256
from pipeline.change_detection.bit_alignment import align_bit_logits
from pipeline.change_detection.oscd_dataset import load_split_manifest
from pipeline.change_detection.oscd_training import (
    LossAccumulator,
    _forward_patch,
    _make_datasets,
    _make_optimizer,
    _process_memory_mib,
    _select_and_report_runtime,
    masked_weighted_bce_dice,
    load_training_config,
    seed_everything,
)
from scripts.evaluate_oscd_bit import _aggregate, _measure, _write_geotiff
from scripts.evaluate_oscd_cv5_baseline import discrimination_auc


CONFIG_PATH = PROJECT_ROOT / "configs/oscd_bit_pos20_fold0.yaml"
RUN_ROOT = PROJECT_ROOT / "models/bit/BIT_OSCD_ablation_pos20/fold_0"
PREDICTION_ROOT = PROJECT_ROOT / "data/processed/oscd_pos20_fold0"
EXPECTED_VALIDATION = ("bercy", "mumbai", "pisa")
DIAGNOSTIC_THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.96)


def require_new_or_empty(paths: tuple[Path, ...]) -> None:
    occupied = [str(path) for path in paths
                if path.exists() and (not path.is_dir() or any(path.iterdir()))]
    if occupied:
        raise FileExistsError("Refusing to overwrite existing ablation outputs: " + ", ".join(occupied))


def probability_group_stats(probability: np.ndarray, target: np.ndarray) -> dict:
    outputs = {}
    for name, selected in (("changed", target.astype(bool)), ("unchanged", ~target.astype(bool))):
        values = probability[selected].astype(np.float64, copy=False)
        if values.size == 0 or not np.isfinite(values).all():
            raise ValueError(f"No finite {name} validation probabilities")
        p90, p95, p99 = np.percentile(values, (90, 95, 99))
        outputs[name] = {
            "pixels": int(values.size), "mean": float(values.mean()),
            "median": float(np.median(values)), "p90": float(p90),
            "p95": float(p95), "p99": float(p99),
            "fraction_ge_0_50": float(np.mean(values >= 0.50)),
            "fraction_ge_0_75": float(np.mean(values >= 0.75)),
            "fraction_ge_0_90": float(np.mean(values >= 0.90)),
            "fraction_ge_0_95": float(np.mean(values >= 0.95)),
        }
    return outputs


def validate_probability_and_mask(probability: np.ndarray, mask: np.ndarray, target_shape: tuple[int, int]) -> None:
    if probability.shape != target_shape or mask.shape != target_shape:
        raise ValueError("Probability/mask dimensions differ from the registered target grid")
    if not np.isfinite(probability).all() or np.any((probability < 0) | (probability > 1)):
        raise ValueError("Probability map must be finite and within [0,1]")
    if not set(np.unique(mask)) <= {0, 1}:
        raise ValueError("Prediction mask must be binary")


def screening_stop_reason(epoch: int, metrics: dict) -> str | None:
    """Apply the user's early-stop rule from epoch 3 onward."""
    if epoch < 3:
        return None
    if metrics["precision"] < 0.20 and metrics["f1"] < 0.25:
        return "precision below 20% and F1 below 25% after at least three epochs"
    baseline_precision, baseline_f1 = 0.0511504409, 0.0930390328
    substantial_gain = (metrics["precision"] >= baseline_precision + 0.10
                        or metrics["f1"] >= baseline_f1 + 0.10)
    if metrics["recall"] < 0.25 and not substantial_gain:
        return "recall below 25% without a substantial precision/F1 improvement"
    return None


def finalize_existing_screening(run_dir: Path = RUN_ROOT, prediction_root: Path = PREDICTION_ROOT) -> dict:
    """Record a manually stopped run's final epoch without altering model files."""
    run_dir, prediction_root = run_dir.resolve(), prediction_root.resolve()
    metrics_path = run_dir / "metrics.json"
    probability_path = run_dir / "probability_diagnostics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    diagnostics = json.loads(probability_path.read_text(encoding="utf-8"))
    epochs = metrics.get("epochs_completed", [])
    if not epochs:
        raise ValueError("Cannot finalize an ablation with no completed epochs")
    last = epochs[-1]
    stop_reason = screening_stop_reason(last["epoch"], last["validation"]["aggregates"]["micro"])
    if stop_reason is None:
        raise ValueError("The last completed epoch does not meet the configured stop rule")
    checkpoint = run_dir / "checkpoints" / f"epoch_{last['epoch']:02d}.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Missing final completed checkpoint: {checkpoint}")
    last["stop_reason"] = stop_reason
    # Complete the pooled diagnostic threshold sweep from the already-saved
    # probability rasters; this does not rerun model inference.
    for record in epochs:
        per_loc_prob, per_loc_target = [], []
        for location in EXPECTED_VALIDATION:
            pred_dir = prediction_root / f"epoch_{record['epoch']:02d}" / location
            prob_path = pred_dir / f"{location}_probability.tif"
            target_path = (PROJECT_ROOT / "data/processed/oscd_cv5_validation_baseline/fold_0"
                           / location / f"{location}_ground_truth.tif")
            with rasterio.open(prob_path) as src:
                prob = src.read(1)
            with rasterio.open(target_path) as src:
                target = src.read(1)
            if prob.shape != target.shape or not np.isfinite(prob).all():
                raise ValueError(f"Saved screening probability map is invalid: {location}, epoch {record['epoch']}")
            per_loc_prob.append(prob.reshape(-1))
            per_loc_target.append(target.reshape(-1))
        pooled_prob, pooled_target = np.concatenate(per_loc_prob), np.concatenate(per_loc_target)
        sweep = {
            f"{threshold:.2f}": _measure((pooled_prob >= threshold).astype(np.uint8), pooled_target)
            for threshold in DIAGNOSTIC_THRESHOLDS
        }
        record["validation"]["aggregates"]["threshold_sweep"] = sweep
        best_threshold = max(DIAGNOSTIC_THRESHOLDS,
                             key=lambda threshold: (sweep[f"{threshold:.2f}"]["f1"], threshold))
        record["validation"]["aggregates"]["best_f1_diagnostic_threshold"] = best_threshold
    status = {
        "state": "stopped_by_screening_rule",
        "training_complete": False,
        "completed_epochs": len(epochs),
        "stopped_after_epoch": last["epoch"],
        "stop_reason": stop_reason,
        "final_checkpoint": str(checkpoint),
        "final_prediction_directory": str(prediction_root / f"epoch_{last['epoch']:02d}"),
    }
    metrics["screening_status"] = status
    diagnostics["screening_status"] = status
    diagnostics["epochs"] = [
        {"epoch": row["epoch"], **row["probability_diagnostics"]}
        for row in epochs
    ]
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    probability_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    return status


def _baseline_probability_diagnostics(location: str, target: np.ndarray) -> dict:
    directory = PROJECT_ROOT / "data/processed/oscd_cv5_validation_baseline/fold_0" / location
    with rasterio.open(directory / f"{location}_probability.tif") as src:
        probability = src.read(1)
    with rasterio.open(directory / f"{location}_ground_truth.tif") as src:
        baseline_target = src.read(1)
    if not np.array_equal(target, baseline_target):
        raise RuntimeError(f"Fold 0 validation mask differs from existing baseline at {location}")
    return probability_group_stats(probability, target)


def _validation_pass(model, dataset, config: dict, device: torch.device, epoch_dir: Path) -> tuple[dict, dict, dict]:
    model.eval()
    accumulator = LossAccumulator()
    scenes: dict[str, dict] = {}
    root = Path(config["data"]["root"])
    with torch.inference_mode():
        for index in range(len(dataset)):
            sample = dataset[index]
            meta = sample["metadata"]
            location = meta["location_id"]
            if location not in EXPECTED_VALIDATION:
                raise RuntimeError(f"Unexpected validation location: {location}")
            t1, t2 = sample["t1"].unsqueeze(0).to(device), sample["t2"].unsqueeze(0).to(device)
            target_patch = sample["target"].unsqueeze(0).to(device)
            valid_patch = sample["valid"].unsqueeze(0).to(device)
            logits = align_bit_logits(model(t1, t2), tuple(target_patch.shape[-2:]))
            loss_parts = masked_weighted_bce_dice(logits, target_patch, valid_patch, **config["loss"])
            accumulator.add(loss_parts)
            valid_h, valid_w = int(meta["valid_height"]), int(meta["valid_width"])
            if location not in scenes:
                reference = root / "Onera Satellite Change Detection dataset - Images" / location / "imgs_1_rect" / "B04.tif"
                with rasterio.open(reference) as src:
                    shape = (src.height, src.width)
                scenes[location] = {
                    "reference": reference,
                    "probability": np.full(shape, np.nan, dtype=np.float32),
                    "target": np.zeros(shape, dtype=np.uint8),
                }
            scene = scenes[location]
            row, col = int(meta["row"]), int(meta["col"])
            window = np.s_[row:row + valid_h, col:col + valid_w]
            if np.isfinite(scene["probability"][window]).any():
                raise RuntimeError(f"Validation patch overlap detected for {location}")
            scene["probability"][window] = torch.softmax(logits.float(), dim=1)[0, 1, :valid_h, :valid_w].cpu().numpy()
            scene["target"][window] = sample["target"][:valid_h, :valid_w].numpy().astype(np.uint8)

    if set(scenes) != set(EXPECTED_VALIDATION):
        raise RuntimeError(f"Fold 0 validation roster mismatch: {sorted(scenes)}")
    val_loss = accumulator.report(
        bce_weight=config["loss"]["bce_weight"], dice_weight=config["loss"]["dice_weight"],
        smooth=config["loss"]["smooth"],
    )
    per_location, probabilities, targets = {}, [], []
    baseline_probabilities = []
    diagnostics = {}
    for location in EXPECTED_VALIDATION:
        scene = scenes[location]
        prob, target = scene["probability"], scene["target"]
        if not np.isfinite(prob).all():
            raise ValueError(f"Unfilled/non-finite validation probability map for {location}")
        mask = (prob >= 0.50).astype(np.uint8)
        validate_probability_and_mask(prob, mask, target.shape)
        per_location[location] = _measure(mask, target)
        auc_roc, auc_pr = discrimination_auc(prob, target)
        per_location[location]["roc_auc"] = auc_roc
        per_location[location]["pr_auc_average_precision"] = auc_pr
        per_location[location]["threshold_sweep"] = {
            f"{threshold:.2f}": _measure((prob >= threshold).astype(np.uint8), target)
            for threshold in DIAGNOSTIC_THRESHOLDS
        }
        current_diagnostics = probability_group_stats(prob, target)
        baseline_diagnostics = _baseline_probability_diagnostics(location, target)
        diagnostics[location] = {**current_diagnostics, "baseline": baseline_diagnostics}
        out_dir = epoch_dir / location
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_geotiff(out_dir / f"{location}_probability.tif", prob, scene["reference"], dtype="float32", predictor=3)
        _write_geotiff(out_dir / f"{location}_prediction_threshold_0.50.tif", mask, scene["reference"], dtype="uint8", predictor=2)
        probabilities.append(prob.reshape(-1))
        targets.append(target.reshape(-1))
        baseline_directory = PROJECT_ROOT / "data/processed/oscd_cv5_validation_baseline/fold_0" / location
        with rasterio.open(baseline_directory / f"{location}_probability.tif") as src:
            baseline_probabilities.append(src.read(1).reshape(-1))

    aggregate = _aggregate(per_location)
    all_probability = np.concatenate(probabilities)
    all_target = np.concatenate(targets)
    aggregate["micro"]["roc_auc"], aggregate["micro"]["pr_auc_average_precision"] = discrimination_auc(all_probability, all_target)
    aggregate["macro"]["roc_auc"] = float(np.mean([per_location[x]["roc_auc"] for x in EXPECTED_VALIDATION]))
    aggregate["macro"]["pr_auc_average_precision"] = float(np.mean([per_location[x]["pr_auc_average_precision"] for x in EXPECTED_VALIDATION]))
    aggregate["threshold_sweep"] = {
        f"{threshold:.2f}": _measure((all_probability >= threshold).astype(np.uint8), all_target)
        for threshold in DIAGNOSTIC_THRESHOLDS
    }
    pooled_probability_diagnostics = probability_group_stats(all_probability, all_target)
    pooled_probability_diagnostics["baseline"] = probability_group_stats(
        np.concatenate(baseline_probabilities), all_target,
    )
    return {"loss": val_loss, "per_location": per_location, "aggregates": aggregate}, {
        "per_location": diagnostics, "pooled": pooled_probability_diagnostics,
    }, scenes


def _validate_config_against_baseline(config: dict, baseline: dict) -> None:
    if config["cross_validation"] != baseline["cross_validation"]:
        raise ValueError("Fold/split seed differs from baseline configuration")
    if config["data"] != baseline["data"] or config["input"] != baseline["input"]:
        raise ValueError("Dataset or input normalization/band configuration differs from baseline")
    if config["patch"] != baseline["patch"]:
        raise ValueError("Patching or augmentation differs from baseline")
    expected_training = dict(baseline["training"])
    expected_training["epochs"] = 5
    if config["training"] != expected_training:
        raise ValueError("Training settings differ from baseline except required five-epoch screening cap")
    expected_loss = dict(baseline["loss"])
    expected_loss["positive_weight"] = 20
    if config["loss"] != expected_loss:
        raise ValueError("Loss configuration must differ only by positive_weight=20")
    if config["model"]["architecture"] != baseline["model"]["architecture"]:
        raise ValueError("BIT architecture differs from the baseline")
    if Path(config["model"]["checkpoint"]).as_posix() != "models/bit/BIT_OSCD_CV5/fold_0/best_oscd_bit.pt":
        raise ValueError("The initialization must be the existing best Fold 0 OSCD checkpoint")
    if Path(config["output"]["checkpoint_directory"]).as_posix() != "models/bit/BIT_OSCD_ablation_pos20":
        raise ValueError("Ablation checkpoints must use the isolated pos20 output directory")


def run_experiment(config_path: Path = CONFIG_PATH) -> dict:
    config_path = config_path.resolve()
    config = load_training_config(config_path)
    baseline_config = load_training_config(PROJECT_ROOT / "configs/oscd_bit_training.yaml")
    _validate_config_against_baseline(config, baseline_config)
    require_new_or_empty((RUN_ROOT, PREDICTION_ROOT))

    init_path = (PROJECT_ROOT / config["model"]["checkpoint"]).resolve()
    if not init_path.is_file():
        raise FileNotFoundError(f"Fold 0 OSCD initialization checkpoint is missing: {init_path}")
    init_sha256 = hashlib.sha256(init_path.read_bytes()).hexdigest()
    container = torch.load(init_path, map_location="cpu", weights_only=False)
    if container.get("base_checkpoint_sha256") != BIT_CHECKPOINT_SHA256:
        raise ValueError("Initialization checkpoint is not descended from the verified official LEVIR BIT weights")
    if container.get("config", {}).get("cross_validation", {}).get("fold") != 0:
        raise ValueError("Initialization checkpoint does not belong to Fold 0")
    if int(container.get("epoch", -1)) != 16:
        raise ValueError("Expected the verified Fold 0 best checkpoint at epoch 16")
    if not isinstance(container.get("model_state_dict"), dict):
        raise ValueError("OSCD checkpoint has no model_state_dict")

    selected_device, environment = _select_and_report_runtime(config["training"]["device"])
    seed = int(config["training"]["seed"])
    seed_everything(seed)
    torch.set_num_threads(int(config["training"].get("cpu_threads", 4)))
    if selected_device.type == "cuda":
        torch.cuda.set_device(selected_device.index if selected_device.index is not None else torch.cuda.current_device())

    train_data, validation_data, fold_index = _make_datasets(config)
    if fold_index != 0 or set(validation_data.source.location_ids) != set(EXPECTED_VALIDATION):
        raise RuntimeError("Dataset builder did not produce the exact Fold 0 validation roster")
    manifest = load_split_manifest(config["data"]["root"], config["data"]["splits"])
    if set(train_data.source.location_ids) & set(manifest["test"]):
        raise RuntimeError("Official test location leaked into the training dataset")

    model = BITArchitecture()
    model.load_state_dict(container["model_state_dict"], strict=True)
    model.to(selected_device)
    optimizer = _make_optimizer(model, config["training"])
    run_dir = RUN_ROOT
    checkpoint_dir = run_dir / "checkpoints"
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    PREDICTION_ROOT.mkdir(parents=True, exist_ok=True)
    effective_config = {
        **config,
        "experiment": {
            "name": "Fold 0 positive BCE weight ablation",
            "initialization_checkpoint": str(init_path),
            "initialization_checkpoint_sha256": init_sha256,
            "initialization_epoch": int(container["epoch"]),
            "optimizer_state": "fresh AdamW state; same optimizer type and configured hyperparameters",
            "primary_evaluation": "raw probabilities at threshold 0.50; no Phase 1 post-processing",
        },
    }
    (run_dir / "config.json").write_text(json.dumps(effective_config, indent=2), encoding="utf-8")
    (run_dir / "runtime.json").write_text(json.dumps({
        **environment, "seed": seed, "train_locations": train_data.source.location_ids,
        "validation_locations": list(EXPECTED_VALIDATION), "training_patch_count": len(train_data),
        "validation_patch_count": len(validation_data), "training_positive_weight": 20,
    }, indent=2), encoding="utf-8")

    epochs = []
    screening_status = {"state": "running", "training_complete": False}
    for epoch in range(1, int(config["training"]["epochs"]) + 1):
        epoch_started = time.perf_counter()
        train_data.set_epoch(epoch - 1)
        model.train()
        train_accumulator = LossAccumulator()
        for index in range(len(train_data)):
            sample = train_data[index]
            optimizer.zero_grad(set_to_none=True)
            _, logits, (target, valid), _ = _forward_patch(model, sample, selected_device)
            components = masked_weighted_bce_dice(logits, target, valid, **config["loss"])
            components["total"].backward()
            optimizer.step()
            train_accumulator.add(components)
        train_metrics = train_accumulator.report(
            bce_weight=config["loss"]["bce_weight"], dice_weight=config["loss"]["dice_weight"],
            smooth=config["loss"]["smooth"],
        )
        epoch_predictions = PREDICTION_ROOT / f"epoch_{epoch:02d}"
        validation, probability_diagnostics, _ = _validation_pass(
            model, validation_data, config, selected_device, epoch_predictions,
        )
        micro = validation["aggregates"]["micro"]
        stop_reason = screening_stop_reason(epoch, micro)
        record = {
            "epoch": epoch, "initialization_epoch": int(container["epoch"]),
            "train_loss": train_metrics, "validation": validation,
            "probability_diagnostics": probability_diagnostics,
            "prediction_directory": str(epoch_predictions),
            "elapsed_seconds": time.perf_counter() - epoch_started,
            "stop_reason": stop_reason,
        }
        epochs.append(record)
        (run_dir / "metrics.json").write_text(json.dumps({
            "experiment": "OOF Fold 0 positive weight ablation; screening only",
            "threshold_primary": 0.50,
            "diagnostic_thresholds": list(DIAGNOSTIC_THRESHOLDS),
            "epochs_completed": epochs,
            "official_test_evaluated": False,
            "screening_status": {"state": "stopping" if stop_reason else "running",
                                 "training_complete": False, "stop_reason": stop_reason},
        }, indent=2), encoding="utf-8")
        (run_dir / "probability_diagnostics.json").write_text(json.dumps({
            "comparison_note": "Fold 0 baseline statistics are read from saved OOF probability maps; ablation maps are raw model probabilities.",
            "epochs": [{"epoch": item["epoch"], **item["probability_diagnostics"]} for item in epochs],
        }, indent=2), encoding="utf-8")

        checkpoint_name = ("final_oscd_bit.pt" if epoch == int(config["training"]["epochs"]) or stop_reason
                           else f"epoch_{epoch:02d}.pt")
        checkpoint_path = checkpoint_dir / checkpoint_name
        if checkpoint_path.exists():
            raise FileExistsError(f"Refusing to overwrite checkpoint: {checkpoint_path}")
        torch.save({
            "model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch, "initialization_epoch": int(container["epoch"]),
            "train_metrics": train_metrics, "validation_metrics": validation,
            "base_checkpoint_sha256": BIT_CHECKPOINT_SHA256,
            "initialization_checkpoint": str(init_path),
            "initialization_checkpoint_sha256": init_sha256,
            "config": effective_config,
        }, checkpoint_path)
        epochs[-1]["checkpoint"] = str(checkpoint_path)
        (run_dir / "metrics.json").write_text(json.dumps({
            "experiment": "OOF Fold 0 positive weight ablation; screening only",
            "threshold_primary": 0.50,
            "diagnostic_thresholds": list(DIAGNOSTIC_THRESHOLDS),
            "epochs_completed": epochs,
            "official_test_evaluated": False,
            "screening_status": {"state": "stopped_by_screening_rule" if stop_reason else
                                 ("completed_max_epochs" if epoch == int(config["training"]["epochs"]) else "running"),
                                 "training_complete": stop_reason is None and epoch == int(config["training"]["epochs"]),
                                 "stop_reason": stop_reason,
                                 "final_checkpoint": str(checkpoint_path) if stop_reason or epoch == int(config["training"]["epochs"]) else None},
        }, indent=2), encoding="utf-8")
        print(yaml.safe_dump({
            "epoch": epoch, "train_loss": train_metrics,
            "validation_loss": validation["loss"],
            "validation_micro_threshold_0_50": validation["aggregates"]["micro"],
            "checkpoint": str(checkpoint_path),
        }, sort_keys=True).strip(), flush=True)
        if stop_reason:
            screening_status = {"state": "stopped_by_screening_rule", "training_complete": False,
                                "completed_epochs": epoch, "stopped_after_epoch": epoch,
                                "stop_reason": stop_reason, "final_checkpoint": str(checkpoint_path)}
            break
        if epoch == int(config["training"]["epochs"]):
            screening_status = {"state": "completed_max_epochs", "training_complete": True,
                                "completed_epochs": epoch, "final_checkpoint": str(checkpoint_path)}
    return {"run_dir": str(run_dir), "prediction_dir": str(PREDICTION_ROOT),
            "epochs": epochs, "screening_status": screening_status}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--finalize-existing", action="store_true",
                        help="Record early-stop status for an already-saved screening run; does not train")
    args = parser.parse_args()
    if args.finalize_existing:
        print(json.dumps(finalize_existing_screening(), indent=2))
        return
    result = run_experiment(args.config)
    print(json.dumps({"run_dir": result["run_dir"], "prediction_dir": result["prediction_dir"],
                      "epochs": [{"epoch": row["epoch"], "metrics": row["validation"]["aggregates"],
                                  "checkpoint": row["checkpoint"]} for row in result["epochs"]]}, indent=2))


if __name__ == "__main__":
    main()
