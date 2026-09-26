from pipeline.acquisition.sentinel1 import (
    SENTINEL1_COLLECTION,
    scene_from_stac,
)


def test_scene_from_stac():
    feature = {
        "id": "S1_TEST",
        "bbox": [75.8, 22.7, 75.9, 22.8],
        "geometry": {
            "type": "Polygon",
            "coordinates": [],
        },
        "properties": {
            "datetime": "2025-03-29T05:28:41Z",
            "sat:orbit_state": "ascending",
            "sar:polarizations": ["VV", "VH"],
        },
    }

    scene = scene_from_stac(feature)

    assert scene.scene_id == "S1_TEST"
    assert scene.sensor == "sentinel-1"
    assert scene.collection == SENTINEL1_COLLECTION
    assert scene.orbit_direction == "ascending"
    assert scene.polarization == ["VV", "VH"]


def test_sentinel1_collection():
    assert SENTINEL1_COLLECTION == "sentinel-1-grd"