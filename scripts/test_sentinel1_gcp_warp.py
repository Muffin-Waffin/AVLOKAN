from pathlib import Path
import subprocess


VV_PATH = Path(
    "data/raw/sentinel1/"
    "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_"
    "058483_073C1B_C9AA_COG/VV.tif"
)

OUTPUT_PATH = Path("data/processed/sar/test_vv_gcp_warp.tif")


def main():
    if not VV_PATH.exists():
        raise RuntimeError(f"VV file not found: {VV_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()

    command = [
        "gdalwarp",
        "-overwrite",

        # Use the GCPs contained in the Sentinel-1 COG.
        "-order", "2",

        # Reproject the GCP-geolocated image into WGS84.
        "-t_srs", "EPSG:4326",

        # Keep this test lightweight.
        "-tr", "0.001", "0.001",

        # Bilinear interpolation for the test.
        "-r", "bilinear",

        "-of", "GTiff",

        str(VV_PATH),
        str(OUTPUT_PATH),
    ]

    print("Running Sentinel-1 GCP warp test...\n")
    print("Command:")
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
            f"gdalwarp failed with exit code {result.returncode}"
        )

    print("Warp completed.")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Size: {OUTPUT_PATH.stat().st_size:,} bytes")

    print("\nInspecting output...")

    info = subprocess.run(
        ["gdalinfo", str(OUTPUT_PATH)],
        capture_output=True,
        text=True,
        check=True,
    )

    for line in info.stdout.splitlines():
        if any(
            key in line
            for key in [
                "Driver:",
                "Size is",
                "Coordinate System is:",
                "Origin =",
                "Pixel Size =",
                "Upper Left",
                "Lower Left",
                "Upper Right",
                "Lower Right",
            ]
        ):
            print(line)

    print("\nPASS: GCP warp produced a georeferenced raster.")


if __name__ == "__main__":
    main()