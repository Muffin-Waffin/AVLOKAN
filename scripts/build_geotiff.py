from pathlib import Path

from pipeline.preprocessing.geotiff import (
    build_multiband_geotiff,
)


SCENE_DIR = Path(
    "data/raw/sentinel2/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014"
)

OUTPUT = Path(
    "data/processed/optical/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014_4band.tif"
)


def main():
    print("Building 4-band Sentinel-2 GeoTIFF...")

    result = build_multiband_geotiff(
        SCENE_DIR,
        OUTPUT,
    )

    print(f"Created: {result}")
    print(f"Size: {result.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()