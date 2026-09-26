from pathlib import Path

import rasterio

from pipeline.preprocessing.sar_filter import lee_filter


INPUTS = {
    "VV": Path("data/processed/sar/aoi_test/VV_aoi.tif"),
    "VH": Path("data/processed/sar/aoi_test/VH_aoi.tif"),
}

OUTPUT_DIR = Path("data/processed/sar/aoi_test")


def inspect(path: Path):
    with rasterio.open(path) as src:
        data = src.read(1)
        valid = data > 0

        return {
            "width": src.width,
            "height": src.height,
            "crs": src.crs,
            "resolution": src.res,
            "transform": src.transform,
            "bounds": src.bounds,
            "nodata": src.nodata,
            "mean": float(data[valid].mean()),
            "std": float(data[valid].std()),
        }


def main():
    outputs = {}

    for polarization, input_path in INPUTS.items():
        if not input_path.exists():
            raise RuntimeError(
                f"Missing {polarization} input: {input_path}"
            )

        output_path = (
            OUTPUT_DIR / f"{polarization}_aoi_lee.tif"
        )

        print(f"\nFiltering {polarization}...")
        lee_filter(
            input_path,
            output_path,
            window_size=3,
        )

        outputs[polarization] = output_path

    print("\nInspecting filtered outputs...")

    vv = inspect(outputs["VV"])
    vh = inspect(outputs["VH"])

    for polarization, info in [
        ("VV", vv),
        ("VH", vh),
    ]:
        print(f"\n{polarization}:")
        for key, value in info.items():
            print(f"  {key}: {value}")

    checks = {
        "dimensions match": (
            vv["width"] == vh["width"]
            and vv["height"] == vh["height"]
        ),
        "CRS matches": vv["crs"] == vh["crs"],
        "resolution matches": (
            vv["resolution"] == vh["resolution"]
        ),
        "transform matches": (
            vv["transform"] == vh["transform"]
        ),
        "bounds match": (
            vv["bounds"] == vh["bounds"]
        ),
        "VV has valid pixels": vv["mean"] > 0,
        "VH has valid pixels": vh["mean"] > 0,
    }

    print("\nValidation:")

    all_passed = True

    for name, passed in checks.items():
        print(
            f"  [{'PASS' if passed else 'FAIL'}] {name}"
        )

        if not passed:
            all_passed = False

    if not all_passed:
        raise RuntimeError(
            "Dual-polarization SAR validation failed."
        )

    print(
        "\nPASS: VV and VH were filtered successfully "
        "and remain on the same spatial grid."
    )


if __name__ == "__main__":
    main()
