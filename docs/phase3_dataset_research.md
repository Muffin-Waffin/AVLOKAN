# Phase 3 additional-data research: S2MTCP verification

## Scope and integrity

This is an unlabeled-data inspection only. No BIT training, OSCD training,
checkpoint, split, evaluation result, or official OSCD test data was changed.
S2MTCP is not added to the supervised OSCD loader. No pixel is assumed to be
unchanged and no supervised precision/recall/F1 was calculated.

The verified source archive remains at
`data/oscd/s2mtcp/raw/S2MTCP_data.7z` (10,638,331,176 bytes; MD5
`6f6750f54fe5bb311ad67815f78064cc`, matching the Zenodo checksum). It was
resumed by HTTP Range and preserved. The extracted tree is
`data/oscd/s2mtcp/extracted/data_S21C/`; both raw and extracted data are
git-ignored. No second download was performed.

## Direct observations from the staged files

- Official metadata contains 1,520 pair identifiers and 3,040 rows, one `a`
  and one `b` row per pair. Each row references `{im_idx}_{a|b}.npy`.
- The extracted directory contains 3,042 NPY files. `833_a.npy` and
  `833_b.npy` are not referenced in the metadata; they are inventoried as
  extras and excluded from the metadata-driven loader.
- Every metadata-referenced array is NPY, H×W×14, float64. The 14 channel-like
  planes are not named or ordered by the official file README. Returned loader
  arrays are CHW float32, without scaling, band selection, or resampling.
- There are 432 distinct spatial shapes. Height is 600–601 pixels, width
  477–1,024 pixels. All 1,520 `a`/`b` pairs have identical dimensions.
- Metadata-referenced arrays passed a full finite-value scan. No nodata
  convention is documented or inferred. Zero is present in some channel
  values and cannot be treated as nodata based on this evidence.
- Across the 24 representative pairs, the first 13 channels' observed raw
  values span 1–28,000. This sampled range is descriptive, not a verified
  scaling/quantification convention.
- The final stored channel (index 13) is nonzero in 110 of the 3,040
  metadata-referenced files. Its meaning is undocumented; it is preserved and
  must not be assigned a spectral or quality-mask interpretation by guess.
- Source arrays contain no CRS or affine transform. This inspection invents
  no georeferencing.
- Acquisition dates/times make chronological ordering possible for 1,477
  pairs: 767 have `a` earlier, 710 have `b` earlier; 43 have identical
  timestamps and retain `a`/`b` order as explicitly ambiguous. The date gap is
  0–1,600 days (median 384); 46 pairs are same-day. `a` is not a synonym for
  T1. There are 33 pairs with identical `system_idx` values.

The loader sorts unequal timestamps chronologically and keeps same-timestamp
pairs in `a`,`b` order with `same_timestamp_order_ambiguous` metadata. It
preserves all 14 channels, leaves values unnormalized, and always returns
`change_mask=None`.

## Representative temporal and registration screening

The inspection sampled 24 metadata pairs evenly across sorted pair indices,
including Kota, Bengbu, Cartagena, Poznan, Balikesir, Jember, Jiangmen, Venice,
Zhenjiang, Mexico City, Xuanzhou, Blida, Valencia, Neuquen, Erbil, Rizhao,
Rampur, Samsun, Ajmer, Bakersfield, Mirzapur, Qinzhou, Santa Clarita, and
Jacksonville. This is a deterministic screening sample, not a labeled
benchmark.

For the first 13 channels, per-pair median Pearson correlation ranged from
0.269 to 0.960 (median 0.769). Relative MAE ranged from 0.066 to 0.597
(median 0.187). Across sampled pairs, the median fraction of pixels with
absolute normalized difference `|(T2-T1)/(|T1|+|T2|+eps)| >= 0.5` was 0.0074
(range about 0.00001–0.220).
These are descriptive temporal differences only: they mix genuine changes,
seasonality, illumination/atmosphere, sensor effects, and any residual
registration errors. They are not change labels.

A windowed Fourier phase-correlation screening was run independently over
channels 0–12. Across 24 sampled pairs, the median magnitude of the per-pair
channel-median shift was 0.0036 pixels; one pair exceeded 1 pixel (maximum
1.546 pixels), and none exceeded 2 pixels. Individual channel outliers also
occur. The estimates are texture/spectral dependent and are not ground-truth
registration measurements. No shift was applied. These results do not
establish exact pixel alignment; they indicate that registration quality
should be checked before any pixelwise consistency objective.

The official README describes approximately 600×600 Sentinel-2 L1C urban
areas, sub-10 m bands resampled to 10 m, and no additional geometric or
radiometric correction. The paper reports that L1C processing provides
subpixel georegistration and that the authors did not perform further image
registration. Neither statement supplies transforms for these NPY arrays or
proves exact alignment for every pair.

## Evidence, inference, and downstream suitability

**Observed:** the data are temporally paired, multi-channel Sentinel-2 arrays
with acquisition metadata, no pixel masks, matching pair shapes, varying
temporal similarity, and no stored georeferencing. The README does not name
the 14 channel positions; index 13 has nonzero values in a minority of files.

**Inference:** date/time supports chronological ordering except timestamp
ties. Similarity and phase-correlation suggest many pairs may be useful for
temporal representation tasks, but weak correlations and offset outliers make
pixelwise correspondence uncertain without pair-specific checks.

**Use assessment:**

- **Supervised change detection:** not suitable as-is; there are no pixel
  labels. Treating pairs as all-no-change would fabricate supervision.
- **Pseudo-label generation:** not justified as ground truth. Any future
  pseudo-label study requires an independently validated method and must
  report its noise; it is not the next recommended step.
- **Temporal consistency/self-supervision:** a plausible candidate, but only
  with an objective that does not assert every pixel is unchanged and with
  explicit handling of alignment uncertainty.
- **Representation pretraining:** plausible as a separate experiment. The
  source paper demonstrates self-supervised use of S2MTCP, but with its own
  method; this does not establish benefit for AVLOKAN's BIT checkpoint. First
  resolve/document channel semantics and define an input mapping without
  pretending the 14 channels are RGB or B04/B03/B02.

Recommended next step: independently identify the channel schema from an
authoritative source and validate registration on a broader, stratified set
of pairs. Then design a small isolated self-supervised representation
pretraining pilot that avoids fabricated no-change labels. Do not add S2MTCP
to the OSCD supervised loss until there is a defensible target.

## Generated artifacts and tests

- `data/oscd/s2mtcp/inventory.json`: metadata-linked file inventory, per-array
  shape/dtype/finite status, and unreferenced-file report.
- `data/oscd/s2mtcp/inspection.json`: all-location header checks and 24-pair
  value, similarity, normalized-difference, and registration diagnostics.
- `scripts/build_s2mtcp_inventory.py` and `scripts/inspect_s2mtcp.py`: repeatable
  inspection utilities.
- `pipeline/change_detection/bitemporal_data.py`:
  unlabeled chronological loader; no mask synthesis or implicit transforms.
- `tests/change_detection/test_bitemporal_data.py`: synthetic loader contract
  tests plus real staged-pair smoke checks (skipped when data is absent).

Official sources: [S2MTCP Zenodo record](https://zenodo.org/records/4280482),
[official README](https://zenodo.org/records/4280482/files/README.txt?download=1),
and [S2MTCP paper](https://arxiv.org/abs/2101.08122).
