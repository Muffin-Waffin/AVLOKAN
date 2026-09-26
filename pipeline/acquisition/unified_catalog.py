from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pipeline.acquisition.catalog import SceneCatalog
from pipeline.acquisition.models import Scene


class UnifiedCatalog:
    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.catalog = SceneCatalog(path)

    def add(self, scene: Scene) -> bool:
        return self.catalog.add(scene)

    def add_many(
        self,
        scenes: list[Scene],
    ) -> int:
        return self.catalog.add_many(scenes)

    def all(self) -> list[Scene]:
        return self.catalog.get_all()

    def count(self) -> int:
        return self.catalog.count()

    def by_sensor(
        self,
        sensor: str,
    ) -> list[Scene]:

        return [
            scene
            for scene in self.all()
            if scene.sensor.lower()
            == sensor.lower()
        ]

    def by_date_range(
        self,
        start: str,
        end: str,
    ) -> list[Scene]:

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        results = []

        for scene in self.all():

            scene_dt = datetime.fromisoformat(
                scene.acquisition_datetime
                .replace("Z", "+00:00")
            )

            if start_dt <= scene_dt <= end_dt:
                results.append(scene)

        return results

    def downloaded(self) -> list[Scene]:
        return [
            scene
            for scene in self.all()
            if scene.downloaded
        ]

    def pending_downloads(self) -> list[Scene]:
        return [
            scene
            for scene in self.all()
            if not scene.downloaded
        ]
