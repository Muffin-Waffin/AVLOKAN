# OSCD-to-BIT alignment and training preparation

## Spatial shape trace

The OSCD loader selects named B04/B03/B02 bands and returns each registered pair as `[T=2,C=3,H,W]` raw-DN float32. `bit_inputs(quantification_value=10000)` divides both dates by the same explicit scalar, clips reflectance to `[0,1]`, then applies `2x-1` to produce float32 `[-1,1]`; there is no second normalization in `BITDetector`. The BIT ResNet stem uses a 7x7 stride-2 convolution and a stride-2 max pool; layer 2 has stride 2, while layer 3 uses dilation in place of another stride. Thus the encoder feature grid is `ceil(H/8) x ceil(W/8)`. `forward_single` upsamples features x2 (nearest) before `conv_pred`; the transformer decoder operates on that feature grid without changing H/W; the absolute feature difference is upsampled x4 bilinearly before the two-class classifier. Final output is `8*ceil(H/8) x 8*ceil(W/8)`.

Observed checkpoint-backed shapes:

| Location | Loader/input and mask | layer3 feature | decoder input | raw logits/probability |
| --- | --- | --- | --- | --- |
| Bercy | 395x360 | 50x45 | 100x90 (N=9,000 tokens per date) | 400x360 |
| Abu Dhabi | 799x785 | 100x99 | 200x198 (N=39,600 tokens per date) | 800x792 |

The discrepancy is stride rounding in the encoder followed by fixed-factor decoder upsampling, not a changed checkpoint architecture. No model parameters or decoder dimensions were changed.

`align_bit_logits` bilinearly interpolates continuous two-class logits to the original input/mask H/W with `align_corners=False`; softmax is applied after alignment. This maps every output to the full registered-image pixel extent instead of cropping off edge rows/columns or resampling the ground-truth mask. Labels remain in their original pixel grid. `align_categorical_mask` exists only for cases that genuinely need mask-grid conversion and uses nearest-neighbor semantics. The registered OSCD TIFFs have no CRS or meaningful affine transform, so all learning alignment is in their documented registered pixel coordinates; no georeferencing is fabricated.

Native image geometry is preserved in sample metadata. For Abu Dhabi native B04, the T1 grid is 785x799 at about 9.4e-5 degrees/pixel and T2 is 782x795 at about 9.44e-5 degrees/pixel; both report EPSG:4326 and nearly identical bounds. Native files are not the training grid: OSCD supplies the separate registered 10 m rectified pair and aligned mask. Bercy's native B04 T1/T2 both report EPSG:4326 and 360x395.

## Class balance (official test excluded)

The official 10 test locations were not loaded or counted. Development train (11 locations) contains 4,946,744 pixels: 104,224 changed and 4,842,520 unchanged, or 2.1069% change. Validation (3 locations) contains 1,570,834 pixels: 44,966 changed and 1,525,868 unchanged, or 2.8626% change. Training locations range from 0.2878% changed (Paris) to 3.5649% (Hong Kong); validation ranges from 1.6403% (Aguas Claras) to 3.7614% (Abu Dhabi). The class imbalance is substantial. Bercy has 0.7356% changed pixels; Abu Dhabi has 3.7614%.

One defensible first loss is `0.5 * weighted BCEWithLogits + 0.5 * soft Dice`, with positive BCE weight estimated only on development-train pixels as unchanged/changed = 46.46. BCE supplies per-pixel supervision; Dice contributes overlap sensitivity under sparse positives. The ratio is a baseline statistic, not tuned against validation/test performance; validation should reveal whether this weighting is useful. The official test set remains reserved.

## Memory and patch proposal

This environment has no CUDA device; Windows reports 15.1 GiB installed RAM and about 4.2 GiB available during inspection. The largest development-train scene is Beirut, 1180x1070. The paired 3-band float32 input alone is about 30.1 MiB; a two-date autograd graph also retains encoder and eight decoder-layer activations. At the 64-channel first convolution, each date has a 590x535 activation (~76.8 MiB), before saved intermediates and gradients. Full-frame training therefore risks multi-GiB memory pressure on CPU; no full-frame training peak was measured.

The preparation config proposes deterministic, row-major, non-overlapping 256x256 patches (a multiple of BIT's total stride 8). Pad only bottom/right image edges to complete the grid, reflect image values, and mark padded target pixels invalid for loss/metrics. This covers every real label pixel exactly once and does not randomly discard labels. The paired RGB patch tensors alone occupy 1.5 MiB; this is materially safer for batch-size-1 CPU training, although the actual backward-memory footprint must be measured in a short training dry run before a full run.

`configs/oscd_bit_preparation.yaml` records the proposed data, patch, optimizer, loss, epoch, seed, and checkpoint settings. It is configuration only; no optimizer, trainer, scheduler, checkpoint selection, or training execution is included in this step.
