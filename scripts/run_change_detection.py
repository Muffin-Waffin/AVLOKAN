"""Run BIT change inference for two aligned Sentinel-2 reflectance GeoTIFFs."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.change_detection.inference import run_change_detection
from pipeline.change_detection.temporal_pair import TemporalPair


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t1", type=Path, required=True)
    parser.add_argument("--t2", type=Path, required=True)
    parser.add_argument("--t1-date", required=True, help="ISO acquisition date/time for T1")
    parser.add_argument("--t2-date", required=True, help="ISO acquisition date/time for T2")
    parser.add_argument(
        "--preserve-input-order", action="store_true",
        help="allow T1 to be later than T2 while retaining the supplied raster roles",
    )
    parser.add_argument("--probability", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=Path("models/bit/BIT_LEVIR/best_ckpt.pt"))
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    pair = TemporalPair.from_paths(
        tile_id="phase6-validation", t1_path=args.t1, t2_path=args.t2,
        t1_date=args.t1_date, t2_date=args.t2_date,
        allow_reversed_dates=args.preserve_input_order,
    )
    outputs = run_change_detection(
        pair, args.probability, args.mask,
        checkpoint_path=args.checkpoint, threshold=args.threshold, device=args.device,
    )
    print(f"Probability GeoTIFF: {outputs[0]}")
    print(f"Binary mask GeoTIFF: {outputs[1]}")


if __name__ == "__main__":
    main()
