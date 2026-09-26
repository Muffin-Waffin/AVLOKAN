from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import time

import numpy as np
import yaml

from pipeline.embeddings.remoteclip import CHECKPOINT_NAME, RemoteCLIPAdapter
from pipeline.indexing.incremental_index import IncrementalIndex
from pipeline.indexing.tile_catalog import TileCatalog
from pipeline.retrieval.retriever import Retriever


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search AVLOKAN's local satellite tile index.")
    subparsers = parser.add_subparsers(dest="kind", required=True)
    for kind in ("text", "image"):
        sub = subparsers.add_parser(kind)
        sub.add_argument("query", help="text prompt or path to a Phase 2 GeoTIFF tile")
        sub.add_argument("--top-k", type=int, default=5)
        sub.add_argument("--sensor")
        sub.add_argument("--date-from")
        sub.add_argument("--date-to")
        sub.add_argument("--bbox", nargs=4, type=float, metavar=("MIN_X", "MIN_Y", "MAX_X", "MAX_Y"))
        sub.add_argument("--exclude-query-tile", action="store_true",
                         help="exclude the indexed tile when the image query matches a catalog path")
        sub.add_argument("--repeat", type=int, default=1,
                         help="repeat the same query for a small latency diagnostic")
        sub.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
        sub.add_argument("--checkpoint", default=f"models/remoteclip/{CHECKPOINT_NAME}")
        sub.add_argument("--config", default="configs/embeddings.yaml")
    return parser


def _load_paths(config_path: str) -> dict:
    with Path(config_path).open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    return config["paths"]


def _run(retriever: Retriever, args) -> dict:
    options = {
        "top_k": args.top_k,
        "sensor": args.sensor,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "bbox": args.bbox,
    }
    if args.kind == "text":
        return retriever.search_text(args.query, **options)
    return retriever.search_image(args.query, exclude_query_tile=args.exclude_query_tile, **options)


def _print_report(report: dict, args, model_load_ms: float, benchmark: list[float]) -> None:
    print("=" * 60)
    print("AVLOKAN SEMANTIC SEARCH")
    print("=" * 60)
    print(f"Query:\n{args.query}")
    print(f"\nType:\n{report['query_type']}")
    if report.get("query_tile_id"):
        print(f"\nQuery tile: {report['query_tile_id']}" +
              (" (excluded from results)" if report["query_tile_excluded"] else ""))
    print("\nResults:")
    if not report["results"]:
        print("No indexed tiles matched the query and filters.")
    for item in report["results"]:
        tag = " [QUERY TILE]" if item["is_query_tile"] else ""
        resolution = " × ".join(f"{abs(value):g}" for value in item["resolution"])
        date_value = item["acquisition_datetime"] or "unknown"
        print(f"\n#{item['rank']}{tag}")
        print(f"Tile ID: {item['tile_id']}")
        print(f"Similarity: {item['score']:.4f}")
        print(f"Sensor: {item['sensor'] or 'unknown'}")
        print(f"Date: {date_value}")
        print(f"Resolution: {resolution} m")
        print(f"Bounds ({item['crs']}): {item['bounds']}")
        print(f"Path: {item['path']}")

    timings = report["timings"]
    print("\nTimings:")
    print(f"Model load: {model_load_ms:.1f} ms (once per process)")
    print(f"Query embedding: {timings['query_embedding_ms']:.3f} ms")
    if report["query_type"] == "image":
        print(f"Image preprocessing/read (included above): {timings['image_preprocessing_ms']:.3f} ms")
    print(f"FAISS search: {timings['faiss_search_ms']:.3f} ms")
    print(f"Metadata lookup/filter: {timings['metadata_lookup_ms']:.3f} ms")
    print(f"Total retrieval: {timings['total_ms']:.3f} ms")
    scores = report["diagnostics"]["score_distribution"]
    if scores:
        print(f"Score distribution (returned results): min={scores['min']:.4f}, "
              f"mean={scores['mean']:.4f}, max={scores['max']:.4f}")
    print(f"Candidates: {report['diagnostics']['indexed_eligible_tiles']} indexed / "
          f"{report['diagnostics']['eligible_catalog_tiles']} eligible catalog tiles")
    if len(benchmark) > 1:
        print(f"\nPrototype-scale benchmark ({len(benchmark)} repeated queries; not an accuracy metric):")
        print(f"Total retrieval mean: {statistics.mean(benchmark):.3f} ms")
        print(f"Total retrieval median: {statistics.median(benchmark):.3f} ms")
        print(f"Total retrieval p95: {float(np.percentile(benchmark, 95)):.3f} ms")
    print("=" * 60)


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    if args.top_k <= 0:
        parser.error("--top-k must be greater than zero")
    if args.repeat <= 0:
        parser.error("--repeat must be greater than zero")
    if args.kind == "text" and not args.query.strip():
        parser.error("text query must not be empty")
    if args.kind == "image" and not Path(args.query).is_file():
        parser.error(f"query image does not exist: {args.query}")
    try:
        paths = _load_paths(args.config)
        started = time.perf_counter()
        model = RemoteCLIPAdapter(args.checkpoint, device=args.device)
        model_load_ms = (time.perf_counter() - started) * 1000
        index = IncrementalIndex(paths["index"])
        retriever = Retriever(model, index, TileCatalog(paths["catalog"]))
        report = _run(retriever, args)
        benchmark = [report["timings"]["total_ms"]]
        for _ in range(1, args.repeat):
            repeated = _run(retriever, args)
            benchmark.append(repeated["timings"]["total_ms"])
        _print_report(report, args, model_load_ms, benchmark)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
