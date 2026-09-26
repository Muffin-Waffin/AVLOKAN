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

    with rasterio.open(input_path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        nodata = src.nodata

    valid = data > 0

    if nodata is not None:
        valid &= data != nodata

    if not np.any(valid):
        raise SARFilterError("Input contains no valid pixels.")

    # Replace invalid pixels with zero temporarily.
    working = np.where(valid, data, 0.0)

    # Local mean and second moment.
    local_mean = uniform_filter(
        working,
        size=window_size,
        mode="nearest",
    )

    local_mean_sq = uniform_filter(
        working * working,
        size=window_size,
        mode="nearest",
    )

    local_variance = np.maximum(
        local_mean_sq - local_mean * local_mean,
        0.0,
    )

    # Estimate noise variance from valid pixels.
    noise_variance = np.median(local_variance[valid])

    signal_variance = np.maximum(
        local_variance - noise_variance,
        0.0,
    )

    weights = signal_variance / (
        signal_variance + noise_variance + 1e-8
    )

    filtered = local_mean + weights * (
        working - local_mean
    )

    # Restore NoData.
    filtered[~valid] = 0

    profile.update(
        dtype="float32",
        count=1,
        nodata=0,
        compress="deflate",
        predictor=3,
    )

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(filtered.astype(np.float32), 1)

    return output_path
