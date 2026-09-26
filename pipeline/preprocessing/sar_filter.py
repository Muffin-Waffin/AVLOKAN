from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import uniform_filter


class SARFilterError(RuntimeError):
    """Raised when SAR filtering fails."""


def lee_filter(
    input_path: str | Path,
    output_path: str | Path,
    *,
    window_size: int = 3,
) -> Path:
    """
    Apply a basic Lee speckle filter to a single-band SAR raster.

    The input is expected to contain non-negative intensity/amplitude
    values with zero representing NoData.
    """

    if window_size < 3 or window_size % 2 == 0:
        raise SARFilterError(
            "window_size must be an odd integer >= 3."
        )

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise SARFilterError(f"Input raster does not exist: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    radius = window_size // 2
    with rasterio.open(input_path) as src:
        profile = src.profile.copy()
        profile.update(dtype="float32", count=1, nodata=0,
                       compress="deflate", predictor=3)
        with rasterio.open(output_path, "w", **profile) as dst:
            any_valid = False
            block = 512
            for row in range(0, src.height, block):
                for col in range(0, src.width, block):
                    height = min(block, src.height - row)
                    width = min(block, src.width - col)
                    core = rasterio.windows.Window(col, row, width, height)
                    expanded = rasterio.windows.Window(
                        max(0, col - radius), max(0, row - radius),
                        min(src.width, col + width + radius) - max(0, col - radius),
                        min(src.height, row + height + radius) - max(0, row - radius),
                    )
                    data = src.read(1, window=expanded, masked=True).astype(np.float32)
                    values = data.filled(0)
                    valid = (~np.ma.getmaskarray(data)) & (values > 0)
                    if src.nodata is not None:
                        valid &= values != src.nodata
                    if valid.any():
                        any_valid = True
                    working = np.where(valid, values, 0.0).astype(np.float32, copy=False)
                    valid_weight = uniform_filter(valid.astype(np.float32), size=window_size, mode="nearest")
                    local_mean = uniform_filter(working, size=window_size, mode="nearest")
                    local_mean_sq = uniform_filter(working * working, size=window_size, mode="nearest")
                    local_mean = np.divide(local_mean, valid_weight, out=np.zeros_like(local_mean), where=valid_weight > 0)
                    local_mean_sq = np.divide(local_mean_sq, valid_weight, out=np.zeros_like(local_mean_sq), where=valid_weight > 0)
                    variance = np.maximum(local_mean_sq - local_mean * local_mean, 0.0)
                    noise_variance = float(np.median(variance[valid])) if valid.any() else 0.0
                    signal_variance = np.maximum(variance - noise_variance, 0.0)
                    weights = signal_variance / (signal_variance + noise_variance + 1e-8)
                    filtered = local_mean + weights * (working - local_mean)
                    filtered[~valid] = 0.0
                    # Write only the requested core, excluding the halo.
                    y0, x0 = row - int(expanded.row_off), col - int(expanded.col_off)
                    dst.write(filtered[y0:y0 + height, x0:x0 + width], 1, window=core)
            if not any_valid:
                raise SARFilterError("Input contains no valid pixels.")

    return output_path
