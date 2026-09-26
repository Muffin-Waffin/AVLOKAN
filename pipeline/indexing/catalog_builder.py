"""Incrementally discover GeoTIFF tiles and persist their metadata."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

import rasterio

from pipeline.indexing.tile_catalog import TileCatalog, TileMetadata
from pipeline.preprocessing.raster_inspector import inspect_raster


class CatalogBuildError(RuntimeError):
    """Raised when tile discovery or metadata validation fails."""


@dataclass(frozen=True)
class CatalogBuildReport:
    discovered: int
    added: int
    updated: int
    total: int
    missing_files: tuple[str, ...]
    duplicate_ids: tuple[str, ...]


def _stable_tile_id(relative_path: Path) -> str:
    without_suffix = relative_path.with_suffix("").as_posix()
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", without_suffix.replace("/", "__"))


def _stored_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _manifest_records(root: Path) -> dict[Path, dict]:
    records = {}
    for manifest_path in sorted(root.rglob("tiles.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CatalogBuildError(f"Invalid tile manifest: {manifest_path}") from exc
        for record in manifest.get("tiles", []):
            raw_path = Path(record["path"])
            options = [raw_path]
            if not raw_path.is_absolute():
                options.extend((Path.cwd() / raw_path, manifest_path.parent / raw_path.name))
            for candidate in options:
                if candidate.exists():
                    records[candidate.resolve()] = record
                    break
    return records


def build_tile_catalog(input_dir: str | Path, output_catalog: str | Path) -> CatalogBuildReport:
    root, output = Path(input_dir), Path(output_catalog)
    if not root.is_dir():
        raise CatalogBuildError(f"Tile input directory does not exist: {root}")
    catalog = TileCatalog(output)
    old_records = catalog.list_tiles()
    manifests = _manifest_records(root)
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".tif", ".tiff"})
    found: dict[str, TileMetadata] = {}
    duplicates: set[str] = set()

    for path in files:
        relative = path.relative_to(root)
        inspection = inspect_raster(path)
        manifest = manifests.get(path.resolve(), {})
        scene_id = str(manifest.get("source_scene") or (relative.parent.as_posix() if relative.parent != Path(".") else path.stem))
        tile_id = _stable_tile_id(relative)
        if tile_id in found:
            duplicates.add(tile_id)
            continue
        with rasterio.open(path) as src:
            dtypes = list(src.dtypes)
        dtype: str | list[str] = dtypes[0] if len(set(dtypes)) == 1 else dtypes
        acquired = manifest.get("acquisition_datetime") or manifest.get("acquisition_date")
        metadata = TileMetadata(
            tile_id=tile_id,
            source_scene_id=scene_id,
            sensor=manifest.get("sensor"),
            acquisition_datetime=acquired,
            tile_path=_stored_path(path),
            width=inspection.width,
            height=inspection.height,
            crs=inspection.crs or "",
            resolution=inspection.resolution,
            bounds=inspection.bounds,
            transform=inspection.transform,
            band_count=inspection.count,
            dtype=dtype,
            valid_fraction=(float(manifest["valid_fraction"]) if "valid_fraction" in manifest else
                            min((band.valid_fraction for band in inspection.bands), default=None)),
            parent_scene_path=manifest.get("source") or manifest.get("parent_scene_path"),
        )
        found[tile_id] = metadata

    added, updated = catalog.upsert_many(list(found.values()))
    missing = tuple(sorted(record.tile_id for record in old_records if not Path(record.tile_path).exists()))
    return CatalogBuildReport(len(files), added, updated, catalog.count(), missing, tuple(sorted(duplicates)))
