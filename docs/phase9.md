# Phase 9 — Frontend / Backend Integration

## Objective and architecture

Phase 9 wires the existing plain HTML/CSS/JavaScript AVLOKAN screens to the Phase 8 FastAPI service. It keeps the existing script-module structure and visual system; it adds no framework or build step. `frontend/js/api-client.js` centralizes the configurable base URL (the `avlokan-api-base` meta value in `frontend/index.html`, default `http://127.0.0.1:8000`) and fetch/HTTP error handling.

The frontend is served separately, for example with `python -m http.server 5500 --directory frontend`. FastAPI serves JSON, local image previews, and analysis artifacts; it does not serve the HTML application. The configured CORS origin permits this local setup.

## Existing frontend inspected

- Entry and shell: `frontend/index.html`
- Core state, helpers, routing, and bootstrap: `frontend/js/data.js`, `helpers.js`, `router.js`, `main.js`, `topo.js`
- Feature modules: `frontend/js/modules/search.js`, `results.js`, `investigate.js`, `analysis.js`, `map-engine.js`, `scene-map.js`, `review-audit.js`, `dashboard.js`
- Related CSS: shared `frontend/css/base.css`, `components.css`, `layout.css`, `variables.css`; screen modules `analysis.css`, `dashboard.css`, `investigate.css`, `results.css`, `review-audit.css`, `scene-map.css`, `search.css`
- Palette module/styles remain local UI preferences and were not connected to the API.

The app is a plain-script single-page UI. It uses global `App` state plus module-level objects and builds several views dynamically. There were no prior fetch/XHR/WebSocket calls. Its original search hits, dashboard totals and AOIs, scene timeline, review records, map-density layer, and before/after/change renders were generated or hardcoded in the browser. Palette preferences are stored in `localStorage`.

## Phase 8 API inspected and integrated

| Route | Frontend use |
|---|---|
| `GET /api/health` | Dashboard service status and local index/catalog counts |
| `GET /api/dashboard` | Dashboard counts and recent backend activity |
| `GET /api/aois`, `POST /api/aois` | AOI registry, map points, and registration |
| `POST /api/search/text` | Actual semantic text search and metadata filters |
| `POST /api/search/image` | Actual multipart image search using a selected real file |
| `GET /api/tiles/{tile_id}/preview` | JPEG result-card and tile-detail preview |
| `POST /api/scenes/search` | Local catalog scene query for AOI selection/investigation |
| `POST /api/change-analyses` | Run the existing analyzer on two backend-local raster paths |
| `GET /api/change-analyses/{analysis_id}` | Retrieve persisted analysis result |
| `GET /api/change-analyses/{analysis_id}/artifacts/{kind}` | GeoTIFF/JSON files and T1/T2 JPEG previews |
| `GET /api/change-analyses/{analysis_id}/artifacts/{probability,raw_mask,candidate_mask}_preview` | Added bounded PNG views for the browser; original GeoTIFF downloads remain available |
| `GET /api/review-queue` | Load backend-created candidate records and status filters |
| `POST /api/review-queue/{candidate_id}/decision` | Confirm, reject, or request review; server records the audit event |
| `GET /api/audit` | Server audit events and SHA-256 chain-integrity result |

There is no dedicated temporal-observation endpoint; the scene screen uses `POST /api/scenes/search`. There is no `/provenance/{analysis_id}` endpoint; the UI uses the analysis response and its metadata artifact. The analysis request requires server-local file paths and dates, so the browser never sends a local browser path or runs model code.

The additive PNG preview route addresses the existing browser/raster mismatch: browsers do not directly render the returned GeoTIFF. It downsamples to a bounded preview, displays probabilities as linear grayscale over 0–1, and displays mask-positive pixels in red with transparency elsewhere. It does not replace or alter the saved TIFF. The endpoint returns 422 with an explanation if a preview cannot be rendered.

## Integration map and behavior

- **Dashboard:** API counts replace the mock counters; unavailable latency/sync values are shown as unavailable. AOI points and activity come from the backend. The generated terrain remains explicitly described as an illustrative canvas.
- **Search and results:** Search submissions call the real endpoint; result similarity is retained as similarity, not confidence. Returned metadata is displayed only when present. The named-region selector remains a legacy UI control because the API accepts a bbox and the UI does not define real region boundaries; selecting one is disclosed as unapplied. Cloud values remain unknown when the API reports null. Local JPEG previews use the returned tile URL.
- **Image search:** The existing picker/drop-zone uploads the original file as multipart data. Supported extensions and the backend 20 MiB limit are checked/reported. Generated demo imagery is no longer offered as a real query. TIFF browser preview is explicitly unavailable; backend ingestion remains supported.
- **Investigation and map:** Backend AOIs can be opened with their real coordinates/radius/creation time and a local scene-catalog timeline. AOI pins are backend registry records. Map backgrounds are not satellite imagery; synthetic coverage and severity overlays are not represented as backend facts.
- **Scene/temporal selection:** An AOI location queries the local scene catalog and uses the returned sensor/date/cloud/local-path metadata. The UI does not manufacture dates or cloud/quality scores. It enables analysis only when both observations have available local Sentinel-2 rasters.
- **Change analysis and artifacts:** When an eligible pair exists, the existing analysis/detection views call the API, show an indeterminate running state, retrieve metadata and artifact previews, and display backend statistics/provenance. Probability and masks have separate labels. Candidate scores are identified as triage scores; no confidence value is invented.
- **Review:** Queue cards come from the backend and show component area, mean model probability, candidate score, and status. Confirm/reject/need-review actions use the returned candidate ID and refresh the queue/dashboard after success.
- **Audit/provenance:** Events and integrity state come from `/api/audit`; the browser's demo FNV hash chain and tamper simulation are no longer presented as the authoritative ledger. The full analysis provenance is available through the metadata artifact.
- **Errors/loading:** Shared fetch handling covers offline/network failures, response status/detail, and malformed JSON. Search, scene query, analysis, review, and audit show existing spinner/tip/panel states. Analysis has no fabricated percentage progress.

## Hardcoded data disposition

The original examples and generated canvas routines remain in source for the legacy design, but connected workflows no longer call their mock generation paths. The review seed is not loaded. Search results, dashboard operational counters/activity, AOI registry, queried scene records, review decisions, and audit history are sourced from API responses. Static examples and palette/theme settings remain UI configuration. The API has no authentication; the login remains a local demo gate and now states that it is not backend authentication.

## Files changed

- `frontend/index.html`
- `frontend/css/components.css`, `frontend/css/modules/analysis.css`, `frontend/css/modules/search.css`
- `frontend/js/api-client.js`
- `frontend/js/helpers.js`, `frontend/js/main.js`, `frontend/js/router.js`
- `frontend/js/modules/analysis.js`, `dashboard.js`, `investigate.js`, `map-engine.js`, `results.js`, `review-audit.js`, `scene-map.js`, `search.js`
- `pipeline/api/app.py` (additive browser-preview route)
- `tests/api/test_api.py` (preview route assertions)
- `docs/phase9.md`

Before the first frontend edit, a 29-file backup was created outside the repository at `%TEMP%\avlokan-phase9-frontend-backup-20260927-173604`.

## Testing and observed limits

The existing local inventory contains four indexed/catalog tiles and ten scene catalog records. All ten scene records currently have no local raster path, so the UI correctly reports metadata-only scenes and disables BIT analysis for those pairs. No alternate pair is silently selected. Backend analysis can still be invoked by the existing API with an eligible local pair.

The FastAPI integration tests include text/image retrieval, analysis with the existing repository-local Phase 6 pair, review/audit, and browser-preview image responses. The API-focused suite passed **8 tests**. The full `pytest -v` run passed **166 tests** (134 dependency/Rasterio warnings). `node --check` passed for all **15** frontend JavaScript files and `git diff --check` passed. Live HTTP checks returned frontend HTTP 200, API health `ok`, a text search with two real results, a successful CORS preflight, ten scene records (zero with local raster paths), and a returned local tile JPEG. The in-app browser runtime reported no available browser instance in this environment, so interactive browser testing is not claimed.

OpenCLIP logs `No pretrained weights loaded ... Model initialized randomly` when AVLOKAN constructs the architecture with `pretrained=None`. AVLOKAN then loads the configured local RemoteCLIP state dict with `strict=True`. A local adapter verification confirmed that a checkpoint tensor equals the corresponding loaded model tensor and that the adapter reports the configured checkpoint SHA-256. The warning describes the intermediate architecture initialization, not the final adapter state. No weights were changed or fetched.

## Features intentionally not integrated or available

- No image upload control was added beyond the existing picker; its existing sample tile was removed from backend search because it was synthetic.
- The frontend does not query external STAC or download scenes.
- Current local scene records cannot launch BIT because their `local_path` values are absent and they are not locally available.
- The legacy map is an illustrative coordinate canvas, not a georeferenced satellite basemap. It does not draw scene footprints or real raster tiles.
- Side-by-side search-result comparison is disabled for API results because similarity-ranked tiles are not a chronological T1/T2 pair. Actual T1/T2 and change artifacts are displayed after a backend analysis.
- The API has no user authentication, per-user identity, progress polling, or per-analysis provenance route. The UI does not claim those capabilities.
- No Phase 10 work is included.
