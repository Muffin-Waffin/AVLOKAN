from pathlib import Path

from pipeline.acquisition.aoi import load_aoi, get_bbox
from pipeline.acquisition.cdse import CDSEClient
from pipeline.acquisition.sentinel1_downloader import (
    get_https_asset_url,
)
from pipeline.acquisition.downloader import download_asset


AOI_PATH = Path("data/aoi/test_area.geojson")

OUTPUT_DIR = Path(
    "data/raw/sentinel1/"
    "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_058483_073C1B_C9AA_COG"
)


def main():
    print("Searching for Sentinel-1 scene...")

    aoi = load_aoi(AOI_PATH)

    client = CDSEClient()

    result = client.search(
        collection="sentinel-1-grd",
        bbox=get_bbox(aoi),
        start="2025-03-27",
        end="2025-03-27",
        limit=10,
    )

    features = result.get("features", [])

    if not features:
        raise RuntimeError("No Sentinel-1 scene found.")

    feature = next(
        (
            item
            for item in features
            if item["id"]
            == "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_058483_073C1B_C9AA_COG"
        ),
        None,
    )

    if feature is None:
        raise RuntimeError(
            "Expected Sentinel-1 scene was not returned."
        )

    print("Scene found.")
    print(f"Scene: {feature['id']}")

    vv_url = get_https_asset_url(
        feature,
        "vv",
    )

    output = OUTPUT_DIR / "VV.tif"

    if output.exists():
        print(f"VV already exists: {output}")
        print(f"Size: {output.stat().st_size:,} bytes")
        return

    print()
    print("Downloading VV...")
    print("This may take a while because the asset is large.")

    path = download_asset(
        vv_url,
        output,
        timeout=300,
    )

    print()
    print(f"Download complete: {path}")
    print(f"File exists: {path.exists()}")
    print(f"File size: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()