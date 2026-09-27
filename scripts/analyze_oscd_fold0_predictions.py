"""Failure diagnostics for the saved Fold 0 validation maps (never opens test imagery)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio
from PIL import Image, ImageDraw
import scipy.ndimage as ndi
import torch

from pipeline.change_detection.bit import BITArchitecture, BIT_CHECKPOINT_SHA256
from pipeline.change_detection.bit_alignment import align_bit_logits
from pipeline.change_detection.oscd_dataset import (
    BIT_RGB_BANDS,
    normalize_bit_dn,
)
from pipeline.change_detection.oscd_training import (
    OSCDPatchDataset,
    load_training_config,
    training_device,
)


LOCATIONS = ("bercy", "mumbai", "pisa")
EVALUATION_ROOT = PROJECT_ROOT / "data/processed/oscd_fold0_validation"
CHECKPOINT = PROJECT_ROOT / "models/bit/BIT_OSCD_CV5/fold_0/best_oscd_bit.pt"
BASE_CHECKPOINT = PROJECT_ROOT / "models/bit/BIT_LEVIR/best_ckpt.pt"
DIAGNOSTIC_ROOT = EVALUATION_ROOT / "diagnostics"
PATCH_SIZE = 256
THRESHOLD = 0.5


def _read(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as source:
        return source.read(1), {
            "width": source.width,
            "height": source.height,
            "crs": source.crs.to_string() if source.crs else None,
            "transform": tuple(source.transform),
            "dtype": source.dtypes[0],
        }


def _distribution(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values, dtype=np.float64)
    percentiles = np.percentile(values, (90, 95, 99))
    return {
        "count": int(values.size),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "p90": float(percentiles[0]),
        "p95": float(percentiles[1]),
        "p99": float(percentiles[2]),
        "fraction_ge_0_25": float(np.mean(values >= 0.25)),
        "fraction_ge_0_50": float(np.mean(values >= 0.50)),
        "fraction_ge_0_75": float(np.mean(values >= 0.75)),
    }


def _metric_pair(prediction: np.ndarray, target: np.ndarray) -> dict[str, int]:
    pred, truth = prediction.astype(bool), target.astype(bool)
    return {
        "tp": int(np.count_nonzero(pred & truth)),
        "fp": int(np.count_nonzero(pred & ~truth)),
        "fn": int(np.count_nonzero(~pred & truth)),
        "tn": int(np.count_nonzero(~pred & ~truth)),
    }


def _pair_images(root: Path, location: str) -> tuple[np.ndarray, np.ndarray, dict]:
    base = root / "Onera Satellite Change Detection dataset - Images" / location
    dates = [line.strip().split(":", 1)[-1].strip()
             for line in (base / "dates.txt").read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if len(dates) != 2:
        raise RuntimeError(f"Expected exactly two acquisition dates for {location}: {dates}")

    arrays: list[list[np.ndarray]] = [[], []]
    grids: list[dict] = []
    signatures = []
    for time_index, folder_name in enumerate(("imgs_1_rect", "imgs_2_rect")):
        for band in BIT_RGB_BANDS:
            path = base / folder_name / f"{band}.tif"
            with rasterio.open(path) as source:
                profile = (source.width, source.height, source.crs, source.transform)
                signatures.append(profile)
                arrays[time_index].append(source.read(1))
                grids.append({
                    "path": str(path.relative_to(PROJECT_ROOT)),
                    "width": source.width,
                    "height": source.height,
                    "crs": source.crs.to_string() if source.crs else None,
                    "transform": tuple(source.transform),
                    "dtype": source.dtypes[0],
                    "nodata": source.nodata,
                    "band": band,
                })
    reference = signatures[0]
    same_grid = all(signature == reference for signature in signatures)
    if not same_grid:
        raise RuntimeError(f"Registered pair/channel grid mismatch for {location}")
    t1 = np.stack(arrays[0], axis=-1).astype(np.float32) / 10000.0
    t2 = np.stack(arrays[1], axis=-1).astype(np.float32) / 10000.0
    t1 = np.clip(t1, 0, 1)
    t2 = np.clip(t2, 0, 1)
    return t1, t2, {
        "dates": dates,
        "bands": list(BIT_RGB_BANDS),
        "registered_grid_matches_across_dates_and_bands": same_grid,
        "crs": grids[0]["crs"],
        "transform": grids[0]["transform"],
        "width": grids[0]["width"],
        "height": grids[0]["height"],
        "bands_checked": grids,
    }


def _probability_histogram(path: Path, target: np.ndarray, probability: np.ndarray) -> None:
    bins = np.linspace(0, 1, 101)
    changed_hist = np.histogram(probability[target == 1], bins=bins)[0]
    unchanged_hist = np.histogram(probability[target == 0], bins=bins)[0]
    changed_hist = changed_hist / max(int(changed_hist.sum()), 1)
    unchanged_hist = unchanged_hist / max(int(unchanged_hist.sum()), 1)
    maximum = max(float(changed_hist.max()), float(unchanged_hist.max()), 1e-8)
    width, height = 920, 480
    left, top, right, bottom = 74, 36, 890, 400
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.line((left, top, left, bottom, right, bottom), fill="black", width=2)
    for fraction in (0.25, 0.5, 0.75, 1.0):
        y = bottom - int((bottom - top) * fraction)
        draw.line((left, y, right, y), fill=(225, 225, 225), width=1)
    for threshold in (0.25, 0.50, 0.75):
        x = left + int((right - left) * threshold)
        draw.line((x, top, x, bottom), fill=(110, 110, 110), width=1)
        draw.text((x + 3, bottom + 8), f"{threshold:.2f}", fill="black")
    for hist, color in ((unchanged_hist, (55, 105, 205)), (changed_hist, (220, 60, 45))):
        points = []
        for index, value in enumerate(hist):
            x = left + int((right - left) * index / (len(hist) - 1))
            y = bottom - int((bottom - top) * value / maximum)
            points.append((x, y))
        draw.line(points, fill=color, width=3)
    draw.text((left, 10), "Within-class probability histograms (each class normalized to unit area)", fill="black")
    draw.text((left + 10, top + 8), "unchanged", fill=(55, 105, 205))
    draw.text((left + 110, top + 8), "changed", fill=(220, 60, 45))
    draw.text((left, bottom + 28), "Predicted change probability", fill="black")
    draw.text((8, top), "relative", fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _confusion_overlay(path: Path, rgb: np.ndarray, target: np.ndarray,
                       prediction: np.ndarray) -> None:
    low, high = [], []
    for channel in range(3):
        low.append(float(np.percentile(rgb[..., channel], 2)))
        high.append(max(float(np.percentile(rgb[..., channel], 98)), low[-1] + 1e-6))
    base = np.stack([
        np.clip((rgb[..., channel] - low[channel]) / (high[channel] - low[channel]), 0, 1)
        for channel in range(3)
    ], axis=-1)
    base = (base * 255).astype(np.uint8)
    overlay = np.zeros_like(base)
    truth, pred = target.astype(bool), prediction.astype(bool)
    overlay[truth & pred] = (20, 230, 80)       # TP: green
    overlay[~truth & pred] = (255, 35, 30)      # FP: red
    overlay[truth & ~pred] = (35, 110, 255)     # FN: blue
    active = truth | pred
    base[active] = (0.38 * base[active] + 0.62 * overlay[active]).astype(np.uint8)
    image = Image.fromarray(base, mode="RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for seam in range(PATCH_SIZE, width, PATCH_SIZE):
        draw.line((seam, 0, seam, height), fill=(255, 230, 30), width=2)
    for seam in range(PATCH_SIZE, height, PATCH_SIZE):
        draw.line((0, seam, width, seam), fill=(255, 230, 30), width=2)
    draw.rectangle((4, 4, 344, 24), fill="white")
    draw.text((8, 8), "TP green | FP red | FN blue | 256px seams yellow", fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _spatial_analysis(probability: np.ndarray, target: np.ndarray,
                      prediction: np.ndarray) -> dict:
    height, width = target.shape
    fp = prediction.astype(bool) & ~target.astype(bool)
    tp = prediction.astype(bool) & target.astype(bool)
    y, x = np.ogrid[:height, :width]
    scene_edge = (y < 8) | (y >= height - 8) | (x < 8) | (x >= width - 8)
    seam_y = np.zeros(height, dtype=bool)
    seam_x = np.zeros(width, dtype=bool)
    for seam in range(PATCH_SIZE, height, PATCH_SIZE):
        seam_y[max(0, seam - 8):min(height, seam + 8)] = True
    for seam in range(PATCH_SIZE, width, PATCH_SIZE):
        seam_x[max(0, seam - 8):min(width, seam + 8)] = True
    seams = seam_y[:, None] | seam_x[None, :]

    components, count = ndi.label(fp, structure=np.ones((3, 3), dtype=np.uint8))
    sizes = np.bincount(components.ravel())[1:]
    sizes_sorted = np.sort(sizes)[::-1]
    distance_to_change = ndi.distance_transform_edt(~target.astype(bool))
    fp_count = int(fp.sum())

    def zone(mask: np.ndarray) -> dict[str, float | int]:
        area = int(mask.sum())
        zone_fp = int((fp & mask).sum())
        return {
            "pixels": area,
            "false_positive_pixels": zone_fp,
            "false_positive_rate": zone_fp / area if area else 0.0,
            "fraction_of_all_false_positives": zone_fp / fp_count if fp_count else 0.0,
            "mean_probability": float(probability[mask].mean()) if area else 0.0,
        }

    per_patch = []
    for row in range(0, height, PATCH_SIZE):
        for col in range(0, width, PATCH_SIZE):
            window = np.s_[row:min(row + PATCH_SIZE, height), col:min(col + PATCH_SIZE, width)]
            tile_pred = prediction[window].astype(bool)
            tile_truth = target[window].astype(bool)
            tile_fp = tile_pred & ~tile_truth
            per_patch.append({
                "row": row,
                "col": col,
                "height": int(tile_truth.shape[0]),
                "width": int(tile_truth.shape[1]),
                "predicted_change_percent": 100 * float(tile_pred.mean()),
                "ground_truth_change_percent": 100 * float(tile_truth.mean()),
                "false_positive_pixels": int(tile_fp.sum()),
            })

    distance_groups = {
        "within_2px_of_gt_change": fp & (distance_to_change <= 2),
        "within_8px_of_gt_change": fp & (distance_to_change <= 8),
        "more_than_8px_from_gt_change": fp & (distance_to_change > 8),
    }
    return {
        "false_positive_components_8_connected": int(count),
        "largest_component_pixels": int(sizes_sorted[0]) if len(sizes_sorted) else 0,
        "largest_10_component_fraction_of_fp": float(sizes_sorted[:10].sum() / fp_count) if fp_count else 0.0,
        "components_at_least_256_pixels": int(np.count_nonzero(sizes >= 256)),
        "fp_within_2px_of_gt_change_fraction": float(distance_groups["within_2px_of_gt_change"].sum() / fp_count) if fp_count else 0.0,
        "fp_within_8px_of_gt_change_fraction": float(distance_groups["within_8px_of_gt_change"].sum() / fp_count) if fp_count else 0.0,
        "fp_more_than_8px_from_gt_change_fraction": float(distance_groups["more_than_8px_from_gt_change"].sum() / fp_count) if fp_count else 0.0,
        "scene_edge_8px_band": zone(scene_edge),
        "internal_patch_seam_8px_band": zone(seams),
        "outside_internal_patch_seams": zone(~seams),
        "patch_grid": per_patch,
    }


def _spectral_comparison(t1: np.ndarray, t2: np.ndarray, target: np.ndarray,
                         prediction: np.ndarray) -> dict:
    fp = prediction.astype(bool) & ~target.astype(bool)
    tn = ~prediction.astype(bool) & ~target.astype(bool)
    tp = prediction.astype(bool) & target.astype(bool)
    delta = np.abs(t2 - t1)
    result = {}
    for name, mask in (("false_positive", fp), ("true_negative", tn), ("true_positive", tp)):
        result[name] = {
            "pixels": int(mask.sum()),
            "mean_reflectance_t1_b04_b03_b02": t1[mask].mean(axis=0).astype(float).tolist() if mask.any() else [],
            "mean_reflectance_t2_b04_b03_b02": t2[mask].mean(axis=0).astype(float).tolist() if mask.any() else [],
            "mean_absolute_temporal_difference_b04_b03_b02": delta[mask].mean(axis=0).astype(float).tolist() if mask.any() else [],
            "median_absolute_temporal_difference_b04_b03_b02": np.median(delta[mask], axis=0).astype(float).tolist() if mask.any() else [],
        }
    return result


def _verify_checkpoint() -> dict:
    fine_tuned = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    base_digest = hashlib.sha256(BASE_CHECKPOINT.read_bytes()).hexdigest()
    if base_digest != BIT_CHECKPOINT_SHA256:
        raise RuntimeError("Official LEVIR base checkpoint SHA-256 verification failed")
    base = torch.load(BASE_CHECKPOINT, map_location="cpu", weights_only=False)
    base_state = base.get("model_G_state_dict")
    fine_state = fine_tuned.get("model_state_dict")
    if not isinstance(base_state, dict) or not isinstance(fine_state, dict):
        raise RuntimeError("Checkpoint state dictionaries are missing")
    base_model, fine_model = BITArchitecture(), BITArchitecture()
    base_model.load_state_dict(base_state, strict=True)
    fine_model.load_state_dict(fine_state, strict=True)
    differences = []
    total = 0
    delta_sq = 0.0
    base_sq = 0.0
    for name, base_value in base_model.state_dict().items():
        fine_value = fine_model.state_dict()[name]
        if base_value.shape != fine_value.shape:
            raise RuntimeError(f"Checkpoint tensor shape changed at {name}")
        changed = int(torch.count_nonzero(base_value != fine_value))
        total += base_value.numel()
        if changed:
            differences.append({"tensor": name, "changed_values": changed, "total_values": base_value.numel()})
        diff = fine_value.float() - base_value.float()
        delta_sq += float(torch.sum(diff * diff))
        base_sq += float(torch.sum(base_value.float() * base_value.float()))
    if not differences:
        raise RuntimeError("Fine-tuned checkpoint is identical to the LEVIR initialization")
    return {
        "fine_tuned_checkpoint": str(CHECKPOINT.relative_to(PROJECT_ROOT)),
        "fine_tuned_sha256": hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),
        "fine_tuned_epoch": int(fine_tuned["epoch"]),
        "fold": int(fine_tuned["config"]["cross_validation"]["fold"]),
        "recorded_base_sha256": fine_tuned.get("base_checkpoint_sha256"),
        "verified_base_sha256": base_digest,
        "strict_state_dict_load": True,
        "changed_tensors": len(differences),
        "total_tensors": len(base_state),
        "changed_values": sum(row["changed_values"] for row in differences),
        "total_values": total,
        "fraction_of_state_values_changed": sum(row["changed_values"] for row in differences) / total,
        "relative_l2_weight_delta": float(np.sqrt(delta_sq / max(base_sq, 1e-30))),
        "largest_changed_tensors": sorted(differences, key=lambda row: row["changed_values"], reverse=True)[:12],
    }


def analyze(device_name: str = "cuda") -> dict:
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary_path = EVALUATION_ROOT / "metrics.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["locations"] != list(LOCATIONS) or summary["fold"] != 0:
        raise RuntimeError("Saved evaluation metadata is not exactly the requested Fold 0 validation set")
    config = load_training_config(PROJECT_ROOT / "configs/oscd_bit_training.yaml")
    device = training_device(device_name)

    checkpoint_info = _verify_checkpoint()
    fine_tuned = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = BITArchitecture()
    model.load_state_dict(fine_tuned["model_state_dict"], strict=True)
    model.eval().to(device)
    dataset = OSCDPatchDataset(
        split="validation", locations=list(LOCATIONS),
        patch_size=PATCH_SIZE, patch_stride=PATCH_SIZE,
        quantification_value=float(config["input"]["quantification_value"]),
        augmentation=False, seed=int(config["training"]["seed"]),
        root=config["data"]["root"], splits_path=config["data"]["splits"],
    )

    results: dict[str, dict] = {}
    source_arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    saved_arrays: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, dict]] = {}
    for location in LOCATIONS:
        loc_dir = EVALUATION_ROOT / location
        probability, prob_profile = _read(loc_dir / f"{location}_probability.tif")
        prediction, pred_profile = _read(loc_dir / f"{location}_prediction_threshold_0.50.tif")
        saved_target, target_profile = _read(loc_dir / f"{location}_ground_truth.tif")
        if not np.isfinite(probability).all() or probability.min() < 0 or probability.max() > 1:
            raise RuntimeError(f"Invalid probability values for {location}")
        if not set(np.unique(prediction).tolist()) <= {0, 1}:
            raise RuntimeError(f"Prediction is not binary for {location}")
        if not set(np.unique(saved_target).tolist()) <= {0, 1}:
            raise RuntimeError(f"Saved target is not binary for {location}")
        grid_keys = ("width", "height", "crs", "transform")
        if any(
            tuple(profile[key] for key in grid_keys)
            != tuple(prob_profile[key] for key in grid_keys)
            for profile in (pred_profile, target_profile)
        ):
            raise RuntimeError(f"Saved probability/prediction/target grids differ for {location}")
        saved_target = saved_target.astype(np.uint8)
        prediction = prediction.astype(np.uint8)
        if not np.array_equal(prediction, probability >= THRESHOLD):
            raise RuntimeError(f"Saved prediction mask does not match threshold {THRESHOLD} for {location}")

        data_root = Path(config["data"]["root"]).resolve()
        t1, t2, pair = _pair_images(data_root, location)
        if (pair["height"], pair["width"]) != saved_target.shape:
            raise RuntimeError(f"Input and saved output dimensions differ for {location}")
        raw_label_path = data_root / "Onera Satellite Change Detection dataset - Train Labels" / location / "cm" / f"{location}-cm.tif"
        raw_label, raw_profile = _read(raw_label_path)
        if raw_label.shape != saved_target.shape or not np.array_equal(raw_label == 2, saved_target):
            raise RuntimeError(f"Saved ground truth differs from the registered source TIFF for {location}")
        if (raw_profile["width"], raw_profile["height"], raw_profile["crs"], raw_profile["transform"]) != (
            pair["width"], pair["height"], pair["crs"], pair["transform"],
        ):
            raise RuntimeError(f"Source label dimensions differ from registered imagery for {location}")

        changed, unchanged = saved_target == 1, saved_target == 0
        all_stats = _distribution(probability)
        changed_stats = _distribution(probability[changed])
        unchanged_stats = _distribution(probability[unchanged])
        # For two-class softmax, logit(change)-logit(no-change) = log(p/(1-p));
        # logits were not persisted, so this is reconstructed from the saved probability map.
        clipped = np.clip(probability.astype(np.float64), 1e-7, 1 - 1e-7)
        logit_difference = np.log(clipped / (1 - clipped))
        metrics = summary["per_location"][location]
        fp = (prediction == 1) & unchanged
        tn = (prediction == 0) & unchanged
        profile_match = (
            prob_profile["width"], prob_profile["height"],
            prob_profile["crs"], prob_profile["transform"],
        ) == (pair["width"], pair["height"], pair["crs"], pair["transform"])
        if not profile_match:
            raise RuntimeError(f"Saved prediction georeferencing/pixel transform differs for {location}")
        results[location] = {
            "pair": pair,
            "grid_checks": {
                "inputs_all_bands_same_registered_grid": pair["registered_grid_matches_across_dates_and_bands"],
                "input_output_dimensions_match": profile_match,
                "registered_crs": pair["crs"],
                "registered_transform": pair["transform"],
                "source_label_equals_saved_ground_truth": True,
                "prediction_equals_probability_ge_0_50": True,
                "prediction_values": np.unique(prediction).astype(int).tolist(),
                "probability_min_max_within_unit_interval": [float(probability.min()), float(probability.max())],
                "padded_pixels_in_outputs": 0,
            },
            "probability_all_pixels": all_stats,
            "probability_ground_truth_changed": changed_stats,
            "probability_ground_truth_unchanged": unchanged_stats,
            "reconstructed_logit_difference_changed": _distribution(logit_difference[changed]),
            "reconstructed_logit_difference_unchanged": _distribution(logit_difference[unchanged]),
            "saved_confusion_counts": _metric_pair(prediction, saved_target),
            "false_positive_spatial": _spatial_analysis(probability, saved_target, prediction),
            "false_positive_vs_true_negative_spectral": _spectral_comparison(t1, t2, saved_target, prediction),
        }
        source_arrays[location] = (t1, t2)
        saved_arrays[location] = (probability, prediction, saved_target, prob_profile)
        _probability_histogram(
            DIAGNOSTIC_ROOT / f"{location}_probability_by_truth_histogram.png",
            saved_target, probability,
        )
        _confusion_overlay(
            DIAGNOSTIC_ROOT / f"{location}_confusion_overlay.png",
            t1, saved_target, prediction,
        )

    # Re-run only these validation patches and compare their aligned model output to the saved maps.
    reproduction_max_abs: dict[str, float] = {location: 0.0 for location in LOCATIONS}
    normalization_verified: dict[str, bool] = {location: False for location in LOCATIONS}
    with torch.inference_mode():
        for index in range(len(dataset)):
            sample = dataset[index]
            metadata = sample["metadata"]
            location = metadata["location_id"]
            if location not in LOCATIONS:
                raise RuntimeError(f"Unexpected validation patch location: {location}")
            row, col = int(metadata["row"]), int(metadata["col"])
            valid_h, valid_w = int(metadata["valid_height"]), int(metadata["valid_width"])
            t1_in = sample["t1"].unsqueeze(0).to(device)
            t2_in = sample["t2"].unsqueeze(0).to(device)
            logits = align_bit_logits(model(t1_in, t2_in), (PATCH_SIZE, PATCH_SIZE))
            probability = torch.softmax(logits.float(), dim=1)[0, 1, :valid_h, :valid_w].cpu().numpy()
            saved_probability = saved_arrays[location][0]
            difference = np.abs(probability - saved_probability[row:row + valid_h, col:col + valid_w])
            reproduction_max_abs[location] = max(reproduction_max_abs[location], float(difference.max()))
            if row == 0 and col == 0:
                raw, _, _ = dataset.source.read_window(
                    location, row=0, col=0, height=valid_h, width=valid_w,
                )
                normalized = normalize_bit_dn(
                    raw, quantification_value=float(config["input"]["quantification_value"]),
                )
                normalization_verified[location] = bool(
                    torch.allclose(sample["t1"][:, :valid_h, :valid_w], normalized[0, :, :valid_h, :valid_w])
                    and torch.allclose(sample["t2"][:, :valid_h, :valid_w], normalized[1, :, :valid_h, :valid_w])
                    and metadata["bands"] == list(BIT_RGB_BANDS)
                )

    for location in LOCATIONS:
        results[location]["pipeline_reproduction"] = {
            "max_abs_probability_difference_from_saved_map": reproduction_max_abs[location],
            "normalization_and_b04_b03_b02_verified_on_first_patch": normalization_verified[location],
            "patch_size": PATCH_SIZE,
            "patch_stride": PATCH_SIZE,
            "augmentation": False,
            "aligned_logits_to_input_patch_shape": True,
        }
        if reproduction_max_abs[location] > 2e-5 or not normalization_verified[location]:
            raise RuntimeError(f"Saved prediction did not reproduce cleanly for {location}")

    loss = fine_tuned["validation_metrics"]
    analysis = {
        "scope": {"fold": 0, "locations": list(LOCATIONS), "official_test_evaluated": False},
        "threshold": THRESHOLD,
        "checkpoint": checkpoint_info,
        "saved_validation_loss_components": loss,
        "class_imbalance_context": {
            "validation_changed_fraction": summary["aggregates"]["micro"]["ground_truth_changed_percent"] / 100,
            "positive_bce_weight": float(fine_tuned["config"]["loss"]["positive_weight"]),
            "bce_weight": float(fine_tuned["config"]["loss"]["bce_weight"]),
            "dice_weight": float(fine_tuned["config"]["loss"]["dice_weight"]),
            "interpretation": "validation objective is continuous weighted BCE plus soft Dice; checkpoint selection did not optimize thresholded F1",
        },
        "locations": results,
        "diagnostic_images": {
            location: {
                "confusion_overlay": str(DIAGNOSTIC_ROOT / f"{location}_confusion_overlay.png"),
                "probability_by_truth_histogram": str(DIAGNOSTIC_ROOT / f"{location}_probability_by_truth_histogram.png"),
            }
            for location in LOCATIONS
        },
        "notes": [
            "Registered OSCD imagery has no meaningful CRS/geotransform; all alignment checks are in registered pixel coordinates.",
            "False-positive spectral summaries compare B04/B03/B02 reflectance and temporal absolute differences; they are not land-cover labels.",
            "Logit differences are reconstructed as log(p/(1-p)) because raw logits were not saved; probabilities are clipped only for finite logit summaries.",
        ],
    }
    output_path = DIAGNOSTIC_ROOT / "failure_analysis.json"
    output_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    analysis["report_path"] = str(output_path)
    return analysis


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cuda")
    args = parser.parse_args()
    print(json.dumps(analyze(args.device), indent=2))


if __name__ == "__main__":
    main()
