"""Catalog-backed candidate selection for retrieval filters."""
from __future__ import annotations

from datetime import date, datetime
from typing import Sequence

from pipeline.indexing.tile_catalog import TileCatalog, TileMetadata


def eligible_tiles(
    catalog: TileCatalog,
    *,
    sensor: str | None = None,
    date_from: str | date | datetime | None = None,
    date_to: str | date | datetime | None = None,
    bbox: Sequence[float] | None = None,
) -> list[TileMetadata]:
    """Resolve eligible catalog records before FAISS ranking."""
    if bbox is not None:
        if len(bbox) != 4:
            raise ValueError("bbox must be [min_x, min_y, max_x, max_y]")
        left, bottom, right, top = (float(value) for value in bbox)
        if left > right or bottom > top:
            raise ValueError("bbox minimum coordinates must not exceed maximum coordinates")
        bbox = (left, bottom, right, top)
    return catalog.filter_tiles(
        sensor=sensor,
        start_date=date_from,
        end_date=date_to,
        bbox=bbox,
    )
