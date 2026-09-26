"""Incremental add-and-persist workflow for supplied embedding vectors."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.indexing.faiss_index import FaissVectorIndex


class IncrementalIndex:
    def __init__(
        self,
        index_path: str | Path,
        *,
        dimension: int | None = None,
        mapping_path: str | Path | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.mapping_path = Path(mapping_path) if mapping_path else FaissVectorIndex.default_mapping_path(index_path)
        has_index, has_mapping = self.index_path.exists(), self.mapping_path.exists()
        if has_index != has_mapping:
            raise FileNotFoundError("FAISS index and ID mapping must both exist or both be absent")
        if has_index:
            self.index = FaissVectorIndex.load(self.index_path, self.mapping_path)
            if dimension is not None and dimension != self.index.dimension():
                raise ValueError("requested dimension does not match persisted index")
        elif dimension is not None:
            self.index = FaissVectorIndex.create_index(dimension)
        else:
            raise ValueError("dimension is required when creating a new index")

    def add_embeddings(self, vectors: np.ndarray, tile_ids: list[str] | tuple[str, ...]) -> None:
        self.index.add(vectors, tile_ids)
        self.index.save(self.index_path, self.mapping_path)

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        *,
        allowed_tile_ids: set[str] | None = None,
    ) -> list[dict]:
        return self.index.search(query_vector, k, allowed_tile_ids=allowed_tile_ids)

    def size(self) -> int:
        return self.index.size()

    def dimension(self) -> int:
        return self.index.dimension()

    def contains(self, tile_id: str) -> bool:
        return self.index.contains(tile_id)
