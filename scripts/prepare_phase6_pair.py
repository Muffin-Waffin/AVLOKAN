"""Fetch a matching AOI window from Planetary Computer Sentinel-2 COGs."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.windows import from_bounds

ITEM_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a/items/{item_id}"
BANDS = ("B02", "B03", "B04", "B08")


def prepare(t1_path: Path, output_path: Path, item_id: str) -> Path:
    try:
        import planetary_computer
    except ImportError as exc:
        raise RuntimeError("Install planetary-computer to sign Sentinel-2 COG URLs") from exc
    item = requests.get(ITEM_URL.format(item_id=item_id), timeout=30)
    item.raise_for_status()
    properties = item.json()["properties"]
    acquired = properties["datetime"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(t1_path) as reference:
        if reference.count < 4 or reference.crs is None:
            raise ValueError("T1 must be a georeferenced four-band B02/B03/B04/B08 raster")
        profile = reference.profile.copy()
        profile.update(count=4, dtype="float32", nodata=np.nan, compress="deflate", predictor=3)
        with rasterio.open(output_path, "w", **profile) as dst:
            for index, band in enumerate(BANDS, start=1):
                href = item.json()["assets"][band]["href"]
                with rasterio.open(planetary_computer.sign(href)) as src:
                    if src.crs != reference.crs:
                        raise ValueError(f"{band} CRS does not match T1")
                    window = from_bounds(*reference.bounds, transform=src.transform)
                    window = window.round_offsets().round_lengths()
                    if (window.width, window.height) != (reference.width, reference.height):
                        raise ValueError(f"{band} COG grid does not match requested AOI window: {window}")
                    data = src.read(1, window=window)
                    # Sentinel-2 L2A COG pixel values are integer DN at scale 1e-4.
                    reflectance = data.astype(np.float32) * np.float32(0.0001)
                    reflectance[data == 0] = np.nan
                    dst.write(reflectance, index)
            dst.update_tags(
                sensor="sentinel-2", acquisition_datetime=acquired,
                source_scene_id=item.json()["id"], bands=",".join(BANDS),
                radiometry="L2A surface reflectance = DN * 0.0001",
                source="Microsoft Planetary Computer Sentinel-2 L2A COG; AOI window only",
            )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t1", type=Path, default=Path("data/processed/phase2_validation/s2_reflectance_512.tif"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/phase6_validation/s2_20250324_512.tif"))
    parser.add_argument("--item-id", default="S2B_MSIL2A_20250324T052649_R105_T43QEF_20250324T074123")
    args = parser.parse_args()
    print(prepare(args.t1, args.output, args.item_id))


if __name__ == "__main__":
    main()
