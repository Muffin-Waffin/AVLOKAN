from pathlib import Path

import pytest

from pipeline.acquisition.sentinel2_downloader import (
    Sentinel2DownloadError,
    get_https_asset_url,
)


def test_get_https_asset_url():
    feature = {
        "assets": {
            "B04_10m": {
                "alternate": {
                    "https": {
                        "href": "https://example.com/B04.jp2"
                    }
                }
            }
        }
    }

    url = get_https_asset_url(
        feature,
        "B04_10m",
    )

    assert url == "https://example.com/B04.jp2"


def test_missing_asset():
    feature = {
        "assets": {}
    }

    with pytest.raises(Sentinel2DownloadError):
        get_https_asset_url(
            feature,
            "B04_10m",
        )


def test_missing_https_url():
    feature = {
        "assets": {
            "B04_10m": {
                "alternate": {}
            }
        }
    }

    with pytest.raises(Sentinel2DownloadError):
        get_https_asset_url(
            feature,
            "B04_10m",
        )