from pathlib import Path

import json

from pipeline.acquisition.aoi import load_aoi
from pipeline.acquisition.sentinel1 import search_sentinel1


AOI_PATH = Path("data/aoi/test_area.geojson")


def main():
    aoi = load_aoi(AOI_PATH)

    scenes = search_sentinel1(
        aoi=aoi,
        start="2025-01-01",
        end="2025-03-31",
        limit=1,
    )

    if not scenes:
        raise RuntimeError("No Sentinel-1 scenes found.")

    scene = scenes[0]

    print("Selected Sentinel-1 scene")
    print("=========================")
    print(f"Scene ID:     {scene.scene_id}")
    print(f"Date:         {scene.acquisition_datetime}")
    print(f"Orbit:        {scene.orbit_direction}")
    print(f"Polarization: {scene.polarization}")
    print()

    # Search again at the raw STAC level so we can inspect
    # the complete asset structure.
    from pipeline.acquisition.cdse import CDSEClient
    from pipeline.acquisition.aoi import get_bbox

    client = CDSEClient()

    result = client.search(
        collection="sentinel-1-grd",
        bbox=get_bbox(aoi),
        start="2025-01-01",
        end="2025-03-31",
        limit=1,
    )

    feature = result["features"][0]

    print("STAC properties")
    print("===============")

    for key, value in feature.get("properties", {}).items():
        print(f"{key}: {value}")

    print()
    print("Assets")
    print("======")

    for key, asset in feature.get("assets", {}).items():
        print(f"\n[{key}]")

        for field, value in asset.items():
            print(f"{field}: {value}")


if __name__ == "__main__":
    main()