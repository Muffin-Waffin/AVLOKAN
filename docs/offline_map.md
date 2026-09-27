# AVLOKAN offline map

AVLOKAN uses Leaflet 1.9.4 from `frontend/vendor/leaflet`. The browser loads both the library and its marker assets locally; no CDN is referenced by the frontend.

## Local basemap

The default tile layer is `assets/map-tiles/{z}/{x}/{y}.png`, served relative to the frontend root. It is a bounded XYZ raster set downloaded from OpenStreetMap's standard tile service during setup. OSM attribution is shown in the Leaflet control.

The checked-in prototype coverage is generated from the existing georeferenced Phase 2 Sentinel-2 raster `data/processed/phase2_validation/s2_reflectance_512.tif`. No external map tiles are downloaded. The tile set is bounded around the real AVLOKAN Sentinel-2 scene footprint and `data/aoi/test_area.geojson`:

- west/east: 74.7°E to 76.4°E
- south/north: 22.2°N to 23.8°N
- zoom: 7 through 14; zooms 11–14 contain only source-intersecting detail tiles
- tiles: 82
- raster storage: approximately 1.1 MB

The basemap source is the existing local Sentinel-2 prototype raster, displayed as RGB satellite context. Attribution is `AVLOKAN local Sentinel-2 prototype raster · Copernicus Sentinel data`. The local copy is intended for this SIH prototype and is not a global road map archive.

To regenerate the set, reproject the existing Phase 2 Sentinel-2 raster to EPSG:3857 and write XYZ PNGs into `frontend/assets/map-tiles/{z}/{x}/{y}.png`, then update this document if the bounds, source, or size changes. Runtime uses only the local files. A missing tile leaves the geographic map and interactions usable and reports partial local coverage in the map footer.

## AVLOKAN geometry mapping

Backend AOIs currently expose latitude, longitude, and `radius_km`, so the UI renders an explicitly radius-derived Leaflet circle and center marker. It does not present that circle as a surveyed polygon. Scene search records expose WGS84 `bbox` values and optional GeoJSON `footprint` values. Footprints are rendered as polygons; a bbox is rendered as a rectangle labeled “bbox-derived display geometry”. The Phase 10 prototype observation bboxes are transformed by the backend from the source EPSG:32643 rasters.

The map helper also accepts analysis preview URLs with the backend response's WGS84 `spatial.bbox`, so a probability or candidate mask preview can be overlaid using the source raster extent rather than screen coordinates. Candidate records remain pixel/CRS data unless the backend supplies geographic candidate coordinates.

## Offline behavior and limitations

Leaflet initializes without probing an external service. Panning, zooming, AOI circles, scene footprints, and local API backed metadata continue to work without internet access. The basemap is intentionally limited to the prototype region and zoom range. The API itself remains a separate local dependency at `127.0.0.1:8000` when backend data is required.
