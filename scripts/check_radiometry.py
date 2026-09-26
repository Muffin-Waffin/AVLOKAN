from pathlib import Path

from pipeline.preprocessing.radiometry import (
    read_radiometric_metadata,
)


RASTER_PATH = Path(
    "data/processed/optical/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014_4band.tif"
)


def main():
    metadata = read_radiometric_metadata(RASTER_PATH)

    print("Radiometric metadata")
    print("====================")

    for item in metadata:
        print(
            f"{item.band}: "
            f"scale={item.scale}, "
            f"offset={item.offset}"
        )


if __name__ == "__main__":
    main()