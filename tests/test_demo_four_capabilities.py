"""Comprehensive test suite for the 4 final AVLOKAN demo capabilities:
1. Real SAR Fallback (Sentinel-1 VV/VH terrain-corrected)
2. Optical + SAR Sensor Agreement
3. Change Confidence / Evidence Score
4. Real Incremental Indexing (FAISS IndexIDMap2)
"""
import os
import socket
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from pipeline.api.app import app
from pipeline.change_detection.sar_fallback import (
    SAR_DEFAULT_RASTER,
    SAR_ACQUISITION_TIMESTAMP,
    SAR_SENSOR,
    SAR_POLARIZATIONS,
    compute_sar_window_evidence,
    compute_sensor_agreement,
    compute_candidate_fusion_score,
    render_sar_preview,
)
from pipeline.indexing.incremental_index import IncrementalIndex

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def enable_demo_env(monkeypatch):
    """Ensure AVLOKAN_DEMO_MODE is set for testing demo endpoints."""
    monkeypatch.setenv("AVLOKAN_DEMO_MODE", "1")


def test_sar_fallback_real_data_and_evidence():
    """Verify SAR fallback loads real Sentinel-1 VV/VH data and computes evidence."""
    sar_path = ROOT / SAR_DEFAULT_RASTER
    assert sar_path.exists(), f"SAR artifact missing at {sar_path}"

    bounds = [582100.0, 2519110.0, 584660.0, 2521670.0]  # AOI in EPSG:32643
    vv_raw, vh_raw, e_vv, e_vh, e_sar = compute_sar_window_evidence(sar_path, bounds)

    assert SAR_SENSOR == "Sentinel-1"
    assert "2025-03-27" in SAR_ACQUISITION_TIMESTAMP
    assert SAR_POLARIZATIONS == ["VV", "VH"]

    # Verify deterministic evidence values within valid probability/evidence bounds
    np_mean = float(e_sar.mean())
    assert 0.0 <= np_mean <= 1.0
    assert 0.0 <= float(e_vv.mean()) <= 1.0
    assert 0.0 <= float(e_vh.mean()) <= 1.0
    assert np_mean == pytest.approx(0.6165, abs=0.02)


def test_sensor_agreement_matrix_and_candidate_scores():
    """Verify optical + SAR sensor agreement and deterministic evidence score formula."""
    # Candidate 2: High Optical (0.9861) + High SAR (0.5759) -> HIGH AGREEMENT
    opt_level, sar_level, label, score = compute_candidate_fusion_score(
        mean_optical_prob=0.9861,
        mean_sar_evidence=0.5759,
        data_quality=1.0,
    )
    assert opt_level == "HIGH"
    assert sar_level == "HIGH"
    assert label == "HIGH AGREEMENT"
    assert score == pytest.approx(84.7, abs=0.2)

    # Low Optical + High SAR -> SAR-ONLY
    _, _, label_sar_only, score_sar_only = compute_candidate_fusion_score(
        mean_optical_prob=0.20,
        mean_sar_evidence=0.60,
    )
    assert label_sar_only == "SAR-ONLY"
    assert score_sar_only < score

    # High Optical + Low SAR -> OPTICAL-ONLY
    _, _, label_opt_only, score_opt_only = compute_candidate_fusion_score(
        mean_optical_prob=0.85,
        mean_sar_evidence=0.30,
    )
    assert label_opt_only == "OPTICAL-ONLY"

    # Low Optical + Low SAR -> NO STRONG EVIDENCE
    _, _, label_none, score_none = compute_candidate_fusion_score(
        mean_optical_prob=0.15,
        mean_sar_evidence=0.20,
    )
    assert label_none == "NO STRONG EVIDENCE"
    assert score_none < score_opt_only


def test_sar_and_agreement_raster_previews():
    """Verify PNG preview rendering for VV, VH, SAR evidence, and agreement."""
    import numpy as np
    dummy_arr = np.linspace(0.0, 1.0, 100).reshape((10, 10))

    vv_bytes = render_sar_preview(dummy_arr, colormap="sar_grayscale")
    assert vv_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    ev_bytes = render_sar_preview(dummy_arr, colormap="sar_evidence")
    assert ev_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    agree_bytes = render_sar_preview(np.array([[3, 2], [1, 0]], dtype=np.uint8), colormap="sensor_agreement")
    assert agree_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_api_sar_and_agreement_endpoints():
    """Verify FastAPI routes for SAR fallback and sensor agreement."""
    client = TestClient(app)

    # 1. Demo SAR Fallback endpoint
    resp = client.get("/api/demo/sar-fallback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sensor"] == "Sentinel-1"
    assert "2025-03-27" in data["acquisition_datetime"]
    assert data["calibration_status"] == "Evidence Score (not calibrated probability)"
    assert "not a calibrated probability" in data["disclaimer"]
    assert "artifacts" in data

    # 2. Demo Sensor Agreement endpoint
    resp = client.get("/api/demo/sensor-agreement")
    assert resp.status_code == 200
    data = resp.json()
    assert "primary_candidate" in data
    c2 = data["primary_candidate"]
    assert c2["component_id"] == 2
    assert c2["sensor_agreement"] == "HIGH AGREEMENT"
    assert c2["evidence_score"] == pytest.approx(84.7, abs=0.2)
    assert "agreement_matrix" in data
    assert len(data["agreement_matrix"]) == 4

    # 3. Artifact image endpoints
    for art in ["sar_vv_preview", "sar_vh_preview", "sar_evidence_preview", "agreement_preview"]:
        resp = client.get(f"/api/artifacts/{art}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG")


def test_real_incremental_indexing_workflow():
    """Verify incremental indexing without rebuild, search discovery, persistence, and reset."""
    client = TestClient(app)

    # Step 0: Ensure clean baseline
    client.post("/api/demo/indexing/reset")

    # Step 1: Baseline status check
    status_resp = client.get("/api/demo/indexing/status")
    assert status_resp.status_code == 200
    status_before = status_resp.json()
    assert status_before["indexed_count"] == 4
    assert status_before["catalog_count"] == 4
    assert status_before["staged_scene"]["is_indexed"] is False

    # Step 2: Incremental ingest (1 real local scene tile)
    ingest_resp = client.post("/api/demo/indexing/incremental-ingest")
    assert ingest_resp.status_code == 200
    ingest_result = ingest_resp.json()
    assert ingest_result["count_before"] == 4
    assert ingest_result["count_after"] == 5
    assert ingest_result["tile_id"] == "s2_20250324__tile_000000"
    assert ingest_result["vector_dimension"] == 512
    assert ingest_result["rebuild_performed"] is False
    assert ingest_result["elapsed_ms"] > 0

    # Step 3: Status shows 5 indexed scenes
    status_after = client.get("/api/demo/indexing/status").json()
    assert status_after["indexed_count"] == 5
    assert status_after["catalog_count"] == 5
    assert status_after["staged_scene"]["is_indexed"] is True

    # Step 4: Verify search immediately finds the newly ingested tile
    search_resp = client.post("/api/search/text", json={"query": "quarry river excavation", "top_k": 5})
    assert search_resp.status_code == 200
    search_results = search_resp.json()
    results = search_results.get("results", [])
    found = any(r.get("tile_id") == "s2_20250324__tile_000000" for r in results)
    assert found, f"Newly ingested tile not found in search results: {results}"

    # Step 5: Verify persistence across index reloads (simulate restart)
    index_path = ROOT / "data" / "index" / "remoteclip_vit_b32.index"
    mapping_path = ROOT / "data" / "index" / "remoteclip_vit_b32_ids.json"
    reloaded_idx = IncrementalIndex(index_path, mapping_path=mapping_path)
    assert reloaded_idx.size() == 5, f"Expected 5 items after reload, found {reloaded_idx.size()}"
    assert reloaded_idx.contains("s2_20250324__tile_000000")

    # Step 6: Reset index back to baseline for repeat demo
    reset_resp = client.post("/api/demo/indexing/reset")
    assert reset_resp.status_code == 200
    status_reset = client.get("/api/demo/indexing/status").json()
    assert status_reset["indexed_count"] == 4
    assert status_reset["catalog_count"] == 4
    assert status_reset["staged_scene"]["is_indexed"] is False


def test_offline_zero_network_access(monkeypatch):
    """Verify that SAR fallback, sensor agreement, evidence score, and incremental indexing work with external network blocked."""
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        if isinstance(address, tuple):
            host = str(address[0])
            if host in ("127.0.0.1", "localhost", "::1"):
                return orig_connect(self, address)
        raise RuntimeError(f"External network access attempted to {address} during offline test!")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    # 1. SAR Fallback offline
    sar_path = ROOT / SAR_DEFAULT_RASTER
    bounds = [582100.0, 2519110.0, 584660.0, 2521670.0]
    vv_raw, vh_raw, e_vv, e_vh, e_sar = compute_sar_window_evidence(sar_path, bounds)
    assert float(e_sar.mean()) > 0

    # 2. Sensor Agreement & Evidence Score offline
    _, _, label, score = compute_candidate_fusion_score(0.9861, 0.5759, 1.0)
    assert label == "HIGH AGREEMENT"
    assert score == pytest.approx(84.7, abs=0.2)

    # 3. Incremental Indexing offline
    client = TestClient(app)
    resp = client.get("/api/demo/indexing/status")
    assert resp.status_code == 200
    assert resp.json()["indexed_count"] == 4
