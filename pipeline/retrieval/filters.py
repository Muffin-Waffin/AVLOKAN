"""Catalog-backed candidate selection for retrieval filters."""
from __future__ import annotations

from datetime import date, datetime
from typing import Sequence
from rasterio.crs import CRS
from rasterio.warp import transform_bounds

from pipeline.indexing.tile_catalog import TileCatalog, TileMetadata


def eligible_tiles(
    catalog: TileCatalog,
    *,
    sensor: str | None = None,
    date_from: str | date | datetime | None = None,
    date_to: str | date | datetime | None = None,
    bbox: Sequence[float] | None = None,
    bbox_crs: str | CRS | None = None,
) -> list[TileMetadata]:
    """Resolve eligible catalog records before FAISS ranking."""
    if bbox is not None:
        if len(bbox) != 4:
            raise ValueError("bbox must be [min_x, min_y, max_x, max_y]")
        left, bottom, right, top = (float(value) for value in bbox)
        if left > right or bottom > top:
            raise ValueError("bbox minimum coordinates must not exceed maximum coordinates")
        bbox = (left, bottom, right, top)
    if bbox is None or bbox_crs is None:
        return catalog.filter_tiles(
            sensor=sensor,
            start_date=date_from,
            end_date=date_to,
            bbox=bbox,
        )
    source_crs = CRS.from_user_input(bbox_crs)
    left, bottom, right, top = (float(value) for value in bbox)
    eligible = catalog.filter_tiles(sensor=sensor, start_date=date_from, end_date=date_to)
    selected = []
    for record in eligible:
        if not record.crs:
            continue
        target_crs = CRS.from_user_input(record.crs)
        if source_crs == target_crs:
            query_bounds = (left, bottom, right, top)
        else:
            query_bounds = transform_bounds(source_crs, target_crs, left, bottom, right, top)
        qleft, qbottom, qright, qtop = query_bounds
        rleft, rbottom, rright, rtop = record.bounds
        if not (rright < qleft or qright < rleft or rtop < qbottom or qtop < rbottom):
            selected.append(record)
    return selected
