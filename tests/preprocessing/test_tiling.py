import json

import numpy as np
import rasterio
from rasterio.transform import from_origin

from pipeline.preprocessing.tiling import tile_raster


def test_tiles_are_fixed_size_georeferenced_and_keep_metadata(tmp_path):
    source = tmp_path / "scene.tif"
    with rasterio.open(source, "w", driver="GTiff", width=300, height=270,
                       count=2, dtype="uint16", crs="EPSG:32643",
                       transform=from_origin(500000, 2500000, 10, 10), nodata=0) as dst:
        dst.write(np.ones((2, 270, 300), dtype=np.uint16))

    tiles = tile_raster(source, tmp_path / "tiles", scene="scene",
                        sensor="sentinel-2", acquisition_date="2025-03-29")
    assert len(tiles) == 4
    first = tiles[0]
    assert first.tile_id == "tile_000000"
    assert first.crs == "EPSG:32643"
    assert first.sensor == "sentinel-2"
    assert first.acquisition_date == "2025-03-29"
    assert first.transform == tuple(from_origin(500000, 2500000, 10, 10))
    with rasterio.open(first.path) as src:
        assert (src.width, src.height, src.count) == (256, 256, 2)
        assert src.nodata == 0
        assert src.transform == from_origin(500000, 2500000, 10, 10)
    assert json.loads((tmp_path / "tiles/scene/tiles.json").read_text())["rejected_tiles"] == 0


def test_tiles_reject_low_valid_fraction_and_pad_with_nodata(tmp_path):
    source = tmp_path / "masked.tif"
    values = np.ones((20, 20), dtype=np.uint8)
    values[:10, :] = 0
    with rasterio.open(source, "w", driver="GTiff", width=20, height=20,
                       count=1, dtype="uint8", crs="EPSG:32643",
                       transform=from_origin(0, 200, 10, 10), nodata=0) as dst:
        dst.write(values, 1)

    tiles = tile_raster(source, tmp_path / "tiles", tile_size=16,
                        min_valid_fraction=0.5)
    assert tiles == []
    manifest = json.loads((tmp_path / "tiles/masked/tiles.json").read_text())
    assert manifest["rejected_tiles"] == 4
