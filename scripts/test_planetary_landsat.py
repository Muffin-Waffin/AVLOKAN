from pystac_client import Client
import planetary_computer


STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

bbox = [75.80, 22.70, 75.90, 22.80]

catalog = Client.open(STAC_URL)

search = catalog.search(
    collections=["landsat-c2-l2"],
    bbox=bbox,
    datetime="2025-03-20/2025-03-31",
    query={
        "eo:cloud_cover": {
            "lte": 20
        }
    },
    max_items=10,
)

items = list(search.items())

print(f"Found {len(items)} scenes.")

if not items:
    raise RuntimeError("No Landsat scenes found.")

scene = min(
    items,
    key=lambda item: item.properties.get(
        "eo:cloud_cover",
        100
    ),
)

print(f"\nScene: {scene.id}")
print(
    "Cloud:",
    scene.properties.get("eo:cloud_cover")
)

print("\nOriginal blue URL:")
print(scene.assets["blue"].href)

signed = planetary_computer.sign(scene)

print("\nSigned blue URL:")
print(signed.assets["blue"].href)

print("\nDownloading blue band...")

output = "data/raw/landsat/test_planetary_blue.tif"

import requests

response = requests.get(
    signed.assets["blue"].href,
    stream=True,
    timeout=120,
)

response.raise_for_status()

with open(output, "wb") as file:
    for chunk in response.iter_content(
        chunk_size=1024 * 1024
    ):
        if chunk:
            file.write(chunk)

print(f"Saved: {output}")
