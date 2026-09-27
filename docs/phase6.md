# Phase 6: Change analysis integration

## Purpose and scope

Phase 6 wraps AVLOKAN's existing Sentinel-2 and BIT research components in a
reusable application pipeline that returns probability, raw and processed
masks, statistics, spatial metadata, and provenance. Model performance is not
being optimized. This phase integrates existing research components into
AVLOKAN; it does not start training, use S2MTCP for training, or introduce a
dataset.

The BIT weights are prototype working checkpoints for integration and demo
use, not a final or production model. No confidence field is emitted. The BIT
softmax output is a change probability, not confidence.

## Existing components reused

- `pipeline/change_detection/temporal_pair.py` validates supplied T1/T2 paths,
  dates, CRS, transform, bounds, dimensions, and bands. Supplied T1/T2 roles
  are preserved; reversed dates require explicit permission.
- `pipeline/change_detection/preprocessing.py` supplies bounded 256 by 256
  windows and Sentinel-2 B04/B03/B02 model input. Four-band source stacks use
  B02/B03/B04/B08 order. Reflectance is clipped to [0,1] then mapped to [-1,1].
- `pipeline/change_detection/bit.py` and `help_funcs.py` provide the existing
  BIT architecture and strict model loading. The detector accepts the pinned
  official LEVIR checkpoint or an AVLOKAN fine-tuned checkpoint that records
  the verified LEVIR base hash; model state loading remains strict.
- `pipeline/change_detection/bit_alignment.py` remains the logit alignment
  implementation used by `BITDetector.predict` before softmax.
- `scripts/evaluate_oscd_cv5_baseline.py` and
  `scripts/calibrate_change_detection.py` remain the source for the saved OOF
  results and calibration configuration. Their existing outputs are not
  changed by application analysis.
- `pipeline/embeddings/remoteclip.py` supplies the existing RemoteCLIP adapter.

## OOF checkpoint provenance and application checkpoint policy

The existing calibrated OOF probability maps came from five distinct saved
best checkpoints. Each was evaluated only on its assigned three validation
locations (the final fold has two). The fold evaluator loads
`fold_<n>/best_oscd_bit.pt`, checks the saved fold and seed, and records the
checkpoint hash and epoch in `data/processed/oscd_cv5_validation_baseline/metrics.json`.
Calibration reads those saved maps; it does not load checkpoints or run model
inference.

| Fold | Checkpoint | SHA-256 | Epoch | Assigned validation locations |
| ---: | --- | --- | ---: | --- |
| 0 | `models/bit/BIT_OSCD_CV5/fold_0/best_oscd_bit.pt` | `8a75efe679aab0d1624888906cf3c9ed756772b7f3e92d439b7d0fb0fe3cac4b` | 16 | bercy, mumbai, pisa |
| 1 | `models/bit/BIT_OSCD_CV5/fold_1/best_oscd_bit.pt` | `7cfdb1ddd856aa72973ce56b9f0e234049a7fe9a72ae7166add05a9eec1336a2` | 10 | abudhabi, bordeaux, rennes |
| 2 | `models/bit/BIT_OSCD_CV5/fold_2/best_oscd_bit.pt` | `d9a886dafc0185b70cb017c329bece3892bda4bfd72ea2f52eb5f799f2b939ce` | 5 | aguasclaras, beihai, hongkong |
| 3 | `models/bit/BIT_OSCD_CV5/fold_3/best_oscd_bit.pt` | `4c31d9df42e285ad8dbe20c09e2ed2b3ed87e642f11e9e5f55d2d264d479fd26` | 23 | cupertino, nantes, paris |
| 4 | `models/bit/BIT_OSCD_CV5/fold_4/best_oscd_bit.pt` | `9a16a13763db506bf44dc57c8f597096bb06e7b2351fd569a8f03f2fb0024a17` | 28 | beirut, saclay_e |

The repository does not define a principled fold-checkpoint choice for an
arbitrary new scene. `ChangeAnalysisConfig.checkpoint` is therefore explicit.
For deterministic execution, the user selected fold 0 as the application
demonstration checkpoint. This does not claim it is globally best. The
existing five-fold evaluation and its saved outputs remain untouched.

## Prototype checkpoint selection

- Path: `models/bit/BIT_OSCD_CV5/fold_0/best_oscd_bit.pt`.
- SHA-256: `8a75efe679aab0d1624888906cf3c9ed756772b7f3e92d439b7d0fb0fe3cac4b`.
- Configuration role: `prototype_demo_checkpoint`.
- Reason: an explicit deterministic choice makes the application runnable
  while retaining the existing five-fold research evaluation unchanged.
- This is only a deterministic prototype choice; it is not a model-selection
  or ranking claim and does not assert better accuracy or generalization.
- The saved validation value **0.9254** is not used as a model-selection
  score. The ambiguous “0.92” terminology is intentionally abandoned.

The prototype operating configuration is threshold **0.96**, minimum
component area **32**, morphology **none**, and **8-connected** components.
The threshold is the selected pooled OOF calibration threshold, not a
universal probability calibration claim.

## Prototype operating configuration

The configuration records:

- Probability threshold: **0.96**.
- Minimum component area: **32 pixels**.
- Morphology: **none**.
- Connectivity: **8-connected**.
- Raw mask threshold: **0.50**.

The 0.96 setting was selected by maximum pooled F1 over the predefined global
configuration grid on the existing 14-location OSCD out-of-fold validation
maps. It is not a universal probability calibration claim and its performance
is not asserted to generalize to other data. The postprocessor is
`pipeline/change_detection/postprocessing.py`; it preserves mask shape and
applies the configured valid-pixel mask.

## Input contract and inference

Inputs are aligned four-band Sentinel-2 surface-reflectance GeoTIFFs in
B02/B03/B04/B08 order. Both rasters must exist and match in width, height,
band types, CRS, and affine transform. The pair must provide distinct dates;
chronological ordering is enforced unless `--preserve-input-order` is given.
No reordering happens inside the analyzer. The current model consumes B04,
B03, B02 and ignores B08. Invalid or nodata RGB pixels are excluded from
statistics and are written as zero in output masks/probability values; the
valid pixel count is included in result statistics.

`ChangeAnalyzer.analyze(pair, config)` loads the explicitly configured
checkpoint, preprocesses one bounded tile at a time, runs the existing BIT
detector, aligns logits to each input window through the shared alignment
helper, and computes softmax change probability. It retains both a raw
threshold-0.50 mask and the configured final mask. No UI, HTTP, or frontend
logic is included.

## Outputs, statistics, and provenance

Each analysis writes `<analysis_id>_probability.tif` (float32),
`<analysis_id>_raw_mask.tif` (uint8), `<analysis_id>_mask.tif` (uint8), and
`<analysis_id>_metadata.json`. GeoTIFF outputs inherit source dimensions,
CRS, and transform. Statistics include total and valid pixels, changed
pixels and fraction, 8-connected component count, largest and median
component area, and the ten largest component areas. Physical changed area is
included only when the CRS is projected and both axes have known linear units;
otherwise only pixel counts are reported.

Metadata records pair and available scene identifiers/timestamps, spatial
properties, model/checkpoint path and SHA-256, config, threshold,
postprocessing, source files, preprocessing description, and stage timings.
`temporal_embedding_similarity` is cosine similarity between L2-normalized
RemoteCLIP image embeddings of 224-pixel T1 and T2 previews. It is semantic
image similarity, not pixel change detection, and never gates BIT inference.
It is enabled in the current demonstration config and can be disabled for a
BIT-only run.

## CLI

The default config pins the prototype demonstration checkpoint and its
SHA-256. An explicit `--checkpoint` can override the path, but a different
checkpoint must also have its expected hash updated in the config.

```powershell
python scripts\analyze_change.py `
  --t1 data\processed\phase2_validation\s2_reflectance_512.tif `
  --t2 data\processed\phase6_validation\s2_20250324_512.tif `
  --t1-date 2025-03-29 --t2-date 2025-03-24 `
  --preserve-input-order
```

The CLI reports summary statistics, stage timings, and output paths. These
timings are prototype measurements on the current hardware/data and are not
production latency claims.

## Real Sentinel-2 smoke test

The real pair uses the existing `s2_reflectance_512.tif` T1 scene (catalog
acquisition time `2025-03-29T05:28:41.025Z`) and
`s2_20250324_512.tif` T2 scene (raster tag
`2025-03-24T05:26:49.024000Z`). The pair is 512 by 512, four-band float32,
EPSG:32643, with identical 10 m transforms and bounds. T1/T2 roles remain in
the supplied reverse-chronological order.

The real CLI run completed with the configured fold 0 demonstration
checkpoint. All outputs are 512 by 512 on the source grid. Probability is
float32 with min 0.00670594, max 0.99943620, mean 0.16527629, and median
0.05798453. The raw threshold-0.50 mask contains 29,837 changed pixels
(11.3819%); the final threshold-0.96 mask contains 1,968 (0.7507%), with 10
8-connected components and a largest component of 726 pixels. The projected
10 m grid supports an area calculation of 196,800 m². Metadata statistics
were recomputed from the written final mask and source validity mask and
matched exactly. These are integration checks only, not a ground-truth
assessment of detected changes.

On the run hardware, measured times were 1.2396 s model load (including
RemoteCLIP), 0.0716 s preprocessing, 15.3146 s inference, 0.0070 s
postprocessing, and 17.1431 s total. These are prototype measurements, not
production-latency claims. The T1/T2 RemoteCLIP temporal embedding cosine
similarity was 0.98035693; it did not gate BIT inference.

## Known limitations and verification state

- Fold 0 is explicitly selected only for the deterministic prototype demo;
  no global checkpoint ranking is implied.
- Sentinel-2 inference is an integration demonstration; OSCD performance
  results do not establish Sentinel-2 prototype-pair accuracy.
- Invalid pixels are encoded as zero in output values; validity is represented
  in metadata and statistics rather than a separate validity raster.
- No confidence score is defined or returned.
- RemoteCLIP temporal similarity is supported as optional cosine similarity
  between its normalized T1/T2 preview embeddings. It is informational and
  never gates BIT inference.
- No training, S2MTCP pretraining, or new dataset is part of this phase.
