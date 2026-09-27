"""Create Sentinel-2 NDVI T1/T2 and signed ΔNDVI GeoTIFF products."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio

from pipeline.change_detection.ndvi import compute_temporal_ndvi
from pipeline.change_detection.temporal_pair import TemporalPair


def _report(path: Path, name: str) -> np.ndarray:
    with rasterio.open(path) as src:
        values = src.read(1, masked=True)
    finite = np.asarray(values.compressed(), dtype=np.float64)
    invalid = int(values.size - finite.size)
    print(f"{name}: {path}")
    print(f"  finite_pixels={finite.size} invalid_pixels={invalid}")
    if finite.size:
        print(
            f"  min={finite.min():.7f} max={finite.max():.7f} "
            f"mean={finite.mean():.7f} median={np.median(finite):.7f}"
        )
    return finite


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t1", type=Path, required=True)
    parser.add_argument("--t2", type=Path, required=True)
    parser.add_argument("--t1-date", required=True)
    parser.add_argument("--t2-date", required=True)
    parser.add_argument("--preserve-input-order", action="store_true")
    parser.add_argument("--ndvi-t1", type=Path, required=True)
    parser.add_argument("--ndvi-t2", type=Path, required=True)
    parser.add_argument("--delta", type=Path, required=True)
    args = parser.parse_args()
    pair = TemporalPair.from_paths(
        tile_id="phase6-validation", t1_path=args.t1, t2_path=args.t2,
        t1_date=args.t1_date, t2_date=args.t2_date,
        allow_reversed_dates=args.preserve_input_order,
    )
    outputs = compute_temporal_ndvi(
        pair.t1_path, pair.t2_path, args.ndvi_t1, args.ndvi_t2, args.delta,
    )
    print(f"Input order: T1={pair.t1_date.date()} then T2={pair.t2_date.date()}")
    if pair.t1_date > pair.t2_date:
        print("Dates are reverse chronological; input roles are preserved.")
    print("Delta convention: Delta NDVI = NDVI_T2 - NDVI_T1 (negative=decrease, positive=increase).")
    _report(outputs[0], "NDVI_T1")
    _report(outputs[1], "NDVI_T2")
    delta = _report(outputs[2], "Delta_NDVI")
    if delta.size:
        denominator = delta.size
        print(f"  decrease (delta < 0): {(delta < 0).sum() / denominator * 100:.3f}%")
        print(f"  increase (delta > 0): {(delta > 0).sum() / denominator * 100:.3f}%")
        print("  exploratory absolute-change shares (not calibrated thresholds):")
        for cutoff in (0.05, 0.10, 0.20):
            print(
                f"    |delta| >= {cutoff:.2f}: "
                f"decrease={(delta <= -cutoff).sum() / denominator * 100:.3f}% "
                f"increase={(delta >= cutoff).sum() / denominator * 100:.3f}%"
            )


if __name__ == "__main__":
    main()
