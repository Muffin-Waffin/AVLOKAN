from pipeline.acquisition.models import Scene
from pipeline.acquisition.unified_catalog import UnifiedCatalog


def make_scene(
    scene_id: str,
    sensor: str,
    date: str,
) -> Scene:

    return Scene(
        scene_id=scene_id,
        sensor=sensor,
        collection="test",
        acquisition_datetime=date,
        bbox=[75.8, 22.7, 75.9, 22.8],
        footprint={
            "type": "Polygon",
            "coordinates": [],
        },
    )


def test_sensor_filter(tmp_path):

    catalog = UnifiedCatalog(
        tmp_path / "scenes.json"
    )

    catalog.add_many(
        [
            make_scene(
                "s2-001",
                "sentinel-2",
                "2025-03-20T00:00:00+00:00",
            ),
            make_scene(
                "s1-001",
                "sentinel-1",
                "2025-03-21T00:00:00+00:00",
            ),
            make_scene(
                "landsat-001",
                "landsat",
                "2025-03-22T00:00:00+00:00",
            ),
        ]
    )

    assert len(
        catalog.by_sensor("sentinel-2")
    ) == 1

    assert len(
        catalog.by_sensor("LANDSAT")
    ) == 1


def test_date_filter(tmp_path):

    catalog = UnifiedCatalog(
        tmp_path / "scenes.json"
    )

    catalog.add_many(
        [
            make_scene(
                "s1",
                "sentinel-1",
                "2025-03-01T00:00:00+00:00",
            ),
            make_scene(
                "s2",
                "sentinel-2",
                "2025-03-15T00:00:00+00:00",
            ),
            make_scene(
                "s3",
                "sentinel-2",
                "2025-04-01T00:00:00+00:00",
            ),
        ]
    )

    results = catalog.by_date_range(
        "2025-03-01T00:00:00+00:00",
        "2025-03-31T23:59:59+00:00",
    )

    assert len(results) == 2


def test_download_status(tmp_path):

    catalog = UnifiedCatalog(
        tmp_path / "scenes.json"
    )

    scene = make_scene(
        "downloaded",
        "sentinel-2",
        "2025-03-01T00:00:00+00:00",
    )

    scene.downloaded = True

    catalog.add(scene)

    catalog.add(
        make_scene(
            "pending",
            "landsat",
            "2025-03-02T00:00:00+00:00",
        )
    )

    assert len(catalog.downloaded()) == 1
    assert len(catalog.pending_downloads()) == 1
