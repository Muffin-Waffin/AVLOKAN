# OSCD dataset staging and loader

OSCD was obtained from the public archive linked by the [official OSCD project](https://rcdaudt.github.io/oscd/), using the pinned archive URLs and checksums in the [TorchGeo OSCD dataset definition](https://raw.githubusercontent.com/torchgeo/torchgeo/main/torchgeo/datasets/oscd.py). SHA-256 checks were performed before extraction. Raw archives and extracted files are stored under `data/oscd/raw/` and are ignored by Git. `data/oscd/inventory.json` and `data/oscd/splits.json` are the lightweight, reproducible records.

The image archive contains 24 location directories. Its `train.txt` lists 14 official training locations and `test.txt` lists 10 official test locations. For development only, the alphabetically first three official training IDs (`abudhabi`, `aguasclaras`, `beihai`) form validation; the other 11 are training locations. This deterministic location-level split is recorded before model work in `data/oscd/splits.json`. Official test locations remain separate and must not be used for training or model selection.

Each location has `imgs_1`/`imgs_2` original, per-band Sentinel-2 TIFFs and `imgs_1_rect`/`imgs_2_rect` registered, 10 m resampled per-band TIFFs. Each rectified date has 13 separate files named by band (`B01` through `B12`, including `B8A`; there is no `B09` omission). The rectified pairs and masks match in pixel dimensions. These rectified TIFFs have no CRS or meaningful geotransform; the archive README documents registration and nominal 10 m resolution. Native TIFFs retain georeferencing and their original mixed resolutions. The inventory records both sets of native per-band properties.

The BIT model is three-channel. `OSCDDataset` selects bands by filename, in exact model order `B04`, `B03`, `B02` (red, green, blue), from each registered date. The raw loader returns float32 digital numbers without resizing, cropping, or radiometric scaling. `OSCDSample.bit_inputs(quantification_value=10000)` makes scaling explicit, clips to [0, 1], and maps to [-1, 1], matching the existing BIT RGB normalization convention. The architecture remains unchanged.

The archive README describes TIFF mask classes as 0/1, but inspection of every staged categorical TIFF found uint8 values 1/2. The loader verifies the accompanying visualization PNG and explicitly maps TIFF 1 (no change) to loader class 0 and TIFF 2 (change) to class 1. PNGs are not used as labels because at least one is antialiased. This discrepancy is recorded in the generated inventory and should be rechecked if the source archive changes.

Inventory and validation command:

```powershell
.venv\Scripts\python.exe scripts\build_oscd_inventory.py
```

No trainer, optimizer, or evaluation/model-selection code is part of this staging step. LEVIR checkpoint predictions over OSCD are only input/model smoke tests, not accuracy measurements.
