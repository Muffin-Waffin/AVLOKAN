import json

import numpy as np
import rasterio
from rasterio.transform import from_origin

from pipeline.indexing.catalog_builder import build_tile_catalog
from pipeline.indexing.tile_catalog import TileCatalog, TileMetadata


def make_tile(path, x=500000):
    with rasterio.open(path, "w", driver="GTiff", width=8, height=8,
                       count=2, dtype="uint16", crs="EPSG:32643",
                       transform=from_origin(x, 2500000, 10, 10), nodata=0) as dst:
        dst.write(np.ones((2, 8, 8), dtype=np.uint16))


def test_catalog_builder_and_repeat_run_do_not_duplicate(tmp_path):
    root = tmp_path / "tiles"
    folder = root / "scene_a"
    folder.mkdir(parents=True)
    make_tile(folder / "tile_000000.tif")
    make_tile(folder / "tile_000001.tif", 500080)
    manifest = {"source": "source_scene.tif", "tiles": [
        {"path": str(folder / "tile_000000.tif"), "source_scene": "scene_a",
         "sensor": "sentinel-2", "acquisition_date": "2025-03-29", "valid_fraction": 0.9},
    ]}
    (folder / "tiles.json").write_text(json.dumps(manifest))
    catalog_path = tmp_path / "catalog/tiles.json"

    first = build_tile_catalog(root, catalog_path)
    second = build_tile_catalog(root, catalog_path)
    catalog = TileCatalog(catalog_path)

    assert first.added == 2
    assert second.added == 0
    assert second.updated == 0
    assert catalog.count() == 2
    item = catalog.get_tile("scene_a__tile_000000")
    assert item is not None
    assert item.source_scene_id == "scene_a"
    assert item.sensor == "sentinel-2"
    assert item.acquisition_datetime == "2025-03-29"
    assert item.width == item.height == 8
    assert item.crs == "EPSG:32643"
    assert item.band_count == 2
    assert item.dtype == "uint16"
    assert item.valid_fraction == 0.9
    assert catalog_path.exists()


def test_catalog_reload_lookup_listing_and_filters(tmp_path):
    path = tmp_path / "tiles.json"
    catalog = TileCatalog(path)
    rows = [
        TileMetadata("a", "s1", "sentinel-2", "2025-03-29T05:00:00Z", "a.tif", 256, 256,
                     "EPSG:32643", (10.0, 10.0), (0.0, 0.0, 10.0, 10.0), tuple(range(9)), 4, "uint16", 0.9),
        TileMetadata("b", "s2", "landsat", "2025-04-10", "b.tif", 256, 256,
                     "EPSG:32643", (30.0, 30.0), (20.0, 20.0, 30.0, 30.0), tuple(range(9)), 1, "float32", 1.0),
    ]
    catalog.upsert_many(rows)
    reloaded = TileCatalog(path)
    assert reloaded.get_tile("a").tile_id == "a"
    assert [x.tile_id for x in reloaded.list_tiles()] == ["a", "b"]
    assert [x.tile_id for x in reloaded.filter_tiles(sensor="SENTINEL-2")] == ["a"]
    assert [x.tile_id for x in reloaded.filter_tiles(start_date="2025-03-29", end_date="2025-03-29")] == ["a"]
    assert [x.tile_id for x in reloaded.filter_tiles(bbox=(5, 5, 25, 25))] == ["a", "b"]
    assert reloaded.filter_tiles(bbox=(100, 100, 101, 101)) == []


def test_upsert_prevents_duplicates_and_updates_metadata(tmp_path):
    catalog = TileCatalog(tmp_path / "tiles.json")
    record = TileMetadata("id", "scene", None, None, "tile.tif", 1, 1, "EPSG:32643",
                          (1.0, 1.0), (0.0, 0.0, 1.0, 1.0), tuple(range(9)), 1, "uint8", 1.0)
    assert catalog.upsert_many([record]) == (1, 0)
    revised = TileMetadata(**{**record.to_dict(), "valid_fraction": 0.5})
    assert catalog.upsert_many([revised]) == (0, 1)
    assert catalog.count() == 1
    assert catalog.get_tile("id").valid_fraction == 0.5


def test_builder_preserves_old_record_and_reports_missing_file(tmp_path):
    catalog_path = tmp_path / "catalog.json"
    catalog = TileCatalog(catalog_path)
    record = TileMetadata("old", "scene", None, None, str(tmp_path / "gone.tif"),
                          1, 1, "EPSG:32643", (1.0, 1.0), (0.0, 0.0, 1.0, 1.0),
                          tuple(range(9)), 1, "uint8", 1.0)
    catalog.upsert_many([record])
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    report = build_tile_catalog(empty_root, catalog_path)
    assert report.total == 1
    assert report.missing_files == ("old",)
    assert TileCatalog(catalog_path).get_tile("old") is not None
