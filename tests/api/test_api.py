from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import yaml

from pipeline.api.app import ROOT, create_app


@pytest.fixture
def api_client(tmp_path):
    settings = yaml.safe_load((ROOT / "configs/api.yaml").read_text(encoding="utf-8"))
    settings["database"] = str(tmp_path / "api.sqlite")
    settings["analysis_output_directory"] = str(tmp_path / "change-output")
    change_settings = yaml.safe_load((ROOT / "configs/change_detection.yaml").read_text(encoding="utf-8"))
    change_settings["checkpoint"] = str((ROOT / change_settings["checkpoint"]).resolve())
    change_settings["remoteclip_checkpoint"] = str((ROOT / change_settings["remoteclip_checkpoint"]).resolve())
    change_settings["output_directory"] = str(tmp_path / "change-output")
    change_config = tmp_path / "change_detection.yaml"
    change_config.write_text(yaml.safe_dump(change_settings), encoding="utf-8")
    settings["change_analysis"] = str(change_config)
    config_file = tmp_path / "api.yaml"
    config_file.write_text(yaml.safe_dump(settings), encoding="utf-8")
    app = create_app(config_file)
    with TestClient(app) as client:
        yield client


def test_openapi_and_health_report_actual_local_artifact_counts(api_client):
    response = api_client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["retrieval"]["available"] is True
    assert payload["retrieval"]["indexed_tiles"] == 4
    assert payload["retrieval"]["catalog_tiles"] == 4
    assert payload["scene_catalog_records"] == 10
    assert payload["change_checkpoint"]["exists"] is True
    schema = api_client.get("/openapi.json").json()
    assert "/api/search/text" in schema["paths"]
    assert "/api/change-analyses" in schema["paths"]
    response_schemas = schema["components"]["schemas"]
    assert "SearchResponse" in response_schemas
    assert "ChangeAnalysisResponse" in response_schemas
    assert {"id", "lat", "lng", "date", "sensor", "sim", "cloud", "thumbnail_url"} <= set(
        response_schemas["SearchTileResult"]["properties"]
    )


def test_dashboard_counts_are_catalog_and_database_backed(api_client):
    response = api_client.get("/api/dashboard")
    assert response.status_code == 200
    result = response.json()
    assert result["statistics"] == {
        "tiles_indexed": 4, "local_scenes": 10, "pending_review": 0, "analysis_runs": 0,
    }
    assert result["source"].startswith("local catalog")


def test_aoi_create_list_and_audit_chain(api_client):
    created = api_client.post("/api/aois", json={
        "name": "Test AOI", "lat": 23.0, "lng": 75.5, "radius_km": 4,
    })
    assert created.status_code == 201
    aoi = created.json()
    assert aoi["name"] == "Test AOI"
    assert aoi["radius_km"] == 4
    assert api_client.get("/api/aois").json()["items"] == [aoi]
    audit = api_client.get("/api/audit").json()
    assert audit["integrity"]["intact"] is True
    assert audit["items"][0]["action"] == "AOI"
    assert len(audit["items"][0]["h"]) == 64


def test_scene_search_uses_local_catalog_and_spatial_temporal_filters(api_client):
    response = api_client.post("/api/scenes/search", json={
        "lat": 23.0, "lng": 75.5, "radius_km": 80,
        "date_from": "2025-03-01", "date_to": "2025-04-01",
        "sensors": ["s2"], "max_cloud": 20,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["external_catalog_queried"] is False
    assert result["count"] >= 1
    assert all(item["sensor"] == "sentinel-2" for item in result["items"])
    assert all(item["date"].startswith("2025-03") for item in result["items"])
    assert all(item["cloud"] is None or item["cloud"] <= 20 for item in result["items"])


def test_scene_search_includes_distinct_analysis_ready_prototype_observations(api_client):
    response = api_client.post("/api/scenes/search", json={
        "lat": 22.78, "lng": 75.82, "radius_km": 8, "sensors": ["sentinel-2"],
        "date_from": "2025-03-24", "date_to": "2025-03-29",
    })
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    prototypes = [item for item in items if item["record_type"] == "prototype_analysis_ready"]
    assert [(item["observation_role"], item["date"]) for item in prototypes] == [
        ("T2", "2025-03-24"), ("T1", "2025-03-29"),
    ]
    assert [item["acquisition_datetime"] for item in prototypes] == [
        "2025-03-24T05:26:49.024000+00:00", "2025-03-29T05:28:41.025000+00:00",
    ]
    assert all(item["available_locally"] for item in prototypes)
    assert all(item["source"] == "existing local prototype analysis asset" for item in prototypes)
    assert all(Path(item["local_path"]).as_posix().startswith("data/processed/") for item in prototypes)
    assert all(item["cloud"] is None and item["cloud_metadata_available"] is False for item in prototypes)
    assert all(item["bbox"] == pytest.approx([75.799662, 22.754107, 75.849814, 22.800612], abs=1e-5)
               for item in prototypes)
    archives = [item for item in items if item["record_type"] == "archive_scene"]
    assert archives and all(item["source"] == "local archive scene catalog" for item in archives)


def test_analysis_ready_observation_ids_validate_as_a_supplied_temporal_pair(api_client, monkeypatch):
    from types import SimpleNamespace
    from pipeline.change_detection.analyzer import ChangeAnalyzer

    captured = {}

    def fake_analyze(analyzer, pair):
        captured["pair"] = pair
        output = analyzer.config.output_directory
        output.mkdir(parents=True, exist_ok=True)
        metadata_path = output / "analysis-observation-id-test_metadata.json"
        raster_a = ROOT / "data/processed/phase2_validation/s2_reflectance_512.tif"
        raster_b = ROOT / "data/processed/phase6_validation/s2_20250324_512.tif"
        metadata_path.write_text(json.dumps({
            "probability_raster": str(output / "prob.tif"),
            "raw_mask_raster": str(output / "raw.tif"),
            "candidate_mask_raster": str(output / "mask.tif"),
            "metadata_path": str(metadata_path),
            "provenance": {"source_files": {"T1": str(raster_a), "T2": str(raster_b)}},
        }), encoding="utf-8")
        return SimpleNamespace(
            analysis_id="analysis-observation-id-test", timestamp="2026-09-27T00:00:00+00:00",
            pair_id=pair.pair_id, t1_scene_id=None, t2_scene_id=None,
            t1_acquisition_timestamp=pair.t1_date.isoformat(), t2_acquisition_timestamp=pair.t2_date.isoformat(),
            sensor=pair.sensor, crs=pair.crs, transform=(10, 0, 582100, 0, -10, 2521670, 0, 0, 1),
            width=512, height=512, bounding_box=(582100.0, 2516550.0, 587220.0, 2521670.0),
            model_name="BIT", checkpoint_role="prototype_demo_checkpoint",
            checkpoint_sha256="a" * 64, threshold=0.96, statistics={}, temporal_embedding_similarity=None,
            candidates=[], candidate_count=0, filtering_statistics={"raw_component_count": 0,
            "components_removed": 0, "components_retained": 0, "pixels_removed": 0, "pixels_retained": 0},
            timings_seconds={}, metadata_path=str(metadata_path),
        )

    monkeypatch.setattr(ChangeAnalyzer, "analyze", fake_analyze)
    t1_id, t2_id = "avlokan-prototype-s2-t1-20250329", "avlokan-prototype-s2-t2-20250324"
    invalid = api_client.post("/api/change-analyses", json={
        "t1_observation_id": "missing", "t2_observation_id": t2_id,
    })
    assert invalid.status_code == 404
    swapped = api_client.post("/api/change-analyses", json={
        "t1_observation_id": t2_id, "t2_observation_id": t1_id,
    })
    assert swapped.status_code == 422
    result = api_client.post("/api/change-analyses", json={
        "t1_observation_id": t1_id, "t2_observation_id": t2_id,
    })
    assert result.status_code == 201, result.text
    data = result.json()
    pair = captured["pair"]
    assert pair.t1_path == ROOT / "data/processed/phase2_validation/s2_reflectance_512.tif"
    assert pair.t2_path == ROOT / "data/processed/phase6_validation/s2_20250324_512.tif"
    assert pair.t1_date.isoformat().startswith("2025-03-29")
    assert pair.t2_date.isoformat().startswith("2025-03-24")
    assert data["temporal"]["t1_scene_id"] == t1_id
    assert data["temporal"]["t2_scene_id"] == t2_id
    assert data["temporal"]["t1_role"] == "T1" and data["temporal"]["t2_role"] == "T2"
    fetched = api_client.get(f"/api/change-analyses/{data['analysis_id']}")
    assert fetched.status_code == 200 and fetched.json()["pair_id"] == data["pair_id"]
    metadata = api_client.get(data["artifacts"]["metadata"])
    assert metadata.status_code == 200
    metadata_json = metadata.json()
    assert metadata_json["observation_references"]["T1"]["id"] == t1_id
    assert metadata_json["observation_references"]["T2"]["id"] == t2_id
    assert api_client.get("/api/audit").json()["items"][-1]["action"] == "ANALYSIS"


def test_review_decisions_persist_and_refuse_final_decision_replay(api_client):
    db = api_client.app.state.database
    with db.connect() as connection:
        connection.execute("INSERT INTO analyses VALUES(?,?,?,?)", ("analysis-1", "2026-09-27T00:00:00Z", "pair-1", "{}"))
        connection.execute(
            "INSERT INTO review_candidates(id,analysis_id,component_id,status,candidate_json,created_at) VALUES(?,?,?,?,?,?)",
            ("analysis-1:1", "analysis-1", 1, "pending", json.dumps({
                "id": "analysis-1:1", "analysis_id": "analysis-1", "component_id": 1, "rank": 1,
                "area_pixels": 4, "bbox_pixels": {"xmin": 1, "ymin": 1, "xmax_exclusive": 3, "ymax_exclusive": 3},
                "centroid_pixels": {"x": 1.5, "y": 1.5}, "mean_probability": 0.98,
                "maximum_probability": 0.99, "median_probability": 0.98,
                "candidate_score": 0.98, "confidence": None, "valid_fraction": 1.0,
                "retained": True, "rejection_reasons": [],
            }), "2026-09-27T00:00:00Z"),
        )
    decided = api_client.post("/api/review-queue/analysis-1:1/decision", json={
        "decision": "confirm", "analyst": "Analyst Test", "note": "Reviewed",
    })
    assert decided.status_code == 200
    assert decided.json()["status"] == "confirmed"
    assert api_client.get("/api/review-queue?status=all").json()["items"][0]["status"] == "confirmed"
    replay = api_client.post("/api/review-queue/analysis-1:1/decision", json={"decision": "reject"})
    assert replay.status_code == 409
    audit = api_client.get("/api/audit?action=verdicts").json()
    assert audit["integrity"]["intact"] is True
    assert audit["items"][-1]["action"] == "CONFIRMED"


def test_input_validation_and_analysis_root_guard(api_client, tmp_path):
    bad_aoi = api_client.post("/api/aois", json={"name": "bad", "lat": 92, "lng": 0})
    assert bad_aoi.status_code == 422
    bad_search = api_client.post("/api/search/text", json={"query": "valid", "sensors": ["mars"]})
    # Unsupported values are checked before loading the RemoteCLIP model.
    assert bad_search.status_code == 422
    outside_path = tmp_path / "outside.tif"
    outside_path.write_bytes(b"existing but outside the configured input root")
    outside = api_client.post("/api/change-analyses", json={
        "t1_path": str(outside_path), "t2_path": str(outside_path),
        "t1_date": "2025-01-01T00:00:00Z", "t2_date": "2025-01-02T00:00:00Z",
    })
    assert outside.status_code == 403


@pytest.mark.integration
def test_local_semantic_search_calls_existing_retriever(api_client):
    response = api_client.post("/api/search/text", json={
        "query": "urban development", "sensors": ["s2"], "top_k": 2,
        "min_similarity": -1, "bbox": [74.9, 22.4, 76.2, 23.7],
        "bbox_crs": "EPSG:4326",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["query_type"] == "text"
    assert data["diagnostics"]["indexed_tiles"] == 4
    assert all({"id", "lat", "lng", "date", "sensor", "sim", "cloud"} <= set(row) for row in data["results"])
    catalog = json.loads((ROOT / "data/catalog/tiles.json").read_text(encoding="utf-8"))
    local_tile = next((ROOT / item["tile_path"] for item in catalog if (ROOT / item["tile_path"]).is_file()), None)
    if local_tile is None:
        pytest.skip("no local indexed tile raster is available for image-query integration")
    image_response = api_client.post(
        "/api/search/image",
        files={"file": (local_tile.name, local_tile.read_bytes(), "image/tiff")},
        data={"sensors": "s2", "top_k": "2", "min_similarity": "-1"},
    )
    assert image_response.status_code == 200, image_response.text
    assert image_response.json()["query_type"] == "image"
    assert not list(api_client.app.state.paths["database"].parent.joinpath("uploads").glob("*"))


@pytest.mark.integration
def test_change_analysis_endpoint_runs_existing_analyzer_and_serves_artifacts(api_client):
    t1 = ROOT / "data/processed/phase2_validation/s2_reflectance_512.tif"
    t2 = ROOT / "data/processed/phase6_validation/s2_20250324_512.tif"
    if not t1.is_file() or not t2.is_file():
        pytest.skip("repository-local Phase 6 Sentinel-2 pair is unavailable")
    response = api_client.post("/api/change-analyses", json={
        "t1_path": str(t1), "t2_path": str(t2),
        "t1_date": "2025-03-29T05:28:41.025Z", "t2_date": "2025-03-24T05:26:49.024Z",
        "tile_id": "api-phase6-regression", "allow_reversed_dates": True,
        "name": "API integration regression",
    })
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["sensor"] == "sentinel-2"
    assert result["model"]["checkpoint_sha256"] == "8a75efe679aab0d1624888906cf3c9ed756772b7f3e92d439b7d0fb0fe3cac4b"
    assert result["statistics"]["connected_component_count"] == result["candidate_count"]
    assert result["candidate_count"] == 10
    assert result["candidates"][0]["candidate_score"] == result["candidates"][0]["mean_probability"]
    assert result["candidates"][0]["candidate_score"] is not None
    assert result["candidates"][0].get("confidence") is None
    assert api_client.get(f"/api/change-analyses/{result['analysis_id']}").json()["pair_id"] == result["pair_id"]
    probability = api_client.get(result["artifacts"]["probability"])
    assert probability.status_code == 200
    assert probability.headers["content-type"].startswith("image/tiff")
    candidate_raster = api_client.get(result["artifacts"]["candidate_mask"])
    assert candidate_raster.status_code == 200
    assert candidate_raster.headers["content-type"].startswith("image/tiff")
    for kind in ("probability_preview", "raw_mask_preview", "candidate_mask_preview"):
        artifact_preview = api_client.get(f"/api/change-analyses/{result['analysis_id']}/artifacts/{kind}")
        assert artifact_preview.status_code == 200, artifact_preview.text
        assert artifact_preview.headers["content-type"] == "image/png"
    preview = api_client.get(result["artifacts"]["t1_preview"])
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/jpeg"
    queue = api_client.get("/api/review-queue").json()
    assert queue["count"] == result["candidate_count"]
    assert api_client.get("/api/audit").json()["integrity"]["intact"] is True
