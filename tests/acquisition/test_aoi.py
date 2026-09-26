import json

import pytest

from pipeline.acquisition.aoi import (
    AOIError,
    get_bbox,
    load_aoi,
)


def create_aoi_file(tmp_path):
    aoi = {
        "type": "Feature",
        "properties": {
            "name": "test-area"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [75.80, 22.70],
                    [75.90, 22.70],
                    [75.90, 22.80],
                    [75.80, 22.80],
                    [75.80, 22.70],
                ]
            ],
        },
    }

    path = tmp_path / "test_aoi.geojson"

    with path.open("w", encoding="utf-8") as file:
        json.dump(aoi, file)

    return path


def test_load_valid_aoi(tmp_path):
    path = create_aoi_file(tmp_path)

    aoi = load_aoi(path)

    assert aoi["type"] == "Feature"
    assert aoi["geometry"]["type"] == "Polygon"


def test_get_bbox(tmp_path):
    path = create_aoi_file(tmp_path)

    aoi = load_aoi(path)

    bbox = get_bbox(aoi)

    assert bbox == [75.80, 22.70, 75.90, 22.80]


def test_missing_aoi():
    with pytest.raises(AOIError):
        load_aoi("does_not_exist.geojson")


def test_invalid_geometry(tmp_path):
    aoi = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Point",
            "coordinates": [75.8, 22.7],
        },
    }

    path = tmp_path / "invalid.geojson"

    with path.open("w", encoding="utf-8") as file:
        json.dump(aoi, file)

    with pytest.raises(AOIError):
        load_aoi(path)