from pipeline.acquisition.aoi import load_aoi, get_bbox
from pipeline.acquisition.sentinel2 import search_sentinel2


AOI_PATH = "data/aoi/test_area.geojson"


def main() -> None:
    print("Loading AOI...")

    aoi = load_aoi(AOI_PATH)

    print("AOI bbox:")
    print(get_bbox(aoi))

    print()
    print("Searching Sentinel-2...")

    scenes = search_sentinel2(
        aoi=aoi,
        start="2025-01-01",
        end="2025-03-31",
        max_cloud_cover=20,
        limit=10,
    )

    print()
    print(f"Found {len(scenes)} Sentinel-2 scenes.")

    for index, scene in enumerate(scenes, start=1):
        print()
        print(f"--- Scene {index} ---")
        print("ID:", scene.scene_id)
        print("Sensor:", scene.sensor)
        print("Collection:", scene.collection)
        print("Date:", scene.acquisition_datetime)
        print("Cloud:", scene.cloud_cover)
        print("BBox:", scene.bbox)
        print("Downloaded:", scene.downloaded)


if __name__ == "__main__":
    main()