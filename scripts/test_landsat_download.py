from pystac_client import Client

import planetary_computer

from pipeline.acquisition.landsat_downloader import (
    download_landsat_assets,
)


STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def main():

    client = Client.open(STAC_URL)

    search = client.search(
        collections=["landsat-c2-l2"],
        bbox=[75.80, 22.70, 75.90, 22.80],
        datetime="2025-03-20/2025-03-31",
        max_items=10,
    )

    items = list(search.items())

    if not items:
        raise RuntimeError(
            "No Landsat scenes found."
        )

    item = min(
        items,
        key=lambda x: x.properties.get(
            "eo:cloud_cover",
            100,
        ),
    )

    print("Selected scene:", item.id)
    print(
        "Cloud cover:",
        item.properties.get("eo:cloud_cover"),
    )

    item = planetary_computer.sign(item)

    assets = download_landsat_assets(
        item,
        "data/raw/landsat",
    )

    print("\nDownloaded:")

    for name, path in assets.items():

        print(
            f"{name}: "
            f"{path} "
            f"({path.stat().st_size:,} bytes)"
        )


if __name__ == "__main__":
    main()
