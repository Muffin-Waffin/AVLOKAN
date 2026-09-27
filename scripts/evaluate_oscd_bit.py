"""Evaluate the selected Fold 0 BIT checkpoint on its three validation locations only."""
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
from PIL import Image, ImageDraw

from pipeline.change_detection.bit import BITArchitecture, BIT_CHECKPOINT_SHA256
from pipeline.change_detection.bit_alignment import align_bit_logits
from pipeline.change_detection.oscd_dataset import DEFAULT_OSCD_ROOT, load_split_manifest
from pipeline.change_detection.oscd_training import (
    OSCDPatchDataset,
    load_training_config,
    make_location_folds,
    training_device,
)


FOLD0_VALIDATION = ("bercy", "mumbai", "pisa")
DEFAULT_CHECKPOINT = PROJECT_ROOT / "models/bit/BIT_OSCD_CV5/fold_0/best_oscd_bit.pt"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/processed/oscd_fold0_validation"


def _scores(tp: int, fp: int, fn: int, tn: int, total_pixels: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "predicted_changed_percent": 100.0 * (tp + fp) / total_pixels,
        "ground_truth_changed_percent": 100.0 * (tp + fn) / total_pixels,
        "total_pixels": total_pixels,
    }


def _measure(prediction: np.ndarray, target: np.ndarray) -> dict[str, float | int]:
    predicted = prediction.astype(bool, copy=False)
    truth = target.astype(bool, copy=False)
    tp = int(np.count_nonzero(predicted & truth))
    fp = int(np.count_nonzero(predicted & ~truth))
    fn = int(np.count_nonzero(~predicted & truth))
    tn = int(np.count_nonzero(~predicted & ~truth))
    return _scores(tp, fp, fn, tn, int(target.size))


def _aggregate(location_metrics: dict[str, dict[str, float | int]]) -> dict[str, dict[str, float | int]]:
    keys = ("precision", "recall", "f1", "iou")
    totals = {
        name: sum(int(metrics[name]) for metrics in location_metrics.values())
        for name in ("tp", "fp", "fn", "tn", "total_pixels")
    }
    micro = _scores(
        totals["tp"], totals["fp"], totals["fn"], totals["tn"], totals["total_pixels"],
    )
    macro = {key: float(np.mean([float(m[key]) for m in location_metrics.values()])) for key in keys}
    return {"micro": micro, "macro": macro}


def _rgb_panel(reflectance: np.ndarray, low: list[float], high: list[float]) -> Image.Image:
    # Input channel order is B04/B03/B02, which maps directly to RGB display order.
    rgb = np.stack([
        np.clip((reflectance[..., channel] - low[channel]) / (high[channel] - low[channel]), 0, 1)
        for channel in range(3)
    ], axis=-1)
    return Image.fromarray(np.round(rgb * 255).astype(np.uint8), mode="RGB")


def _binary_panel(mask: np.ndarray) -> Image.Image:
    gray = (mask.astype(np.uint8) * 255)
    return Image.fromarray(np.repeat(gray[..., None], 3, axis=-1), mode="RGB")


def _probability_panel(probability: np.ndarray) -> tuple[Image.Image, float]:
    stretch = max(float(np.percentile(probability, 99.5)), 1e-8)
    scaled = np.clip(probability / stretch, 0, 1)
    # A fixed dark-blue -> cyan -> yellow diagnostic ramp; the p99.5 stretch is display-only.
    stops = np.array([[12, 20, 65], [20, 190, 210], [255, 235, 55]], dtype=np.float32)
    position = scaled * 2
    lower = np.minimum(position.astype(np.int32), 1)
    fraction = (position - lower)[..., None]
    color = stops[lower] * (1 - fraction) + stops[lower + 1] * fraction
    return Image.fromarray(np.round(color).astype(np.uint8), mode="RGB"), stretch


def _save_panel(
    output: Path,
    t1_reflectance: np.ndarray,
    t2_reflectance: np.ndarray,
    target: np.ndarray,
    probability: np.ndarray,
    prediction: np.ndarray,
) -> None:
    low, high = [], []
    for channel in range(3):
        pair_values = np.concatenate((
            t1_reflectance[..., channel].ravel(), t2_reflectance[..., channel].ravel(),
        ))
        lo, hi = np.percentile(pair_values, (2, 98)).astype(float)
        if hi <= lo:
            hi = lo + 1e-6
        low.append(lo)
        high.append(hi)
    probability_image, stretch = _probability_panel(probability)
    panels = [
        ("T1 | B04/B03/B02, shared 2-98% stretch", _rgb_panel(t1_reflectance, low, high)),
        ("T2 | B04/B03/B02, shared 2-98% stretch", _rgb_panel(t2_reflectance, low, high)),
        ("Ground truth | white = change", _binary_panel(target)),
        (f"Probability | display p99.5={stretch:.4g}", probability_image),
        ("Prediction | threshold 0.50", _binary_panel(prediction)),
    ]
    width, height = panels[0][1].size
    header = 30
    canvas = Image.new("RGB", (width * 3, (height + header) * 2), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (label, image) in enumerate(panels):
        col, row = index % 3, index // 3
        x, y = col * width, row * (height + header)
        draw.text((x + 8, y + 7), label, fill="black")
        canvas.paste(image, (x, y + header))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def _write_geotiff(path: Path, array: np.ndarray, reference: Path, *, dtype: str, predictor: int) -> None:
    with rasterio.open(reference) as source:
        profile = source.profile.copy()
    profile.update(
        driver="GTiff", count=1, dtype=dtype, nodata=None,
        compress="deflate", predictor=predictor,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as destination:
        destination.write(array.astype(dtype, copy=False), 1)
        destination.update_tags(
            spatial_reference_note="OSCD registered pixel grid; source TIFF has no meaningful CRS/geotransform",
        )


def evaluate(
    checkpoint_path: Path = DEFAULT_CHECKPOINT,
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    threshold: float = 0.5,
    device_name: str = "auto",
) -> dict:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    checkpoint_path = checkpoint_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty evaluation output directory: {output_dir}")
    container = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = container.get("config")
    if not isinstance(config, dict) or config.get("cross_validation", {}).get("fold") != 0:
        raise ValueError("Checkpoint metadata does not identify the requested Fold 0 run")
    if container.get("base_checkpoint_sha256") != BIT_CHECKPOINT_SHA256:
        raise ValueError("Fine-tuned checkpoint does not record the verified official BIT LEVIR base checkpoint")
    if container.get("epoch") is None or not isinstance(container.get("validation_metrics"), dict):
        raise ValueError("Checkpoint is missing its saved epoch/validation selection record")

    manifest = load_split_manifest(config["data"]["root"], config["data"]["splits"])
    folds = make_location_folds(
        manifest["official_train"], manifest["test"],
        n_splits=int(config["cross_validation"]["n_splits"]),
        seed=int(config["cross_validation"]["seed"]),
    )
    validation_locations = tuple(folds[0]["validation"])
    if validation_locations != FOLD0_VALIDATION:
        raise RuntimeError(f"Fold 0 roster differs from requested validation locations: {validation_locations}")
    if set(validation_locations) & set(manifest["test"]):
        raise RuntimeError("Official test location found in Fold 0 validation roster")

    device = training_device(device_name)
    model = BITArchitecture()
    model.load_state_dict(container["model_state_dict"], strict=True)
    model.eval().to(device)

    patch = config["patch"]
    dataset = OSCDPatchDataset(
        split="validation",
        locations=list(validation_locations),
        patch_size=int(patch["patch_size"]),
        patch_stride=int(patch.get("validation_stride", patch["patch_size"])),
        quantification_value=float(config["input"]["quantification_value"]),
        augmentation=False,
        seed=int(config["training"]["seed"]),
        root=config["data"]["root"],
        splits_path=config["data"]["splits"],
    )

    scenes: dict[str, dict[str, np.ndarray | Path]] = {}
    with torch.inference_mode():
        for index in range(len(dataset)):
            sample = dataset[index]
            metadata = sample["metadata"]
            location = metadata["location_id"]
            if location not in FOLD0_VALIDATION:
                raise RuntimeError(f"Unexpected location reached evaluator: {location}")
            if location not in scenes:
                reference = Path(config["data"]["root"]) / "Onera Satellite Change Detection dataset - Images" / location / "imgs_1_rect" / "B04.tif"
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
            probability = torch.softmax(logits.float(), dim=1)[0, 1, :valid_h, :valid_w].cpu().numpy()
            scene = scenes[location]
            destination = np.s_[row:row + valid_h, col:col + valid_w]
            if np.isfinite(scene["probability"][destination]).any():
                raise RuntimeError(f"Patch overlap found while building non-overlapping evaluation map: {location}")
            scene["probability"][destination] = probability
            scene["target"][destination] = sample["target"][:valid_h, :valid_w].numpy().astype(np.uint8)
            scene["t1"][destination] = ((sample["t1"][:, :valid_h, :valid_w].permute(1, 2, 0).numpy() + 1) / 2)
            scene["t2"][destination] = ((sample["t2"][:, :valid_h, :valid_w].permute(1, 2, 0).numpy() + 1) / 2)

    if set(scenes) != set(FOLD0_VALIDATION):
        raise RuntimeError(f"Evaluator did not produce exactly the Fold 0 validation locations: {sorted(scenes)}")

    per_location: dict[str, dict[str, float | int]] = {}
    diagnostics: dict[str, dict] = {}
    artifacts: dict[str, dict[str, str]] = {}
    diagnostic_thresholds = (0.25, 0.5, 0.75)
    for location in FOLD0_VALIDATION:
        scene = scenes[location]
        probability = scene["probability"]
        target = scene["target"]
        if not np.isfinite(probability).all():
            raise RuntimeError(f"Probability map has unfilled/non-finite pixels: {location}")
        prediction = (probability >= threshold).astype(np.uint8)
        per_location[location] = _measure(prediction, target)
        diagnostics[location] = {
            f"{value:.2f}": _measure((probability >= value).astype(np.uint8), target)
            for value in diagnostic_thresholds
        }

        loc_dir = output_dir / location
        loc_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "probability": loc_dir / f"{location}_probability.tif",
            "prediction": loc_dir / f"{location}_prediction_threshold_{threshold:.2f}.tif",
            "ground_truth": loc_dir / f"{location}_ground_truth.tif",
            "panel": loc_dir / f"{location}_panel.png",
        }
        reference = scene["reference"]
        _write_geotiff(paths["probability"], probability, reference, dtype="float32", predictor=3)
        _write_geotiff(paths["prediction"], prediction, reference, dtype="uint8", predictor=2)
        _write_geotiff(paths["ground_truth"], target, reference, dtype="uint8", predictor=2)
        _save_panel(paths["panel"], scene["t1"], scene["t2"], target, probability, prediction)
        artifacts[location] = {key: str(value) for key, value in paths.items()}

    output = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        "base_checkpoint_sha256": container["base_checkpoint_sha256"],
        "epoch": int(container["epoch"]),
        "saved_validation_metrics": container["validation_metrics"],
        "fold": 0,
        "locations": list(FOLD0_VALIDATION),
        "threshold": threshold,
        "threshold_convention": "change probability >= threshold",
        "evaluation_device": str(device),
        "per_location": per_location,
        "aggregates": _aggregate(per_location),
        "threshold_diagnostics": diagnostics,
        "artifacts": artifacts,
        "official_test_evaluated": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    output["metrics_path"] = str(metrics_path)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    print(json.dumps(evaluate(
        args.checkpoint, args.output_dir, threshold=args.threshold, device_name=args.device,
    ), indent=2))


if __name__ == "__main__":
    main()
