from __future__ import annotations

from pathlib import Path
from typing import Any

import planetary_computer

from pipeline.acquisition.downloader import download_asset


REQUIRED_ASSETS = {
    "blue": "blue",
    "green": "green",
    "red": "red",
    "nir08": "nir08",
    "qa_pixel": "qa_pixel",
}


class LandsatDownloadError(RuntimeError):
    """Raised when Landsat asset acquisition fails."""


def get_signed_asset_url(
    item: Any,
    asset_key: str,
) -> str:

    asset = item.assets.get(asset_key)

    if asset is None:
        raise LandsatDownloadError(
            f"Asset not found: {asset_key}"
        )

    signed_item = planetary_computer.sign(item)

    signed_asset = signed_item.assets.get(asset_key)

    if signed_asset is None:
        raise LandsatDownloadError(
            f"Signed asset not found: {asset_key}"
        )

    if not signed_asset.href:
        raise LandsatDownloadError(
            f"Signed asset has no URL: {asset_key}"
        )

    return signed_asset.href


def download_landsat_assets(
    item: Any,
    output_root: str | Path,
) -> dict[str, Path]:

    output_root = Path(output_root)

    scene_id = item.id

    if not scene_id:
        raise LandsatDownloadError(
            "Landsat item has no scene ID."
        )

    scene_dir = output_root / scene_id
    scene_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    downloaded: dict[str, Path] = {}

    for asset_name in REQUIRED_ASSETS:

        url = get_signed_asset_url(
            item,
            asset_name,
        )

        output_path = (
            scene_dir / f"{asset_name}.tif"
        )

        if output_path.exists():

            downloaded[asset_name] = output_path
            continue

        download_asset(
            url,
            output_path,
        )

        downloaded[asset_name] = output_path

    return downloaded
