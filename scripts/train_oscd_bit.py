"""Train BIT on one development OSCD location-CV fold, or run one dry-run step."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.change_detection.oscd_training import dry_run, load_training_config, train


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/oscd_bit_training.yaml")
    parser.add_argument("--checkpoint", type=Path, help="Override only the verified base BIT checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Run one forward/backward/optimizer step, no epoch training")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), help="Override configured device selection")
    parser.add_argument("--fold", type=int, choices=range(5), help="Override the configured 0-based CV fold")
    args = parser.parse_args()
    config = load_training_config(args.config)
    if args.fold is not None:
        config["cross_validation"]["fold"] = args.fold
    if args.dry_run:
        print(json.dumps(dry_run(config, checkpoint=args.checkpoint, device=args.device), indent=2, default=str))
    else:
        train(config, checkpoint=args.checkpoint, device=args.device)


if __name__ == "__main__":
    main()
