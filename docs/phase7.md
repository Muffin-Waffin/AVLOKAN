# Phase 7 — False-alarm suppression and change candidate quality

## Purpose and scope

Phase 7 adds an auditable candidate layer after BIT inference. It leaves BIT weights and Phase 6 probability, raw 0.50 mask, calibrated threshold, component-area cutoff, and morphology untouched. The intent is candidate review and ranking, not a claim that postprocessing improves model accuracy.

## Raw output and analyst candidates

The analyzer preserves three distinct products:

1. The continuous float32 BIT probability raster.
2. The raw uint8 model mask at probability `>= 0.50`.
3. The analyst candidate mask at the configured operating threshold, the existing minimum component area, and any explicitly enabled candidate filters.

The Phase 7 mask continues to use the `_mask.tif` path and `final_mask_raster` result field for Phase 6 compatibility. `candidate_mask_raster` names the same artifact explicitly. With the checked-in configuration, edge and validity rejection are inactive, so the real Phase 7 candidate mask is byte-for-byte equal to the Phase 6 calibrated mask.

## Candidate components, geometry, and ranking

Candidates are 8-connected components extracted from the Phase 6 postprocessed mask. Each record includes component ID, rank, pixel area, pixel bounding box (exclusive maximum coordinates), pixel centroid, mean/maximum/median probability, p90/p95 probability, fraction of pixels meeting the operating threshold, distance to the image edge, validity fraction, retention status, and rejection reasons. When a valid raster grid exists, map-coordinate bounding boxes and centroids are expressed in that raster's CRS; no geographic coordinates are synthesized.

`candidate_score` is exactly the component mean BIT change-class probability. Candidates are ranked in descending score with component ID as the stable tie-break. This is an analyst triage score, not a calibrated probability of true change or a scientifically validated confidence score. `temporal_embedding_similarity` remains informational and does not affect candidate filtering or ranking.

## Filters and quality information

The existing `postprocess_probability` implementation remains responsible for thresholding, optional validity masking, the configured minimum component area, and the existing morphology option. Morphology remains `none`.

Candidate filtering is configured under `candidate_filtering` in `configs/change_detection.yaml`. `reject_edge_components` is false and `min_valid_fraction` is null. If explicitly enabled, image-edge rejection uses distance in pixels to the outermost image row/column and validity rejection compares the fraction of component pixels marked valid against the configured minimum. All filter decisions and removed/retained counts and pixels are recorded in metadata.

The current BIT inputs expose source nodata/nonfinite validity only. The analyzer does not load an SCL or cloud/shadow classification raster. It does not infer clouds from zero-valued model output. Existing OSCD OOF maps have no quality-mask or tile-seam metadata, so quality and seam filters were not included in the OOF experiment. Image-edge contact is observable, but it is not a reliable proxy for a tile seam. No seam filter is implemented.

## Controlled OOF experiment

Run `python scripts/run_phase7_oof_ablation.py` to reproduce the single-filter comparison from existing OSCD five-fold OOF probability maps. It writes `data/processed/phase7_candidate_filtering/oof_image_edge_ablation.json`, a new Phase 7 artifact. The script reads probabilities and labels only; it does not edit the Phase 6 calibration artifact, OOF maps, splits, checkpoints, or evaluation results.

Both arms use threshold 0.96, minimum component area 32, no morphology, and 8-connectivity. The filter arm additionally removes components touching the outermost raster row or column. No margin was tuned.

| Pooled OOF metric | Baseline | Plus image-edge rejection |
|---|---:|---:|
| TP | 47,191 | 43,688 |
| FP | 100,598 | 91,045 |
| FN | 101,999 | 105,502 |
| TN | 6,267,790 | 6,277,343 |
| Precision | 0.3193 | 0.3243 |
| Recall | 0.3163 | 0.2928 |
| F1 | 0.3178 | 0.3077 |
| IoU | 0.1889 | 0.1819 |
| Predicted changed fraction | 2.2675% | 2.0672% |

The filter removes 9,553 false-positive pixels and 3,503 true-positive pixels pooled. It decreases pooled F1. Location effects are mixed: FP decreases in 9 of 14 locations; F1 decreases in Mumbai, Abu Dhabi, Bordeaux, Beihai, Nantes, and Beirut, and increases in Pisa, Hong Kong, Cupertino, and Saclay East among the locations with changed predictions. Several locations are unchanged. This is insufficient support for enabling image-edge rejection by default. The complete per-location counts and metrics are in the new JSON artifact.

These are OOF evaluation observations for this fixed filter, not evidence of arbitrary-scene generalization or a new model-quality claim.

## Real Sentinel-2 regression

The existing Phase 6 pair was rerun through `scripts/analyze_change.py`; outputs were written to a new Phase 7 folder. Dimensions, CRS (`EPSG:32643`), affine transform, dtypes, probability range, mask values, and metadata statistics were checked. The final candidate mask exactly matches the previously saved Phase 6 final mask. The current 10 m projected pixel grid allows the existing area calculation; this run reports 196,800 m².

The result is a pipeline regression and numerical sanity check. It is not labeled evaluation, and the detected mask is not treated as ground truth.

## Performance

For the final local 512×512 CLI run, candidate extraction took 0.00508 s, filtering 0.0000063 s, and scoring/ranking 0.0000091 s. Full postprocessing took 0.01351 s. These are prototype measurements on the current machine, not production-latency claims.

## Limitations

- The OOF edge experiment has mixed location effects and lower pooled F1; edge rejection stays off by default.
- The application validity signal covers source nodata/nonfinite pixels, not Sentinel-2 SCL cloud/shadow classes.
- Tile seams cannot be determined reliably from the current analysis metadata.
- Mean probability ranking is heuristic ordering only, not confidence calibration.
- OOF data and the single Sentinel-2 scene do not establish performance on future scenes.
- False-alarm suppression is system-level postprocessing; it does not alter BIT weights.
- The existing OSCD research artifacts, five-fold evaluation, checkpoints, calibration artifact, and splits remain untouched.
