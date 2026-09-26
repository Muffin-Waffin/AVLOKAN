from pathlib import Path

from pipeline.acquisition.downloader import download_asset


BASE_URL = (
    "https://zipper.dataspace.copernicus.eu/odata/v1/"
    "Products(ae0a8b2e-97ad-40da-87e7-a27665bbce3a)/"
    "Nodes(S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014.SAFE)/"
    "Nodes(GRANULE)/"
    "Nodes(L2A_T43QEF_A002935_20250329T053314)/"
    "Nodes(IMG_DATA)/"
    "Nodes(R10m)/"
)


BANDS = {
    "B02": (
        BASE_URL
        + "Nodes(T43QEF_20250329T052841_B02_10m.jp2)/$value"
    ),
    "B03": (
        BASE_URL
        + "Nodes(T43QEF_20250329T052841_B03_10m.jp2)/$value"
    ),
    "B04": (
        BASE_URL
        + "Nodes(T43QEF_20250329T052841_B04_10m.jp2)/$value"
    ),
    "B08": (
        BASE_URL
        + "Nodes(T43QEF_20250329T052841_B08_10m.jp2)/$value"
    ),
}


OUTPUT_DIR = Path(
    "data/raw/sentinel2/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014"
)


def main():
    for band, url in BANDS.items():
        output = OUTPUT_DIR / f"{band}_10m.jp2"

        print()
        print(f"Downloading {band}_10m...")

        if output.exists():
            print(f"Already exists: {output}")
            print(f"File size: {output.stat().st_size:,} bytes")
            continue

        path = download_asset(
            url,
            output,
        )

        print(f"Downloaded: {path}")
        print(f"File size: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()