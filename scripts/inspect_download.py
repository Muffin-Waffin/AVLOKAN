from pathlib import Path

import rasterio


RASTER_PATH = Path(
    "data/raw/sentinel2/test_scene/B04_10m.jp2"
)


def main():
    print("Opening Sentinel-2 raster...")
    print()

    with rasterio.open(RASTER_PATH) as src:
        print(f"Driver:       {src.driver}")
        print(f"Width:        {src.width}")
        print(f"Height:       {src.height}")
        print(f"Band count:   {src.count}")
        print(f"Data type:    {src.dtypes[0]}")
        print(f"CRS:          {src.crs}")
        print(f"Resolution:   {src.res}")
        print(f"NoData:       {src.nodata}")
        print(f"Bounds:       {src.bounds}")
        print(f"Transform:    {src.transform}")

        band = src.read(1)

        print()
        print("Pixel statistics:")
        print(f"Minimum:      {band.min()}")
        print(f"Maximum:      {band.max()}")
        print(f"Mean:         {band.mean():.2f}")
        print(f"Non-zero:     {(band != 0).sum():,}")
        print(f"Total pixels: {band.size:,}")


if __name__ == "__main__":
    main()