from pipeline.acquisition.aoi import load_aoi, get_bbox
from pipeline.acquisition.cdse import CDSEClient


SCENE_ID = (
    "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_"
    "058483_073C1B_C9AA_COG"
)

AOI_PATH = "data/aoi/test_area.geojson"


def main():
    aoi = load_aoi(AOI_PATH)

    client = CDSEClient()

    print("Searching CDSE for Sentinel-1 scene...")

    result = client.search(
        collection="sentinel-1-grd",
        bbox=get_bbox(aoi),
        start="2025-03-27",
        end="2025-03-27",
        limit=20,
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

    print("\nScene:")
    print(feature.get("id"))

    print("\nProperties:")
    for key, value in feature.get("properties", {}).items():
        print(f"  {key}: {value}")

    print("\nLinks:")

    for link in feature.get("links", []):
        print(
            f"  rel={link.get('rel')}"
            f"  href={link.get('href')}"
            f"  type={link.get('type')}"
        )

    print("\nAssets:")

    for key, asset in feature.get("assets", {}).items():
        print(f"\n[{key}]")
        print(f"  title: {asset.get('title')}")
        print(f"  type:  {asset.get('type')}")
        print(f"  href:  {asset.get('href')}")

        alternate = asset.get("alternate", {})

        if alternate:
            for alt_name, alt_value in alternate.items():
                print(f"  alternate[{alt_name}]: {alt_value}")


if __name__ == "__main__":
    main()
