from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window


class RasterInspectionError(RuntimeError):
    """Raised when raster inspection fails."""


@dataclass
class BandInspection:
    band: int
    dtype: str
    nodata: float | None
    min_value: float | None
    max_value: float | None
    mean_value: float | None
    valid_fraction: float


@dataclass
class RasterInspection:
    path: str
    driver: str
    width: int
    height: int
    count: int
    crs: str | None
    resolution: tuple[float, float]
    bounds: tuple[float, float, float, float]
    transform: tuple[float, ...]
    bands: list[BandInspection]

    def to_dict(self) -> dict:
        return asdict(self)


def _sample_windows(
    width: int,
    height: int,
    window_size: int,
    samples_per_axis: int,
) -> list[Window]:

    if width <= 0 or height <= 0:
        raise RasterInspectionError(
            "Raster has invalid dimensions."
        )

    if samples_per_axis < 1:
        raise RasterInspectionError(
            "samples_per_axis must be >= 1."
        )

    if window_size < 1:
        raise RasterInspectionError(
            "window_size must be >= 1."
        )

    if width <= window_size:
        x_positions = [0]
    else:
        x_positions = np.linspace(
            0,
            width - window_size,
            samples_per_axis,
            dtype=int,
        )

    if height <= window_size:
        y_positions = [0]
    else:
        y_positions = np.linspace(
            0,
            height - window_size,
            samples_per_axis,
            dtype=int,
        )

    windows = []

    for y in y_positions:
        for x in x_positions:
            windows.append(
                Window(
                    col_off=int(x),
                    row_off=int(y),
                    width=min(window_size, width - int(x)),
                    height=min(window_size, height - int(y)),
                )
            )

    return windows


def inspect_raster(
    path: str | Path,
    *,
    window_size: int = 256,
    samples_per_axis: int = 3,
) -> RasterInspection:

    path = Path(path)

    if not path.exists():
        raise RasterInspectionError(
            f"Raster does not exist: {path}"
        )

    if not path.is_file():
        raise RasterInspectionError(
            f"Raster path is not a file: {path}"
        )

    with rasterio.open(path) as src:

        if src.width <= 0 or src.height <= 0:
            raise RasterInspectionError(
                "Raster has invalid dimensions."
            )

        if src.count <= 0:
            raise RasterInspectionError(
                "Raster contains no bands."
            )

        if src.crs is None:
            raise RasterInspectionError(
                f"Raster has no CRS: {path}"
            )

        if src.transform.is_identity:
            raise RasterInspectionError(
                f"Raster has an identity transform: {path}"
            )

        windows = _sample_windows(
            src.width,
            src.height,
            window_size,
            samples_per_axis,
        )

        bands = []

        for band_index in range(1, src.count + 1):

            total_valid = 0
            total_pixels = 0

            minimum = None
            maximum = None
            value_sum = 0.0

            for window in windows:

                data = src.read(
                    band_index,
                    window=window,
                    masked=True,
                )
                total_pixels += data.size

                values = data.compressed()

                if values.size == 0:
                    continue

                values = values.astype(
                    np.float64,
                    copy=False,
                )

                finite = np.isfinite(values)

                if not finite.any():
                    continue

                values = values[finite]

                total_valid += values.size

                local_min = float(values.min())
                local_max = float(values.max())

                if minimum is None:
                    minimum = local_min
                else:
                    minimum = min(
                        minimum,
                        local_min,
                    )

                if maximum is None:
                    maximum = local_max
                else:
                    maximum = max(
                        maximum,
                        local_max,
                    )

                value_sum += float(
                    values.sum()
                )

            mean_value = (
                value_sum / total_valid
                if total_valid
                else None
            )

            valid_fraction = (
                total_valid / total_pixels
                if total_pixels
                else 0.0
            )

            nodata = src.nodata

            if nodata is not None:
                nodata = float(nodata)

            bands.append(
                BandInspection(
                    band=band_index,
                    dtype=src.dtypes[
                        band_index - 1
                    ],
                    nodata=nodata,
                    min_value=minimum,
                    max_value=maximum,
                    mean_value=mean_value,
                    valid_fraction=valid_fraction,
                )
            )

        return RasterInspection(
            path=str(path),
            driver=src.driver,
            width=src.width,
            height=src.height,
            count=src.count,
            crs=src.crs.to_string(),
            resolution=(
                float(src.res[0]),
                float(src.res[1]),
            ),
            bounds=(
                float(src.bounds.left),
                float(src.bounds.bottom),
                float(src.bounds.right),
                float(src.bounds.top),
            ),
            transform=tuple(src.transform),
            bands=bands,
        )
