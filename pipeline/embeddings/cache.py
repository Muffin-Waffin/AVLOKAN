"""Small file cache for normalized float32 vectors and their provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from pipeline.embeddings.normalization import normalize_embeddings


class EmbeddingCache:
    def __init__(self, root: str | Path, model_name: str) -> None:
        self.root = Path(root) / model_name.replace("/", "_")

    def _stem(self, tile_id: str) -> str:
        return hashlib.sha256(tile_id.encode("utf-8")).hexdigest()

    def get(
        self,
        tile_id: str,
        model_version: str,
        *,
        expected_dimension: int | None = None,
        source_fingerprint: str | None = None,
    ) -> np.ndarray | None:
        stem = self._stem(tile_id)
        array_path, metadata_path = self.root / f"{stem}.npy", self.root / f"{stem}.json"
        if not array_path.is_file() or not metadata_path.is_file():
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (metadata.get("tile_id") != tile_id
                    or metadata.get("model_name") != self.root.name
                    or metadata.get("model_version") != model_version
                    or metadata.get("normalized") is not True
                    or (expected_dimension is not None and metadata.get("embedding_dim") != expected_dimension)
                    or (source_fingerprint is not None and metadata.get("source_fingerprint") != source_fingerprint)):
                return None
            values = np.load(array_path, allow_pickle=False)
            if values.dtype != np.float32 or values.ndim != 1:
                return None
            if expected_dimension is not None and values.shape[0] != expected_dimension:
                return None
            norm = float(np.linalg.norm(values))
            if not np.isfinite(values).all() or not np.isclose(norm, 1.0, atol=1e-5):
                return None
            return values
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def put(
        self,
        tile_id: str,
        model_version: str,
        embedding: np.ndarray,
        *,
        source_fingerprint: str | None = None,
    ) -> None:
        vector = normalize_embeddings(embedding)[0]
        self.root.mkdir(parents=True, exist_ok=True)
        stem = self._stem(tile_id)
        array_path, metadata_path = self.root / f"{stem}.npy", self.root / f"{stem}.json"
        array_tmp, metadata_tmp = array_path.with_suffix(".npy.tmp"), metadata_path.with_suffix(".json.tmp")
        with array_tmp.open("wb") as file:
            np.save(file, vector, allow_pickle=False)
        metadata = {
            "tile_id": tile_id,
            "model_name": self.root.name,
            "model_version": model_version,
            "embedding_dim": int(vector.shape[0]),
            "embedding_dtype": "float32",
            "normalized": True,
            "source_fingerprint": source_fingerprint,
        }
        metadata_tmp.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        array_tmp.replace(array_path)
        metadata_tmp.replace(metadata_path)

