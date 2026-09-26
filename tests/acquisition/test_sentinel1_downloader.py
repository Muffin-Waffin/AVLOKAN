import pytest

from pipeline.acquisition.sentinel1_downloader import (
    Sentinel1DownloadError,
    get_https_asset_url,
)


def test_get_vv_https_url():
    feature = {
        "assets": {
            "vv": {
                "alternate": {
                    "https": {
                        "href": "https://example.com/vv.tiff"
                    }
                }
            }
        }
    }

    url = get_https_asset_url(
        feature,
        "vv",
    )

    assert url == "https://example.com/vv.tiff"


def test_get_vh_https_url():
    feature = {
        "assets": {
            "vh": {
                "alternate": {
                    "https": {
                        "href": "https://example.com/vh.tiff"
                    }
                }
            }
        }
    }

    url = get_https_asset_url(
        feature,
        "vh",
    )

    assert url == "https://example.com/vh.tiff"


def test_missing_asset():
    feature = {
        "assets": {}
    }

    with pytest.raises(Sentinel1DownloadError):
        get_https_asset_url(
            feature,
            "vv",
        )


def test_missing_https_url():
    feature = {
        "assets": {
            "vv": {
                "alternate": {}
            }
        }
    }

    with pytest.raises(Sentinel1DownloadError):
        get_https_asset_url(
            feature,
            "vv",
        )