"""Extract a compact, local Indore-area GeoJSON set from the India PBF."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import osmium


ROOT = Path(__file__).resolve().parents[3]
PBF = ROOT / "data/map/osm/source/india-latest.osm.pbf"
OUTPUT = ROOT / "frontend/assets/osm"
SCRATCH = ROOT / "data/map/osm/tmp/node-locations.cache"
# Match the already-local Sentinel-2 demo footprint coverage, with enough
# surrounding geography for Indore-area navigation.
WEST, SOUTH, EAST, NORTH = 74.7, 22.2, 76.4, 23.8

FILES = {
    "roads_major": "roads-major.geojson",
    "roads_local": "roads-local.geojson",
    "water": "water.geojson",
    "context": "context.geojson",
    "buildings": "buildings.geojson",
    "places_major": "places-major.geojson",
    "places_local": "places-local.geojson",
    "boundaries": "boundaries.geojson",
}
ROAD_MAJOR = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary",
    "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link",
}
ROAD_LOCAL = {"residential", "unclassified", "service", "living_street"}
WATERWAYS = {"river", "stream", "canal", "ditch", "drain"}
LANDUSE = {
    "residential", "commercial", "industrial", "retail", "forest", "farmland",
    "meadow", "grass", "park", "recreation_ground", "cemetery", "orchard",
    "vineyard", "quarry", "military", "nature_reserve",
}
NATURAL_AREAS = {"wood", "water", "wetland", "scrub", "grassland", "heath", "beach"}
PLACE_MAJOR = {"city", "town"}
PLACE_LOCAL = {"village", "suburb", "hamlet"}
KEEP_TAGS = (
    "highway", "name", "name:en", "ref", "place", "waterway", "water",
    "building", "landuse", "natural", "boundary", "admin_level",
)


def clip_segment(a: tuple[float, float], b: tuple[float, float]):
    """Liang-Barsky clip of an (lon, lat) segment to the configured bbox."""
    x0, y0 = a
    dx, dy = b[0] - x0, b[1] - y0
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, x0 - WEST), (dx, EAST - x0), (-dy, y0 - SOUTH), (dy, NORTH - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi:
            return None
    return (x0 + lo * dx, y0 + lo * dy), (x0 + hi * dx, y0 + hi * dy)


def clipped_lines(coords: list[tuple[float, float]]):
    lines: list[list[list[float]]] = []
    current: list[list[float]] = []
    for a, b in zip(coords, coords[1:]):
        segment = clip_segment(a, b)
        if segment is None:
            if len(current) > 1:
                lines.append(current)
            current = []
            continue
        start, end = segment
        start, end = [list(start), list(end)]
        if current and current[-1] == start:
            if current[-1] != end:
                current.append(end)
        else:
            if len(current) > 1:
                lines.append(current)
            current = [start, end]
    if len(current) > 1:
        lines.append(current)
    if not lines:
        return None
    if len(lines) == 1:
        return {"type": "LineString", "coordinates": lines[0]}
    return {"type": "MultiLineString", "coordinates": lines}


def clip_ring(coords: list[tuple[float, float]]):
    """Sutherland-Hodgman clip of a closed way ring to the bbox rectangle."""
    points = list(coords[:-1] if len(coords) > 1 and coords[0] == coords[-1] else coords)
    edges = (
        (lambda p: p[0] >= WEST, lambda a, b: (WEST, a[1] + (b[1] - a[1]) * (WEST - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= EAST, lambda a, b: (EAST, a[1] + (b[1] - a[1]) * (EAST - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= SOUTH, lambda a, b: (a[0] + (b[0] - a[0]) * (SOUTH - a[1]) / (b[1] - a[1]), SOUTH)),
        (lambda p: p[1] <= NORTH, lambda a, b: (a[0] + (b[0] - a[0]) * (NORTH - a[1]) / (b[1] - a[1]), NORTH)),
    )
    for inside, intersect in edges:
        if not points:
            return None
        source, points = points, []
        previous = source[-1]
        for current in source:
            if inside(current):
                if not inside(previous):
                    points.append(intersect(previous, current))
                points.append(current)
            elif inside(previous):
                points.append(intersect(previous, current))
            previous = current
    if len(points) < 3:
        return None
    points.append(points[0])
    return [[float(x), float(y)] for x, y in points]


def geometry_for_way(way, closed: bool):
    coords = []
    try:
        for node in way.nodes:
            if not node.location.valid():
                return None
            coords.append((node.lon, node.lat))
    except (RuntimeError, ValueError):
        return None
    if closed:
        ring = clip_ring(coords)
        return {"type": "Polygon", "coordinates": [ring]} if ring else None
    return clipped_lines(coords)


def write_feature(handles, counts: Counter, category: str, obj, tags, geometry):
    if geometry is None:
        return
    properties = {"osm_id": int(obj.id), "osm_type": "node" if obj.is_node() else "way", "layer": category}
    for key in KEEP_TAGS:
        value = tags.get(key)
        if value:
            properties[key] = value
    feature = {"type": "Feature", "geometry": geometry, "properties": properties}
    handle = handles[category]
    if counts[category]:
        handle.write(",")
    json.dump(feature, handle, ensure_ascii=False, separators=(",", ":"))
    counts[category] += 1


def main():
    if not PBF.is_file():
        raise FileNotFoundError(f"Verified source PBF missing: {PBF}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    SCRATCH.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    counts = Counter()
    handles = {}
    try:
        with contextlib.ExitStack() as stack:
            for category, filename in FILES.items():
                handle = stack.enter_context((OUTPUT / filename).open("w", encoding="utf-8", newline=""))
                handle.write('{"type":"FeatureCollection","features":[')
                handles[category] = handle

            way_filter = osmium.filter.KeyFilter(
                "highway", "waterway", "boundary", "building", "landuse", "natural", "water"
            ).enable_for(osmium.osm.WAY)
            pool = osmium.io.ThreadPool(num_threads=4, max_queue_size=4)
            processor = (
                osmium.FileProcessor(PBF, thread_pool=pool)
                .with_locations(f"sparse_file_array,{SCRATCH}")
                .with_filter(way_filter)
            )
            seen = 0
            for obj in processor:
                seen += 1
                if seen % 2_000_000 == 0:
                    print(f"Scanned {seen:,} OSM objects; exported {sum(counts.values()):,} features", flush=True)
                tags = obj.tags
                if obj.is_node():
                    place = tags.get("place")
                    if place not in PLACE_MAJOR | PLACE_LOCAL:
                        continue
                    if not obj.location.valid() or not (WEST <= obj.lon <= EAST and SOUTH <= obj.lat <= NORTH):
                        continue
                    category = "places_major" if place in PLACE_MAJOR else "places_local"
                    geom = {"type": "Point", "coordinates": [obj.lon, obj.lat]}
                    write_feature(handles, counts, category, obj, tags, geom)
                    continue
                if not obj.is_way():
                    continue

                highway = tags.get("highway")
                waterway = tags.get("waterway")
                admin = tags.get("boundary") == "administrative"
                building = tags.get("building") not in (None, "", "no", "false")
                landuse = tags.get("landuse") in LANDUSE
                natural = tags.get("natural") in NATURAL_AREAS
                water_area = tags.get("natural") == "water" or tags.get("water") or tags.get("landuse") == "reservoir"
                closed = obj.is_closed()

                if highway in ROAD_MAJOR | ROAD_LOCAL:
                    geom = geometry_for_way(obj, False)
                    category = "roads_major" if highway in ROAD_MAJOR else "roads_local"
                    write_feature(handles, counts, category, obj, tags, geom)
                elif waterway in WATERWAYS or admin:
                    geom = geometry_for_way(obj, False)
                    category = "water" if waterway in WATERWAYS else "boundaries"
                    write_feature(handles, counts, category, obj, tags, geom)

                if closed and (building or landuse or natural or water_area):
                    geom = geometry_for_way(obj, True)
                    if water_area:
                        write_feature(handles, counts, "water", obj, tags, geom)
                    elif building:
                        write_feature(handles, counts, "buildings", obj, tags, geom)
                    else:
                        write_feature(handles, counts, "context", obj, tags, geom)

            for handle in handles.values():
                handle.write("]}")
    finally:
        pass

    sizes = {category: (OUTPUT / filename).stat().st_size for category, filename in FILES.items()}
    result = {
        "source": str(PBF),
        "bbox_wsen": [WEST, SOUTH, EAST, NORTH],
        "crs": "EPSG:4326",
        "format": "GeoJSON FeatureCollection, minified; separate local class files",
        "counts": dict(counts),
        "sizes_bytes": sizes,
        "total_size_bytes": sum(sizes.values()),
        "processing_seconds": round(time.monotonic() - start, 2),
        "pyosmium": getattr(osmium, "__version__", "installed"),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
