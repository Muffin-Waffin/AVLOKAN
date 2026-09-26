from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


class SCLAlignmentError(RuntimeError):
    """Raised when Sentinel-2 SCL alignment fails."""


def align_scl_to_reference(
    scl_path: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
) -> Path:
    """
    Resample a Sentinel-2 SCL raster onto a reference raster grid.

    SCL is categorical data, therefore nearest-neighbour resampling
    is mandatory.
    """

    scl_path = Path(scl_path)
    reference_path = Path(reference_path)
    output_path = Path(output_path)

    if not scl_path.exists():
        raise SCLAlignmentError(
            f"SCL raster does not exist: {scl_path}"
        )

    if not reference_path.exists():
        raise SCLAlignmentError(
            f"Reference raster does not exist: {reference_path}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with rasterio.open(scl_path) as src:
        with rasterio.open(reference_path) as ref:

            if src.count != 1:
                raise SCLAlignmentError(
                    "SCL raster must contain exactly one band."
                )

            if src.crs is None:
                raise SCLAlignmentError(
                    "SCL raster has no CRS."
                )

            if ref.crs is None:
                raise SCLAlignmentError(
                    "Reference raster has no CRS."
                )

            profile = ref.profile.copy()

            profile.update(
                count=1,
                dtype="uint8",
                nodata=0,
                compress="deflate",
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

                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=ref.transform,
                    dst_crs=ref.crs,
                    dst_width=ref.width,
                    dst_height=ref.height,
                    resampling=Resampling.nearest,
                )

    return output_path
