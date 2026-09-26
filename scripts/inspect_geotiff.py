from pathlib import Path

import rasterio


RASTER_PATH = Path(
    "data/processed/optical/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014_4band.tif"
)


def main():
    print("Opening AVLOKAN GeoTIFF...")
    print()

    with rasterio.open(RASTER_PATH) as src:
        print(f"Driver:       {src.driver}")
        print(f"Width:        {src.width}")
        print(f"Height:       {src.height}")
        print(f"Band count:   {src.count}")
        print(f"Data types:   {src.dtypes}")
        print(f"CRS:          {src.crs}")
        print(f"Resolution:   {src.res}")
        print(f"NoData:       {src.nodata}")
        print(f"Bounds:       {src.bounds}")
        print(f"Transform:    {src.transform}")
        print(f"Descriptions: {src.descriptions}")

        print()
        print("Band statistics:")

        for index in range(1, src.count + 1):
            band = src.read(index)

            print(
                f"  Band {index} ({src.descriptions[index - 1]}): "
                f"min={band.min()}, "
                f"max={band.max()}, "
                f"mean={band.mean():.2f}"
            )


if __name__ == "__main__":
    main()