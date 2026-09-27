# OSCD BIT fine-tuning data preparation

## Data isolation and location cross-validation

The existing fixed 11/3 development split remains recorded in `data/oscd/splits.json`, but the training config now uses deterministic five-fold location-level CV over only the 14 official training locations. Fold assignment uses seed 42; each official training location is validation exactly once and training in the other four folds. The official 10-location test partition is not loaded as a dataset, used for patch enumeration, class balance, augmentation, or model selection. The loader rejects any official test location passed as a train or validation location.

With `n_splits: 5`, `fold: 0`, and seed 42, the groups are:

| Fold | Validation locations | Training locations |
| --- | --- | --- |
| 0 | bercy, mumbai, pisa | abudhabi, aguasclaras, beihai, beirut, bordeaux, cupertino, hongkong, nantes, paris, rennes, saclay_e |
| 1 | abudhabi, bordeaux, rennes | aguasclaras, beihai, beirut, bercy, cupertino, hongkong, mumbai, nantes, paris, pisa, saclay_e |
| 2 | aguasclaras, beihai, hongkong | abudhabi, beirut, bercy, bordeaux, cupertino, mumbai, nantes, paris, pisa, rennes, saclay_e |
| 3 | cupertino, nantes, paris | abudhabi, aguasclaras, beihai, beirut, bercy, bordeaux, hongkong, mumbai, pisa, rennes, saclay_e |
| 4 | beirut, saclay_e | abudhabi, aguasclaras, beihai, bercy, bordeaux, cupertino, hongkong, mumbai, nantes, paris, pisa, rennes |

The runtime prints all assignments and the selected fold. Select another fold with `--fold 0` through `--fold 4`; it writes to a fold-specific checkpoint subdirectory if training is deliberately started. Fold membership is fixed independent of validation results.

## Patch sampling and augmentation

Training patches use a deterministic row-major full-coverage grid of 256×256 with stride 128. Validation uses stride 256 so its pixel-aggregated loss does not count overlapping pixels more than once. Partial right/bottom windows are reflected for image input; labels are padded with zero and padded positions are excluded by the validity mask. No image or mask resizing occurs. T1, T2, target, and validity mask share every transform.

Training-only, on-the-fly augmentation randomly selects one of identity, horizontal flip, vertical flip, or 90°/180°/270° rotation. A local RNG derived from configured seed, epoch, and patch index makes the choice reproducible. It does not create additional files or alter spectral values. Validation cannot enable augmentation. The patch index list is built eagerly as small location/coordinate metadata; image and mask windows are read lazily one patch at a time, so scene arrays are not retained.

For the 14 official training locations, valid pixels total 6,517,578. Patch counts from the inspected registered dimensions are:

| Location | Valid pixels | Stride 256 (previous grid) | Stride 128 (training grid) |
| --- | ---: | ---: | ---: |
| abudhabi | 627,215 | 16 | 49 |
| aguasclaras | 247,275 | 6 | 20 |
| beihai | 696,344 | 16 | 56 |
| beirut | 1,262,600 | 25 | 90 |
| bercy | 142,200 | 4 | 12 |
| bordeaux | 238,337 | 6 | 20 |
| cupertino | 799,820 | 16 | 56 |
| hongkong | 375,300 | 9 | 30 |
| mumbai | 477,906 | 12 | 35 |
| nantes | 303,804 | 9 | 25 |
| paris | 159,120 | 4 | 16 |
| pisa | 557,168 | 12 | 42 |
| rennes | 190,857 | 6 | 15 |
| saclay_e | 439,632 | 9 | 30 |
| **Total** | **6,517,578** | **150** | **496** |

Stride-count estimates for the same 14 locations are 236 patches at stride 192 and 1,765 at stride 64. The selected 128 stride is about 3.31× the old all-location patch count. Per-fold training patch counts are 407, 412, 390, 399, and 376 respectively (validation uses the non-overlapping grid). Compared with the prior 112 training patches from the old 11-location split, this is about 3.36–3.68× as many optimizer updates per epoch. Overlap repeats some pixels intentionally; it does not multiply storage. Augmentation offers up to six geometric views of a patch over time, but there is still one presentation per patch per epoch, not six batches.

Memory remains bounded by one patch and the BIT activations/optimizer state: the pair input is about 1.5 MiB as float32 before intermediate tensors. Overlap increases patch I/O and per-epoch compute, not persistent image memory. Validation stays non-overlapping and unaugmented for interpretable pixel aggregation.

## Input, model, loss, and configuration

The unchanged channel order is B04/B03/B02. Raw DN is normalized once by divide-by-10000, clip to `[0,1]`, and map to `[-1,1]`. BIT architecture, official LEVIR initialization, strict checkpoint SHA verification, registered pixel alignment, and OSCD mask labels are unchanged.

The unchanged loss is `0.5 * weighted BCEWithLogits + 0.5 * soft Dice`, with positive weight 46.46. Padded pixels are excluded from both terms. Config remains batch size 1, AdamW (`lr=1e-4`, `weight_decay=1e-4`), 30 epochs, seed 42, `device: auto`, and CUDA when available. CV uses `configs/oscd_bit_training.yaml`.

No training or official-test evaluation is launched by this data-preparation change. For a later one-step smoke test only, use:

```powershell
python scripts/train_oscd_bit.py --dry-run --fold 0 --device cuda
```

Full training requires a deliberate invocation without `--dry-run`; it has not been run as part of this task. Existing BIT checkpoints are left untouched.
