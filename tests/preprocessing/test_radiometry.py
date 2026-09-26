import numpy as np
import rasterio

from rasterio.transform import from_origin

from pipeline.preprocessing.radiometry import (
    LANDSAT_C2_L2_SR_SPEC,
    SENTINEL2_L2A_SPEC,
    convert_array,
    convert_raster,
)


def test_sentinel2_scaling():

    values = np.array(
        [[0, 1000, 2500, 10000]],
        dtype=np.uint16,
    )

    result = convert_array(
        values,
        SENTINEL2_L2A_SPEC,
    )

    np.testing.assert_allclose(
        result,
        [[0.0, 0.1, 0.25, 1.0]],
    )


def test_landsat_scaling():

    values = np.array(
        [[0, 7273, 10000, 20000]],
        dtype=np.uint16,
    )

    result = convert_array(
        values,
        LANDSAT_C2_L2_SR_SPEC,
    )

    assert np.isnan(result[0, 0])

    expected = (
        values.astype(np.float32)
        * np.float32(0.0000275)
        + np.float32(-0.2)
    )

    np.testing.assert_allclose(
        result[0, 1:],
        expected[0, 1:],
        rtol=1e-6,
        atol=1e-6,
    )

def test_output_is_float32():

    values = np.array(
        [[1000, 2000]],
        dtype=np.uint16,
    )

    result = convert_array(
        values,
        SENTINEL2_L2A_SPEC,
    )

    assert result.dtype == np.float32


def test_windowed_raster_conversion(tmp_path):

    input_path = tmp_path / "input.tif"
    output_path = tmp_path / "output.tif"

    transform = from_origin(
        500000,
        2500000,
        10,
        10,
    )

    data = np.full(
        (2048, 2048),
        2500,
        dtype=np.uint16,
    )

    with rasterio.open(
        input_path,
        "w",
        driver="GTiff",
        width=2048,
        height=2048,
        count=1,
        dtype="uint16",
        crs="EPSG:32643",
        transform=transform,
    ) as dst:

        dst.write(data, 1)

    convert_raster(
        input_path,
        output_path,
        SENTINEL2_L2A_SPEC,
        window_size=256,
    )

    with rasterio.open(output_path) as src:

        assert src.width == 2048
        assert src.height == 2048
        assert src.dtypes == ("float32",)
        assert src.crs.to_string() == "EPSG:32643"

        sample = src.read(
            1,
            window=((0, 256), (0, 256)),
        )

        np.testing.assert_allclose(
            sample,
            0.25,
        )


def test_raster_conversion_masks_source_nodata(tmp_path):
    input_path = tmp_path / "landsat.tif"
    output_path = tmp_path / "landsat_reflectance.tif"
    with rasterio.open(input_path, "w", driver="GTiff", width=4, height=2,
                       count=1, dtype="uint16", crs="EPSG:32643",
                       transform=from_origin(500000, 2500000, 30, 30),
                       nodata=0) as dst:
        dst.write(np.array([[0, 1000, 2000, 3000], [4000, 5000, 6000, 7000]], dtype=np.uint16), 1)

    convert_raster(input_path, output_path, LANDSAT_C2_L2_SR_SPEC, window_size=2)
    with rasterio.open(output_path) as src:
        result = src.read(1)
        assert np.isnan(src.nodata)
        assert np.isnan(result[0, 0])
        np.testing.assert_allclose(result[0, 1], 1000 * 0.0000275 - 0.2)
