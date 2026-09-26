from pathlib import Path

import rasterio


RASTER_PATH = Path(
    "data/processed/optical/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014_4band.tif"
)


def main():
    with rasterio.open(RASTER_PATH) as src:
        print("GeoTIFF metadata")
        print("================")

        print(f"Scales:  {src.scales}")
        print(f"Offsets: {src.offsets}")
        print()

        print("Tags")
        print("====")

        for index in range(1, src.count + 1):
            print(f"\nBand {index} ({src.descriptions[index - 1]})")

            tags = src.tags(index)

            if tags:
                for key, value in tags.items():
                    print(f"  {key}: {value}")
            else:
                print("  No band-specific tags.")


if __name__ == "__main__":
    main()