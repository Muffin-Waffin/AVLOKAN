# AVLOKAN Phase 2: Data preprocessing

Phase 2 prepares acquired imagery for later prototype stages. It covers
raster inspection, sensor-specific radiometry, quality masks, the demonstrated
Sentinel-1 SNAP workflow, and model-sized GeoTIFF tiles. This remains an SIH
prototype and does not implement embeddings, retrieval, or change detection.

## Processing flow

1. Inspect raster metadata and sampled pixel statistics with
   `pipeline.preprocessing.raster_inspector.inspect_raster`.
2. Convert optical digital numbers using `radiometry.convert_raster`.
3. Align SCL to the optical grid with `scl_alignment.align_scl_to_reference`,
   then apply the SCL or Landsat QA mask using `quality_mask.mask_raster_windowed`.
4. Prepare Sentinel-1 calibrated Sigma0, speckle filtering, and terrain
   correction with the SNAP graphs under `configs/` (see limitations below).
5. Create fixed-size tiles using `tiling.tile_raster`.

Raster processing uses Rasterio windows. Default tile size and overlap are
256 and 0 pixels. Tiles are padded at scene edges using the raster nodata value
(or zero when the source has none), and a `tiles.json` manifest records tile
IDs, bounds, CRS, transform, sensor/date supplied by the caller, and valid
fraction. Set `min_valid_fraction` to reject mostly empty tiles.

## Sentinel-2

The acquired 10 m B02/B03/B04/B08 bands are stacked into a four-band GeoTIFF.
L2A reflectance is `DN * 0.0001`, stored as float32. SCL is categorical at
20 m and must be aligned onto the reference 10 m grid with nearest-neighbor
resampling. Classes 0, 1, 3, 8, 9, 10, and 11 are masked; other classes remain
usable. SCL is the implemented cloud/quality source. s2cloudless is not
implemented.

## Landsat

Collection 2 Level-2 surface reflectance uses
`DN * 0.0000275 - 0.2` in float32. DN zero is treated as fill. QA_PIXEL masks
fill, dilated cloud, cirrus, cloud, cloud shadow, and snow bits. Both conversion
and quality masking process windows.

## Sentinel-1

The existing SNAP graphs specify orbit application, Sigma0 calibration,
Refined Lee speckle filtering with a 7x7 window, and terrain correction with
external SRTM, EPSG:32643, and 10 m pixel spacing. Sigma0 is preserved as
calibrated intensity (no optical scaling). The reusable AOI graph
`configs/s1_aoi_terrain_correction.xml` starts from the already speckle-filtered
VV/VH product, applies SNAP `Subset` with geographic `geoRegion` WKT, then
terrain-corrects only that subset. The operator options were checked with
`gpt Subset -h` before adding the graph. Example for the bundled demo inputs:

```bash
SNAP_USER_DIR=/tmp/avlokan-snap-user gpt -c 2G \
  configs/s1_aoi_terrain_correction.xml \
  -Ssource=data/processed/sar/s1_speckle_filtered.dim \
  -PgeoRegion='POLYGON ((75.80 22.70, 75.90 22.70, 75.90 22.80, 75.80 22.80, 75.80 22.70))' \
  -Pdem=data/processed/sar/dem/dem_utm43_10m.tif \
  -Ptarget=data/processed/sar/aoi_test/s1_aoi_terrain_corrected.tif
```

A real run produced `data/processed/sar/aoi_test/s1_aoi_terrain_corrected.tif`:
1440 x 1491 pixels, three float32 bands, EPSG:32643, 10 m, about 23 MB. The
GeoTIFF has no nodata value or band descriptions, so finite-pixel fraction
alone is not informative. A full windowed scan found nonzero fractions of
0.723, 0.723, and 0.0 for the three bands; the graph requests VV, VH, and the
layover/shadow mask. A windowed Python Lee helper is also available for
bounded AOI rasters; ESA SNAP remains the demonstrated path for the full SAR
preprocessing chain. Do not terrain-correct the full swath for the demo AOI.

## Resource use

Inspection samples bounded windows. Radiometry, masking, stacking, SAR filtering,
and tiling read bounded windows; SAR filtering adds a filter-radius halo so
block edges do not become seams. No CUDA or multiprocessing is required.
The prototype targets a typical 4-core/16 GB workstation. Temporary and output
raster storage can still be substantial, so use the limited demo AOI.

## Real-data validation available in this checkout

The repository contains a real four-band Sentinel-2 raster and 10 m aligned
SCL, raw Landsat optical/QA rasters, AOI-clipped Sentinel-1 VV/VH and
speckle-filtered AOI rasters, and the AOI terrain-corrected VV/VH output above.
The earlier full-scene file `data/processed/sar/s1_tc_vv.tif` is 28,400 x
21,485 pixels; inspection showed its bands are Sigma0_VV and
`layoverShadowMask`, not VV/VH. The mask band is mostly nodata, so it is not
used as the VV/VH validation result. Large outputs should be inspected with
sampled windows or `gdalinfo`; do not read them fully into memory. Generated
products live under ignored `data/processed/`.

## Known limitations

- The SNAP graphs are processing configuration, not a complete automated
  product runner. Existing AOI VV/VH files were created by a GDAL warp of
  downloaded COG data; they demonstrate AOI clipping but are not the SNAP
  terrain-corrected product.
- The prior real terrain-correction result is full-swath sized. It is retained
  as evidence and should not be regenerated for routine prototype validation.
- SNAP/CDSE border-noise removal is skipped because the downloaded SAFE
  metadata previously caused SNAP's `noiseVectorListElem is null` failure.
- The Python SAR helper is a basic Lee filter. The SNAP graph retains the
  demonstrated Refined Lee filter; the helper does not replace SNAP.
- This is a limited AOI prototype, not a production Earth-observation system.
