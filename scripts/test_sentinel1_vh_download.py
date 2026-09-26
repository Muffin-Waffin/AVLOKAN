from pathlib import Path

from pipeline.acquisition.aoi import load_aoi, get_bbox
from pipeline.acquisition.cdse import CDSEClient
from pipeline.acquisition.sentinel1_downloader import (
    get_https_asset_url,
)
from pipeline.acquisition.downloader import download_asset


AOI_PATH = Path("data/aoi/test_area.geojson")

SCENE_ID = (
    "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_"
    "058483_073C1B_C9AA_COG"
)

OUTPUT_DIR = Path(
    "data/raw/sentinel1"
) / SCENE_ID


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

    feature = next(
        (
            item
            for item in result.get("features", [])
            if item.get("id") == SCENE_ID
        ),
        None,
    )

    if feature is None:
        raise RuntimeError(
            f"Scene not found: {SCENE_ID}"
        )

    vh_url = get_https_asset_url(
        feature,
        "vh",
    )

    output = OUTPUT_DIR / "VH.tif"

    if output.exists():
        print(f"VH already exists: {output}")
        print(f"Size: {output.stat().st_size:,} bytes")
        return

    print("Downloading VH...")
    print("This is a large asset and may take a while.")

    path = download_asset(
        vh_url,
        output,
        timeout=300,
    )

    print()
    print(f"Download complete: {path}")
    print(f"File exists: {path.exists()}")
    print(f"File size: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()