from pathlib import Path

import rasterio

from pipeline.preprocessing.sar_filter import lee_filter


INPUT = Path(
    "data/processed/sar/aoi_test/VV_aoi.tif"
)

OUTPUT = Path(
    "data/processed/sar/aoi_test/VV_aoi_lee.tif"
)


def main():
    if not INPUT.exists():
        raise RuntimeError(
            f"Run the AOI warp test first. Missing: {INPUT}"
        )

    print("Applying Lee speckle filter...")
    print(f"Input:  {INPUT}")
    print(f"Output: {OUTPUT}")

    lee_filter(
        INPUT,
        OUTPUT,
        window_size=3,
    )

    with rasterio.open(INPUT) as src:
        before = src.read(1)
        before_profile = src.profile

    with rasterio.open(OUTPUT) as src:
        after = src.read(1)

        print("\nOutput:")
        print(f"  Size:       {src.width} x {src.height}")
        print(f"  CRS:        {src.crs}")
        print(f"  Resolution: {src.res}")
        print(f"  dtype:      {src.dtypes[0]}")
        print(f"  NoData:     {src.nodata}")

    valid_before = before > 0
    valid_after = after > 0

    print("\nStatistics:")
    print(
        f"  Before mean: {before[valid_before].mean():.4f}"
    )
    print(
        f"  After mean:  {after[valid_after].mean():.4f}"
    )
    print(
        f"  Before std:  {before[valid_before].std():.4f}"
    )
    print(
        f"  After std:   {after[valid_after].std():.4f}"
    )

    if not valid_after.any():
        raise RuntimeError(
            "Filtering produced no valid pixels."
        )

    print("\nPASS: SAR speckle filter produced a valid raster.")


if __name__ == "__main__":
    main()
