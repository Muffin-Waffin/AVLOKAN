"""Run the configured AVLOKAN change-analysis prototype on a raster pair."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.change_detection.analyzer import ChangeAnalysisConfig, ChangeAnalyzer
from pipeline.change_detection.temporal_pair import TemporalPair


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t1", type=Path, required=True)
    parser.add_argument("--t2", type=Path, required=True)
    parser.add_argument("--t1-date", required=True)
    parser.add_argument("--t2-date", required=True)
    parser.add_argument("--tile-id", default="change-analysis-input")
    parser.add_argument("--pair-id")
    parser.add_argument("--sensor", default="sentinel-2")
    parser.add_argument("--preserve-input-order", action="store_true")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/change_detection.yaml")
    parser.add_argument("--checkpoint", type=Path, help="Explicit local BIT checkpoint override")
    parser.add_argument("--output", type=Path, help="Override the configured output directory")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--show-candidates", action="store_true", help="Print every ranked change candidate")
    args = parser.parse_args()

    config = ChangeAnalysisConfig.load(args.config, checkpoint=args.checkpoint)
    if args.output is not None or args.device is not None:
        from dataclasses import replace
        config = replace(config,
                         output_directory=args.output or config.output_directory,
                         device=args.device or config.device)
        config.validate()
    pair = TemporalPair.from_paths(
        tile_id=args.tile_id, pair_id=args.pair_id, t1_path=args.t1, t2_path=args.t2,
        t1_date=args.t1_date, t2_date=args.t2_date, sensor=args.sensor,
        allow_reversed_dates=args.preserve_input_order,
    )
    result = ChangeAnalyzer(config).analyze(pair)
    stats = result.statistics
    print("AVLOKAN Change Analysis")
    print("-----------------------")
    print(f"T1: {pair.t1_path}")
    print(f"T2: {pair.t2_path}")
    print(f"Sensor: {result.sensor}")
    print(f"Model: {result.model_name}")
    print(f"Checkpoint: {result.checkpoint_path}")
    print(f"Threshold: {result.threshold:.2f}")
    print(f"Valid pixels: {stats['valid_pixels']}")
    print(f"Changed pixels: {stats['changed_pixels']}")
    print(f"Changed fraction: {stats['changed_pixel_fraction']:.6f}")
    print(f"Components: {stats['connected_component_count']}")
    print(f"Largest component: {stats['largest_component_pixels']}")
    filtering = result.filtering_statistics
    print("Change Candidates")
    print("-----------------")
    print(f"Raw components: {filtering['raw_component_count']}")
    print(f"Retained: {filtering['components_retained']}")
    print(f"Removed: {filtering['components_removed']}")
    for item in result.candidates:
        if not item["retained"]:
            continue
        if not args.show_candidates and item["rank"] > 3:
            continue
        print(f"#{item['rank']} area={item['area_pixels']} mean_probability={item['mean_probability']:.4f} "
              f"candidate_score={item['candidate_score']:.4f} bbox={item['bbox_pixels']}")
    print(f"Timings (s): {result.timings_seconds}")
    print(f"Probability: {result.probability_raster}")
    print(f"Raw mask: {result.raw_mask_raster}")
    print(f"Final mask: {result.final_mask_raster}")
    print(f"Metadata: {result.metadata_path}")


if __name__ == "__main__":
    main()
