from pipeline.acquisition.catalog import SceneCatalog
from pipeline.acquisition.models import Scene


def create_scene(scene_id: str) -> Scene:
    return Scene(
        scene_id=scene_id,
        sensor="sentinel-2",
        collection="sentinel-2-l2a",
        acquisition_datetime="2025-01-01T00:00:00Z",
        bbox=[75.8, 22.7, 75.9, 22.8],
        footprint={
            "type": "Polygon",
            "coordinates": [],
        },
        cloud_cover=5.0,
    )


def test_add_scene(tmp_path):
    catalog_path = tmp_path / "scenes.json"
    catalog = SceneCatalog(catalog_path)

    scene = create_scene("scene-001")

    assert catalog.add(scene) is True
    assert catalog.count() == 1


def test_duplicate_scene_is_not_added(tmp_path):
    catalog_path = tmp_path / "scenes.json"
    catalog = SceneCatalog(catalog_path)

    scene = create_scene("scene-001")

    assert catalog.add(scene) is True
    assert catalog.add(scene) is False
    assert catalog.count() == 1


def test_get_scene(tmp_path):
    catalog_path = tmp_path / "scenes.json"
    catalog = SceneCatalog(catalog_path)

    scene = create_scene("scene-001")

    catalog.add(scene)

    result = catalog.get("scene-001")

    assert result is not None
    assert result.scene_id == "scene-001"


def test_get_missing_scene(tmp_path):
    catalog_path = tmp_path / "scenes.json"
    catalog = SceneCatalog(catalog_path)

    assert catalog.get("does-not-exist") is None


def test_catalog_persists(tmp_path):
    catalog_path = tmp_path / "scenes.json"

    catalog = SceneCatalog(catalog_path)
    catalog.add(create_scene("scene-001"))

    # Create a completely new catalog object.
    new_catalog = SceneCatalog(catalog_path)

    assert new_catalog.count() == 1

    scene = new_catalog.get("scene-001")

    assert scene is not None
    assert scene.sensor == "sentinel-2"