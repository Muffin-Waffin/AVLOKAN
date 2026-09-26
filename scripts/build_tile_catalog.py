from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import time

from pipeline.indexing.catalog_builder import build_tile_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or update the local AVLOKAN tile catalog.")
    parser.add_argument("--input", default="data/processed/tiles", help="Directory containing tile GeoTIFFs")
    parser.add_argument("--output", default="data/catalog/tiles.json", help="Output JSON catalog path")
    args = parser.parse_args()

    started = time.perf_counter()
    report = build_tile_catalog(args.input, args.output)
    result = asdict(report)
    result.update(output=args.output, elapsed_seconds=round(time.perf_counter() - started, 4))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
