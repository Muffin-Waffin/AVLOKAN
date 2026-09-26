from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import rasterio


Sensor = Literal[
    "sentinel-2",
    "landsat",
    "sentinel-1",
]


class RadiometryError(RuntimeError):
    """Raised when radiometric processing fails."""


@dataclass(frozen=True)
class RadiometricSpec:
    sensor: Sensor
    representation: str
    scale: float
    offset: float
    fill_value: float | None
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


SENTINEL2_L2A_SPEC = RadiometricSpec(
    sensor="sentinel-2",
    representation="surface_reflectance",
    scale=0.0001,
    offset=0.0,
    fill_value=None,
    source="Sentinel-2 L2A",
)

LANDSAT_C2_L2_SR_SPEC = RadiometricSpec(
    sensor="landsat",
    representation="surface_reflectance",
    scale=0.0000275,
    offset=-0.2,
    fill_value=0.0,
    source="Landsat Collection 2 Level-2 Surface Reflectance",
)

SENTINEL1_SIGMA0_SPEC = RadiometricSpec(
    sensor="sentinel-1",
    representation="calibrated_sigma0",
    scale=1.0,
    offset=0.0,
    fill_value=0.0,
    source="SNAP calibrated Sigma0",
)


def get_radiometric_spec(
    sensor: Sensor,
) -> RadiometricSpec:

    if sensor == "sentinel-2":
        return SENTINEL2_L2A_SPEC

    if sensor == "landsat":
        return LANDSAT_C2_L2_SR_SPEC

    if sensor == "sentinel-1":
        return SENTINEL1_SIGMA0_SPEC

    raise RadiometryError(
        f"Unsupported sensor: {sensor}"
    )


def convert_array(
    values: np.ndarray,
    spec: RadiometricSpec,
) -> np.ndarray:

    result = values.astype(np.float32, copy=True)

    if spec.fill_value is not None:

        fill_mask = values == spec.fill_value

        result = (
            result * np.float32(spec.scale)
            + np.float32(spec.offset)
        )

        result[fill_mask] = np.nan

    else:

        result = (
            result * np.float32(spec.scale)
            + np.float32(spec.offset)
        )

    return result


def convert_raster(
    input_path: str | Path,
    output_path: str | Path,
    spec: RadiometricSpec,
    *,
    window_size: int = 1024,
) -> Path:

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise RadiometryError(
            f"Input raster does not exist: {input_path}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with rasterio.open(input_path) as src:
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

        with rasterio.open(
            output_path,
            "w",
            **profile,
        ) as dst:

            for row in range(
                0,
                src.height,
                window_size,
            ):

                height = min(
                    window_size,
                    src.height - row,
                )

                for col in range(
                    0,
                    src.width,
                    window_size,
                ):

                    width = min(
                        window_size,
                        src.width - col,
                    )

                    window = rasterio.windows.Window(
                        col,
                        row,
                        width,
                        height,
                    )

                    data = src.read(window=window, masked=True)

                    converted = convert_array(
                        data.filled(spec.fill_value or 0),
                        spec,
                    )

                    # Respect source mask/nodata as well as sensor fill values.
                    source_invalid = np.ma.getmaskarray(data)
                    if source_invalid.any():
                        converted[source_invalid] = np.nan

                    dst.write(
                        converted,
                        window=window,
                    )

    return output_path
