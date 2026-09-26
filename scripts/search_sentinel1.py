from pipeline.acquisition.aoi import load_aoi
from pipeline.acquisition.sentinel1 import search_sentinel1


AOI_PATH = "data/aoi/test_area.geojson"


def main():
    aoi = load_aoi(AOI_PATH)

    print("Searching Sentinel-1 scenes...")
    print()

    scenes = search_sentinel1(
        aoi=aoi,
        start="2025-01-01",
        end="2025-03-31",
        limit=10,
    )

    print(f"Found {len(scenes)} scenes")
    print()

    for scene in scenes:
        print(f"ID:          {scene.scene_id}")
        print(f"Date:        {scene.acquisition_datetime}")
        print(f"Orbit:       {scene.orbit_direction}")
        print(f"Polarization:{scene.polarization}")
        print()


if __name__ == "__main__":
    main()