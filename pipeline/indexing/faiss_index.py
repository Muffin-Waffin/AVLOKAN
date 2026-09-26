"""CPU FAISS index for caller-supplied vectors and stable tile IDs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

try:
    import faiss
except ImportError as exc:  # pragma: no cover - exercised only without dependency
    raise ImportError("FAISS is required; install the pinned faiss-cpu dependency.") from exc


class FaissIndexError(ValueError):
    """Raised for invalid vectors, IDs, or persisted index data."""


class FaissVectorIndex:
    """IndexFlatIP wrapped in IndexIDMap2, with cosine-normalized vectors."""

    FORMAT_VERSION = 1

    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise FaissIndexError("dimension must be greater than zero")
        self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(int(dimension)))
        self._dimension = int(dimension)
        self._tile_to_id: dict[str, int] = {}
        self._id_to_tile: dict[int, str] = {}
        self._next_id = 0

    @classmethod
    def create_index(cls, dimension: int) -> "FaissVectorIndex":
        return cls(dimension)

    @staticmethod
    def _normalized_matrix(vectors: np.ndarray, dimension: int) -> np.ndarray:
        values = np.asarray(vectors, dtype=np.float32)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        if values.ndim != 2 or values.shape[1] != dimension:
            raise FaissIndexError(f"vector dimension mismatch; expected shape (N, {dimension})")
        if not np.isfinite(values).all():
            raise FaissIndexError("vectors must contain only finite values")
        values = np.ascontiguousarray(values)
        norms = np.linalg.norm(values, axis=1)
        if np.any(norms == 0):
            raise FaissIndexError("zero vectors cannot be normalized")
        # Phase 4 returns unit vectors already; skip another normalization.
        if np.allclose(norms, 1.0, rtol=1e-5, atol=1e-5):
            return values
        return np.ascontiguousarray(values / norms[:, None], dtype=np.float32)

    def add(self, vectors: np.ndarray, tile_ids: list[str] | tuple[str, ...]) -> None:
        ids = list(tile_ids)
        matrix = self._normalized_matrix(vectors, self._dimension)
        if len(ids) != matrix.shape[0]:
            raise FaissIndexError("tile_ids count must match vector count")
        if any(not isinstance(tile_id, str) or not tile_id for tile_id in ids):
            raise FaissIndexError("tile IDs must be non-empty strings")
        if len(set(ids)) != len(ids) or any(tile_id in self._tile_to_id for tile_id in ids):
            raise FaissIndexError("duplicate tile ID")
        if not ids:
            return
        numeric_ids = np.arange(self._next_id, self._next_id + len(ids), dtype=np.int64)
        self._index.add_with_ids(matrix, numeric_ids)
        for numeric_id, tile_id in zip(numeric_ids.tolist(), ids):
            self._tile_to_id[tile_id] = numeric_id
            self._id_to_tile[numeric_id] = tile_id
        self._next_id += len(ids)

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
        *,
        allowed_tile_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if k <= 0:
            raise FaissIndexError("k must be greater than zero")
        if self.size() == 0:
            return []
        query = self._normalized_matrix(query_vector, self._dimension)
        if query.shape[0] != 1:
            raise FaissIndexError("search accepts one query vector at a time")
        if allowed_tile_ids is None:
            eligible_ids = None
            candidate_count = self.size()
        else:
            eligible_ids = np.asarray(
                sorted(self._tile_to_id[tile_id] for tile_id in allowed_tile_ids
                       if tile_id in self._tile_to_id),
                dtype=np.int64,
            )
            if eligible_ids.size == 0:
                return []
            candidate_count = int(eligible_ids.size)
        parameters = None
        if eligible_ids is not None:
            parameters = faiss.SearchParameters()
            parameters.sel = faiss.IDSelectorBatch(eligible_ids)
        scores, ids = self._index.search(
            query, min(int(k), candidate_count), params=parameters
        )
        return [
            {"tile_id": self._id_to_tile[int(numeric_id)], "score": float(score)}
            for score, numeric_id in zip(scores[0], ids[0])
            if numeric_id >= 0 and int(numeric_id) in self._id_to_tile
        ]

    def size(self) -> int:
        return int(self._index.ntotal)

    def dimension(self) -> int:
        return self._dimension

    def contains(self, tile_id: str) -> bool:
        return tile_id in self._tile_to_id

    @staticmethod
    def default_mapping_path(index_path: str | Path) -> Path:
        path = Path(index_path)
        return path.with_name(f"{path.stem}_ids.json")

    def save(self, path: str | Path, mapping_path: str | Path | None = None) -> tuple[Path, Path]:
        index_path = Path(path)
        ids_path = Path(mapping_path) if mapping_path else self.default_mapping_path(index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        ids_path.parent.mkdir(parents=True, exist_ok=True)
        index_tmp = index_path.with_suffix(index_path.suffix + ".tmp")
        ids_tmp = ids_path.with_suffix(ids_path.suffix + ".tmp")
        faiss.write_index(self._index, str(index_tmp))
        mapping = {
            "format_version": self.FORMAT_VERSION,
            "dimension": self._dimension,
            "next_id": self._next_id,
            "entries": [
                {"faiss_id": numeric_id, "tile_id": tile_id}
                for numeric_id, tile_id in sorted(self._id_to_tile.items())
            ],
        }
        ids_tmp.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
        index_tmp.replace(index_path)
        ids_tmp.replace(ids_path)
        return index_path, ids_path

    @classmethod
    def load(cls, path: str | Path, mapping_path: str | Path | None = None) -> "FaissVectorIndex":
        index_path = Path(path)
        ids_path = Path(mapping_path) if mapping_path else cls.default_mapping_path(index_path)
        try:
            raw = json.loads(ids_path.read_text(encoding="utf-8"))
            if raw.get("format_version") != cls.FORMAT_VERSION:
                raise FaissIndexError("unsupported ID mapping format")
            index = faiss.read_index(str(index_path))
            dimension = int(raw["dimension"])
            entries = raw["entries"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise FaissIndexError(f"Could not load FAISS index or ID mapping: {exc}") from exc
        if not isinstance(index, faiss.IndexIDMap2):
            raise FaissIndexError("persisted FAISS index is not an IndexIDMap2")
        if index.d != dimension:
            raise FaissIndexError("index dimension does not match ID mapping")
        result = cls(dimension)
        result._index = index
        for entry in entries:
            numeric_id, tile_id = int(entry["faiss_id"]), str(entry["tile_id"])
            if tile_id in result._tile_to_id or numeric_id in result._id_to_tile:
                raise FaissIndexError("duplicate ID in persisted mapping")
            result._tile_to_id[tile_id] = numeric_id
            result._id_to_tile[numeric_id] = tile_id
        stored_ids = set(faiss.vector_to_array(index.id_map).astype(np.int64).tolist())
        if stored_ids != set(result._id_to_tile):
            raise FaissIndexError("FAISS index IDs do not match persisted mapping")
        if index.ntotal != len(result._id_to_tile):
            raise FaissIndexError("FAISS index size does not match persisted mapping")
        result._next_id = max(int(raw.get("next_id", 0)), max(result._id_to_tile, default=-1) + 1)
        return result
