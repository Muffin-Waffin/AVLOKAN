"""Build an inspection-only inventory of an already staged S2MTCP release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.change_detection.bitemporal_data import inventory_s2mtcp_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True, help="Official S2MTCP metadata CSV")
    parser.add_argument("--array-root", type=Path, help="Directory containing referenced .npy arrays")
    parser.add_argument("--output", type=Path, required=True, help="New JSON inventory output path")
    args = parser.parse_args()
    result = inventory_s2mtcp_metadata(args.metadata, array_root=args.array_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    existing = sum(record["exists"] for pair in result["records"] for record in pair["pair_images_a_b"])
    print(json.dumps({"samples": result["sample_count"], "arrays_present": existing,
                      "inventory": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
