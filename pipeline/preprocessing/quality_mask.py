from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import rasterio


Sensor = Literal["sentinel-2", "landsat"]


class QualityMaskError(RuntimeError):
    """Raised when quality-mask processing fails."""


@dataclass(frozen=True)
class MaskStatistics:
    total_pixels: int
    valid_pixels: int
    masked_pixels: int
    valid_fraction: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "total_pixels": self.total_pixels,
            "valid_pixels": self.valid_pixels,
            "masked_pixels": self.masked_pixels,
            "valid_fraction": self.valid_fraction,
        }


# Sentinel-2 Scene Classification Layer (SCL) classes
#
# 0  No data
# 1  Saturated / defective
# 2  Topographic / dark features
# 3  Cloud shadows
# 4  Vegetation
# 5  Bare soils
# 6  Water
# 7  Unclassified
# 8  Cloud medium probability
# 9  Cloud high probability
# 10 Thin cirrus
# 11 Snow / ice
S2_INVALID_SCL_CLASSES = frozenset({
    0,   # no data
    1,   # defective
    3,   # cloud shadow
    8,   # medium probability cloud
    9,   # high probability cloud
    10,  # cirrus
    11,  # snow / ice
})


# Landsat Collection 2 QA_PIXEL bit positions.
LANDSAT_QA_FILL_BIT = 0
LANDSAT_QA_DILATED_CLOUD_BIT = 1
LANDSAT_QA_CIRRUS_BIT = 2
LANDSAT_QA_CLOUD_BIT = 3
LANDSAT_QA_CLOUD_SHADOW_BIT = 4
LANDSAT_QA_SNOW_BIT = 5


def _bit_set(values: np.ndarray, bit: int) -> np.ndarray:
    """Return True where a QA bit is set."""
    return (values & (1 << bit)) != 0


def sentinel2_scl_mask(scl: np.ndarray) -> np.ndarray:
    """
    Create a boolean validity mask from Sentinel-2 SCL.

    True  = usable pixel
    False = masked pixel
    """
    if not np.issubdtype(scl.dtype, np.integer):
        raise QualityMaskError(
            f"Sentinel-2 SCL must be integer data, got {scl.dtype}"
        )

    return ~np.isin(scl, list(S2_INVALID_SCL_CLASSES))


def landsat_qa_pixel_mask(qa_pixel: np.ndarray) -> np.ndarray:
    """
    Create a boolean validity mask from Landsat Collection 2 QA_PIXEL.

    True  = usable pixel
    False = masked pixel
    """
    if not np.issubdtype(qa_pixel.dtype, np.integer):
        raise QualityMaskError(
            f"Landsat QA_PIXEL must be integer data, got {qa_pixel.dtype}"
        )

    invalid = (
        _bit_set(qa_pixel, LANDSAT_QA_FILL_BIT)
        | _bit_set(qa_pixel, LANDSAT_QA_DILATED_CLOUD_BIT)
        | _bit_set(qa_pixel, LANDSAT_QA_CIRRUS_BIT)
        | _bit_set(qa_pixel, LANDSAT_QA_CLOUD_BIT)
        | _bit_set(qa_pixel, LANDSAT_QA_CLOUD_SHADOW_BIT)
        | _bit_set(qa_pixel, LANDSAT_QA_SNOW_BIT)
    )

    return ~invalid


def calculate_mask_statistics(mask: np.ndarray) -> MaskStatistics:
    """Calculate basic quality-mask statistics."""
    if mask.dtype != np.bool_:
        mask = mask.astype(bool)

    total = int(mask.size)
    valid = int(mask.sum())
    masked = total - valid

    fraction = valid / total if total else 0.0

    return MaskStatistics(
        total_pixels=total,
        valid_pixels=valid,
        masked_pixels=masked,
        valid_fraction=fraction,
    )


def apply_mask(
    data: np.ndarray,
    mask: np.ndarray,
    *,
    fill_value: float = np.nan,
) -> np.ndarray:
    """
    Apply a boolean validity mask to raster data.

    Supports:
        (height, width)
        (bands, height, width)
    """
    if data.ndim not in (2, 3):
        raise QualityMaskError(
            f"Expected 2D or 3D raster data, got {data.ndim}D"
        )

    if mask.shape != data.shape[-2:]:
        raise QualityMaskError(
            f"Mask shape {mask.shape} does not match "
            f"data spatial shape {data.shape[-2:]}"
        )

    result = data.astype(np.float32, copy=True)

    if data.ndim == 2:
        result[~mask] = fill_value
    else:
        result[:, ~mask] = fill_value

    return result


def build_quality_mask(
    sensor: Sensor,
    quality_data: np.ndarray,
) -> np.ndarray:
    """Build a sensor-specific boolean quality mask."""
    if sensor == "sentinel-2":
        return sentinel2_scl_mask(quality_data)

    if sensor == "landsat":
        return landsat_qa_pixel_mask(quality_data)

    raise QualityMaskError(f"Unsupported optical sensor: {sensor}")


def mask_raster_windowed(
    input_path: str | Path,
    quality_path: str | Path,
    output_path: str | Path,
    sensor: Sensor,
    *,
    window_size: int = 1024,
) -> MaskStatistics:
    """
    Apply a quality mask to an optical raster window-by-window.

    The quality raster must be spatially aligned with the input raster.
    """
    input_path = Path(input_path)
    quality_path = Path(quality_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise QualityMaskError(f"Input raster not found: {input_path}")

    if not quality_path.exists():
        raise QualityMaskError(f"Quality raster not found: {quality_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        rasterio.open(input_path) as src,
        rasterio.open(quality_path) as quality,
    ):
        if src.width != quality.width or src.height != quality.height:
            raise QualityMaskError(
                "Input and quality rasters have different dimensions: "
                f"{src.width}x{src.height} vs "
                f"{quality.width}x{quality.height}"
            )

        if src.transform != quality.transform:
            raise QualityMaskError(
                "Input and quality rasters do not have matching transforms"
            )

        if src.crs != quality.crs:
            raise QualityMaskError(
                f"Input CRS {src.crs} != quality CRS {quality.crs}"
            )

        profile = src.profile.copy()

        profile.update(
            dtype="float32",
            nodata=np.nan,
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            BIGTIFF="IF_SAFER",
        )

        total_pixels = 0
        valid_pixels = 0

        with rasterio.open(output_path, "w", **profile) as dst:
            for row in range(0, src.height, window_size):
                height = min(window_size, src.height - row)

                for col in range(0, src.width, window_size):
                    width = min(window_size, src.width - col)

                    window = rasterio.windows.Window(
                        col,
                        row,
                        width,
                        height,
                    )

                    data = src.read(window=window, masked=True)
                    quality_data = quality.read(
                        1,
                        window=window,
                    )

                    mask = build_quality_mask(
                        sensor,
                        quality_data,
                    )

                    source_invalid = np.ma.getmaskarray(data).any(axis=0)
                    mask &= ~source_invalid
                    masked = apply_mask(data.filled(0), mask)

                    dst.write(masked, window=window)

                    total_pixels += mask.size
                    valid_pixels += int(mask.sum())

        masked_pixels = total_pixels - valid_pixels
        valid_fraction = (
            valid_pixels / total_pixels
            if total_pixels
            else 0.0
        )

        return MaskStatistics(
            total_pixels=total_pixels,
            valid_pixels=valid_pixels,
            masked_pixels=masked_pixels,
            valid_fraction=valid_fraction,
        )
