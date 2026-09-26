from __future__ import annotations

from typing import Any

from pystac_client import Client

from pipeline.acquisition.aoi import get_bbox
from pipeline.acquisition.models import Scene


LANDSAT_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
LANDSAT_COLLECTION = "landsat-c2-l2"


def _client() -> Client:
    return Client.open(LANDSAT_STAC_URL)


def scene_from_stac(item: Any) -> Scene:
    properties = item.properties

    return Scene(
        scene_id=item.id,
        sensor="landsat",
        collection=LANDSAT_COLLECTION,
        acquisition_datetime=item.datetime.isoformat()
        if item.datetime
        else properties.get("datetime"),
        bbox=list(item.bbox),
        footprint=item.geometry,
        cloud_cover=properties.get("eo:cloud_cover"),
        source_url=item.self_href,
    )


def search_landsat(
    aoi: dict[str, Any],
    start: str,
    end: str,
    *,
    max_cloud_cover: float = 20,
    limit: int = 100,
) -> list[Scene]:

    bbox = get_bbox(aoi)

    search = _client().search(
        collections=[LANDSAT_COLLECTION],
        bbox=bbox,
        datetime=f"{start}/{end}",
        max_items=limit,
    )

    scenes = []

    for item in search.items():
        cloud_cover = item.properties.get(
            "eo:cloud_cover"
        )

        if (
            cloud_cover is not None
            and cloud_cover > max_cloud_cover
        ):
            continue

        scenes.append(scene_from_stac(item))

    return scenes
