from pathlib import Path
import subprocess

import rasterio
from rasterio.warp import transform_bounds


SCENE_DIR = Path(
    "data/raw/sentinel1/"
    "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_"
    "058483_073C1B_C9AA_COG"
)

VV_PATH = SCENE_DIR / "VV.tif"
VH_PATH = SCENE_DIR / "VH.tif"

AOI_BBOX = (75.80, 22.70, 75.90, 22.80)

OUTPUT_DIR = Path("data/processed/sar/aoi_test")
VV_OUTPUT = OUTPUT_DIR / "VV_aoi.tif"
VH_OUTPUT = OUTPUT_DIR / "VH_aoi.tif"


def get_warp_bounds():
    """
    Transform the AOI from WGS84 into the source GCP coordinate system.

    The source imagery is GCP-georeferenced in EPSG:4326, so the AOI
    is already expressed in the same geographic CRS.
    """
    return AOI_BBOX


def run_warp(input_path: Path, output_path: Path, bounds):
    command = [
        "gdalwarp",
        "-overwrite",

        # Use the Sentinel-1 GCPs.
        "-order", "2",

        # Output geographic CRS.
        "-t_srs", "EPSG:4326",

        # Same grid resolution for VV and VH.
        "-tr", "0.0001", "0.0001",

        # Explicit AOI clipping.
        "-te",
        str(bounds[0]),
        str(bounds[1]),
        str(bounds[2]),
        str(bounds[3]),

        "-r", "bilinear",

        "-srcnodata", "0",
        "-dstnodata", "0",

        "-of", "GTiff",

        str(input_path),
        str(output_path),
    ]

    print("\nRunning:")
    print(" ".join(command))
    print()

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(
            f"gdalwarp failed for {input_path.name}"
        )


def inspect(path: Path):
    with rasterio.open(path) as src:
        return {
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
            "transform": src.transform,
            "resolution": src.res,
            "bounds": src.bounds,
            "nodata": src.nodata,
        }


def main():
    if not VV_PATH.exists():
        raise RuntimeError(f"Missing VV: {VV_PATH}")

    if not VH_PATH.exists():
        raise RuntimeError(f"Missing VH: {VH_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for path in (VV_OUTPUT, VH_OUTPUT):
        if path.exists():
            path.unlink()

    bounds = get_warp_bounds()

    print("Sentinel-1 AOI warp test")
    print("========================")
    print(f"AOI: {bounds}")

    run_warp(VV_PATH, VV_OUTPUT, bounds)
    run_warp(VH_PATH, VH_OUTPUT, bounds)

    print("\nInspecting outputs...")

    vv = inspect(VV_OUTPUT)
    vh = inspect(VH_OUTPUT)

    print("\nVV:")
    for key, value in vv.items():
        print(f"  {key}: {value}")

    print("\nVH:")
    for key, value in vh.items():
        print(f"  {key}: {value}")

    checks = {
        "CRS matches": vv["crs"] == vh["crs"],
        "dimensions match": (
            vv["width"] == vh["width"]
            and vv["height"] == vh["height"]
        ),
        "resolution matches": vv["resolution"] == vh["resolution"],
        "transform matches": vv["transform"] == vh["transform"],
        "bounds match": vv["bounds"] == vh["bounds"],
        "VV CRS is EPSG:4326": vv["crs"] == "EPSG:4326",
    }

    print("\nValidation:")
    all_passed = True

    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        if not passed:
            all_passed = False

    if not all_passed:
        raise RuntimeError("Sentinel-1 AOI grid validation failed.")

    # Verify the resulting bounds stay inside the requested AOI,
    # allowing for tiny floating-point/grid effects.
    tolerance = 0.0002

    bounds_ok = (
        vv["bounds"].left >= AOI_BBOX[0] - tolerance
        and vv["bounds"].bottom >= AOI_BBOX[1] - tolerance
        and vv["bounds"].right <= AOI_BBOX[2] + tolerance
        and vv["bounds"].top <= AOI_BBOX[3] + tolerance
    )

    print(
        f"  [{'PASS' if bounds_ok else 'FAIL'}] "
        "output remains within AOI"
    )

    if not bounds_ok:
        raise RuntimeError("Output extends beyond requested AOI.")

    print("\nPASS: VV and VH share the same AOI grid.")
    print(f"VV: {VV_OUTPUT}")
    print(f"VH: {VH_OUTPUT}")


if __name__ == "__main__":
    main()
    