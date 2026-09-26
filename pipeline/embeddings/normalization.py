"""Convert model features to contiguous float32 unit vectors."""
from __future__ import annotations

import numpy as np


def normalize_embeddings(values: np.ndarray, *, epsilon: float = 1e-12) -> np.ndarray:
    vectors = np.asarray(values, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    if vectors.ndim != 2 or vectors.shape[1] == 0:
        raise ValueError("embeddings must have shape (N, D) with D > 0")
    if not np.isfinite(vectors).all():
        raise ValueError("embeddings must be finite")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms <= epsilon):
        raise ValueError("zero or near-zero embeddings cannot be normalized")
    if np.allclose(norms, 1.0, rtol=1e-5, atol=1e-5):
        return np.ascontiguousarray(vectors, dtype=np.float32)
    return np.ascontiguousarray(vectors / norms[:, None], dtype=np.float32)

