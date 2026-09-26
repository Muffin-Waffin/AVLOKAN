# AVLOKAN Phase 3: Local tile catalog and index infrastructure

Phase 3 catalogs preprocessed tile files and provides a persistent local FAISS
index that accepts vectors from a future caller. It does not compute or invent
image embeddings. This is a small SIH prototype, not a production search
service.

## Tile catalog

`pipeline/indexing/tile_catalog.py` stores JSON records in
`data/catalog/tiles.json`. A record includes:

- stable `tile_id` based on the tile's relative path under the scanned root
- source scene ID, sensor, acquisition datetime when available
- tile path and optional parent scene path
- dimensions, CRS, resolution, bounds, affine transform
- band count, dtype, and valid fraction

`TileCatalog` supports `get_tile`, `list_tiles`, `filter_tiles`, and `count`.
Date ranges are inclusive ISO date/datetime filters. Bounding-box filtering
uses intersection and assumes the bbox coordinates are in each record's CRS;
the catalog does not reproject mixed-CRS records. Catalog writes use a
temporary JSON file followed by replacement. Repeated builds upsert by tile ID
and retain records that are not present in a later scan.

`catalog_builder.py` recursively finds `.tif` and `.tiff` files. It uses a
nearby Phase 2 `tiles.json` manifest when available and reads raster metadata
with Rasterio without loading pixel arrays. When a manifest has no valid
fraction, the existing sampled raster inspector supplies it.

Build or update a catalog with:

```bash
python scripts/build_tile_catalog.py \
  --input data/processed/tiles \
  --output data/catalog/tiles.json
```

The current checkout's Phase 2 validation tiles are under
`data/processed/phase2_validation/tiles`, so the real-data invocation here is:

```bash
python scripts/build_tile_catalog.py \
  --input data/processed/phase2_validation/tiles \
  --output data/catalog/tiles.json
```

The script reports discovered, added, updated, total, missing-file, and
duplicate-ID counts. The generated catalog and `data/index/` files are ignored
by Git; source code and tests remain tracked.

## FAISS and ID mapping

`FaissVectorIndex` uses CPU `faiss.IndexIDMap2(faiss.IndexFlatIP(D))` with
float32 vectors. Each vector is L2-normalized on insertion, and queries are
normalized before search, so inner product is cosine similarity. The wrapper
assigns stable sequential int64 FAISS IDs and persists the `tile_id` mapping in
a JSON sidecar. Duplicate tile IDs, zero/non-finite vectors, and dimension
mismatches are rejected. The default files are `data/index/avlokan.index` and
`data/index/avlokan_ids.json`.

The `IncrementalIndex` class loads existing files, appends only new vectors,
and persists after each insertion call. `IndexManager.index_embeddings()` and
`IndexManager.search()` provide the narrow interface for Phase 4 to pass
embedding vectors and tile IDs. Search returns `{tile_id, score}` records for
resolution through `TileCatalog`.

## Real-data and performance validation

The local catalog was built from four actual Sentinel-2 Phase 2 tiles. Each is
256 x 256, four float32 bands, EPSG:32643, 10 m resolution, and has a
manifest-reported valid fraction of 1.0. The catalog build took 0.056 s on the
first run; a second run took 0.047 s and added zero records. Both runs reported
four tiles, zero missing files, and zero duplicate IDs. The JSON catalog is
2,703 bytes.

FAISS was validated separately using four synthetic 4D basis vectors mapped
to those real tile IDs. These are test vectors only, not satellite embeddings.
The first basis-vector query returned the matching real tile ID with cosine
score 1.0. Incremental insertion (three vectors, save/reload, then one more)
produced size four; search after another reload returned the same ID. The
4-vector index is 186 bytes and mapping is 375 bytes. Across 1,000 local query
iterations, observed average search latency was about 0.06–0.12 ms for k=5
and k=10. This tiny benchmark validates plumbing, not production throughput.

Unit tests use only synthetic vectors. FAISS is pinned to `faiss-cpu==1.15.1`;
no GPU is needed. Metadata indexing reads only raster headers and bounded
sample windows. No tile pixels are copied into the catalog or FAISS layer.

## Limitations and Phase 4 connection

- Embeddings and image encoders are **not implemented** in Phase 3.
- FAISS validation uses synthetic vectors only; no generated vectors are
  represented as real image embeddings.
- `IndexFlatIP` with normalized vectors is appropriate for the small prototype.
  HNSW and SQ8 are intentionally deferred.
- PostgreSQL/PostGIS is intentionally deferred; the catalog is local JSON.
- The catalog bbox filter does not transform CRS. Filter records in a common
  CRS or perform reprojection in a later component.
- Index and sidecar persistence use local files, with a small interruption
  window between replacing the two files. This is sufficient for the demo.
- To connect Phase 4, generate real `(N, D)` float32 vectors there and pass
  those vectors with their catalog `tile_id` values to
  `IndexManager.index_embeddings()`; query vectors go to `search()`.
