"""JSON-backed catalog for preprocessed raster tiles."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
from typing import Any


class TileCatalogError(RuntimeError):
    """Raised when tile catalog data is invalid or unavailable."""


@dataclass(frozen=True)
class TileMetadata:
    tile_id: str
    source_scene_id: str
    sensor: str | None
    acquisition_datetime: str | None
    tile_path: str
    width: int
    height: int
    crs: str
    resolution: tuple[float, float]
    bounds: tuple[float, float, float, float]
    transform: tuple[float, ...]
    band_count: int
    dtype: str | list[str]
    valid_fraction: float | None
    parent_scene_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TileMetadata":
        value = dict(value)
        for key in ("resolution", "bounds", "transform"):
            if key in value:
                value[key] = tuple(value[key])
        return cls(**value)


def _datetime_value(value: str | date | datetime | None, *, end: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.max if end else time.min)
    else:
        text = str(value)
        if len(text) == 10:
            try:
                as_date = date.fromisoformat(text)
            except ValueError as exc:
                raise ValueError(f"Invalid ISO date/datetime: {value}") from exc
            parsed = datetime.combine(as_date, time.max if end else time.min)
        else:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"Invalid ISO date/datetime: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class TileCatalog:
    """Persistent JSON catalog with tile lookup and metadata filters."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _load(self) -> list[TileMetadata]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise TileCatalogError("Tile catalog JSON must be a list.")
            return [TileMetadata.from_dict(item) for item in raw]
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            raise TileCatalogError(f"Invalid tile catalog: {self.path}") from exc

    def _save(self, records: list[TileMetadata]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps([record.to_dict() for record in records], indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def upsert_many(self, records: list[TileMetadata]) -> tuple[int, int]:
        """Upsert by tile ID; return (new records, updated records)."""
        current = {record.tile_id: record for record in self._load()}
        added = updated = 0
        for record in records:
            if record.tile_id in current:
                if current[record.tile_id] != record:
                    updated += 1
                current[record.tile_id] = record
            else:
                current[record.tile_id] = record
                added += 1
        self._save(sorted(current.values(), key=lambda item: item.tile_id))
        return added, updated

    def get_tile(self, tile_id: str) -> TileMetadata | None:
        return next((record for record in self._load() if record.tile_id == tile_id), None)

    def list_tiles(self) -> list[TileMetadata]:
        return sorted(self._load(), key=lambda item: item.tile_id)

    def filter_tiles(
        self,
        sensor: str | None = None,
        start_date: str | date | datetime | None = None,
        end_date: str | date | datetime | None = None,
        bbox: tuple[float, float, float, float] | list[float] | None = None,
    ) -> list[TileMetadata]:
        """Filter dates inclusively and bounds by intersection.

        ``bbox`` uses the same coordinate reference system as each tile's
        stored bounds. The catalog does not reproject between CRSs.
        """
        start, end = _datetime_value(start_date), _datetime_value(end_date, end=True)
        if bbox is not None and len(bbox) != 4:
            raise ValueError("bbox must be (min_x, min_y, max_x, max_y)")
        found = []
        for item in self._load():
            if sensor is not None and (item.sensor or "").lower() != sensor.lower():
                continue
            if start is not None or end is not None:
                if item.acquisition_datetime is None:
                    continue
                acquired = _datetime_value(item.acquisition_datetime)
                if start is not None and acquired < start:
                    continue
                if end is not None and acquired > end:
                    continue
            if bbox is not None:
                left, bottom, right, top = item.bounds
                qleft, qbottom, qright, qtop = bbox
                if right < qleft or qright < left or top < qbottom or qtop < bottom:
                    continue
            found.append(item)
        return sorted(found, key=lambda item: item.tile_id)

    def count(self) -> int:
        return len(self._load())
