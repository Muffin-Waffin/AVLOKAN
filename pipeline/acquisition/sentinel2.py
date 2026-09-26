from __future__ import annotations

from typing import Any

from pipeline.acquisition.aoi import get_bbox
from pipeline.acquisition.cdse import CDSEClient
from pipeline.acquisition.models import Scene


SENTINEL2_COLLECTION = "sentinel-2-l2a"


def scene_from_stac(feature: dict[str, Any]) -> Scene:
    """
    Convert a Sentinel-2 STAC feature into AVLOKAN's
    internal Scene representation.
    """

    properties = feature.get("properties", {})

    return Scene(
        scene_id=feature["id"],
        sensor="sentinel-2",
        collection=SENTINEL2_COLLECTION,
        acquisition_datetime=properties["datetime"],
        bbox=feature["bbox"],
        footprint=feature["geometry"],
        cloud_cover=properties.get("eo:cloud_cover"),
        source_url=feature.get("self_href"),
    )


def search_sentinel2(
    aoi: dict[str, Any],
    start: str,
    end: str,
    max_cloud_cover: float = 20,
    limit: int = 100,
    client: CDSEClient | None = None,
) -> list[Scene]:
    """
    Search Sentinel-2 L2A scenes intersecting an AOI.
    """

    if client is None:
        client = CDSEClient()

    bbox = get_bbox(aoi)

    result = client.search(
        collection=SENTINEL2_COLLECTION,
        bbox=bbox,
        start=start,
        end=end,
        limit=limit,
        cloud_cover=max_cloud_cover,
    )

    features = result.get("features", [])

    return [
        scene_from_stac(feature)
        for feature in features
    ]
