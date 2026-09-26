import numpy as np
import rasterio
import pytest

from rasterio.transform import from_origin

from pipeline.preprocessing.raster_inspector import (
    RasterInspectionError,
    inspect_raster,
)


def create_raster(path, *, crs="EPSG:32643"):

    transform = from_origin(
        500000,
        2500000,
        10,
        10,
    )

    data = np.arange(
        256 * 256,
        dtype=np.uint16,
    ).reshape(256, 256)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=256,
        height=256,
        count=1,
        dtype="uint16",
        crs=crs,
        transform=transform,
        nodata=0,
    ) as dst:

        dst.write(data, 1)


def test_inspect_valid_raster(tmp_path):

    path = tmp_path / "test.tif"

    create_raster(path)

    result = inspect_raster(path)

    assert result.width == 256
    assert result.height == 256
    assert result.count == 1
    assert result.crs == "EPSG:32643"
    assert result.resolution == (10.0, 10.0)

    band = result.bands[0]

    assert band.band == 1
    assert band.dtype == "uint16"
    assert band.nodata == 0.0
    assert band.min_value == 1.0
    assert band.max_value == 65535.0
    assert 0 < band.valid_fraction <= 1


def test_missing_raster(tmp_path):

    with pytest.raises(RasterInspectionError):

        inspect_raster(
            tmp_path / "missing.tif"
        )


def test_missing_crs(tmp_path):

    path = tmp_path / "no_crs.tif"

    transform = from_origin(
        500000,
        2500000,
        10,
        10,
    )

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=256,
        height=256,
        count=1,
        dtype="uint16",
        transform=transform,
    ) as dst:

        dst.write(
            np.ones(
                (256, 256),
                dtype=np.uint16,
            ),
            1,
        )

    with pytest.raises(RasterInspectionError):

        inspect_raster(path)
