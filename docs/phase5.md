# Phase 5: Semantic retrieval and discovery

## Objective and model

Phase 5 connects the Phase 4 pretrained RemoteCLIP ViT-B/32 text and image
encoders to the existing local FAISS index and tile catalog. It adds local
text-to-image and image-to-image retrieval, catalog filters, a CLI, and timing
diagnostics. It does not implement change detection or a UI.

The existing `RemoteCLIPAdapter` and the local checkpoint
`models/remoteclip/RemoteCLIP-ViT-B-32.pt` are reused without changing model
selection, architecture, or checkpoint. Retrieval does not create another
model or use network services. The adapter constructs the ViT-B/32 module and
then strictly loads the local checkpoint state before inference. Its existing
OpenCLIP initialization log says “No pretrained weights loaded” during that
construction step; the adapter loads the local checkpoint immediately
afterward with `strict=True`.

## Retrieval architecture

```text
Text query ───────→ RemoteCLIP text encoder ──┐
                                               ├→ normalized 512-D vector
GeoTIFF query → Phase 4 image encoder ─────────┘
     → catalog filter produces allowed tile IDs
     → FAISS IndexIDMap2 / IndexFlatIP ranks only allowed IDs
     → stable tile IDs resolve to TileCatalog metadata
     → results + timings + score distribution
```

`Retriever` orchestrates the existing adapter, `IncrementalIndex`,
`ImageEncoder`, and `TileCatalog`. The CLI instantiates the adapter once per
process and reuses it for repeated queries. A new CLI invocation loads the
model again.

## Text and image retrieval

Text queries use `RemoteCLIPAdapter.encode_text`. Image queries use the Phase
4 `ImageEncoder`, including its Sentinel-2 B04/B03/B02 display mapping and
normal model preprocessing. The adapter returns normalized vectors; the
existing normalization helper and FAISS wrapper validate the unit vectors
without normalizing them a second time. Image search identifies a query tile
by resolved catalog path. By default, that tile remains in results with an
`[QUERY TILE]` marker; `--exclude-query-tile` explicitly removes it.

Returned records contain rank, tile ID, cosine similarity, path, sensor,
acquisition datetime, bounds, CRS, resolution, and whether that record is the
query tile. The fields are taken from the existing catalog schema.

## Similarity and filtering

FAISS stores L2-normalized vectors in `IndexFlatIP`; its inner-product score
therefore represents cosine similarity. It is a similarity score, not a
probability or confidence estimate.

Sensor, inclusive date range, and bbox filters are applied to catalog
metadata first. The resulting eligible tile IDs are passed to FAISS through
an ID selector, so ranking is restricted to those candidates rather than
filtering an unbounded ranked list afterward. If fewer than `top_k` eligible
indexed tiles exist, only those available are returned. Bbox filtering uses
intersection and the numeric coordinates must match the tile record CRS;
this prototype does not reproject mixed-CRS catalog entries.

## CLI and offline use

The CLI uses only local checkpoint, catalog, and FAISS files. Once those
artifacts are present, no internet connection is used. `configs/embeddings.yaml`
provides the catalog and index paths; `--config`, `--checkpoint`, and
`--device` can override settings.

```bash
python scripts/search.py text "urban area"
python scripts/search.py text "water body" --top-k 4
python scripts/search.py text "vegetation" --sensor sentinel-2
python scripts/search.py text "urban area" \
  --date-from 2025-03-29 --date-to 2025-03-29 \
  --sensor sentinel-2 --bbox 582200 2519200 584600 2521600
python scripts/search.py image \
  data/processed/phase2_validation/tiles/s2_demo/tile_000001.tif
python scripts/search.py image \
  data/processed/phase2_validation/tiles/s2_demo/tile_000001.tif \
  --exclude-query-tile
python scripts/search.py text "urban area" --repeat 10
```

The filtered bbox example is in EPSG:32643, matching the real tile records.
`--repeat` reports mean, median, and p95 total query latency for that repeated
query. These are prototype-scale diagnostics, not an accuracy evaluation.

## Real-data demonstration

The local catalog and FAISS index contain four real Sentinel-2 tiles. For
`"urban area"`, the CLI actually returned:

| Rank | Tile | Similarity |
| ---: | --- | ---: |
| 1 | `s2_demo__tile_000003` | 0.3070 |
| 2 | `s2_demo__tile_000001` | 0.2949 |
| 3 | `s2_demo__tile_000000` | 0.2871 |
| 4 | `s2_demo__tile_000002` | 0.2638 |

For `"vegetation"`, the observed order was `tile_000000` (0.2796),
`tile_000003` (0.2490), `tile_000001` (0.2360), and `tile_000002` (0.2284).
For `"water body"`, the observed order was `tile_000000` (0.2450),
`tile_000003` (0.2440), `tile_000001` (0.2308), and `tile_000002` (0.2175).
Queries for roads, buildings, and open land also ran and returned four ranked
tiles each. These are recorded outputs only; the tiles have no manually
verified semantic labels, so the ranking is not claimed to be correct.

An image query using `tile_000001.tif` returned that tile first with cosine
similarity 1.0000 and printed `[QUERY TILE]`; the next observed scores were
0.9307, 0.8747, and 0.8280. This self-match checks encoding and ID mapping,
not semantic quality.

The sensor/date/bbox example above reduced the candidate pool from four tiles
to one and returned `s2_demo__tile_000000` (similarity 0.2871). Unit tests
also exercise sensor-only, date-only, bbox-only, and image query exclusion.

## Latency and diagnostics

Each result reports query embedding, image preprocessing/read (for images;
this is a breakdown included in the query-embedding time), FAISS search,
metadata filtering/lookup, and total retrieval latency. It also
reports the number of catalog-eligible and indexed-eligible tiles and min,
mean, and max score over returned results.

On the current CPU-only WSL2 environment, a ten-repeat `"urban area"`
prototype-scale run measured:

| Measure | Observed |
| --- | ---: |
| Model load (once for the CLI process) | 3,685.6 ms |
| First query embedding | 26.469 ms |
| First FAISS search | 6.778 ms |
| First metadata lookup/filter | 0.210 ms |
| First total retrieval | 33.574 ms |
| Ten-query total mean | 43.351 ms |
| Ten-query total median | 40.148 ms |
| Ten-query total p95 | 57.228 ms |

The FAISS index contains only four vectors. These timings validate that the
prototype path runs; they must not be extrapolated to large archives.

## Evaluation limits and later phases

Semantic retrieval quality is currently qualitative because the prototype
dataset contains four tiles and no labeled retrieval benchmark. No
precision@k, recall@k, or semantic accuracy is reported. Demonstration
prompts do not establish ground truth.

RemoteCLIP ViT-B/32 is a pretrained foundation model used for semantic
embeddings. **BIT is not part of Phase 5.** BIT fine-tuning on OSCD belongs to
the later change-detection phase. This phase also does not add HDBSCAN,
temporal pairing, a frontend, APIs, a database, or analyst review.
