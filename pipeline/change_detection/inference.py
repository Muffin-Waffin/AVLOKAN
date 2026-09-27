"""Windowed BIT inference and georeferenced probability/mask output writing."""
from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np
import rasterio
import torch
from rasterio.windows import Window

from pipeline.change_detection.bit import BITDetector
from pipeline.change_detection.preprocessing import BIT_INPUT_SIZE, read_model_tensor
from pipeline.change_detection.temporal_pair import TemporalPair


def infer_pair_arrays(pair: TemporalPair, detector: BITDetector) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Run the shared bounded-window inference path and return aligned probability/validity arrays."""
    probability = np.zeros((pair.height, pair.width), dtype=np.float32)
    valid_grid = np.zeros((pair.height, pair.width), dtype=bool)
    timings = {"preprocessing": 0.0, "inference": 0.0}
    for row in range(0, pair.height, BIT_INPUT_SIZE):
        for col in range(0, pair.width, BIT_INPUT_SIZE):
            window = Window(col, row, BIT_INPUT_SIZE, BIT_INPUT_SIZE)
            prep_started = perf_counter()
            first, valid1 = read_model_tensor(pair.t1_path, window)
            second, valid2 = read_model_tensor(pair.t2_path, window)
            valid = valid1 & valid2
            timings["preprocessing"] += perf_counter() - prep_started
            inference_started = perf_counter()
            result = detector.predict(
                first, second, threshold=0.5, target_shape=(BIT_INPUT_SIZE, BIT_INPUT_SIZE),
            )
            values = result["probability"][0].cpu().numpy().astype(np.float32)
            timings["inference"] += perf_counter() - inference_started
            if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
                raise RuntimeError(f"BIT produced invalid probabilities for {pair.pair_id} at row={row}, col={col}")
            values[~valid] = 0.0
            out_h = min(BIT_INPUT_SIZE, pair.height - row)
            out_w = min(BIT_INPUT_SIZE, pair.width - col)
            probability[row:row + out_h, col:col + out_w] = values[:out_h, :out_w]
            valid_grid[row:row + out_h, col:col + out_w] = valid[:out_h, :out_w]
    return probability, valid_grid, timings


def run_change_detection(
    pair: TemporalPair,
    probability_path: str | Path,
    mask_path: str | Path,
    *,
    checkpoint_path: str | Path,
    threshold: float = 0.5,
    device: str = "cpu",
) -> tuple[Path, Path]:
    """Run BIT for a pair and save aligned probability and threshold mask GeoTIFFs."""
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and within [0, 1]")
    probability_path, mask_path = Path(probability_path), Path(mask_path)
    if probability_path.resolve() == mask_path.resolve():
        raise ValueError("Probability and mask outputs must be different files")
    probability_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    detector = BITDetector(checkpoint_path, device=device)
    probability, valid, _ = infer_pair_arrays(pair, detector)
    mask = (probability >= threshold).astype(np.uint8)
    mask[~valid] = 0

    with rasterio.open(pair.t1_path) as source:
        probability_profile = source.profile.copy()
        probability_profile.update(count=1, dtype="float32", nodata=None, compress="deflate", predictor=3)
    mask_profile = probability_profile.copy()
    mask_profile.update(dtype="uint8", predictor=2)
    with rasterio.open(probability_path, "w", **probability_profile) as dst:
        dst.write(probability, 1)
        dst.update_tags(model=detector.checkpoint_path.name,
                        checkpoint_sha256=detector.checkpoint_sha256,
                        pair_id=pair.pair_id, product="change_probability",
                        probability_semantics="softmax change-class probability")
    with rasterio.open(mask_path, "w", **mask_profile) as dst:
        dst.write(mask, 1)
        dst.update_tags(pair_id=pair.pair_id, threshold=str(threshold),
                        product="binary_change_mask", values="0=no change, 1=change")
    return probability_path, mask_path
