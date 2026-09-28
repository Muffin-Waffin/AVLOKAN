# AVLOKAN SIH 2026 Demo Mode

## What is real and what is simulated

Demo Mode is an opt-in presentation adapter; it leaves RemoteCLIP, FAISS,
BIT, the scientific change pipeline, and normal application behavior intact.
The search ordering/similarity presentation, image-neighbor ranking,
archive-wide similar-site discovery, temporal-consistency/embedding gates,
combined demo confidence, and construction interpretation are deterministic
demonstration simulations. Similar-site discovery does not run HDBSCAN.

Imagery, tile previews, the two analysis-ready Sentinel-2 observations, the
saved probability raster, raw mask, final mask, candidate measurements,
analysis metadata, BIT checkpoint identity, model threshold, and source
timestamps are real local project artifacts. Demo Mode reads the saved BIT
analysis directly; it does not rerun inference. The selected pair is
2025-03-29 (T1) and 2025-03-24 (T2), Sentinel-2, in EPSG:32643. The AOI is
the existing backend-configured WGS84 prototype footprint.

No cloud/shadow masking, independent registration verification, SAR analysis,
SAR agreement, or calibrated combined confidence is claimed. SAR is shown as
an available workflow concept only. Construction is a demo interpretation,
not a classifier result. Review is a human decision; each new decision is
stored locally and written to the existing SHA-256 audit ledger.

## Prepared demo data

`data/demo/` holds the selected scene, prepared text/image results, similar
sites, investigation, the two-observation timeline, evidence notes, provenance,
and review configuration. The four search thumbnails reference the real local
Sentinel-2 tile previews in `data/catalog/tiles.json`; the official image is
`s2_demo__tile_000000`. The presenter-ready RGB upload image `data/demo/demo_query_image.png`
was generated directly from the real satellite tile `data/processed/phase2_validation/tiles/s2_demo/tile_000000.tif`
using the official AVLOKAN/Sentinel-2 RGB band mapping (B04 Red, B03 Green, B02 Blue scaled linearly to 8-bit uint8 RGB)
without any artificial annotations, arrows, labels, or modifications. The original TIFF is unchanged;
`demo_query_image.png` serves as a convenient browser-upload representation of the real satellite tile.
Runtime review state is written to `data/demo/runtime/state.json` and ignored by Git.

The saved analysis ID is `1201535bfe3a41b189653b8533253146`. Its metadata is
under `data/processed/phase10_change_analysis/`; it records the real BIT
checkpoint SHA-256, 0.96 threshold, EPSG:32643, and retained candidates.

## Enable and run

Start the local API with `AVLOKAN_DEMO_MODE=true`, then start the existing
frontend static server. For PowerShell:

```powershell
$env:AVLOKAN_DEMO_MODE = 'true'
python -m uvicorn pipeline.api.app:app --host 127.0.0.1 --port 8000
```

Open the frontend at its normal local address. Remove the environment variable or set it to
`false` to keep the normal application flow. Demo API routes return 404 while
disabled. The frontend and its assets are local; API and imagery
requests use loopback/local file assets only. No external map, imagery, API,
font, JavaScript CDN, or telemetry provider is used by this demo adapter.

## Presenter workflow

1. Sign in to the local console and open Search / Retrieval.
2. Enter `Newly constructed buildings and infrastructure development` (or click the demo query chip) and run search. This exact
   prepared query is supported in Demo Mode; other text receives an explicit
   unsupported-query response.
3. For image search, switch to the Image Query tab, click Choose File, select `data/demo/demo_query_image.png` (or any satellite raster file), preview the tile, and click Search by Image. The uploaded image is encoded and searched over the local FAISS index.
3. Use the existing date, sensor, and location filters and rerun.
4. Open a real local thumbnail. Use Show on map on the prepared result to pin
   the selected area in the existing scene map, then return to results. Use Find
   Similar Sites on the prepared result to inspect the clearly labeled
   simulated discovery list.
5. Click Open investigation on the selected result.
6. Select both dated timeline observations (T1 2025-03-29, T2 2025-03-24),
   then click Analyze Change. The progress state is a UI transition; the result
   is the saved real BIT output.
7. Inspect before/after, probability, raw mask, final mask, candidates,
   checkpoint, threshold, and EPSG:32643 metadata. Evidence and SAR labels
   distinguish real output from demo concepts.
8. Open Analyst Review and choose Confirm or Reject yourself. Review state is
   persisted under `data/demo/runtime/state.json` and added to the local audit
   chain. Open Provenance / Audit to inspect that event.
9. Use Export Investigation to download JSON and a human-readable text report.

No screen advances automatically beyond explicit presenter actions. Repeating
searches and the same review decision is safe; repeating an identical review
returns its existing event. Use the reset endpoint to clear only the demo
review state:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/demo/reset
```

The existing audit ledger is append-only; reset does not delete ledger events.

## Offline and storage

The browser does not load the India OSM PBF. This demo uses the currently
available local AVLOKAN map integration and local raster imagery; the active
OSM build remains separate and untouched by Demo Mode. Existing `data/processed`
imagery and change artifacts remain outside normal Git tracking. Prepared
demo JSON is small and tracked. No network is needed after the local API and
frontend assets are available.

## Rehearsal notes and limitations

The four archive results are local spatial tiles from one Sentinel-2 scene,
not an India-wide retrieval set. Prepared ranking scores and similar-site
scores exist only for deterministic presentation and are not scientific
retrieval/calibration metrics. The prototype pair is an existing project
analysis asset; its mask statistics do not establish that a candidate is
construction. Preserve the full source files and scientific pipeline when
replacing these demonstration adapters with production implementations.
