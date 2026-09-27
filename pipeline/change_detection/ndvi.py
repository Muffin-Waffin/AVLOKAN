"""Sentinel-2 NDVI and aligned temporal NDVI difference products."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio


def compute_ndvi(source_path: str | Path, output_path: str | Path) -> Path:
    """Write float32 NDVI using the Phase 2 B02/B03/B04/B08 band convention.

    B04 is GeoTIFF band 3 and B08 is band 4. Invalid/nodata pixels and pixels
    with an exactly zero denominator are written as NaN nodata.
    """
    source_path, output_path = Path(source_path), Path(output_path)
    if source_path.resolve() == output_path.resolve():
        raise ValueError("NDVI output must not overwrite the source raster")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(source_path) as src:
        if src.count < 4:
            raise ValueError(f"Expected B02/B03/B04/B08 raster with at least 4 bands: {source_path}")
        profile = src.profile.copy()
        profile.update(count=1, dtype="float32", nodata=np.nan, compress="deflate", predictor=3)
        with rasterio.open(output_path, "w", **profile) as dst:
            for _, window in src.block_windows(3):
                red_ma = src.read(3, window=window, masked=True)
                nir_ma = src.read(4, window=window, masked=True)
                red = np.asarray(red_ma.data, dtype=np.float32)
                nir = np.asarray(nir_ma.data, dtype=np.float32)
                with np.errstate(over="ignore", invalid="ignore"):
                    denominator = nir + red
                valid = (
                    ~np.ma.getmaskarray(red_ma)
                    & ~np.ma.getmaskarray(nir_ma)
                    & np.isfinite(red)
                    & np.isfinite(nir)
                    & np.isfinite(denominator)
                    & (denominator != 0)
                )
                values = np.full(red.shape, np.nan, dtype=np.float32)
                with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                    np.divide(nir - red, denominator, out=values, where=valid)
                values[~np.isfinite(values)] = np.nan
                dst.write(values, 1, window=window)
            dst.update_tags(
                product="NDVI", formula="(B08 - B04) / (B08 + B04)",
                red_band="3 (B04)", nir_band="4 (B08)",
                invalid="NaN nodata: source nodata/non-finite or zero denominator",
            )
    return output_path


def _assert_same_grid(first: rasterio.io.DatasetReader, second: rasterio.io.DatasetReader) -> None:
    if first.crs != second.crs:
        raise ValueError(f"NDVI CRS mismatch: {first.crs} != {second.crs}")
    if (first.width, first.height) != (second.width, second.height):
        raise ValueError("NDVI dimensions do not match")
    if first.transform != second.transform:
        raise ValueError("NDVI transforms do not match")


def compute_delta_ndvi(
    ndvi_t1_path: str | Path,
    ndvi_t2_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Write ΔNDVI = NDVI_T2 - NDVI_T1, preserving the aligned grid."""
    ndvi_t1_path, ndvi_t2_path, output_path = map(Path, (ndvi_t1_path, ndvi_t2_path, output_path))
    if output_path.resolve() in {ndvi_t1_path.resolve(), ndvi_t2_path.resolve()}:
        raise ValueError("Delta NDVI output must not overwrite either input")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(ndvi_t1_path) as t1, rasterio.open(ndvi_t2_path) as t2:
        _assert_same_grid(t1, t2)
        profile = t1.profile.copy()
        profile.update(count=1, dtype="float32", nodata=np.nan, compress="deflate", predictor=3)
        with rasterio.open(output_path, "w", **profile) as dst:
            for _, window in t1.block_windows(1):
                first_ma = t1.read(1, window=window, masked=True)
                second_ma = t2.read(1, window=window, masked=True)
                first = np.asarray(first_ma.filled(np.nan), dtype=np.float32)
                second = np.asarray(second_ma.filled(np.nan), dtype=np.float32)
                valid = (
                    ~np.ma.getmaskarray(first_ma)
                    & ~np.ma.getmaskarray(second_ma)
                    & np.isfinite(first)
                    & np.isfinite(second)
                )
                delta = np.full(first.shape, np.nan, dtype=np.float32)
                with np.errstate(over="ignore", invalid="ignore"):
                    np.subtract(second, first, out=delta, where=valid)
                delta[~np.isfinite(delta)] = np.nan
                dst.write(delta, 1, window=window)
            dst.update_tags(
                product="delta_NDVI", formula="NDVI_T2 - NDVI_T1",
                sign_convention="negative=NDVI decrease from T1 to T2; positive=NDVI increase",
            )
    return output_path


def compute_temporal_ndvi(
    t1_path: str | Path,
    t2_path: str | Path,
    ndvi_t1_path: str | Path,
    ndvi_t2_path: str | Path,
    delta_path: str | Path,
) -> tuple[Path, Path, Path]:
    """Compute both observations and ΔNDVI after validating source grids."""
    with rasterio.open(t1_path) as t1, rasterio.open(t2_path) as t2:
        _assert_same_grid(t1, t2)
    first = compute_ndvi(t1_path, ndvi_t1_path)
    second = compute_ndvi(t2_path, ndvi_t2_path)
    delta = compute_delta_ndvi(first, second, delta_path)
    return first, second, delta
