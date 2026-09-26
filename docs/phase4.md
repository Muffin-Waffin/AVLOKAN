# Phase 4: AI embeddings

## Purpose and selected model

Phase 4 converts the small Phase 2 tile files into local image feature vectors and connects those vectors to the Phase 3 FAISS index. It does not implement semantic-search products or evaluate retrieval quality.

The selected checkpoint is the official **RemoteCLIP ViT-B/32** checkpoint from [`chendelong/RemoteCLIP`](https://huggingface.co/chendelong/RemoteCLIP), loaded through OpenCLIP. The upstream [RemoteCLIP repository](https://github.com/ChenDelong1999/RemoteCLIP) documents image and text encoders and is Apache-2.0 licensed ([license](https://github.com/ChenDelong1999/RemoteCLIP/blob/main/LICENSE)). The Hugging Face checkpoint page has no separate model card/license declaration, so this prototype records the upstream source and does not make a separate legal conclusion about the checkpoint distribution.

The AVLOKAN design deck calls for ViT-B/16. The official RemoteCLIP release inspected here provides ViT-B/32, RN50 and ViT-L/14 checkpoints, but no ViT-B/16 checkpoint. This implementation uses the available ViT-B/32 checkpoint rather than inventing a B/16 conversion. Runtime code reads the embedding dimension from the loaded model and checks image and text output dimensions; it does not assume a guessed value.

The checkpoint path is `models/remoteclip/RemoteCLIP-ViT-B-32.pt`. The downloader pins its SHA-256 to `60014e395d930a3f2963d1d89c8522bf4ad56775571e4356e866864789af85c4`. Model files are ignored by Git. Acquire and validate it with:

```bash
python scripts/download_remoteclip.py
```

The actual input size and normalization are obtained from OpenCLIP's preprocessing transform for the selected model (ViT-B/32 uses 224-pixel inputs). The RemoteCLIP text tokenizer and encoder are exposed by the same adapter.

## Sentinel-2 image input

The adapter accepts the Phase 2 four-band float32 GeoTIFF stack in B02, B03, B04, B08 order. The RGB conversion reads only the tile and explicitly maps **R=B04, G=B03, B=B02** (Rasterio bands 3, 2, 1). Reflectance is clipped to [0, 1], scaled to uint8, and passed through RemoteCLIP/OpenCLIP's documented image preprocessing. B08 remains intact in the source tile and is not fed to this RGB-only checkpoint. No source imagery is modified. This is a deterministic prototype display mapping, not a trained four-band adaptation.

Only 256×256 tile files are read. Image batch size defaults to four and is configurable. Inference uses `torch.inference_mode()`. Device `auto` selects CUDA if available and otherwise CPU; FP16 autocast is enabled only on CUDA. CPU inference uses float32.

## Vectors, normalization, and text

The adapter provides image and text encoders. Both outputs are converted to contiguous float32 vectors and L2-normalized once. That representation matches Phase 3's cosine-similarity `IndexFlatIP` behavior. The loaded model's actual output dimension is reported by the build command; image and text dimensions are checked against one another. Text encoding demonstrates compatible vector shape only; no text-search workflow or retrieval-quality claim is made.

## Cache and FAISS integration

`data/embeddings/RemoteCLIP-ViT-B-32/` contains one `.npy` vector and JSON provenance record per tile. Records include tile ID, checkpoint hash, dimension, dtype, normalized status, and source file fingerprint. The cache invalidates when model version, source fingerprint, or expected dimension changes.

`scripts/build_embeddings.py` resolves each input path through the Phase 3 catalog, reuses valid cached vectors, embeds uncached tiles, and incrementally adds only IDs not already present in the local FAISS index. FAISS maintains the tile ID mapping in its sibling JSON file. Re-running the command therefore reuses the embedding cache and does not duplicate index IDs.

```bash
python scripts/build_embeddings.py \
  --input data/processed/phase2_validation/tiles/s2_demo \
  --device auto --batch-size 4
```

## Real-data validation

The Phase 2 validation input contains four real Sentinel-2 tiles (`s2_demo__tile_000000` through `s2_demo__tile_000003`), and all four catalog paths exist. The pinned checkpoint SHA-256 was verified before use. On this CPU-only WSL2 run:

| Measure | Result |
| --- | ---: |
| Model and checkpoint | RemoteCLIP ViT-B/32, SHA-256 pinned above |
| Image/text embedding dimension | 512 |
| Device / batch size | CPU / 4 |
| Model load | 4.38 s |
| Four-tile RGB read | 0.019 s |
| Four-tile model preprocessing | 0.005 s |
| Four-tile inference | 0.128 s (about 0.032 s/tile) |
| First build total | 4.53 s |
| Generated and cached | 4 normalized float32 embeddings |
| FAISS index | 4 vectors, 512 dimensions, 8,314 bytes; ID map 377 bytes |
| Repeated build | 4 cache hits, 0 new vectors, 0 inference seconds |

The real tile ID and vector mapping was checked after reloading FAISS; querying tile 000000 with its own stored vector returned tile 000000 at score 1.0. This is an ID/persistence sanity check, not an assessment of semantic retrieval quality. A real image and text encoding also produced the same dimension and unit norm, and repeating an image encoding was deterministic within the test tolerance.

## Resource behavior

No CUDA device is required. CPU uses float32 and holds only a configurable batch of small RGB tiles plus model tensors; full scenes are never read or converted. The validated environment is WSL2 with a CPU-only PyTorch wheel, 12 visible CPU threads, and roughly 7.6 GiB RAM. The model itself dominates resident memory; peak RSS was not collected. Actual timings are environment-specific.

## Limitations

- This prototype validates embeddings on four Sentinel-2 tiles only.
- Semantic retrieval quality has not been evaluated; Phase 5 must provide an evaluation set before making quality claims.
- The model input uses RGB B04/B03/B02; B08 is retained only in source GeoTIFFs.
- The design's ViT-B/16 choice is not available in the selected official RemoteCLIP release; ViT-B/32 is used.
- No model fine-tuning, production-scale generation, or online inference is implemented.
- Hugging Face's checkpoint file page lacks a separate model card; upstream RemoteCLIP source and license are documented above.
- This is a local SIH prototype, not a production EO embedding service.
