from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from pipeline.preprocessing.scl_alignment import (
    SCLAlignmentError,
    align_scl_to_reference,
)


def create_raster(
    path: Path,
    *,
    width: int,
    height: int,
    resolution: float,
    dtype: str,
    values: np.ndarray,
) -> None:
    transform = from_origin(
        0,
        height * resolution,
        resolution,
        resolution,
    )

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype=dtype,
        crs="EPSG:32643",
        transform=transform,
    ) as dst:
        dst.write(values, 1)


def test_scl_is_resampled_to_reference_grid(tmp_path):
    scl = tmp_path / "scl.tif"
    reference = tmp_path / "reference.tif"
    output = tmp_path / "aligned.tif"

    scl_values = np.array(
        [
            [4, 5],
            [6, 8],
        ],
        dtype=np.uint8,
    )

    reference_values = np.zeros(
        (4, 4),
        dtype=np.uint16,
    )

    create_raster(
        scl,
        width=2,
        height=2,
        resolution=20,
        dtype="uint8",
        values=scl_values,
    )

    create_raster(
        reference,
        width=4,
        height=4,
        resolution=10,
        dtype="uint16",
        values=reference_values,
    )

    result = align_scl_to_reference(
        scl,
        reference,
        output,
    )

    assert result == output
    assert output.exists()

    with rasterio.open(output) as src:
        assert src.width == 4
        assert src.height == 4
        assert src.crs.to_string() == "EPSG:32643"
        assert src.res == (10.0, 10.0)
        assert src.dtypes[0] == "uint8"

        data = src.read(1)

    expected = np.array(
        [
            [4, 4, 5, 5],
            [4, 4, 5, 5],
            [6, 6, 8, 8],
            [6, 6, 8, 8],
        ],
        dtype=np.uint8,
    )

    np.testing.assert_array_equal(data, expected)


def test_missing_scl_raises(tmp_path):
    reference = tmp_path / "reference.tif"
    output = tmp_path / "aligned.tif"

    values = np.zeros(
        (2, 2),
        dtype=np.uint16,
    )

    create_raster(
        reference,
        width=2,
        height=2,
        resolution=10,
        dtype="uint16",
        values=values,
    )

    missing_scl = tmp_path / "missing.tif"

    try:
        align_scl_to_reference(
            missing_scl,
            reference,
            output,
        )
        assert False, "Expected SCLAlignmentError"
    except SCLAlignmentError:
        pass


def test_missing_reference_raises(tmp_path):
    scl = tmp_path / "scl.tif"
    output = tmp_path / "aligned.tif"

    values = np.ones(
        (2, 2),
        dtype=np.uint8,
    )

    create_raster(
        scl,
        width=2,
        height=2,
        resolution=20,
        dtype="uint8",
        values=values,
    )

    missing_reference = tmp_path / "missing_reference.tif"

    try:
        align_scl_to_reference(
            scl,
            missing_reference,
            output,
        )
        assert False, "Expected SCLAlignmentError"
    except SCLAlignmentError:
        pass
