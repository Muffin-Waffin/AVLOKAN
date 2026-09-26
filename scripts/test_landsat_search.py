from pipeline.acquisition.aoi import load_aoi
from pipeline.acquisition.landsat import search_landsat


AOI_PATH = "data/aoi/test_area.geojson"


def main():
    aoi = load_aoi(AOI_PATH)

    scenes = search_landsat(
        aoi,
        "2025-01-01",
        "2025-03-31",
        max_cloud_cover=20,
        limit=10,
    )

    print(f"Found {len(scenes)} Landsat scenes.")

    for scene in scenes:
        print()
        print(f"ID: {scene.id}")
        print(f"Date: {scene.datetime}")
        print(
            "Cloud:",
            scene.properties.get("eo:cloud_cover"),
        )
        print(f"Assets: {len(scene.assets)}")
        print(
            "Bands:",
            list(scene.assets.keys())[:15],
        )


if __name__ == "__main__":
    main()
