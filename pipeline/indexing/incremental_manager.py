"""Incremental indexing manager for real staged scene ingestion without full index rebuild."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from time import perf_counter
from typing import Any

import numpy as np

from pipeline.indexing.incremental_index import IncrementalIndex
from pipeline.indexing.tile_catalog import TileCatalog, TileMetadata
from pipeline.preprocessing.tiling import tile_raster


ROOT = Path(__file__).resolve().parents[2]

STAGED_DIR = ROOT / "data" / "processed" / "staged_tiles"
STAGED_SOURCE = ROOT / "data" / "processed" / "phase6_validation" / "s2_20250324_512.tif"
STAGED_TILE_REL_PATH = "data/processed/staged_tiles/s2_20250324/tile_000000.tif"
STAGED_TILE_ID = "s2_20250324__tile_000000"
STAGED_SCENE_ID = "S2B_MSIL2A_20250324T052649_N0511_R105_T43QEF_20250324T074123"
BACKUP_DIR = ROOT / "data" / "index" / "baseline_backup"


def ensure_staged_tile() -> Path:
    """Ensure the staged local tile raster exists on disk."""
    staged_path = ROOT / STAGED_TILE_REL_PATH
    if staged_path.is_file():
        return staged_path

    if not STAGED_SOURCE.is_file():
        raise FileNotFoundError(f"Staged source raster missing: {STAGED_SOURCE}")

    tile_raster(
        input_path=STAGED_SOURCE,
        output_dir=STAGED_DIR,
        tile_size=256,
        scene="s2_20250324",
        acquisition_date="2025-03-24",
        sensor="sentinel-2",
    )
    if not staged_path.is_file():
        raise RuntimeError(f"Failed to generate staged tile: {staged_path}")
    return staged_path


def get_staged_tile_metadata() -> TileMetadata:
    """Return metadata for the staged scene tile."""
    return TileMetadata(
        tile_id=STAGED_TILE_ID,
        source_scene_id=STAGED_SCENE_ID,
        sensor="sentinel-2",
        acquisition_datetime="2025-03-24T05:26:49.024Z",
        tile_path=STAGED_TILE_REL_PATH,
        width=256,
        height=256,
        crs="EPSG:32643",
        resolution=(10.0, 10.0),
        bounds=(582100.0, 2519110.0, 584660.0, 2521670.0),
        transform=(10.0, 0.0, 582100.0, 0.0, -10.0, 2521670.0),
        band_count=4,
        dtype="float32",
        valid_fraction=1.0,
        parent_scene_path="data/processed/phase6_validation/s2_20250324_512.tif",
    )


def ensure_baseline_backup(index_path: Path, mapping_path: Path, catalog_path: Path) -> None:
    """Save baseline backup of the index and catalog if not present."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    b_idx = BACKUP_DIR / index_path.name
    b_map = BACKUP_DIR / mapping_path.name
    b_cat = BACKUP_DIR / catalog_path.name

    if not b_idx.exists() and index_path.exists():
        shutil.copy2(index_path, b_idx)
    if not b_map.exists() and mapping_path.exists():
        shutil.copy2(mapping_path, b_map)
    if not b_cat.exists() and catalog_path.exists():
        shutil.copy2(catalog_path, b_cat)


def get_incremental_status(index: IncrementalIndex, catalog: TileCatalog) -> dict[str, Any]:
    """Report current indexing state and staged scene availability."""
    ensure_staged_tile()
    is_indexed = index.contains(STAGED_TILE_ID)
    staged_meta = get_staged_tile_metadata()

    return {
        "indexed_count": index.size(),
        "catalog_count": len(catalog.list_tiles()),
        "staged_scene": {
            "tile_id": staged_meta.tile_id,
            "scene_id": staged_meta.source_scene_id,
            "sensor": "Sentinel-2",
            "date": "2025-03-24",
            "region": "Indore Prototype (T1 observation)",
            "local_path": staged_meta.tile_path,
            "is_indexed": is_indexed,
            "resolution": "10 m",
            "bounds": list(staged_meta.bounds),
        },
    }


def perform_incremental_ingest(
    index: IncrementalIndex,
    catalog: TileCatalog,
    encoder,
    retriever=None,
) -> dict[str, Any]:
    """Incrementally ingest the staged scene into FAISS and TileCatalog without index rebuild."""
    tile_path = ensure_staged_tile()
    metadata = get_staged_tile_metadata()

    count_before = index.size()
    if index.contains(metadata.tile_id):
        return {
            "status": "already_indexed",
            "message": f"Scene {metadata.tile_id} is already in the index.",
            "count_before": count_before,
            "count_after": count_before,
            "tile_id": metadata.tile_id,
            "rebuild_performed": False,
        }

    started = perf_counter()

    # 1. Compute real embedding with RemoteCLIP
    embedding = encoder.encode_image(tile_path)
    if embedding.ndim == 1:
        embedding = embedding.reshape(1, -1)

    # 2. Add embedding to FAISS index directly (appends to IndexIDMap2, saves to disk)
    index.add_embeddings(embedding, [metadata.tile_id])

    # 3. Upsert metadata to TileCatalog and persist
    catalog.upsert_many([metadata])

    # 4. If an in-memory retriever is active, ensure its internal structures reflect the update
    if retriever is not None:
        retriever.faiss_index = index
        retriever.catalog = catalog

    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    count_after = index.size()

    return {
        "status": "success",
        "tile_id": metadata.tile_id,
        "source_scene": metadata.source_scene_id,
        "count_before": count_before,
        "count_after": count_after,
        "added_count": count_after - count_before,
        "rebuild_performed": False,
        "vector_dimension": int(embedding.shape[1]),
        "elapsed_ms": elapsed_ms,
        "persistence": "FAISS IndexIDMap2 and catalog JSON updated on disk",
    }


def reset_incremental_index(
    index_path: Path,
    mapping_path: Path,
    catalog_path: Path,
) -> dict[str, Any]:
    """Restore the baseline 4-tile index and catalog from backup."""
    b_idx = BACKUP_DIR / index_path.name
    b_map = BACKUP_DIR / mapping_path.name
    b_cat = BACKUP_DIR / catalog_path.name

    if b_idx.exists() and b_map.exists() and b_cat.exists():
        shutil.copy2(b_idx, index_path)
        shutil.copy2(b_map, mapping_path)
        shutil.copy2(b_cat, catalog_path)
        return {"status": "reset", "message": "Restored baseline index (4 tiles)."}
    return {"status": "error", "message": "Baseline backup not found."}
