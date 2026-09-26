"""Windowed GeoTIFF tiling for model-ready image patches."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window


class TilingError(RuntimeError):
    """Raised when an input cannot be tiled."""


@dataclass(frozen=True)
class TileMetadata:
    source_scene: str
    tile_id: str
    path: str
    bounds: tuple[float, float, float, float]
    crs: str
    transform: tuple[float, ...]
    acquisition_date: str | None
    sensor: str | None
    valid_fraction: float


def tile_raster(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    tile_size: int = 256,
    overlap: int = 0,
    min_valid_fraction: float = 0.0,
    scene: str | None = None,
    acquisition_date: str | None = None,
    sensor: str | None = None,
) -> list[TileMetadata]:
    """Write fixed-size tiles row-major, padding edge tiles with nodata.

    Validity is evaluated per pixel: a pixel is valid only when every band is
    valid.  Partial edge windows are padded to ``tile_size`` and the padded
    area contributes to the valid fraction.
    """
    input_path, output_dir = Path(input_path), Path(output_dir)
    if not input_path.is_file():
        raise TilingError(f"Input raster does not exist: {input_path}")
    if tile_size < 1 or overlap < 0 or overlap >= tile_size:
        raise TilingError("tile_size must be positive and 0 <= overlap < tile_size")
    if not 0.0 <= min_valid_fraction <= 1.0:
        raise TilingError("min_valid_fraction must be between 0 and 1")

    scene_name = scene or input_path.stem
    scene_dir = output_dir / scene_name
    scene_dir.mkdir(parents=True, exist_ok=True)
    step = tile_size - overlap
    results: list[TileMetadata] = []
    rejected = 0

    with rasterio.open(input_path) as src:
        if src.crs is None:
            raise TilingError("Input raster must have a CRS")
        nodata = src.nodata
        if nodata is None:
            # A declared nodata value is needed for padding to remain explicit.
            nodata = 0 if src.dtypes[0] != "float32" else np.nan
        profile = src.profile.copy()
        profile.update(width=tile_size, height=tile_size, nodata=nodata,
                       compress="deflate", BIGTIFF="IF_SAFER")
        if profile.get("tiled"):
            profile["blockxsize"] = max(16, min(256, ((tile_size + 15) // 16) * 16))
            profile["blockysize"] = profile["blockxsize"]

        tile_number = 0
        for row in range(0, src.height, step):
            for col in range(0, src.width, step):
                window = Window(col, row, tile_size, tile_size)
                data = src.read(window=window, boundless=True, masked=True,
                                fill_value=nodata)
                mask = np.ma.getmaskarray(data)
                valid = ~mask.any(axis=0)
                if np.issubdtype(data.dtype, np.floating):
                    valid &= np.isfinite(data.filled(np.nan)).all(axis=0)
                fraction = float(valid.mean())
                tile_id = f"tile_{tile_number:06d}"
                tile_number += 1
                if fraction < min_valid_fraction:
                    rejected += 1
                    continue

                transform = src.window_transform(window)
                tile_profile = profile.copy()
                tile_profile.update(transform=transform)
                tile_path = scene_dir / f"{tile_id}.tif"
                with rasterio.open(tile_path, "w", **tile_profile) as dst:
                    dst.write(data.filled(nodata))
                bounds = rasterio.transform.array_bounds(tile_size, tile_size, transform)
                results.append(TileMetadata(
                    source_scene=scene_name, tile_id=tile_id, path=str(tile_path),
                    bounds=tuple(float(v) for v in bounds), crs=src.crs.to_string(),
                    transform=tuple(transform), acquisition_date=acquisition_date,
                    sensor=sensor, valid_fraction=fraction,
                ))

    manifest = {
        "source": str(input_path), "tile_size": tile_size, "overlap": overlap,
        "min_valid_fraction": min_valid_fraction, "rejected_tiles": rejected,
        "tiles": [asdict(item) for item in results],
    }
    (scene_dir / "tiles.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return results
