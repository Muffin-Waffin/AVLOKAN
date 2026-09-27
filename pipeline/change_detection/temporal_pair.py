"""Bitemporal raster pair metadata and compatibility checks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import rasterio


class TemporalPairError(ValueError):
    """Raised when two observations cannot form a valid temporal pair."""


def _parse_date(value: str | date | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    else:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise TemporalPairError(f"Invalid acquisition date: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class RasterGrid:
    width: int
    height: int
    crs: str
    transform: tuple[float, ...]
    bounds: tuple[float, float, float, float]
    band_count: int
    dtypes: tuple[str, ...]

    @classmethod
    def inspect(cls, path: str | Path) -> "RasterGrid":
        with rasterio.open(path) as src:
            if src.crs is None:
                raise TemporalPairError(f"Raster has no CRS: {path}")
            return cls(
                src.width, src.height, src.crs.to_string(), tuple(src.transform),
                tuple(src.bounds), src.count, tuple(src.dtypes),
            )


@dataclass(frozen=True)
class TemporalPair:
    pair_id: str
    tile_id: str
    t1_path: Path
    t2_path: Path
    t1_date: datetime
    t2_date: datetime
    sensor: str
    crs: str
    resolution: tuple[float, float]
    bounds: tuple[float, float, float, float]
    width: int
    height: int
    band_count: int

    @classmethod
    def from_paths(
        cls,
        *,
        tile_id: str,
        t1_path: str | Path,
        t2_path: str | Path,
        t1_date: str | date | datetime,
        t2_date: str | date | datetime,
        sensor: str = "sentinel-2",
        pair_id: str | None = None,
        allow_reversed_dates: bool = False,
    ) -> "TemporalPair":
        first, second = Path(t1_path), Path(t2_path)
        for name, path in (("T1", first), ("T2", second)):
            if not path.is_file():
                raise TemporalPairError(f"{name} raster does not exist: {path}")
        date1, date2 = _parse_date(t1_date), _parse_date(t2_date)
        if date1 == date2:
            raise TemporalPairError("T1 and T2 acquisition dates must differ")
        if date1 > date2 and not allow_reversed_dates:
            raise TemporalPairError("T1 acquisition date must be earlier than T2")
        grid1, grid2 = RasterGrid.inspect(first), RasterGrid.inspect(second)
        if grid1.crs != grid2.crs:
            raise TemporalPairError(f"CRS mismatch: {grid1.crs} != {grid2.crs}")
        if (grid1.width, grid1.height) != (grid2.width, grid2.height):
            raise TemporalPairError("Raster dimensions do not match")
        if grid1.transform != grid2.transform:
            raise TemporalPairError("Raster transforms/resolutions do not match")
        if grid1.bounds != grid2.bounds:
            raise TemporalPairError("Raster bounds do not match")
        if grid1.band_count != grid2.band_count:
            raise TemporalPairError("Band counts do not match")
        if grid1.dtypes != grid2.dtypes:
            raise TemporalPairError("Band dtypes do not match")
        # Model inputs currently use the four-band Sentinel-2 B02/B03/B04/B08 convention.
        if sensor.lower() == "sentinel-2" and grid1.band_count < 4:
            raise TemporalPairError("Sentinel-2 BIT inputs must contain B02, B03, B04, B08")
        return cls(
            pair_id or f"{tile_id}__{date1:%Y%m%d}_{date2:%Y%m%d}", tile_id,
            first, second, date1, date2, sensor, grid1.crs,
            (abs(grid1.transform[0]), abs(grid1.transform[4])), grid1.bounds,
            grid1.width, grid1.height, grid1.band_count,
        )
