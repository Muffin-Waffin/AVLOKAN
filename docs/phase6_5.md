# Phase 6.5: Sentinel-2 vegetation-change diagnostics

## NDVI products

The Phase 2 stack order is B02, B03, B04, B08. The NDVI component reads
Rasterio bands 3 (B04) and 4 (B08) from each unchanged source raster and writes
float32 NDVI GeoTIFFs with the source grid. Source nodata, non-finite inputs,
and zero denominators become NaN nodata.

The temporal convention follows the supplied input labels:

```text
delta_ndvi = NDVI_T2 - NDVI_T1
```

Thus negative values indicate an NDVI decrease from T1 to T2; positive values
indicate an increase. The demo pair keeps T1=2025-03-29 and T2=2025-03-24 in
that supplied (reverse chronological) order. This sign convention describes
the supplied roles, not forward time.

Run from the project root:

```powershell
python scripts\run_ndvi.py `
  --t1 data\processed\phase2_validation\s2_reflectance_512.tif `
  --t2 data\processed\phase6_validation\s2_20250324_512.tif `
  --t1-date 2025-03-29 --t2-date 2025-03-24 --preserve-input-order `
  --ndvi-t1 data\processed\phase6_validation\ndvi_t1_512.tif `
  --ndvi-t2 data\processed\phase6_validation\ndvi_t2_512.tif `
  --delta data\processed\phase6_validation\delta_ndvi_512.tif
```

The CLI reports raster statistics, directional shares, and exploratory
absolute ΔNDVI shares at 0.05, 0.10, and 0.20. Those cutoffs are descriptive
only; they are not calibrated change thresholds or detector decisions.

## Diagnostic montage

`scripts\render_change_diagnostics.py` uses Pillow to create a four-panel PNG
for T1 NDVI, T2 NDVI, ΔNDVI, and BIT probability. It checks that all four
rasters share a grid. NDVI uses a fixed -1 to +1 color scale; ΔNDVI uses a
symmetric 98th-percentile display stretch (blue decrease, red increase); BIT
uses a 99th-percentile display stretch. These are visualization stretches,
not inference thresholds.

## OSCD adaptation findings and training design

The official OSCD description reports 24 registered Sentinel-2 pairs, 14
training locations and 10 test locations, 13 bands at mixed native 10 m, 20 m,
and 60 m resolutions, and pixel-level urban-change labels. The published
benchmark protocol resamples coarser bands to a common 10 m grid. Current
TorchGeo OSCD documentation describes 13-channel TIFF images and one-channel
PNG masks with 0=no change and 255=change.

No OSCD data is present in this checkout, so no trainer or dataset-specific
loader is added in this step. The least disruptive BIT adaptation is to retain
the exact three-channel checkpoint architecture and feed OSCD B04/B03/B02 in
the same RGB order as the existing BIT preprocessing. This avoids changing the
first convolution and the official checkpoint topology. Use registered
10 m RGB bands directly; no RGB resampling is needed. Convert mask value 255
to class 1 and 0 to class 0; ignore any other mask values if present.

Keep all 10 official OSCD test locations outside training and model selection.
Create a deterministic location-level validation subset from the 14 training
locations before patch sampling; never split adjacent patches from one city
across train and validation. Train only from the remaining training locations.
For initialization, strictly load the LEVIR checkpoint, preserve the
architecture, and record checkpoint hash, band mapping, normalization,
location split, crop/augmentation settings, optimizer settings, epochs, and
loss. Select checkpoints on the location-level validation split, then report
precision, recall, F1, and IoU once on the held-out official test split. Do not
select a model or threshold using the AVLOKAN demo pair.
