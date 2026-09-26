from __future__ import annotations

from typing import Any

from pipeline.acquisition.aoi import get_bbox
from pipeline.acquisition.cdse import CDSEClient
from pipeline.acquisition.models import Scene


SENTINEL1_COLLECTION = "sentinel-1-grd"


def scene_from_stac(feature: dict[str, Any]) -> Scene:
    properties = feature.get("properties", {})

    return Scene(
        scene_id=feature["id"],
        sensor="sentinel-1",
        collection=SENTINEL1_COLLECTION,
        acquisition_datetime=properties["datetime"],
        bbox=feature["bbox"],
        footprint=feature["geometry"],
        cloud_cover=None,
        orbit_direction=properties.get("sat:orbit_state"),
        polarization=properties.get("sar:polarizations"),
        source_url=feature.get("self_href"),
    )


def search_sentinel1(
    aoi: dict[str, Any],
    start: str,
    end: str,
    limit: int = 100,
    client: CDSEClient | None = None,
) -> list[Scene]:

    if client is None:
        client = CDSEClient()

    bbox = get_bbox(aoi)

    result = client.search(
        collection=SENTINEL1_COLLECTION,
        bbox=bbox,
        start=start,
        end=end,
        limit=limit,
    )

    features = result.get("features", [])

    return [
        scene_from_stac(feature)
        for feature in features
    ]