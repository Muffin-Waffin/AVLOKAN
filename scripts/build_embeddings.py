from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import numpy as np

from pipeline.embeddings.cache import EmbeddingCache
from pipeline.embeddings.image_encoder import ImageEncoder
from pipeline.embeddings.remoteclip import CHECKPOINT_NAME, MODEL_NAME, RemoteCLIPAdapter
from pipeline.indexing.incremental_index import IncrementalIndex
from pipeline.indexing.tile_catalog import TileCatalog


def source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed catalogued Phase 2 Sentinel-2 tiles and index them.")
    parser.add_argument("--input", default="data/processed/phase2_validation/tiles/s2_demo")
    parser.add_argument("--catalog", default="data/catalog/tiles.json")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--checkpoint", default=f"models/remoteclip/{CHECKPOINT_NAME}")
    parser.add_argument("--embedding-dir", default="data/embeddings")
    parser.add_argument("--index", default="data/index/remoteclip_vit_b32.index")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be greater than zero")

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        parser.error(f"input tile directory does not exist: {input_dir}")
    tile_paths = sorted(path for path in input_dir.rglob("*")
                         if path.is_file() and path.suffix.lower() in {".tif", ".tiff"})
    if not tile_paths:
        parser.error(f"no GeoTIFF tiles found under {input_dir}")

    catalog = TileCatalog(args.catalog)
    by_path = {Path(item.tile_path).resolve(): item for item in catalog.list_tiles()}
    tile_records = []
    failures: list[dict[str, str]] = []
    for tile_path in tile_paths:
        record = by_path.get(tile_path.resolve())
        if record is None:
            failures.append({"path": str(tile_path), "error": "tile is absent from the Phase 3 catalog"})
        elif record.sensor and record.sensor.lower() != "sentinel-2":
            failures.append({"path": str(tile_path), "error": f"unsupported sensor: {record.sensor}"})
        else:
            tile_records.append((record, tile_path))
    if not tile_records:
        raise RuntimeError("No input tiles resolved to catalogued Sentinel-2 records")

    load_started = time.perf_counter()
    adapter = RemoteCLIPAdapter(args.checkpoint, device=args.device, fp16=True)
    actual_device = str(adapter.device)
    model_load_seconds = time.perf_counter() - load_started
    image_encoder = ImageEncoder(adapter)
    cache = EmbeddingCache(args.embedding_dir, MODEL_NAME)
    embeddings: dict[str, np.ndarray] = {}
    missing = []
    newly_computed: set[str] = set()
    for record, path in tile_records:
        fingerprint = source_fingerprint(path)
        cached = cache.get(record.tile_id, adapter.model_version,
                           expected_dimension=adapter.embedding_dim,
                           source_fingerprint=fingerprint)
        if cached is None:
            missing.append((record, path, fingerprint))
        else:
            embeddings[record.tile_id] = cached

    encode_wall_started = time.perf_counter()
    for start in range(0, len(missing), args.batch_size):
        batch = missing[start:start + args.batch_size]
        try:
            vectors = image_encoder.encode_images([path for _, path, _ in batch], args.batch_size)
            if vectors.shape[0] != len(batch) or vectors.shape[1] != adapter.embedding_dim:
                raise RuntimeError(f"unexpected embedding array shape: {vectors.shape}")
            for (record, path, fingerprint), vector in zip(batch, vectors):
                cache.put(record.tile_id, adapter.model_version, vector,
                          source_fingerprint=fingerprint)
                embeddings[record.tile_id] = vector
                newly_computed.add(record.tile_id)
        except Exception as exc:
            failures.extend({"path": str(path), "error": str(exc)} for _, path, _ in batch)
    encode_wall_seconds = time.perf_counter() - encode_wall_started

    if not embeddings:
        raise RuntimeError(f"No embeddings were produced. Failures: {failures}")
    dimension = int(next(iter(embeddings.values())).shape[0])
    index = IncrementalIndex(args.index, dimension=dimension)
    to_add = [(record.tile_id, embeddings[record.tile_id]) for record, _ in tile_records
              if record.tile_id in embeddings and not index.contains(record.tile_id)]
    if to_add:
        index.add_embeddings(np.stack([vector for _, vector in to_add]),
                             [tile_id for tile_id, _ in to_add])

    report = {
        "model": MODEL_NAME,
        "checkpoint": str(Path(args.checkpoint)),
        "checkpoint_sha256": adapter.model_version,
        "embedding_dimension": dimension,
        "device": actual_device,
        "fp16": adapter.fp16,
        "batch_size": args.batch_size,
        "discovered_tiles": len(tile_paths),
        "catalogued_tiles": len(tile_records),
        "real_embeddings_available": len(embeddings),
        "new_embeddings_computed": len(newly_computed),
        "cache_hits": len(tile_records) - len(missing),
        "new_vectors_added_to_index": len(to_add),
        "faiss_index_size": index.size(),
        "model_load_seconds": round(model_load_seconds, 4),
        "tile_read_seconds": round(image_encoder.tile_read_seconds, 4),
        "model_preprocessing_seconds": round(adapter.preprocessing_seconds, 4),
        "inference_seconds": round(adapter.inference_seconds, 4),
        "embedding_wall_seconds": round(encode_wall_seconds, 4),
        "total_seconds": round(time.perf_counter() - load_started, 4),
        "failures": failures,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
