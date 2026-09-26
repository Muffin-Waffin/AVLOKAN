from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.acquisition.auth import get_access_token
from pipeline.acquisition.downloader import download_asset


REQUIRED_BANDS = {
    "B02": "B02_10m",
    "B03": "B03_10m",
    "B04": "B04_10m",
    "B08": "B08_10m",
}

REQUIRED_QUALITY_LAYERS = {
    "SCL": "SCL_20m",
}


class Sentinel2DownloadError(RuntimeError):
    """Raised when Sentinel-2 asset acquisition fails."""


def get_https_asset_url(
    feature: dict[str, Any],
    asset_name: str,
) -> str:
    """
    Extract the authenticated HTTPS asset URL from a Sentinel-2 STAC feature.
    """

    assets = feature.get("assets", {})
    asset = assets.get(asset_name)

    if not asset:
        raise Sentinel2DownloadError(
            f"Asset not found in STAC feature: {asset_name}"
        )

    alternate = asset.get("alternate", {})
    https = alternate.get("https", {})
    href = https.get("href")

    if not href:
        raise Sentinel2DownloadError(
            f"No HTTPS download URL found for asset: {asset_name}"
        )

    return href


def download_sentinel2_bands(
    feature: dict[str, Any],
    output_root: str | Path,
) -> dict[str, Path]:
    """
    Download the required Sentinel-2 optical bands and SCL quality layer.

    Optical bands:
        B02 Blue
        B03 Green
        B04 Red
        B08 NIR

    Quality:
        SCL Scene Classification Layer at 20 m

    Returns a mapping from asset name to local file path.
    """

    output_root = Path(output_root)

    scene_id = feature.get("id")

    if not scene_id:
        raise Sentinel2DownloadError(
            "STAC feature has no scene ID."
        )

    scene_dir = output_root / scene_id
    scene_dir.mkdir(parents=True, exist_ok=True)

    # Authenticate once for the entire scene.
    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
    }

    downloaded: dict[str, Path] = {}

    assets_to_download = {
        **REQUIRED_BANDS,
        **REQUIRED_QUALITY_LAYERS,
    }

    for asset_name, asset_key in assets_to_download.items():

        url = get_https_asset_url(
            feature,
            asset_key,
        )

        if asset_name == "SCL":
            filename = "SCL_20m.jp2"
        else:
            filename = f"{asset_name}_10m.jp2"

        output_path = scene_dir / filename

        if output_path.exists():
            downloaded[asset_name] = output_path
            continue

        download_asset(
            url,
            output_path,
            headers=headers,
            timeout=300,
        )

        downloaded[asset_name] = output_path

    return downloaded
