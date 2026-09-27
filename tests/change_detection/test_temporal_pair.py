from datetime import date

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from pipeline.change_detection.temporal_pair import TemporalPair, TemporalPairError


@pytest.fixture
def rasters(tmp_path):
    paths = []
    for name, width, crs, xoff in (("a", 8, "EPSG:32643", 500000), ("b", 8, "EPSG:32643", 500000)):
        path = tmp_path / f"{name}.tif"
        with rasterio.open(path, "w", driver="GTiff", width=width, height=8, count=4,
                           dtype="uint16", crs=crs, transform=from_origin(xoff, 2500000, 10, 10)) as dst:
            dst.write(np.ones((4, 8, 8), dtype="uint16"))
        paths.append(path)
    return paths


def test_valid_pair_captures_spatial_metadata(rasters):
    pair = TemporalPair.from_paths(tile_id="tile-a", t1_path=rasters[0], t2_path=rasters[1],
                                   t1_date="2025-03-24", t2_date="2025-03-29")
    assert pair.width == pair.height == 8
    assert pair.resolution == (10, 10)
    assert pair.crs == "EPSG:32643"
    assert pair.t1_date.date() == date(2025, 3, 24)


def test_invalid_order_rejected(rasters):
    with pytest.raises(TemporalPairError, match="earlier"):
        TemporalPair.from_paths(tile_id="x", t1_path=rasters[0], t2_path=rasters[1],
                                t1_date="2025-03-29", t2_date="2025-03-24")


def test_reversed_dates_can_preserve_explicit_input_order(rasters):
    pair = TemporalPair.from_paths(
        tile_id="x", t1_path=rasters[0], t2_path=rasters[1],
        t1_date="2025-03-29", t2_date="2025-03-24",
        allow_reversed_dates=True,
    )
    assert pair.t1_path == rasters[0]
    assert pair.t2_path == rasters[1]
    assert pair.t1_date > pair.t2_date


def test_missing_file_rejected(rasters, tmp_path):
    with pytest.raises(TemporalPairError, match="does not exist"):
        TemporalPair.from_paths(tile_id="x", t1_path=tmp_path / "missing.tif", t2_path=rasters[1],
                                t1_date="2025-03-24", t2_date="2025-03-29")


def test_dimension_mismatch_rejected(rasters, tmp_path):
    short = tmp_path / "short.tif"
    with rasterio.open(short, "w", driver="GTiff", width=7, height=8, count=4, dtype="uint16",
                       crs="EPSG:32643", transform=from_origin(500000, 2500000, 10, 10)) as dst:
        dst.write(np.ones((4, 8, 7), dtype="uint16"))
    with pytest.raises(TemporalPairError, match="dimensions"):
        TemporalPair.from_paths(tile_id="x", t1_path=rasters[0], t2_path=short,
                                t1_date="2025-03-24", t2_date="2025-03-29")


def test_crs_mismatch_rejected(rasters, tmp_path):
    other = tmp_path / "other.tif"
    with rasterio.open(other, "w", driver="GTiff", width=8, height=8, count=4, dtype="uint16",
                       crs="EPSG:32644", transform=from_origin(500000, 2500000, 10, 10)) as dst:
        dst.write(np.ones((4, 8, 8), dtype="uint16"))
    with pytest.raises(TemporalPairError, match="CRS mismatch"):
        TemporalPair.from_paths(tile_id="x", t1_path=rasters[0], t2_path=other,
                                t1_date="2025-03-24", t2_date="2025-03-29")
