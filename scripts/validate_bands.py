from pathlib import Path

import rasterio


SCENE_DIR = Path(
    "data/raw/sentinel2/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014"
)

BANDS = ["B02", "B03", "B04", "B08"]


def main():
    reference = None

    for band in BANDS:
        path = SCENE_DIR / f"{band}_10m.jp2"

        print(f"\n--- {band} ---")

        with rasterio.open(path) as src:
            info = {
                "driver": src.driver,
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "dtype": src.dtypes[0],
                "crs": src.crs,
                "resolution": src.res,
                "transform": src.transform,
                "bounds": src.bounds,
            }

            for key, value in info.items():
                print(f"{key:12}: {value}")

            if reference is None:
                reference = info
                continue

            checks = {
                "dimensions": (
                    (src.width, src.height)
                    == (reference["width"], reference["height"])
                ),
                "CRS": src.crs == reference["crs"],
                "resolution": src.res == reference["resolution"],
                "transform": src.transform == reference["transform"],
                "bounds": src.bounds == reference["bounds"],
            }

            print("\nCompatibility:")
            for name, passed in checks.items():
                print(f"{name:12}: {'PASS' if passed else 'FAIL'}")

            if not all(checks.values()):
                raise RuntimeError(
                    f"{band} is not spatially compatible "
                    "with the reference band."
                )

    print("\n================================")
    print("ALL FOUR BANDS ARE COMPATIBLE")
    print("================================")


if __name__ == "__main__":
    main()