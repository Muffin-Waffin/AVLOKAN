from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pipeline.indexing.incremental_index import IncrementalIndex
from pipeline.indexing.tile_catalog import TileCatalog, TileMetadata
from pipeline.retrieval.retriever import Retriever


class FakeModel:
    embedding_dim = 2
    preprocessing_seconds = 0.0

    def encode_text(self, text: str) -> np.ndarray:
        return np.array([10.0, 0.0], dtype=np.float32)


class FakeImageEncoder:
    tile_read_seconds = 0.0

    def encode_image(self, path: str | Path) -> np.ndarray:
        return np.array([0.0, 3.0], dtype=np.float32)


@pytest.fixture
def retrieval_setup(tmp_path):
    tile_paths = [tmp_path / f"tile-{index}.tif" for index in range(3)]
    for path in tile_paths:
        path.touch()
    records = [
        TileMetadata(
            tile_id=f"tile-{index}", source_scene_id=f"scene-{index}",
            sensor=sensor, acquisition_datetime=acquired,
            tile_path=str(path), width=256, height=256, crs="EPSG:32643",
            resolution=(10.0, 10.0), bounds=bounds, transform=(10, 0, 0, 0, -10, 100, 0, 0, 1),
            band_count=4, dtype="float32", valid_fraction=1.0,
        )
        for index, (path, sensor, acquired, bounds) in enumerate([
            (tile_paths[0], "sentinel-2", "2025-03-29T05:28:41Z", (0, 0, 10, 10)),
            (tile_paths[1], "landsat", "2024-08-10T10:00:00Z", (20, 20, 30, 30)),
            (tile_paths[2], "sentinel-2", "2025-11-01T00:00:00Z", (5, 5, 15, 15)),
        ])
    ]
    catalog_path = tmp_path / "tiles.json"
    catalog = TileCatalog(catalog_path)
    catalog.upsert_many(records)
    index = IncrementalIndex(tmp_path / "tiles.index", dimension=2)
    index.add_embeddings(
        np.array([[1, 0], [0.8, 0.6], [0, 1]], dtype=np.float32),
        [record.tile_id for record in records],
    )
    retriever = Retriever(FakeModel(), index, catalog, FakeImageEncoder())
    return retriever, records, tile_paths
