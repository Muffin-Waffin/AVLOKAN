from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.acquisition.downloader import download_asset


REQUIRED_ASSETS = {
    "vv": "vv",
    "vh": "vh",
}


class Sentinel1DownloadError(RuntimeError):
    """Raised when Sentinel-1 asset acquisition fails."""


def get_https_asset_url(
    feature: dict[str, Any],
    asset_key: str,
) -> str:
    """Get the authenticated HTTPS URL for a Sentinel-1 asset."""

    assets = feature.get("assets", {})
    asset = assets.get(asset_key)

    if not asset:
        raise Sentinel1DownloadError(
            f"Asset not found in STAC feature: {asset_key}"
        )

    alternate = asset.get("alternate", {})
    https = alternate.get("https", {})
    href = https.get("href")

    if not href:
        raise Sentinel1DownloadError(
            f"No HTTPS download URL found for asset: {asset_key}"
        )

    return href


def download_sentinel1_assets(
    feature: dict[str, Any],
    output_root: str | Path,
) -> dict[str, Path]:
    """
    Download VV and VH Sentinel-1 GRD assets.

    Returns:
        Mapping from polarization to local COG path.
    """

    output_root = Path(output_root)

    scene_id = feature.get("id")

    if not scene_id:
        raise Sentinel1DownloadError(
            "STAC feature has no scene ID."
        )

    scene_dir = output_root / scene_id
    scene_dir.mkdir(parents=True, exist_ok=True)

    downloaded: dict[str, Path] = {}

    for polarization in REQUIRED_ASSETS:
        url = get_https_asset_url(
            feature,
            polarization,
        )

        output_path = (
            scene_dir / f"{polarization.upper()}.tif"
        )

        if output_path.exists():
            downloaded[polarization] = output_path
            continue

        download_asset(
            url,
            output_path,
        )

        downloaded[polarization] = output_path

    return downloaded