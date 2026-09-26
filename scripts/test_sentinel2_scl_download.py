from pathlib import Path

from pipeline.acquisition.aoi import load_aoi
from pipeline.acquisition.cdse import CDSEClient
from pipeline.acquisition.sentinel2_downloader import (
    download_sentinel2_bands,
)


SCENE_ID = (
    "S2C_MSIL2A_20250329T052841_N0511_R105_"
    "T43QEF_20250329T105014"
)


def main() -> None:
    aoi = load_aoi("data/aoi/test_area.geojson")

    client = CDSEClient()

    bbox = [
        75.8,
        22.7,
        75.9,
        22.8,
    ]

    result = client.search(
        collection="sentinel-2-l2a",
        bbox=bbox,
        start="2025-03-29",
        end="2025-03-29",
        limit=20,
        cloud_cover=20,
    )

    features = result.get("features", [])

    print(f"Found {len(features)} scene(s).")

    feature = next(
        (
            item
            for item in features
            if item.get("id") == SCENE_ID
        ),
        None,
    )

    if feature is None:
        raise RuntimeError(
            f"Scene not found: {SCENE_ID}"
        )

    print(f"Scene: {SCENE_ID}")

    assets = feature.get("assets", {})

    print("\nSCL asset:")
    print("  exists:", "SCL_20m" in assets)

    if "SCL_20m" in assets:
        print(
            "  title:",
            assets["SCL_20m"].get("title"),
        )

    output_root = Path("data/raw/sentinel2")

    result = download_sentinel2_bands(
        feature,
        output_root,
    )

    print("\nAssets:")

    for name, path in result.items():
        print(f"  {name}: {path}")

    scl_path = result["SCL"]

    print("\nSCL file:")
    print(f"  path: {scl_path}")
    print(f"  exists: {scl_path.exists()}")

    if scl_path.exists():
        size_mb = scl_path.stat().st_size / (1024 ** 2)
        print(f"  size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
