from pathlib import Path

from pipeline.acquisition.product_downloader import (
    download_product,
)


PRODUCT_URL = (
    "https://download.dataspace.copernicus.eu"
    "/odata/v1/Products("
    "d61ad9fc-bc36-4b69-814f-de80a1acd1d8"
    ")/$value"
)

OUTPUT_PATH = Path(
    "data/raw/sentinel1/"
    "S1A_IW_GRDH_1SDV_20250327T005406_20250327T005431_"
    "058483_073C1B_C9AA_COG.SAFE.zip"
)


def main():
    print("Downloading Sentinel-1 product...")
    print()
    print(f"Output: {OUTPUT_PATH}")
    print()

    path = download_product(
        PRODUCT_URL,
        OUTPUT_PATH,
        timeout=600,
    )

    print()
    print("Download complete.")
    print(f"Path: {path}")
    print(f"Exists: {path.exists()}")
    print(
        f"Size: "
        f"{path.stat().st_size / (1024 ** 3):.2f} GB"
    )


if __name__ == "__main__":
    main()
