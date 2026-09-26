from pipeline.acquisition.aoi import load_aoi
from pipeline.acquisition.cdse import CDSEClient


AOI_PATH = "data/aoi/test_area.geojson"


def main() -> None:
    aoi = load_aoi(AOI_PATH)

    from pipeline.acquisition.aoi import get_bbox

    client = CDSEClient()

    result = client.search(
        collection="sentinel-2-l2a",
        bbox=get_bbox(aoi),
        start="2025-01-01",
        end="2025-03-31",
        limit=1,
        cloud_cover=20,
    )

    feature = result["features"][0]

    print("SCENE ID")
    print(feature["id"])

    print("\nSTAC TYPE")
    print(feature["type"])

    print("\nPROPERTIES")
    for key, value in feature.get("properties", {}).items():
        print(f"{key}: {value}")

    print("\nASSETS")
    for name, asset in feature.get("assets", {}).items():
        print(f"\n[{name}]")

        for key, value in asset.items():
            if key != "href":
                print(f"{key}: {value}")

        print("href:", asset.get("href"))


if __name__ == "__main__":
    main()