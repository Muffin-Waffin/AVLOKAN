"""Explicit response contracts aligned with the existing AVLOKAN screen data."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class SensorSummary(BaseModel):
    id: str
    name: str
    tag: str


class SearchTileResult(BaseModel):
    id: str
    tile_id: str
    lat: float | None = None
    lng: float | None = None
    region: str
    date: str | None = None
    sensor: SensorSummary
    sim: float
    cloud: float | None = None
    cloud_percent: float | None = None
    thumbnail_url: str
    seed: int | None = None
    feature: str | None = None
    resolution: list[float] | None = None
    crs: str | None = None
    bounds: list[float] | None = None
    rank: int | None = None
    tile_path: str | None = None


class SearchResponse(BaseModel):
    query: str
    query_type: Literal["text", "image"]
    results: list[SearchTileResult]
    filters: dict[str, Any]
    warnings: list[str]
    diagnostics: dict[str, Any]
    timings: dict[str, Any]


class ServiceHealth(BaseModel):
    available: bool
    indexed_tiles: int | None = None
    catalog_tiles: int | None = None
    reason: str | None = None


class ApiHealthResponse(BaseModel):
    status: str
    service: str
    api_version: str
    retrieval: ServiceHealth
    scene_catalog_records: int
    change_checkpoint: dict[str, Any]
    database: dict[str, Any]


class DashboardStatistics(BaseModel):
    tiles_indexed: int
    local_scenes: int
    pending_review: int
    analysis_runs: int


class DashboardResponse(BaseModel):
    statistics: DashboardStatistics
    aoi_count: int
    services: ServiceHealth
    recent_activity: list[dict[str, Any]]
    source: str


class AOIRecord(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    radius_km: float
    created_at: str


class AOIListResponse(BaseModel):
    items: list[AOIRecord]
    count: int


class SceneRecord(BaseModel):
    id: str | None
    date: str
    acquisition_datetime: str | None = None
    sensor: str
    cloud: float | None = None
    cloud_percent: float | None = None
    blocked: bool
    quality: float | None = None
    quality_basis: str | None = None
    bbox: list[float]
    footprint: dict[str, Any] | None = None
    available_locally: bool
    local_path: str | None = None
    cloud_metadata_available: bool
    record_type: str = "archive_scene"
    source: str | None = None
    observation_role: str | None = None
    pair_id: str | None = None


class SceneSearchResponse(BaseModel):
    items: list[SceneRecord]
    count: int
    bbox: list[float]
    source: str
    external_catalog_queried: bool


class CandidateRecord(BaseModel):
    """Candidate score and geometry, with unused display/demo fields nullable."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    analysis_id: str | None = None
    component_id: int
    rank: int | None = None
    area_pixels: int
    bbox_pixels: dict[str, int]
    centroid_pixels: dict[str, float]
    bbox_coordinates: dict[str, Any] | None = None
    centroid_coordinates: dict[str, Any] | None = None
    mean_probability: float
    maximum_probability: float
    median_probability: float
    candidate_score: float | None = None
    confidence: float | None = None
    valid_fraction: float
    retained: bool
    rejection_reasons: list[str]
    status: str | None = None


class ChangeAnalysisResponse(BaseModel):
    analysis_id: str
    timestamp: str
    pair_id: str
    name: str
    aoi_id: str | None = None
    temporal: dict[str, Any]
    sensor: str
    spatial: dict[str, Any]
    model: dict[str, Any]
    threshold: float
    statistics: dict[str, Any]
    temporal_embedding_similarity: float | None = None
    candidates: list[CandidateRecord]
    candidate_count: int
    filtering_statistics: dict[str, int]
    timings_seconds: dict[str, float]
    artifacts: dict[str, str]


class ReviewQueueResponse(BaseModel):
    items: list[CandidateRecord]
    count: int
    status: str


class DecisionResponse(BaseModel):
    id: str
    status: str
    decision_by: str


class AuditResponse(BaseModel):
    items: list[dict[str, Any]]
    count: int
    filter: str
    integrity: dict[str, Any]


class ChangeListResponse(BaseModel):
    items: list[ChangeAnalysisResponse]
    count: int
