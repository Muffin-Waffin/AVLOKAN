from __future__ import annotations

import json
from pathlib import Path

from pipeline.acquisition.models import Scene


class CatalogError(RuntimeError):
    """Raised when the scene catalog cannot be accessed."""


class SceneCatalog:
    """Persistent local catalog of satellite scenes."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise CatalogError(
                f"Invalid catalog JSON: {self.path}"
            ) from exc

        if not isinstance(data, list):
            raise CatalogError(
                "Scene catalog must contain a JSON list."
            )

        return data

    def _save(self, scenes: list[dict]) -> None:
        self._ensure_parent()

        temporary_path = self.path.with_suffix(".tmp")

        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(
                scenes,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_path.replace(self.path)

    def add(self, scene: Scene) -> bool:
        """
        Add a scene to the catalog.

        Returns:
            True if the scene was added.
            False if the scene already exists.
        """

        scenes = self._load()

        for existing in scenes:
            if existing.get("scene_id") == scene.scene_id:
                return False

        scenes.append(scene.to_dict())
        self._save(scenes)

        return True

    def add_many(self, scenes: list[Scene]) -> int:
        """Add multiple scenes and return the number actually added."""

        existing = self._load()
        existing_ids = {
            scene.get("scene_id")
            for scene in existing
        }

        added = 0

        for scene in scenes:
            if scene.scene_id in existing_ids:
                continue

            existing.append(scene.to_dict())
            existing_ids.add(scene.scene_id)
            added += 1

        self._save(existing)

        return added

    def get_all(self) -> list[Scene]:
        """Return all scenes in the catalog."""

        return [
            Scene.from_dict(data)
            for data in self._load()
        ]

    def get(self, scene_id: str) -> Scene | None:
        """Return a scene by ID."""

        for scene in self.get_all():
            if scene.scene_id == scene_id:
                return scene

        return None

    def count(self) -> int:
        """Return the number of scenes in the catalog."""

        return len(self._load())