"""Deterministic, windowed Sentinel-2 input preparation for official BIT-CD."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
import torch
from rasterio.windows import Window


BIT_INPUT_SIZE = 256
BAND_ORDER = (4, 3, 2)  # model RGB = Sentinel-2 B04, B03, B02; retain B08 in source.


def read_model_tensor(path: str | Path, window: Window, *, size: int = BIT_INPUT_SIZE) -> tuple[torch.Tensor, np.ndarray]:
    """Read one bounded window, return normalized [1,3,H,W] tensor and validity mask.

    Sentinel-2 Phase 2 inputs are surface reflectance (DN * 1e-4). The BIT
    LEVIR pipeline uses RGB values scaled to [0,1], then mean/std 0.5/0.5.
    Here reflectance is clipped to [0,1] and mapped identically to [-1,1].
    Pixels with any-band nodata are normalized to zero and tracked separately.
    """
    with rasterio.open(path) as src:
        if src.count < 4:
            raise ValueError(f"Expected B02/B03/B04/B08 source with at least 4 bands: {path}")
        data = src.read(BAND_ORDER, window=window, boundless=True, fill_value=0, masked=True)
        valid = ~np.ma.getmaskarray(data).any(axis=0)
        # Boundless padding is masked only if the source has nodata. Explicitly
        # mark cells outside the raster invalid as well.
        row0, col0 = int(window.row_off), int(window.col_off)
        h, w = int(window.height), int(window.width)
        y = np.arange(row0, row0 + h)[:, None]
        x = np.arange(col0, col0 + w)[None, :]
        inside = (y >= 0) & (y < src.height) & (x >= 0) & (x < src.width)
        valid &= inside
        reflectance = np.asarray(data.filled(0), dtype=np.float32)
        reflectance = np.clip(reflectance, 0.0, 1.0)
        normalized = reflectance * np.float32(2.0) - np.float32(1.0)
        normalized[:, ~valid] = 0.0
    if normalized.shape[1:] != (size, size):
        raise ValueError(f"BIT windows must be {size}x{size}, got {normalized.shape[1:]}")
    return torch.from_numpy(np.ascontiguousarray(normalized[None])), valid
