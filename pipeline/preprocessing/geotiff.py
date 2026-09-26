from __future__ import annotations

from pathlib import Path

import rasterio


BANDS = ["B02", "B03", "B04", "B08"]


class GeoTIFFError(RuntimeError):
    """Raised when GeoTIFF creation fails."""


def build_multiband_geotiff(
    scene_dir: str | Path,
    output_path: str | Path,
) -> Path:
    """
    Stack Sentinel-2 B02, B03, B04 and B08 10 m bands
    into a single four-band GeoTIFF.

    The original uint16 pixel values are preserved.
    No radiometric scaling is applied at this stage.
    """

    scene_dir = Path(scene_dir)
    output_path = Path(output_path)

    paths = [
        scene_dir / f"{band}_10m.jp2"
        for band in BANDS
    ]

    for path in paths:
        if not path.exists():
            raise GeoTIFFError(
                f"Required band does not exist: {path}"
            )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    sources = []

    try:
        for path in paths:
            sources.append(rasterio.open(path))

        reference = sources[0]

        for src in sources[1:]:
            if (
                src.width != reference.width
                or src.height != reference.height
                or src.crs != reference.crs
                or src.transform != reference.transform
            ):
                raise GeoTIFFError(
                    f"Band {src.name} is not spatially "
                    "compatible with the reference band."
                )

        profile = reference.profile.copy()

        profile.update(
            driver="GTiff",
            count=4,
            dtype="uint16",
            compress="deflate",
            predictor=2,
            tiled=True,
            BIGTIFF="IF_SAFER",
        )

        with rasterio.open(output_path, "w", **profile) as dst:
            block = 512
            for index, src in enumerate(sources, start=1):
                dst.set_band_description(index, BANDS[index - 1])
            for row in range(0, reference.height, block):
                height = min(block, reference.height - row)
                for col in range(0, reference.width, block):
                    width = min(block, reference.width - col)
                    window = rasterio.windows.Window(col, row, width, height)
                    for index, src in enumerate(sources, start=1):
                        dst.write(src.read(1, window=window), index, window=window)

    finally:
        for src in sources:
            src.close()

    return output_path
