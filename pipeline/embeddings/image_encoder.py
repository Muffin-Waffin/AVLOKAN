"""Window-bounded Sentinel-2 GeoTIFF RGB conversion and model inference."""
from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Sequence

import numpy as np
import rasterio
from PIL import Image

from pipeline.embeddings.remoteclip import RemoteCLIPAdapter


# Phase 2's Sentinel-2 stack order is B02, B03, B04, B08. Indices are 1-based.
SENTINEL2_RGB_BANDS = {"red": 3, "green": 2, "blue": 1}


def read_sentinel2_rgb(tile_path: str | Path) -> Image.Image:
    """Map B04/B03/B02 reflectance to a deterministic uint8 RGB PIL image.

    Phase 2 tiles contain float32 surface reflectance. Values are clipped to
    [0, 1] and scaled linearly to [0, 255]; B08 is retained in the GeoTIFF but
    not supplied to this RGB-only checkpoint.
    """
    path = Path(tile_path)
    with rasterio.open(path) as src:
        if src.count < 4:
            raise ValueError(f"Expected the four-band Phase 2 Sentinel-2 stack: {path}")
        if src.dtypes[0] != "float32":
            raise ValueError("Expected float32 Phase 2 surface-reflectance tiles")
        rgb = src.read([
            SENTINEL2_RGB_BANDS["red"],
            SENTINEL2_RGB_BANDS["green"],
            SENTINEL2_RGB_BANDS["blue"],
        ])
    rgb = np.nan_to_num(rgb, nan=0.0, posinf=1.0, neginf=0.0)
    rgb = np.rint(np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    return Image.fromarray(np.moveaxis(rgb, 0, -1), mode="RGB")


class ImageEncoder:
    def __init__(self, adapter: RemoteCLIPAdapter) -> None:
        self.adapter = adapter
        self.tile_read_seconds = 0.0

    def _read(self, tile_path: str | Path) -> Image.Image:
        started = perf_counter()
        image = read_sentinel2_rgb(tile_path)
        self.tile_read_seconds += perf_counter() - started
        return image

    def encode_image(self, tile_path: str | Path) -> np.ndarray:
        return self.adapter.encode_image(self._read(tile_path))

    def encode_images(self, tile_paths: Sequence[str | Path], batch_size: int = 4) -> np.ndarray:
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")
        chunks = []
        for start in range(0, len(tile_paths), batch_size):
            images = [self._read(path) for path in tile_paths[start:start + batch_size]]
            chunks.append(self.adapter.encode_images(images))
        if not chunks:
            return np.empty((0, self.adapter.embedding_dim or 0), dtype=np.float32)
        return np.concatenate(chunks, axis=0).astype(np.float32, copy=False)

    def encode_text(self, text: str) -> np.ndarray:
        return self.adapter.encode_text(text)

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        return self.adapter.encode_texts(texts)
