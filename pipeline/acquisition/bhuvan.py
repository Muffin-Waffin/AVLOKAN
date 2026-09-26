from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BhuvanDataset:
    dataset_id: str
    name: str
    sensor: str | None
    resolution: str | None
    coverage: str | None
    access_type: str
    url: str


BHUVAN_STORE_URL = (
    "https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore.php"
)


BHUVAN_WMS_URL = (
    "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms"
)


BHUVAN_WMTS_URL = (
    "https://bhuvan-vec2.nrsc.gov.in/"
    "bhuvan/gwc/service/wmts"
)


def get_bhuvan_sources() -> list[BhuvanDataset]:
    return [
        BhuvanDataset(
            dataset_id="bhuvan-store",
            name="Bhuvan Open Data / Product Store",
            sensor=None,
            resolution=None,
            coverage="India",
            access_type="download",
            url=BHUVAN_STORE_URL,
        ),
        BhuvanDataset(
            dataset_id="bhuvan-wms",
            name="Bhuvan Thematic WMS",
            sensor=None,
            resolution=None,
            coverage="India",
            access_type="wms",
            url=BHUVAN_WMS_URL,
        ),
        BhuvanDataset(
            dataset_id="bhuvan-wmts",
            name="Bhuvan Thematic WMTS",
            sensor=None,
            resolution=None,
            coverage="India",
            access_type="wmts",
            url=BHUVAN_WMTS_URL,
        ),
    ]


def list_bhuvan_sources() -> list[dict[str, Any]]:
    return [
        {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "sensor": dataset.sensor,
            "resolution": dataset.resolution,
            "coverage": dataset.coverage,
            "access_type": dataset.access_type,
            "url": dataset.url,
        }
        for dataset in get_bhuvan_sources()
    ]
