# AVLOKAN MapLibre map

## Renderer and basemap

AVLOKAN uses locally bundled MapLibre GL JS 5.24.0 (`frontend/vendor/maplibre-gl`) through the shared adapter `frontend/js/modules/maplibre-map.js`. The dashboard, scene selection, and map explorer each use this renderer. MapLibre navigation controls provide zoom; compact attribution controls remain visible.

The default development style is OpenFreeMap Positron, loaded from the documented endpoint `https://tiles.openfreemap.org/styles/positron`. Positron provides a bright, restrained basemap with light land, blue water, muted roads, subtle boundaries, and place labels. OpenFreeMap is the basemap/style source only. The style, vector tiles, glyphs, and sprites are remote resources in this mode. The development map therefore depends on OpenFreeMap and is NOT fully offline.

Use `?map=offline` to select the staged local style/data (or set `window.AVLOKAN_MAP_MODE = 'offline'` before initializing maps). This mode uses India-PBF-derived GeoJSON in `frontend/assets/osm/` and the existing Sentinel-2 raster tiles in `frontend/assets/map-tiles/`. The GeoJSON is a bounded Indore/prototype-region subset, not a full-India browser dataset. Detailed local roads and places load only at higher zooms. No external style, tile, sprite, or glyph service is configured in this mode. Other application API calls are separate; backend-dependent features still need the local API.

## Style label hierarchy

The hosted Positron style was inspected at runtime. The frontend adjusts its actual style layer IDs without changing hosted geometry layers:

- `label_other` (generic/POI labels) is hidden.
- `label_village` begins at zoom 12; `label_town` begins at zoom 9.
- City and capital labels begin at zoom 6; state/country labels retain the style ranges.
- Waterway/line water labels begin at zoom 12; point water labels at zoom 11.
- Major road names begin at zoom 14, minor road names at zoom 16, and paths at zoom 17.
- All hosted symbol layers explicitly disable text and icon overlap where applicable; normal collision handling remains enabled.

The local style uses off-white land, pale blue water, muted roads, subtle boundaries, and priority-ranked local place labels. Local towns appear from zoom 9 and village/locality names from zoom 12. Satellite and analysis imagery remain independent overlay layers.

## AVLOKAN overlays

Each map keeps its own MapLibre instance. Shared GeoJSON sources and layers render AVLOKAN content above the basemap:

- registered AOI points/radii and selected AOI geometry
- T1/T2 or archive scene footprints, selected scene, and investigation point/radius
- search results, selected result, and similar-site markers
- candidate geometries
- georeferenced analysis preview imagery, using the supplied WGS84 bounds
- local Sentinel-2 raster, independently toggleable as Satellite

Basemap and satellite imagery remain separate. Existing map click/pick behavior, scene selection, centering/fitting, overlays, coordinate display, and controls are connected through the shared adapter.

## Attribution and licensing

OpenFreeMap style/source attribution is read from the style and displayed by MapLibre's attribution control. Local OSM-derived features are credited to `© OpenStreetMap contributors`. OSM data is under the Open Database License (ODbL); see [OpenStreetMap copyright and license](https://www.openstreetmap.org/copyright) for attribution and share-alike requirements. Local Sentinel-2 imagery retains Copernicus attribution.

## Offline and storage status

- MapLibre runtime, CSS, and license are in `frontend/vendor/maplibre-gl/`; `frontend/package.json` and lockfile pin the npm dependency.
- Default development mode requests remote OpenFreeMap style/vector resources; it is not offline.
- `?map=offline` uses local GeoJSON and raster resources for prototype-region coverage only.
- This change does not rebuild local map data, satellite imagery, or the India source PBF.

## Development checks

Serve the frontend as usual. Open `/?map=offline` to validate local map assets and `/?map=openfreemap` (or `/`) to validate OpenFreeMap Positron. In the browser Network panel, hosted mode should show OpenFreeMap requests; offline map mode should show no requests to non-local hosts for map assets.
