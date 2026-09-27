# Phase 10 — End-to-End Change Analysis Integration

## Objective and prior gap

Phase 9 connected the existing HTML/CSS/JavaScript screens to FastAPI, but the local scene-search catalog had ten archive records whose `local_path` values were all null. The existing analysis route accepted raster paths, so a user could not select a scene-search result and start BIT from the UI.

Phase 10 exposes the already-existing prototype rasters as explicitly labeled analysis-ready observations. They remain separate from the archive scene catalog and are not represented as arbitrary downloaded satellite products.

## Analysis-ready observation design

The two stable observation IDs are configured under `analysis_ready_observations` in `configs/api.yaml` and returned through the same `POST /api/scenes/search` route when the raster-derived footprint overlaps the query area.

| Observation ID | Role | Acquisition timestamp | Existing raster |
|---|---|---|---|
| `avlokan-prototype-s2-t1-20250329` | Supplied T1 | 2025-03-29T05:28:41.025Z | `data/processed/phase2_validation/s2_reflectance_512.tif` |
| `avlokan-prototype-s2-t2-20250324` | Supplied T2 | 2025-03-24T05:26:49.024Z | `data/processed/phase6_validation/s2_20250324_512.tif` |

The observations are labeled `record_type: prototype_analysis_ready`, source `existing local prototype analysis asset`, with explicit roles and a shared pair ID. The normal archive records remain `record_type: archive_scene`. Prototype cloud and quality metadata remain unknown. Their WGS84 search bbox is transformed from raster bounds (EPSG:32643); no product ID or acquisition details are inferred from the raster where those details are absent.

The rasters share a 512×512 grid, EPSG:32643, 10 m pixels, and the same transform/bounds. T1 is later than T2. The frontend assigns selections by the configured T1/T2 roles and does not sort this pair chronologically. The API permits reversed dates only for this configured T1/T2 observation pair. Existing path/date requests continue to use the original request contract and `allow_reversed_dates` behavior.

## Backend and API changes

- Scene search combines spatially matching archive rows with configured prototype observation rows, preserving separate source/type/role metadata.
- `SceneRecord` gained optional metadata fields; existing response fields remain.
- Change-analysis requests accept either the existing path/date inputs or both prototype observation IDs. IDs are resolved server-side through explicit configuration. Unknown IDs, mixed input modes, wrong roles, and mismatched pairs are rejected.
- The API calls the existing `TemporalPair` and `ChangeAnalyzer`; it contains no BIT implementation.
- API-run outputs use `data/processed/phase10_change_analysis`, separate from Phase 6/7 outputs. Existing output formats and browser-preview routes are reused.
- Analysis responses and metadata include prototype observation IDs, source, and supplied roles. The API persists retained candidates and the normal analysis audit event.

## Frontend and workflow

The existing scene timeline now renders local prototype assets as offset violet markers with explicit T1/T2 and prototype labels, separate from archive markers at matching dates. Selecting both populates the existing pair controls in supplied-role order. The analysis request sends observation IDs; raster paths remain server-side. The existing loading state, result page, probability/raw-mask/final-mask artifact previews, candidate confirm/reject controls, review queue, and audit screen remain in use.

No new page, framework, UI architecture, or map implementation was added. The existing map remains illustrative; no geographic coordinates are fabricated for its background.

## Artifact, review, and audit flow

The real API run created a UUID analysis record, probability and mask GeoTIFFs, metadata JSON, and browser-readable previews. A retained candidate was confirmed through the existing review decision endpoint. The audit response contained both `ANALYSIS` and `CONFIRMED` events and reported intact SHA-256 chain integrity.

## Tests and real inference

- API tests cover discovery, source distinction, transformed footprint, invalid IDs, role-order validation, server-side path/date resolution, persisted analysis retrieval, and observation provenance.
- Full regression result: `pytest -v` passed **168 tests** (134 existing dependency/Rasterio warnings). All 15 frontend JavaScript files passed `node --check`; the API package compiled; `git diff --check` passed.
- A real, unmocked ChangeAnalyzer run used the two local rasters and the configured prototype checkpoint. It produced 512×512 float32 probability and uint8 binary mask rasters on the source grid. Probabilities were finite and in [0,1].
- The run yielded 29,837 raw 0.50 pixels, 1,968 final pixels, ten 8-connected candidates, and a largest component of 726 pixels. These are integration outputs, not accuracy evidence.
- The live Uvicorn HTTP run was `1201535bfe3a41b189653b8533253146`. Timings were model load 1.499 s, preprocessing 0.068 s, inference 15.397 s, postprocessing 0.013 s, and total 17.529 s on the current hardware. Probability min/max/mean/median were 0.006706 / 0.999436 / 0.165276 / 0.057985. These are prototype integration timings/statistics, not accuracy or production-latency claims.
- Artifacts were written under `data/processed/phase10_change_analysis/` with UUID-prefixed probability, raw-mask, final-mask, and metadata files. All three GeoTIFFs were retrieved through HTTP and verified at EPSG:32643 with the exact source transform. All three browser-preview endpoints returned PNG data. The actual paths are `1201535bfe3a41b189653b8533253146_probability.tif`, `_raw_mask.tif`, `_mask.tif`, and `_metadata.json` in that directory.
- Candidate `1201535bfe3a41b189653b8533253146:2` was confirmed through the real decision endpoint. The audit API returned `ANALYSIS` and `CONFIRMED` with intact SHA-256 chain verification.
- The in-app browser runtime was attempted and its browser discovery returned an empty list. Interactive browser workflow is therefore blocked and not claimed as tested. A live Uvicorn HTTP workflow completed all backend, artifact, review, and audit steps.

## Regressions and limitations

No model, training, OSCD split/evaluation, Phase 6/7 artifact, raster input, RemoteCLIP weight, FAISS index, or archive catalog record was changed. No data was downloaded. The prototype pair is a local analysis-ready demonstration pair, not a complete archive ingestion workflow. The current UI requires the analyst to place an AOI over the pair’s actual footprint (approximately 75.80–75.85°E, 22.75–22.80°N) and explicitly select both markers. Browser automation remains unavailable in this environment.


  cd D:\sih\AVLOKAN
  .venv\Scripts\python.exe -m uvicorn pipeline.api.app:app --host 127.0.0.1 --port 8000

  Leave it running. Check health in a browser at http://127.0.0.1:8000/api/health.

  Terminal 2 — serve the existing frontend

  cd D:\sih\AVLOKAN
  .venv\Scripts\python.exe -m http.server 5500 --directory frontend

  Open http://127.0.0.1:5500.