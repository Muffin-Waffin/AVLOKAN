from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Scene:
    scene_id: str
    sensor: str
    collection: str
    acquisition_datetime: str

    bbox: list[float]
    footprint: dict[str, Any]

    cloud_cover: float | None = None

    orbit_direction: str | None = None
    polarization: list[str] | None = None

    source_url: str | None = None
    local_path: str | None = None

    downloaded: bool = False

    resolution_m: float | None = None
    crs: str | None = None

    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "Scene":
        return cls(**data)
