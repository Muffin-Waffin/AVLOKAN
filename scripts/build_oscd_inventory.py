"""Validate staged OSCD files and write a project-relative JSON inventory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.change_detection.oscd_dataset import (
    DEFAULT_OSCD_ROOT,
    DEFAULT_SPLITS_PATH,
    build_oscd_inventory,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_OSCD_ROOT)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS_PATH)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/oscd/inventory.json")
    args = parser.parse_args()
    inventory = build_oscd_inventory(args.root, args.splits)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"Inventory: {args.output}")
    print(f"Locations: {len(inventory['locations'])}")
    print(f"Splits: {inventory['counts']}")


if __name__ == "__main__":
    main()
