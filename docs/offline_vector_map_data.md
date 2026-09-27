# AVLOKAN offline vector map data

## Purpose

The intended basemap uses the full India OpenStreetMap extract so users can navigate across India without rebuilding for each prototype area. The browser must read an optimized local representation, never the source PBF. Satellite imagery remains a separate AVLOKAN layer; its existing Sentinel-2 CRS (EPSG:32643) and backend-derived WGS84 scene bounds remain authoritative. The prototype AOI is an overlay and is not baked into the OSM data.

## Source and provenance

- Provider: Geofabrik, [India extract page](https://download.geofabrik.de/asia/india.html).
- Current extract URL: `https://download.geofabrik.de/asia/india-latest.osm.pbf` (the page can change over time).
- OSM data is licensed under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Required map credit: **© OpenStreetMap contributors**. Review ODbL attribution and share-alike obligations for the actual distribution/use.
- Record the exact downloaded filename, UTC download time, byte size, checksum, and OSM timestamp from the PBF/header in `data/map/osm/metadata.json`; do not treat a moving `latest` URL as a version identifier.

## Processing and output

Preferred production output is a compact, zoom-filtered Mapbox Vector Tile (MVT) archive or local tile tree served from AVLOKAN's own storage. Prepare it from the full PBF with Osmium plus a vector-tile compiler such as tippecanoe, or an equivalent documented toolchain. If that toolchain is unavailable, use GDAL/OGR or PyOsmium to create a spatially indexed GeoPackage in EPSG:4326 as an intermediate; this is not a substitute for the final optimized browser tiles at India scale.

Keep only the styling and query attributes needed by the map: roads (`highway`, `name`, `ref`), places (`place`, `name`), water (`waterway`/`water`, `name`), and boundaries (`admin_level`, `name`). Filter out unrelated tags and obscure feature classes. Include the requested motorways through service roads; include tracks only if size and density remain practical. Include rivers, streams, canals, lakes, reservoirs, water polygons and useful coastline; settlements from city through hamlet; and country/state/district plus useful lower-level administrative boundaries.

## CRS and zoom plan

Keep canonical geographic source/output coordinates in WGS84 (EPSG:4326). MVT renderers use Web Mercator (EPSG:3857) tile coordinates. Do not reproject or alter the Sentinel-2 raster as part of this workflow.

- Low zoom: country/state boundaries, major roads, major cities and large water bodies.
- Medium zoom: state/district boundaries, major and secondary roads, cities/towns, waterways.
- High zoom: local/residential roads, smaller settlements and detailed waterways.

Set layer min/max zooms and simplify/generalize lines and polygons by zoom. Avoid labeling every feature at every scale.

## Validation and offline use

For every build, verify the source checksum and PBF readability; open the output and check its CRS, India-wide coverage, nonzero counts for roads/water/places/boundaries, and retained names. Query the output around the prototype bounds (west 75.79966202098623, south 22.754106944804505, east 75.8498135819418, north 22.800612416259163) and report counts by layer. Confirm Indore-area features and read the processed output with network disabled. The frontend should load only local generated tiles; no remote basemap service is needed.

## Storage and regeneration

`data/map/osm/source/` is for the authoritative PBF and checksum; `processed/` for intermediate/GeoPackage output; `tiles/` for generated tiles; and `metadata.json` for tracked provenance and measured build results. Source, intermediate, and tile payloads are ignored by Git; keep metadata tracked. Reserve at least the PBF's current ~1.6 GB plus workspace for temporary processing and output (actual output size must be measured).

To regenerate, read the current Geofabrik India page, download the PBF and matching checksum, record the UTC time and exact version, verify the checksum, run the documented extraction/tile build with the above classes and zoom filters, validate all layers and the prototype query offline, then update metadata with measured counts, sizes, processing duration, and tool versions. The PBF can be refreshed without changing the AOI overlay or Sentinel-2 data.

## Current preparation status

See `data/map/osm/metadata.json` for this workspace's measured status. If processing tools are missing, do not report empty results as valid data: install a bounded processing toolchain and rerun the full pipeline before enabling the basemap.
