from pathlib import Path

import rasterio


SCENE_DIR = Path(
    "data/raw/sentinel1/"
    "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_"
    "058483_073C1B_C9AA_COG"
)

VV_PATH = SCENE_DIR / "VV.tif"
VH_PATH = SCENE_DIR / "VH.tif"


def main():
    print("Validating Sentinel-1 VV/VH pair...\n")

    if not VV_PATH.exists():
        raise RuntimeError(f"VV file not found: {VV_PATH}")

    if not VH_PATH.exists():
        raise RuntimeError(f"VH file not found: {VH_PATH}")

    with rasterio.open(VV_PATH) as vv, rasterio.open(VH_PATH) as vh:

        print("VV:")
        print(f"  Size:       {vv.width} x {vv.height}")
        print(f"  CRS:        {vv.crs}")
        print(f"  Resolution: {vv.res}")
        print(f"  NoData:     {vv.nodata}")
        print()

        print("VH:")
        print(f"  Size:       {vh.width} x {vh.height}")
        print(f"  CRS:        {vh.crs}")
        print(f"  Resolution: {vh.res}")
        print(f"  NoData:     {vh.nodata}")
        print()

        checks = {
            "dimensions": (
                vv.width == vh.width
                and vv.height == vh.height
            ),
            "resolution": vv.res == vh.res,
            "nodata": vv.nodata == vh.nodata,
        }

        print("Checks:")

        all_passed = True

        for name, passed in checks.items():
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}")

            if not passed:
                all_passed = False

        print()

        if all_passed:
            print("PASS: VV and VH have matching raster geometry.")
        else:
            raise RuntimeError(
                "FAIL: VV and VH are not directly compatible."
            )


if __name__ == "__main__":
    main()