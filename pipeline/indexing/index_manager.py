"""Small Phase 4-facing interface for supplied vectors and search."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.indexing.incremental_index import IncrementalIndex


class IndexManager:
    def __init__(self, index_path: str | Path, *, dimension: int | None = None) -> None:
        self._index = IncrementalIndex(index_path, dimension=dimension)

    def index_embeddings(self, vectors: np.ndarray, tile_ids: list[str] | tuple[str, ...]) -> None:
        self._index.add_embeddings(vectors, tile_ids)

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        *,
        allowed_tile_ids: set[str] | None = None,
    ) -> list[dict]:
        return self._index.search(query_vector, k, allowed_tile_ids=allowed_tile_ids)

    def contains(self, tile_id: str) -> bool:
        return self._index.contains(tile_id)
