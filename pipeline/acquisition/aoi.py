from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AOIError(ValueError):
    """Raised when an Area of Interest is invalid."""


def load_aoi(path: str | Path) -> dict[str, Any]:
    """
    Load and validate a GeoJSON Area of Interest.

    The current implementation expects a GeoJSON Feature
    containing a Polygon or MultiPolygon geometry.
    """

    path = Path(path)

    if not path.exists():
        raise AOIError(f"AOI file does not exist: {path}")

    if not path.is_file():
        raise AOIError(f"AOI path is not a file: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            geojson = json.load(file)
    except json.JSONDecodeError as exc:
        raise AOIError(f"Invalid JSON in AOI file: {path}") from exc

    if geojson.get("type") != "Feature":
        raise AOIError("AOI must be a GeoJSON Feature.")

    geometry = geojson.get("geometry")

    if not geometry:
        raise AOIError("AOI Feature has no geometry.")

    geometry_type = geometry.get("type")

    if geometry_type not in {"Polygon", "MultiPolygon"}:
        raise AOIError(
            "AOI geometry must be Polygon or MultiPolygon, "
            f"got: {geometry_type}"
        )

    coordinates = geometry.get("coordinates")

    if not coordinates:
        raise AOIError("AOI geometry has no coordinates.")

    return geojson


def get_geometry(aoi: dict[str, Any]) -> dict[str, Any]:
    """Return the geometry portion of a validated AOI."""

    geometry = aoi.get("geometry")

    if not geometry:
        raise AOIError("AOI has no geometry.")

    return geometry


def get_bbox(aoi: dict[str, Any]) -> list[float]:
    """
    Calculate the bounding box of the AOI.

    Returns:
        [min_longitude, min_latitude, max_longitude, max_latitude]
    """

    geometry = get_geometry(aoi)
    geometry_type = geometry["type"]
    coordinates = geometry["coordinates"]

    points: list[tuple[float, float]] = []

    if geometry_type == "Polygon":
        for ring in coordinates:
            for point in ring:
                points.append((point[0], point[1]))

    elif geometry_type == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon:
                for point in ring:
                    points.append((point[0], point[1]))

    if not points:
        raise AOIError("AOI contains no coordinate points.")

    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]

    return [
        min(longitudes),
        min(latitudes),
        max(longitudes),
        max(latitudes),
    ]