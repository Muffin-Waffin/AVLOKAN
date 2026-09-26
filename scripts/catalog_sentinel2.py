from pipeline.acquisition.aoi import load_aoi
from pipeline.acquisition.catalog import SceneCatalog
from pipeline.acquisition.sentinel2 import search_sentinel2


AOI_PATH = "data/aoi/test_area.geojson"
CATALOG_PATH = "data/catalog/scenes.json"


def main() -> None:
    print("Loading AOI...")

    aoi = load_aoi(AOI_PATH)

    print("Searching Sentinel-2...")

    scenes = search_sentinel2(
        aoi=aoi,
        start="2025-01-01",
        end="2025-03-31",
        max_cloud_cover=20,
        limit=10,
    )

    print(f"Found {len(scenes)} scenes.")

    catalog = SceneCatalog(CATALOG_PATH)

    added = catalog.add_many(scenes)

    print(f"Added {added} new scenes.")
    print(f"Catalog now contains {catalog.count()} scenes.")

    print()
    print("Catalog:")
    
    for scene in catalog.get_all():
        print(
            f"{scene.scene_id} | "
            f"{scene.acquisition_datetime} | "
            f"cloud={scene.cloud_cover}"
        )


if __name__ == "__main__":
    main()