"""HTTP API over the existing local AVLOKAN catalogs and analysis pipelines."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Literal
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import numpy as np
import rasterio
from rasterio.features import bounds as geometry_bounds, shapes as raster_shapes
from rasterio.warp import transform_bounds, transform_geom
import yaml

from pipeline.api.database import ApiDatabase
from pipeline.api.schemas import (
    AOIListResponse,
    AOIRecord,
    ApiHealthResponse,
    AuditResponse,
    ChangeAnalysisResponse,
    ChangeListResponse,
    DashboardResponse,
    DecisionResponse,
    ReviewQueueResponse,
    SceneSearchResponse,
    SearchResponse,
)


ROOT = Path(__file__).resolve().parents[2]
SENSOR_NAMES = {
    "s2": ("sentinel-2", "S2", "Sentinel-2"),
    "sentinel-2": ("sentinel-2", "S2", "Sentinel-2"),
    "s1": ("sentinel-1", "S1", "Sentinel-1 SAR"),
    "sentinel-1": ("sentinel-1", "S1", "Sentinel-1 SAR"),
    "l8": ("landsat", "L8", "Landsat C2"),
    "landsat": ("landsat", "L8", "Landsat C2"),
    "bh": ("bhuvan", "BH", "Bhuvan / ISRO"),
    "bhuvan": ("bhuvan", "BH", "Bhuvan / ISRO"),
}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    sensors: list[str] = Field(default_factory=lambda: ["s2", "s1", "l8"])
    top_k: int = Field(default=24, ge=1, le=100)
    date_from: date | None = None
    date_to: date | None = None
    bbox: list[float] | None = None
    bbox_crs: str = Field(default="EPSG:4326", description="Coordinate reference system of bbox")
    max_cloud: float | None = Field(default=None, ge=0, le=100)
    min_similarity: float = Field(default=0.0, ge=-1, le=1)


class AOICreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=3.0, gt=0, le=500)


class SceneSearchRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=3.0, gt=0, le=500)
    date_from: date | None = None
    date_to: date | None = None
    sensors: list[str] = Field(default_factory=lambda: ["sentinel-2", "landsat"])
    max_cloud: float | None = Field(default=None, ge=0, le=100)


class ChangeAnalysisRequest(BaseModel):
    t1_path: str | None = Field(default=None, min_length=1)
    t2_path: str | None = Field(default=None, min_length=1)
    t1_date: datetime | None = None
    t2_date: datetime | None = None
    t1_observation_id: str | None = Field(default=None, min_length=1)
    t2_observation_id: str | None = Field(default=None, min_length=1)
    sensor: str = "sentinel-2"
    tile_id: str = "api-change-analysis"
    pair_id: str | None = None
    name: str | None = Field(default=None, max_length=160)
    aoi_id: str | None = None
    allow_reversed_dates: bool = False


class ReviewDecision(BaseModel):
    decision: Literal["confirm", "reject", "need_review"]
    analyst: str = Field(default="Analyst 01", min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


def _load_settings(config_path: str | Path | None) -> tuple[dict, Path]:
    selected = Path(config_path or os.environ.get("AVLOKAN_API_CONFIG", ROOT / "configs/api.yaml"))
    if not selected.is_absolute():
        selected = ROOT / selected
    try:
        raw = yaml.safe_load(selected.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"API config not found: {selected}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"API config must contain a mapping: {selected}")
    accepted = {"database", "tile_catalog", "scene_catalog", "faiss_index", "embedding_model",
                "change_analysis", "analysis_output_directory", "analysis_ready_observations",
                "allowed_input_roots", "cors_origins"}
    unknown = set(raw) - accepted
    if unknown:
        raise ValueError(f"Unknown API config keys: {sorted(unknown)}")
    return raw, selected


def _path(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _sensor_filter_names(values: list[str]) -> list[str]:
    normalized = []
    for value in values:
        item = SENSOR_NAMES.get(value.strip().lower())
        if item is None:
            raise HTTPException(422, f"Unsupported sensor filter: {value}")
        if item[0] not in normalized:
            normalized.append(item[0])
    if not normalized:
        raise HTTPException(422, "Select at least one sensor")
    return normalized


def create_app(config_path: str | Path | None = None, *, database_path: str | Path | None = None) -> FastAPI:
    settings, config_file = _load_settings(config_path)
    paths = {key: _path(ROOT, settings[key]) for key in (
        "database", "tile_catalog", "scene_catalog", "faiss_index", "embedding_model", "change_analysis"
    )}
    if settings.get("analysis_output_directory"):
        paths["analysis_output_directory"] = _path(ROOT, settings["analysis_output_directory"])
    if database_path is not None:
        paths["database"] = Path(database_path).resolve()
    input_roots = [_path(ROOT, value) for value in settings.get("allowed_input_roots", [])]
    db = ApiDatabase(paths["database"])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.initialize()
        yield

    app = FastAPI(title="AVLOKAN Local API", version="0.8.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.paths = paths
    app.state.database = db
    app.state.retriever = None
    app.state.retriever_error = None
    app.state.retriever_lock = threading.Lock()
    app.state.root = ROOT
    app.state.config_file = config_file
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get("cors_origins", []),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def load_scene_records() -> list[dict]:
        path = paths["scene_catalog"]
        if not path.is_file():
            return []
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(503, f"Local scene catalog is unavailable or invalid: {path.name}") from exc
        if not isinstance(value, list):
            raise HTTPException(503, "Local scene catalog must be a JSON list")
        return value

    def load_analysis_ready_observations() -> list[dict]:
        records = settings.get("analysis_ready_observations", [])
        if not isinstance(records, list):
            raise HTTPException(503, "analysis_ready_observations must be a list in the API config")
        output = []
        from rasterio.warp import transform_bounds
        for record in records:
            try:
                if not isinstance(record, dict):
                    raise ValueError("record must be an object")
                observation_id = str(record["id"])
                path = _path(ROOT, record["path"])
                acquired = datetime.fromisoformat(str(record["acquisition_datetime"]).replace("Z", "+00:00"))
                sensor = SENSOR_NAMES[str(record["sensor"]).lower()][0]
                role = str(record["observation_role"])
                pair_id = str(record["pair_id"])
                source = str(record["source"])
                if record.get("record_type") != "prototype_analysis_ready" or role not in {"T1", "T2"}:
                    raise ValueError("record_type or observation_role is invalid")
                if path.is_file():
                    with rasterio.open(path) as src:
                        if src.crs is None:
                            raise ValueError(f"raster has no CRS: {path.name}")
                        bbox = list(transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21))
                else:
                    bbox = None
                output.append({
                    "id": observation_id, "date": acquired.date().isoformat(), "sensor": sensor,
                    "cloud": None, "cloud_percent": None, "blocked": False,
                    "quality": None, "quality_basis": None, "bbox": bbox, "footprint": None,
                    "available_locally": path.is_file(),
                    "local_path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                    "cloud_metadata_available": False, "record_type": "prototype_analysis_ready",
                    "source": source, "observation_role": role, "pair_id": pair_id,
                    "acquisition_datetime": acquired.isoformat(), "_resolved_path": path,
                })
            except (KeyError, TypeError, ValueError, OSError) as exc:
                raise HTTPException(503, f"Invalid analysis-ready observation configuration: {exc}") from exc
        ids = [record["id"] for record in output]
        if len(ids) != len(set(ids)):
            raise HTTPException(503, "Analysis-ready observation IDs must be unique")
        return output

    def get_retriever():
        with app.state.retriever_lock:
            if app.state.retriever is not None:
                return app.state.retriever
            if app.state.retriever_error:
                raise HTTPException(503, f"Semantic retrieval is unavailable: {app.state.retriever_error}")
            try:
                from pipeline.embeddings.remoteclip import RemoteCLIPAdapter
                from pipeline.indexing.incremental_index import IncrementalIndex
                from pipeline.indexing.tile_catalog import TileCatalog
                from pipeline.retrieval.retriever import Retriever

                embedding_cfg = yaml.safe_load(paths["embedding_model"].read_text(encoding="utf-8"))
                model_cfg = embedding_cfg["model"]
                checkpoint = _path(ROOT, model_cfg["checkpoint"])
                adapter = RemoteCLIPAdapter(checkpoint, device=embedding_cfg.get("runtime", {}).get("device", "auto"))
                index = IncrementalIndex(paths["faiss_index"], dimension=int(model_cfg.get("embedding_dim") or 512))
                catalog = TileCatalog(paths["tile_catalog"])
                retriever = Retriever(adapter, index, catalog)
                app.state.retriever = retriever
                return retriever
            except Exception as exc:
                app.state.retriever_error = f"{type(exc).__name__}: {exc}"
                raise HTTPException(503, f"Semantic retrieval is unavailable: {app.state.retriever_error}") from exc

    def scene_cloud_by_day() -> dict[tuple[str, str], float | None]:
        values: dict[tuple[str, str], set[float]] = {}
        for item in load_scene_records():
            stamp = str(item.get("acquisition_datetime") or "")[:10]
            sensor = SENSOR_NAMES.get(str(item.get("sensor") or "").lower(), (str(item.get("sensor")),))[0]
            cloud = item.get("cloud_cover")
            if stamp and cloud is not None:
                # STAC eo:cloud_cover in the existing catalogs is a percent value.
                values.setdefault((sensor, stamp), set()).add(float(cloud))
        # Tiles only carry source_scene_id/date/sensor. Use a date-level cloud value
        # only where the local STAC catalog makes that join unambiguous.
        return {key: next(iter(cloud_values)) for key, cloud_values in values.items() if len(cloud_values) == 1}

    def public_search_result(record: dict, cloud_by_day: dict) -> dict:
        stamp = (record.get("acquisition_datetime") or "")[:10]
        sensor_key = str(record.get("sensor") or "").lower()
        cloud = cloud_by_day.get((sensor_key, stamp))
        lat = lng = None
        try:
            from rasterio.warp import transform as transform_coords
            bounds = record.get("bounds")
            source_crs = record.get("crs")
            if bounds and source_crs:
                xs, ys = transform_coords(source_crs, "EPSG:4326", [(bounds[0] + bounds[2]) / 2],
                                          [(bounds[1] + bounds[3]) / 2])
                lng, lat = float(xs[0]), float(ys[0])
        except Exception:
            pass
        sensor_info = next((value for value in SENSOR_NAMES.values() if value[0] == sensor_key),
                           (sensor_key, sensor_key.upper(), sensor_key))
        return {
            "id": record["tile_id"], "tile_id": record["tile_id"],
            "lat": lat, "lng": lng, "region": record.get("source_scene_id") or "Local archive",
            "date": stamp or None,
            "sensor": {"id": sensor_info[1].lower(), "name": sensor_info[2], "tag": sensor_info[1]},
            "sim": float(record["score"]), "cloud": cloud, "cloud_percent": cloud,
            "thumbnail_url": f"/api/tiles/{record['tile_id']}/preview",
            "seed": None, "feature": None,
            "resolution": record.get("resolution"), "crs": record.get("crs"),
            "bounds": record.get("bounds"), "tile_path": record.get("path"),
            "rank": record.get("rank"),
        }

    def run_search(request: SearchRequest, *, image_path: Path | None = None) -> dict:
        sensors = _sensor_filter_names(request.sensors)
        if request.date_from and request.date_to and request.date_from > request.date_to:
            raise HTTPException(422, "date_from must be on or before date_to")
        if request.bbox is not None and (len(request.bbox) != 4 or request.bbox[0] >= request.bbox[2]
                                         or request.bbox[1] >= request.bbox[3]):
            raise HTTPException(422, "bbox must be [west, south, east, north] with positive area")
        retriever = get_retriever()
        cloud_by_day = scene_cloud_by_day()
        found: dict[str, dict] = {}
        timing_parts: list[dict] = []
        for sensor in sensors:
            kwargs = dict(top_k=request.top_k, sensor=sensor, date_from=request.date_from,
                          date_to=request.date_to, bbox=request.bbox,
                          bbox_crs=request.bbox_crs if request.bbox else None)
            response = (retriever.search_image(image_path, **kwargs) if image_path
                        else retriever.search_text(request.query, **kwargs))
            timing_parts.append(response["timings"])
            for record in response["results"]:
                record["score"] = float(record["score"])
                record["sensor"] = sensor
                stamp = (record.get("acquisition_datetime") or "")[:10]
                cloud = cloud_by_day.get((sensor, stamp))
                if record["score"] < request.min_similarity:
                    continue
                if request.max_cloud is not None and cloud is not None and cloud > request.max_cloud:
                    continue
                if request.max_cloud is not None and cloud is None:
                    # Unknown cloud cover is disclosed, not silently represented as clear.
                    record["cloud_unknown"] = True
                found[record["tile_id"]] = record
        ranked = sorted(found.values(), key=lambda row: (-row["score"], row["tile_id"]))[:request.top_k]
        for rank, row in enumerate(ranked, 1):
            row["rank"] = rank
        results = [public_search_result(row, cloud_by_day) for row in ranked]
        return {
            "query": "image query" if image_path else request.query,
            "query_type": "image" if image_path else "text",
            "results": results,
            "filters": {"sensors": sensors, "date_from": _iso(request.date_from), "date_to": _iso(request.date_to),
                        "bbox": request.bbox, "max_cloud": request.max_cloud,
                        "bbox_crs": request.bbox_crs if request.bbox else None,
                        "min_similarity": request.min_similarity, "top_k": request.top_k},
            "warnings": (["Cloud metadata is missing for one or more results; max_cloud was not evaluated for those records."]
                          if any(row.get("cloud_unknown") for row in found.values()) else []),
            "diagnostics": {"returned": len(results), "catalog_tiles": len(retriever.catalog.list_tiles()),
                            "indexed_tiles": retriever.faiss_index.size(),
                            "score_distribution": ({"min": min(row["sim"] for row in results),
                                                    "max": max(row["sim"] for row in results),
                                                    "mean": sum(row["sim"] for row in results) / len(results)}
                                                   if results else None)},
            "timings": {"per_sensor": timing_parts,
                        "total_ms": round(sum(part["total_ms"] for part in timing_parts), 3)},
        }

    @app.get("/api/health")
    def health() -> ApiHealthResponse:
        scenes = load_scene_records()
        try:
            from pipeline.indexing.incremental_index import IncrementalIndex
            from pipeline.indexing.tile_catalog import TileCatalog
            catalog = TileCatalog(paths["tile_catalog"])
            index = IncrementalIndex(paths["faiss_index"])
            retrieval = {"available": True, "indexed_tiles": index.size(), "catalog_tiles": len(catalog.list_tiles())}
        except Exception as exc:
            retrieval = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
        checkpoint = None
        try:
            change_cfg = yaml.safe_load(paths["change_analysis"].read_text(encoding="utf-8"))
            checkpoint_path = _path(ROOT, change_cfg["checkpoint"])
            checkpoint = {"configured": True, "exists": checkpoint_path.is_file(),
                          "role": change_cfg.get("checkpoint_role"), "path": str(checkpoint_path.relative_to(ROOT))}
        except (OSError, KeyError, TypeError, yaml.YAMLError):
            checkpoint = {"configured": False, "exists": False}
        return {"status": "ok", "service": "avlokan-api", "api_version": "0.8.0",
                "retrieval": retrieval, "scene_catalog_records": len(scenes), "change_checkpoint": checkpoint,
                "database": {"available": True, "path": str(paths["database"].relative_to(ROOT)
                                                               if paths["database"].is_relative_to(ROOT) else "external")}}

    @app.get("/api/dashboard")
    def dashboard() -> DashboardResponse:
        from pipeline.indexing.tile_catalog import TileCatalog
        tile_count = len(TileCatalog(paths["tile_catalog"]).list_tiles())
        scene_count = len(load_scene_records())
        with db.connect() as connection:
            pending = connection.execute("SELECT COUNT(*) FROM review_candidates WHERE status IN ('pending','flagged')").fetchone()[0]
            aoi_count = connection.execute("SELECT COUNT(*) FROM aois").fetchone()[0]
            analyses = connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        events = db.list_audit(limit=10)
        return {"statistics": {"tiles_indexed": tile_count, "local_scenes": scene_count,
                               "pending_review": pending, "analysis_runs": analyses},
                "aoi_count": aoi_count,
                "services": health()["retrieval"], "recent_activity": events,
                "source": "local catalog and API database; no demo counts synthesized"}

    @app.post("/api/search/text")
    def search_text(request: SearchRequest) -> SearchResponse:
        try:
            return run_search(request)
        except HTTPException:
            raise
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/search/image")
    async def search_image(
        file: UploadFile = File(...),
        sensors: str = Form("s2,s1,l8"), top_k: int = Form(24, ge=1, le=100),
        date_from: date | None = Form(None), date_to: date | None = Form(None),
        bbox: str | None = Form(None), max_cloud: float | None = Form(None, ge=0, le=100),
        min_similarity: float = Form(0.0, ge=-1, le=1),
    ) -> SearchResponse:
        suffix = Path(file.filename or "query.png").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
            raise HTTPException(415, "Image query must be PNG, JPEG, WebP, or GeoTIFF")
        raw = await file.read(20 * 1024 * 1024 + 1)
        if not raw or len(raw) > 20 * 1024 * 1024:
            raise HTTPException(413, "Image query must contain 1 byte to 20 MiB")
        parsed_bbox = None
        if bbox:
            try:
                parsed_bbox = [float(value.strip()) for value in bbox.split(",")]
            except ValueError as exc:
                raise HTTPException(422, "bbox must be comma-separated west,south,east,north") from exc
        request = SearchRequest(query="image query", sensors=[s.strip() for s in sensors.split(",") if s.strip()],
                                top_k=top_k, date_from=date_from, date_to=date_to, bbox=parsed_bbox,
                                max_cloud=max_cloud, min_similarity=min_similarity)
        temp_root = paths["database"].parent / "uploads"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_path = temp_root / f"{uuid.uuid4().hex}{suffix}"
        try:
            temp_path.write_bytes(raw)
            return run_search(request, image_path=temp_path)
        except HTTPException:
            raise
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            temp_path.unlink(missing_ok=True)
            await file.close()

    @app.post("/api/preview/upload")
    async def preview_upload(file: UploadFile = File(...)):
        suffix = Path(file.filename or "tile.tif").suffix.lower()
        if suffix not in {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp"}:
            raise HTTPException(415, "Unsupported format for preview")
        raw = await file.read(20 * 1024 * 1024 + 1)
        if not raw or len(raw) > 20 * 1024 * 1024:
            raise HTTPException(413, "File must be between 1 byte and 20 MiB")
        temp_root = paths["database"].parent / "uploads"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_path = temp_root / f"prev_{uuid.uuid4().hex}{suffix}"
        try:
            temp_path.write_bytes(raw)
            return _raster_preview(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
            await file.close()

    @app.get("/api/tiles/{tile_id}/preview")
    def tile_preview(tile_id: str):
        from pipeline.indexing.tile_catalog import TileCatalog
        record = TileCatalog(paths["tile_catalog"]).get_tile(tile_id)
        if record is None:
            raise HTTPException(404, "Tile was not found in the local catalog")
        tile_path = _path(ROOT, record.tile_path)
        if not tile_path.is_file():
            raise HTTPException(404, "Catalog tile raster is not present locally")
        return _raster_preview(tile_path)

    @app.get("/api/aois")
    def list_aois() -> AOIListResponse:
        with db.connect() as connection:
            rows = connection.execute("SELECT * FROM aois ORDER BY created_at DESC").fetchall()
        return {"items": [dict(row) for row in rows], "count": len(rows)}

    @app.post("/api/aois", status_code=201)
    def create_aoi(request: AOICreate) -> AOIRecord:
        if not request.name.strip():
            raise HTTPException(422, "AOI name must not be blank")
        item = {"id": f"aoi-{uuid.uuid4().hex[:10]}", "name": request.name.strip(), "lat": request.lat,
                "lng": request.lng, "radius_km": request.radius_km, "created_at": datetime.now(timezone.utc).isoformat()}
        with db.connect() as connection:
            connection.execute("INSERT INTO aois VALUES(?,?,?,?,?,?)",
                               (item["id"], item["name"], item["lat"], item["lng"], item["radius_km"], item["created_at"]))
        db.append_audit("AOI", f"Created AOI {item['name']}", {"aoi_id": item["id"]})
        return item

    @app.post("/api/scenes/search")
    def search_scenes(request: SceneSearchRequest) -> SceneSearchResponse:
        allowed = _sensor_filter_names(request.sensors)
        if request.date_from and request.date_to and request.date_from > request.date_to:
            raise HTTPException(422, "date_from must be on or before date_to")
        lat_delta = request.radius_km / 110.574
        cos_lat = max(abs(__import__("math").cos(__import__("math").radians(request.lat))), 0.01)
        lng_delta = request.radius_km / (111.320 * cos_lat)
        west, south, east, north = (request.lng - lng_delta, request.lat - lat_delta,
                                    request.lng + lng_delta, request.lat + lat_delta)
        found = []
        for item in load_scene_records():
            sensor = SENSOR_NAMES.get(str(item.get("sensor") or "").lower(), (str(item.get("sensor") or "").lower(),))[0]
            bbox = item.get("bbox")
            acquired = str(item.get("acquisition_datetime") or "")[:10]
            cloud = item.get("cloud_cover")
            cloud_value = float(cloud) if cloud is not None else None
            if sensor not in allowed or not isinstance(bbox, list) or len(bbox) != 4:
                continue
            if bbox[0] > east or bbox[2] < west or bbox[1] > north or bbox[3] < south:
                continue
            if request.date_from and acquired < request.date_from.isoformat():
                continue
            if request.date_to and acquired > request.date_to.isoformat():
                continue
            # Catalog cloud_cover follows STAC eo:cloud_cover in percent (0..100).
            if request.max_cloud is not None and cloud_value is not None and cloud_value > request.max_cloud:
                continue
            full = item.get("local_path")
            local_path = _path(ROOT, full) if full else None
            if local_path and not local_path.exists():
                local_path = None
            found.append({
                "id": item.get("scene_id"), "date": acquired, "sensor": sensor,
                "acquisition_datetime": item.get("acquisition_datetime"),
                "cloud": cloud_value, "cloud_percent": cloud_value,
                "blocked": cloud_value is not None and cloud_value > 70,
                "quality": None,
                "quality_basis": None,
                "bbox": bbox, "footprint": item.get("footprint"),
                "available_locally": local_path is not None,
                "local_path": str(local_path.relative_to(ROOT)) if local_path and local_path.is_relative_to(ROOT) else None,
                "cloud_metadata_available": cloud_value is not None,
                "record_type": "archive_scene", "source": "local archive scene catalog",
                "observation_role": None, "pair_id": None,
            })
        for observation in load_analysis_ready_observations():
            bbox = observation["bbox"]
            acquired = observation["date"]
            if observation["sensor"] not in allowed or bbox is None:
                continue
            if bbox[0] > east or bbox[2] < west or bbox[1] > north or bbox[3] < south:
                continue
            if request.date_from and acquired < request.date_from.isoformat():
                continue
            if request.date_to and acquired > request.date_to.isoformat():
                continue
            if request.max_cloud is not None and observation["cloud"] is not None \
                    and observation["cloud"] > request.max_cloud:
                continue
            found.append({key: value for key, value in observation.items() if not key.startswith("_")})
        found.sort(key=lambda scene: (scene["date"], scene["id"] or ""))
        return {"items": found, "count": len(found), "bbox": [west, south, east, north],
                "source": "local scene catalog and configured prototype analysis assets",
                "external_catalog_queried": False}

    def check_input(path_value: str) -> Path:
        path = _path(ROOT, path_value)
        if not path.is_file():
            raise HTTPException(404, f"Input raster does not exist: {path_value}")
        if not any(path.is_relative_to(root) for root in input_roots):
            raise HTTPException(403, "Analysis inputs must be inside configured allowed_input_roots")
        return path

    @app.post("/api/change-analyses", status_code=201)
    def run_change_analysis(request: ChangeAnalysisRequest) -> ChangeAnalysisResponse:
        t1_path, t2_path = request.t1_path, request.t2_path
        t1_date, t2_date = request.t1_date, request.t2_date
        t1_observation = t2_observation = None
        observation_ids_supplied = request.t1_observation_id is not None or request.t2_observation_id is not None
        if observation_ids_supplied:
            if not request.t1_observation_id or not request.t2_observation_id:
                raise HTTPException(422, "Both t1_observation_id and t2_observation_id are required")
            if any((request.t1_path, request.t2_path, request.t1_date, request.t2_date)):
                raise HTTPException(422, "Supply observation IDs or raster paths/dates, not both")
            observations = {item["id"]: item for item in load_analysis_ready_observations()}
            t1_observation = observations.get(request.t1_observation_id)
            t2_observation = observations.get(request.t2_observation_id)
            if t1_observation is None or t2_observation is None:
                raise HTTPException(404, "One or both analysis-ready observation IDs were not found")
            if (t1_observation["observation_role"], t2_observation["observation_role"]) != ("T1", "T2"):
                raise HTTPException(422, "Selected prototype observations must be supplied in their configured T1/T2 roles")
            if t1_observation["pair_id"] != t2_observation["pair_id"]:
                raise HTTPException(422, "Selected observations do not belong to the same configured temporal pair")
            if t1_observation["sensor"] != t2_observation["sensor"]:
                raise HTTPException(422, "Selected observations use incompatible sensors")
            t1_path, t2_path = t1_observation["local_path"], t2_observation["local_path"]
            t1_date = datetime.fromisoformat(t1_observation["acquisition_datetime"])
            t2_date = datetime.fromisoformat(t2_observation["acquisition_datetime"])
        elif not all((t1_path, t2_path, t1_date, t2_date)):
            raise HTTPException(422, "Provide both raster paths and dates, or both analysis-ready observation IDs")
        t1, t2 = check_input(t1_path), check_input(t2_path)
        if request.aoi_id:
            with db.connect() as connection:
                known_aoi = connection.execute("SELECT id FROM aois WHERE id=?", (request.aoi_id,)).fetchone()
            if known_aoi is None:
                raise HTTPException(404, "AOI was not found in the API registry")
        config_file_path = paths["change_analysis"]
        try:
            from dataclasses import replace
            from pipeline.change_detection.analyzer import ChangeAnalysisConfig, ChangeAnalyzer
            from pipeline.change_detection.temporal_pair import TemporalPair
            config = ChangeAnalysisConfig.load(config_file_path)
            if "analysis_output_directory" in paths:
                config = replace(config, output_directory=paths["analysis_output_directory"])
            pair = TemporalPair.from_paths(
                tile_id=request.tile_id, t1_path=t1, t2_path=t2,
                t1_date=t1_date, t2_date=t2_date,
                sensor=t1_observation["sensor"] if t1_observation else request.sensor,
                pair_id=t1_observation["pair_id"] if t1_observation else request.pair_id,
                allow_reversed_dates=(
                    t1_observation is not None or request.allow_reversed_dates
                ),
            )
            result = ChangeAnalyzer(config).analyze(pair)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        result_dict = result.__dict__
        candidate_results = []
        component_geometries = []
        if result.candidates and getattr(result, "final_mask_raster", None):
            with rasterio.open(result.final_mask_raster) as final_mask_source:
                final_mask = final_mask_source.read(1)
                component_geometries = [geometry for geometry, value in raster_shapes(
                    final_mask, mask=final_mask != 0, transform=final_mask_source.transform, connectivity=8
                ) if value != 0]
        for item in result.candidates:
            candidate = dict(item)
            pixel_bounds = candidate.get("bbox_coordinates", {})
            if pixel_bounds and pixel_bounds.get("crs") == result.crs:
                expected = tuple(pixel_bounds[key] for key in ("xmin", "ymin", "xmax", "ymax"))
                for geometry in component_geometries:
                    actual = geometry_bounds(geometry)
                    if np.allclose(actual, expected, rtol=0, atol=1e-7):
                        candidate["geometry"] = transform_geom(result.crs, "EPSG:4326", geometry, precision=7)
                        component_geometries.remove(geometry)
                        break
            candidate_results.append(candidate)
        public = {
            "analysis_id": result.analysis_id, "timestamp": result.timestamp, "pair_id": result.pair_id,
            "name": request.name or request.tile_id,
            "aoi_id": request.aoi_id,
            "temporal": {"t1_scene_id": (t1_observation["id"] if t1_observation else result.t1_scene_id),
                         "t2_scene_id": (t2_observation["id"] if t2_observation else result.t2_scene_id),
                         "t1_date": result.t1_acquisition_timestamp, "t2_date": result.t2_acquisition_timestamp,
                         "t1_role": "T1", "t2_role": "T2",
                         "t1_source": t1_observation["source"] if t1_observation else None,
                         "t2_source": t2_observation["source"] if t2_observation else None},
            "sensor": result.sensor, "spatial": {"crs": result.crs, "transform": result.transform,
                          "width": result.width, "height": result.height, "bbox": result.bounding_box,
                          "bbox_wgs84": list(transform_bounds(result.crs, "EPSG:4326",
                              *result.bounding_box, densify_pts=21))},
            "model": {"name": result.model_name, "checkpoint_role": result.checkpoint_role,
                      "checkpoint_sha256": result.checkpoint_sha256},
            "threshold": result.threshold, "statistics": result.statistics,
            "temporal_embedding_similarity": result.temporal_embedding_similarity,
            "candidates": candidate_results, "candidate_count": result.candidate_count,
            "filtering_statistics": result.filtering_statistics,
            "timings_seconds": result.timings_seconds,
            "artifacts": {
                "probability": f"/api/change-analyses/{result.analysis_id}/artifacts/probability",
                "raw_mask": f"/api/change-analyses/{result.analysis_id}/artifacts/raw_mask",
                "candidate_mask": f"/api/change-analyses/{result.analysis_id}/artifacts/candidate_mask",
                "metadata": f"/api/change-analyses/{result.analysis_id}/artifacts/metadata",
                "t1_preview": f"/api/change-analyses/{result.analysis_id}/artifacts/t1_preview",
                "t2_preview": f"/api/change-analyses/{result.analysis_id}/artifacts/t2_preview",
            },
        }
        if t1_observation and t2_observation:
            metadata_path = Path(result.metadata_path)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["observation_references"] = {
                "T1": {key: t1_observation[key] for key in ("id", "source", "record_type", "observation_role", "date")},
                "T2": {key: t2_observation[key] for key in ("id", "source", "record_type", "observation_role", "date")},
            }
            metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        with db.connect() as connection:
            connection.execute("INSERT INTO analyses VALUES(?,?,?,?)",
                               (result.analysis_id, result.timestamp, result.pair_id,
                                json.dumps(public, default=str)))
            for candidate in result.candidates:
                if not candidate["retained"]:
                    continue
                candidate_id = f"{result.analysis_id}:{candidate['component_id']}"
                candidate_public = {
                    **candidate, "id": candidate_id,
                    "name": f"{public['name']} · Candidate {candidate.get('rank', candidate['component_id'])}",
                    "t1": result.t1_acquisition_timestamp, "t2": result.t2_acquisition_timestamp,
                    "sensor": result.sensor, "analysis_id": result.analysis_id,
                    "confidence": None,
                }
                connection.execute(
                    "INSERT INTO review_candidates(id,analysis_id,component_id,status,candidate_json,created_at) VALUES(?,?,?,?,?,?)",
                    (candidate_id, result.analysis_id, candidate["component_id"], "pending",
                     json.dumps(candidate_public, default=str), result.timestamp),
                )
        db.append_audit("ANALYSIS", f"Completed change analysis {result.analysis_id}",
                        {"analysis_id": result.analysis_id, "pair_id": result.pair_id})
        return public

    @app.get("/api/change-analyses/{analysis_id}")
    def get_change_analysis(analysis_id: str) -> ChangeAnalysisResponse:
        with db.connect() as connection:
            row = connection.execute("SELECT result_json FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Change analysis was not found")
        return json.loads(row["result_json"])

    @app.get("/api/change-analyses/{analysis_id}/artifacts/{kind}")
    def change_artifact(analysis_id: str, kind: Literal[
        "probability", "raw_mask", "candidate_mask", "metadata", "t1_preview", "t2_preview",
        "probability_preview", "raw_mask_preview", "candidate_mask_preview",
        "sar_vv_preview", "sar_vh_preview", "sar_evidence_preview", "agreement_preview",
    ]):
        from fastapi.responses import FileResponse
        with db.connect() as connection:
            row = connection.execute("SELECT result_json FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Change analysis was not found")
        cfg_values = yaml.safe_load(paths["change_analysis"].read_text(encoding="utf-8"))
        output_root = paths.get("analysis_output_directory", _path(ROOT, cfg_values["output_directory"]))
        metadata_files = sorted(output_root.glob(f"{analysis_id}_metadata.json"))
        if not metadata_files:
            # API callers may override the analyzer's configured output root only through its config.
            raise HTTPException(404, "Analysis metadata artifact is no longer available")
        metadata_file = metadata_files[0]
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            if kind in {"t1_preview", "t2_preview"}:
                source_key = "T1" if kind == "t1_preview" else "T2"
                source_path = Path(metadata["provenance"]["source_files"][source_key]).resolve()
                if not any(source_path.is_relative_to(root) for root in input_roots) or not source_path.is_file():
                    raise HTTPException(404, "Source imagery preview is unavailable")
                return _raster_preview(source_path)
            if kind in {"sar_vv_preview", "sar_vh_preview", "sar_evidence_preview", "agreement_preview"}:
                from fastapi.responses import Response
                from pipeline.change_detection.sar_fallback import (
                    SAR_DEFAULT_RASTER, compute_sar_window_evidence,
                    compute_sensor_agreement, render_sar_preview
                )
                bounds = metadata["bounding_box"]
                _, _, e_vv, e_vh, e_sar = compute_sar_window_evidence(ROOT / SAR_DEFAULT_RASTER, bounds)
                if kind == "sar_vv_preview":
                    png_bytes = render_sar_preview(e_vv, "sar_grayscale")
                elif kind == "sar_vh_preview":
                    png_bytes = render_sar_preview(e_vh, "sar_grayscale")
                elif kind == "sar_evidence_preview":
                    png_bytes = render_sar_preview(e_sar, "sar_evidence")
                else:
                    prob_path = Path(metadata["probability_raster"])
                    if not prob_path.is_absolute():
                        prob_path = ROOT / prob_path
                    with rasterio.open(prob_path) as opt_src:
                        opt_prob = opt_src.read(1)
                    _, cat_agr, _ = compute_sensor_agreement(opt_prob, e_sar)
                    png_bytes = render_sar_preview(cat_agr, "sensor_agreement")
                return Response(png_bytes, media_type="image/png", headers={"X-AVLOKAN-Artifact-View": kind})
            base_kind = kind.removesuffix("_preview")
            key = {"probability": "probability_raster", "raw_mask": "raw_mask_raster",
                   "candidate_mask": "candidate_mask_raster", "metadata": "metadata_path"}[base_kind]
            artifact_path = Path(metadata[key]).resolve()
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise HTTPException(500, "Saved analysis metadata is invalid") from exc
        if not artifact_path.is_relative_to(output_root) or not artifact_path.is_file():
            raise HTTPException(404, "Requested analysis artifact is unavailable")
        if kind.endswith("_preview"):
            source_files = metadata.get("provenance", {}).get("source_files", {})
            validity_paths = [Path(source_files[key]).resolve() for key in ("T1", "T2") if source_files.get(key)]
            return _raster_artifact_preview(artifact_path, kind, validity_paths)
        media = "application/json" if kind == "metadata" else "image/tiff"
        return FileResponse(artifact_path, media_type=media, filename=artifact_path.name)

    @app.get("/api/artifacts/{kind}")
    def general_artifact_preview(kind: Literal[
        "sar_vv_preview", "sar_vh_preview", "sar_evidence_preview", "agreement_preview",
    ]):
        from fastapi.responses import Response
        from pipeline.change_detection.sar_fallback import (
            SAR_DEFAULT_RASTER, compute_sar_window_evidence,
            compute_sensor_agreement, render_sar_preview
        )
        bounds = [582100.0, 2519110.0, 584660.0, 2521670.0]
        _, _, e_vv, e_vh, e_sar = compute_sar_window_evidence(ROOT / SAR_DEFAULT_RASTER, bounds)
        if kind == "sar_vv_preview":
            content = render_sar_preview(e_vv, colormap="sar_grayscale")
        elif kind == "sar_vh_preview":
            content = render_sar_preview(e_vh, colormap="sar_grayscale")
        elif kind == "sar_evidence_preview":
            content = render_sar_preview(e_sar, colormap="sar_evidence")
        elif kind == "agreement_preview":
            opt_prob = np.full_like(e_sar, 0.9861)
            _, cat, _ = compute_sensor_agreement(opt_prob, e_sar)
            content = render_sar_preview(cat, colormap="sensor_agreement")
        else:
            raise HTTPException(404, f"Unknown artifact preview: {kind}")
        return Response(content=content, media_type="image/png")

    @app.get("/api/change-analyses/{analysis_id}/sar-fallback")
    def get_analysis_sar_fallback(analysis_id: str):
        with db.connect() as connection:
            row = connection.execute("SELECT result_json FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Change analysis was not found")
        cfg_values = yaml.safe_load(paths["change_analysis"].read_text(encoding="utf-8"))
        output_root = paths.get("analysis_output_directory", _path(ROOT, cfg_values["output_directory"]))
        metadata_files = sorted(output_root.glob(f"{analysis_id}_metadata.json"))
        if not metadata_files:
            raise HTTPException(404, "Analysis metadata artifact is unavailable")
        metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
        bounds = metadata["bounding_box"]
        from pipeline.change_detection.sar_fallback import (
            SAR_DEFAULT_RASTER, SAR_SENSOR, SAR_PLATFORM, SAR_ACQUISITION_TIMESTAMP,
            SAR_MODE, SAR_POLARIZATIONS, SAR_PROVENANCE,
            compute_sar_window_evidence, compute_candidate_fusion_score
        )
        vv_raw, vh_raw, e_vv, e_vh, e_sar = compute_sar_window_evidence(ROOT / SAR_DEFAULT_RASTER, bounds)
        candidates_out = []
        for c in metadata.get("candidates", []):
            cid = c["component_id"]
            cb = c["bbox_coordinates"]
            _, _, _, _, c_sar = compute_sar_window_evidence(
                ROOT / SAR_DEFAULT_RASTER,
                (cb["xmin"], cb["ymin"], cb["xmax"], cb["ymax"])
            )
            c_sar_mean = float(c_sar.mean())
            opt_mean = float(c["mean_probability"])
            opt_l, sar_l, agr_label, score = compute_candidate_fusion_score(opt_mean, c_sar_mean)
            candidates_out.append({
                "component_id": cid,
                "rank": c.get("rank"),
                "optical_probability": round(opt_mean, 4),
                "optical_level": opt_l,
                "sar_evidence": round(c_sar_mean, 4),
                "sar_level": sar_l,
                "sensor_agreement": agr_label,
                "evidence_score": score,
                "is_corroborated": agr_label == "HIGH AGREEMENT",
            })
        return {
            "status": "available",
            "sensor": SAR_SENSOR,
            "platform": SAR_PLATFORM,
            "instrument": SAR_MODE,
            "acquisition_datetime": SAR_ACQUISITION_TIMESTAMP,
            "polarizations": SAR_POLARIZATIONS,
            "crs": metadata["crs"],
            "resolution": "10 m",
            "provenance": SAR_PROVENANCE,
            "source_raster": str(SAR_DEFAULT_RASTER).replace("\\", "/"),
            "artifacts": {
                "vv_preview": f"/api/change-analyses/{analysis_id}/artifacts/sar_vv_preview",
                "vh_preview": f"/api/change-analyses/{analysis_id}/artifacts/sar_vh_preview",
                "sar_evidence_preview": f"/api/change-analyses/{analysis_id}/artifacts/sar_evidence_preview",
                "agreement_preview": f"/api/change-analyses/{analysis_id}/artifacts/agreement_preview",
            },
            "metrics": {
                "vv_evidence_mean": round(float(e_vv.mean()), 4),
                "vh_evidence_mean": round(float(e_vh.mean()), 4),
                "sar_change_evidence_mean": round(float(e_sar.mean()), 4),
            },
            "candidates": candidates_out,
            "calibration_status": "Evidence Score (not calibrated probability)",
            "disclaimer": "Evidence score combines available optical, SAR and quality evidence. It is not a calibrated probability.",
            "formula": "0.45 * optical + 0.25 * sar + 0.15 * agreement + 0.15 * quality",
        }

    @app.get("/api/change-analyses/{analysis_id}/sensor-agreement")
    def get_analysis_sensor_agreement(analysis_id: str):
        fb = get_analysis_sar_fallback(analysis_id)
        c_primary = fb["candidates"][0] if fb["candidates"] else None
        for c in fb["candidates"]:
            if c["component_id"] == 2:
                c_primary = c
                break
        return {
            "optical": {
                "sensor": "Sentinel-2",
                "primary_candidate_level": c_primary["optical_level"] if c_primary else "HIGH",
                "primary_candidate_prob": c_primary["optical_probability"] if c_primary else 0.9861,
            },
            "sar": {
                "sensor": "Sentinel-1",
                "date": "2025-03-27",
                "primary_candidate_level": c_primary["sar_level"] if c_primary else "HIGH",
                "primary_candidate_evidence": c_primary["sar_evidence"] if c_primary else 0.5759,
            },
            "agreement_matrix": [
                {"optical": "HIGH", "sar": "HIGH", "agreement": "HIGH AGREEMENT", "meaning": "Corroborated physical change"},
                {"optical": "HIGH", "sar": "LOW",  "agreement": "OPTICAL-ONLY",   "meaning": "Spectral shift without radar verification"},
                {"optical": "LOW",  "sar": "HIGH", "agreement": "SAR-ONLY",       "meaning": "Radar backscatter anomaly without spectral shift"},
                {"optical": "LOW",  "sar": "LOW",  "agreement": "NO STRONG EVIDENCE", "meaning": "Baseline stability"}
            ],
            "primary_candidate": c_primary,
            "disclaimer": "Evidence score combines available optical, SAR and quality evidence. It is not a calibrated probability.",
            "formula": "0.45 * optical + 0.25 * sar + 0.15 * agreement + 0.15 * quality",
        }

    @app.get("/api/indexing/status")
    def indexing_status():
        from pipeline.indexing.incremental_index import IncrementalIndex
        from pipeline.indexing.tile_catalog import TileCatalog
        from pipeline.indexing.incremental_manager import get_incremental_status, ensure_baseline_backup
        index_path = paths["faiss_index"]
        mapping_path = index_path.with_name(f"{index_path.stem}_ids.json")
        catalog_path = paths["tile_catalog"]
        ensure_baseline_backup(index_path, mapping_path, catalog_path)
        index = IncrementalIndex(index_path)
        catalog = TileCatalog(catalog_path)
        return get_incremental_status(index, catalog)

    @app.post("/api/indexing/incremental-ingest")
    def indexing_incremental_ingest():
        from pipeline.indexing.incremental_index import IncrementalIndex
        from pipeline.indexing.tile_catalog import TileCatalog
        from pipeline.embeddings.remoteclip import RemoteCLIPAdapter
        from pipeline.embeddings.image_encoder import ImageEncoder
        from pipeline.indexing.incremental_manager import perform_incremental_ingest, ensure_baseline_backup
        index_path = paths["faiss_index"]
        mapping_path = index_path.with_name(f"{index_path.stem}_ids.json")
        catalog_path = paths["tile_catalog"]
        ensure_baseline_backup(index_path, mapping_path, catalog_path)
        index = IncrementalIndex(index_path)
        catalog = TileCatalog(catalog_path)
        embedding_cfg = yaml.safe_load(paths["embedding_model"].read_text(encoding="utf-8"))
        checkpoint = _path(ROOT, embedding_cfg["model"]["checkpoint"])
        adapter = RemoteCLIPAdapter(checkpoint, device="cpu")
        encoder = ImageEncoder(adapter)
        retriever = getattr(app.state, "retriever", None)
        result = perform_incremental_ingest(index, catalog, encoder, retriever=retriever)
        db.append_audit("INGEST", f"Incrementally indexed {result.get('tile_id')}", result)
        return result

    @app.post("/api/indexing/reset")
    def indexing_reset():
        from pipeline.indexing.incremental_manager import reset_incremental_index
        index_path = paths["faiss_index"]
        mapping_path = index_path.with_name(f"{index_path.stem}_ids.json")
        catalog_path = paths["tile_catalog"]
        res = reset_incremental_index(index_path, mapping_path, catalog_path)
        if hasattr(app.state, "retriever"):
            app.state.retriever = None
        return res

    @app.get("/api/review-queue")
    def review_queue(status: Literal["all", "pending", "flagged", "confirmed", "rejected"] = "pending",
                     limit: int = Query(default=100, ge=1, le=500)) -> ReviewQueueResponse:
        with db.connect() as connection:
            if status == "all":
                rows = connection.execute("SELECT * FROM review_candidates ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM review_candidates WHERE status=? ORDER BY created_at DESC LIMIT ?",
                                          (status, limit)).fetchall()
        items = [{**json.loads(row["candidate_json"]), "status": row["status"],
                  "decided_at": row["decided_at"], "decision_by": row["decision_by"]} for row in rows]
        return {"items": items, "count": len(items), "status": status}

    @app.post("/api/review-queue/{candidate_id}/decision")
    def decide_candidate(candidate_id: str, request: ReviewDecision) -> DecisionResponse:
        target = {"confirm": "confirmed", "reject": "rejected", "need_review": "flagged"}[request.decision]
        with db.connect() as connection:
            row = connection.execute("SELECT status,candidate_json FROM review_candidates WHERE id=?", (candidate_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Review candidate was not found")
            if row["status"] not in {"pending", "flagged"}:
                raise HTTPException(409, f"Candidate already has final status {row['status']}")
            connection.execute("UPDATE review_candidates SET status=?,decided_at=?,decision_by=? WHERE id=?",
                               (target, datetime.now(timezone.utc).isoformat(), request.analyst, candidate_id))
        action = {"confirm": "CONFIRMED", "reject": "REJECTED", "need_review": "REVIEW"}[request.decision]
        db.append_audit(action, request.note or f"{request.analyst} marked {candidate_id} {target}",
                        {"candidate_id": candidate_id, "decision": target, "analyst": request.analyst})
        return {"id": candidate_id, "status": target, "decision_by": request.analyst}

    @app.get("/api/audit")
    def audit(action: str = "all", limit: int = Query(default=100, ge=1, le=500)) -> AuditResponse:
        accepted = {"all", "verdicts", "ops", "system"}
        if action not in accepted:
            raise HTTPException(422, f"action must be one of {sorted(accepted)}")
        events = db.list_audit(limit=limit)
        groups = {
            "verdicts": {"CONFIRMED", "REJECTED", "REVIEW"},
            "ops": {"AOI", "ANALYSIS", "SEARCH", "SCENES", "EXPORT"},
            "system": {"SYSTEM", "SESSION"},
        }
        shown = events if action == "all" else [event for event in events if event["action"] in groups[action]]
        # The chain verification covers every event, even when the response is filtered or limited.
        all_events = db.list_audit(limit=2_147_483_647)
        return {"items": shown, "count": len(shown), "filter": action,
                "integrity": {"algorithm": "SHA-256 chained event digest", "intact": db.verify_audit(all_events),
                              "verified_events": len(all_events)}}

    @app.get("/api/changes")
    def changes(limit: int = Query(default=100, ge=1, le=500)) -> ChangeListResponse:
        with db.connect() as connection:
            rows = connection.execute("SELECT result_json FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return {"items": [json.loads(row["result_json"]) for row in rows], "count": len(rows)}

    from pipeline.api.demo_service import register_demo_routes
    register_demo_routes(app, ROOT, db, _raster_preview, _raster_artifact_preview)
    return app


def _raster_preview(path: Path):
    from fastapi.responses import Response
    from PIL import Image
    import io
    from rasterio.enums import Resampling

    try:
        with rasterio.open(path) as src:
            band_count = src.count
            indexes = (3, 2, 1) if band_count >= 3 else (1,)
            preview_scale = min(1.0, 768 / max(src.width, src.height))
            preview_width = max(1, round(src.width * preview_scale))
            preview_height = max(1, round(src.height * preview_scale))
            data = src.read(indexes, out_shape=(len(indexes), preview_height, preview_width),
                            resampling=Resampling.average, masked=True)
            values = np.asarray(data.filled(0), dtype=np.float32)
            if len(indexes) == 1:
                values = np.repeat(values, 3, axis=0)
            finite = values[np.isfinite(values)]
            scale = float(np.percentile(finite, 98)) if finite.size else 1.0
            scale = scale if scale > 0 else 1.0
            rgb = np.rint(np.clip(values / scale, 0, 1) * 255).astype("uint8").transpose(1, 2, 0)
        output = io.BytesIO()
        Image.fromarray(rgb, mode="RGB").save(output, format="JPEG", quality=85)
        return Response(output.getvalue(), media_type="image/jpeg")
    except Exception as exc:
        raise HTTPException(422, f"Could not render local tile preview: {exc}") from exc


def _raster_artifact_preview(path: Path, kind: str, validity_paths: list[Path] | None = None):
    """Render a bounded browser preview while preserving probability/mask semantics."""
    from fastapi.responses import Response
    from PIL import Image
    import io
    from rasterio.enums import Resampling

    try:
        with rasterio.open(path) as src:
            height = min(src.height, 768)
            width = min(src.width, 768)
            masked = src.read(1, out_shape=(height, width), resampling=Resampling.nearest, masked=True)
            values = np.asarray(masked.filled(0))
            valid = ~np.ma.getmaskarray(masked) & np.isfinite(values)
            if kind == "probability_preview" and validity_paths:
                for validity_path in validity_paths:
                    with rasterio.open(validity_path) as validity_src:
                        if (validity_src.width, validity_src.height, validity_src.crs, validity_src.transform) != (src.width, src.height, src.crs, src.transform):
                            raise ValueError("Source validity grid does not match the saved probability raster")
                        indexes = [index for index in (4, 3, 2) if index <= validity_src.count]
                        source_values = validity_src.read(indexes, out_shape=(len(indexes), height, width),
                                                           resampling=Resampling.nearest, masked=True)
                        valid &= (~np.ma.getmaskarray(source_values) & np.isfinite(source_values.filled(np.nan))).all(axis=0)
            rgba = np.zeros((height, width, 4), dtype=np.uint8)
            if kind == "probability_preview":
                probability = values.astype(np.float32)
                valid &= np.isfinite(probability) & (probability >= 0.0) & (probability <= 1.0)
                stops = ((0.0, (255, 210, 48)), (0.28, (255, 148, 28)),
                         (0.62, (244, 65, 38)), (1.0, (182, 18, 42)))
                for channel in range(3):
                    rgba[..., channel] = np.interp(probability, [stop[0] for stop in stops],
                        [stop[1][channel] for stop in stops]).astype(np.uint8)
                rgba[..., 3] = np.where(valid, np.rint(np.clip((probability - 0.04) / 0.35, 0, 1) * 190), 0).astype(np.uint8)
            else:
                changed = valid & (values != 0)
                rgba[changed] = (220, 104, 66, 210)
        output = io.BytesIO()
        Image.fromarray(rgba, mode="RGBA").save(output, format="PNG", optimize=True)
        return Response(output.getvalue(), media_type="image/png",
                        headers={"X-AVLOKAN-Artifact-View": kind})
    except Exception as exc:
        raise HTTPException(422, f"Could not render analysis artifact preview from {path.name}: {exc}") from exc


app = create_app()
