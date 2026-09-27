import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from pipeline.change_detection.ndvi import compute_delta_ndvi, compute_ndvi, compute_temporal_ndvi
from pipeline.change_detection.preprocessing import read_model_tensor
from rasterio.windows import Window


@pytest.fixture
def source_pair(tmp_path):
    paths = []
    arrays = [
        np.array([[0.2, 0.0, -9999.0], [0.1, 0.1, 0.0]], dtype=np.float32),
        np.array([[0.6, 0.0, 0.3], [0.0, 0.3, 0.0]], dtype=np.float32),
    ]
    for name, red, nir, x in (
        ("t1", arrays[0], arrays[1], 500000),
        ("t2", np.where(arrays[0] == -9999.0, -9999.0, arrays[0] * 0.5), arrays[1], 500000),
    ):
        path = tmp_path / f"{name}.tif"
        data = np.stack([np.ones((2, 3), dtype=np.float32), np.ones((2, 3), dtype=np.float32), red, nir])
        with rasterio.open(
            path, "w", driver="GTiff", width=3, height=2, count=4,
            dtype="float32", nodata=-9999.0, crs="EPSG:32643",
            transform=from_origin(x, 2500000, 10, 10),
        ) as dst:
            dst.write(data)
        paths.append(path)
    return paths


def test_ndvi_formula_nodata_zero_division_dtype_and_georeferencing(source_pair, tmp_path):
    output = tmp_path / "ndvi.tif"
    compute_ndvi(source_pair[0], output)
    with rasterio.open(source_pair[0]) as source, rasterio.open(output) as result:
        values = result.read(1, masked=True)
        assert values.dtype == np.float32
        assert (result.width, result.height) == (source.width, source.height)
        assert result.crs == source.crs
        assert result.transform == source.transform
        assert values[0, 0] == pytest.approx((0.6 - 0.2) / (0.6 + 0.2))
        assert np.ma.getmaskarray(values)[0, 1]  # zero denominator
        assert np.ma.getmaskarray(values)[0, 2]  # source nodata
        assert np.isfinite(values.compressed()).all()


def test_delta_is_t2_minus_t1_and_preserves_invalid_pixels(source_pair, tmp_path):
    first, second = tmp_path / "t1_ndvi.tif", tmp_path / "t2_ndvi.tif"
    delta = tmp_path / "delta.tif"
    compute_ndvi(source_pair[0], first)
    compute_ndvi(source_pair[1], second)
    compute_delta_ndvi(first, second, delta)
    with rasterio.open(first) as a, rasterio.open(second) as b, rasterio.open(delta) as result:
        av, bv, dv = a.read(1, masked=True), b.read(1, masked=True), result.read(1, masked=True)
        assert dv[1, 1] == pytest.approx(float(bv[1, 1] - av[1, 1]))
        assert result.tags()["formula"] == "NDVI_T2 - NDVI_T1"
        assert np.ma.getmaskarray(dv)[0, 1]
        assert np.isfinite(dv.compressed()).all()


def test_temporal_ndvi_rejects_misaligned_input_grids(source_pair, tmp_path):
    misaligned = tmp_path / "misaligned.tif"
    with rasterio.open(source_pair[1]) as src:
        profile = src.profile.copy()
        profile.update(transform=from_origin(500010, 2500000, 10, 10))
        with rasterio.open(misaligned, "w", **profile) as dst:
            dst.write(src.read())
    with pytest.raises(ValueError, match="transforms"):
        compute_temporal_ndvi(
            source_pair[0], misaligned,
            tmp_path / "a.tif", tmp_path / "b.tif", tmp_path / "d.tif",
        )


def test_bit_rgb_mapping_uses_b04_b03_b02_from_phase2_stack(tmp_path):
    source = tmp_path / "four_band.tif"
    data = np.stack([np.full((2, 2), v, dtype=np.float32) for v in (0.1, 0.2, 0.3, 0.4)])
    with rasterio.open(
        source, "w", driver="GTiff", width=2, height=2, count=4,
        dtype="float32", crs="EPSG:32643", transform=from_origin(500000, 2500000, 10, 10),
    ) as dst:
        dst.write(data)
    tensor, valid = read_model_tensor(source, Window(0, 0, 2, 2), size=2)
    np.testing.assert_allclose(tensor[0, :, 0, 0].numpy(), [-0.4, -0.6, -0.8])
    assert valid.all()
