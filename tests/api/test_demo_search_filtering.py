"""Test suite to verify demo query retrieval and filter contract resolution."""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from pipeline.api.app import app

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def enable_demo_mode(monkeypatch):
    monkeypatch.setenv("AVLOKAN_DEMO_MODE", "1")


def test_demo_text_search_retrieves_and_normalizes_sensor():
    """Verify demo text query returns 4 results with normalized sensor objects."""
    client = TestClient(app)
    response = client.post(
        "/api/demo/search/text",
        json={"query": "Newly constructed buildings and infrastructure development", "sensors": ["s2", "s1", "l8"], "top_k": 24},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "demo-prepared"
    results = data["results"]
    assert len(results) == 4

    for r in results:
        # Verify result structure and IDs
        assert r["id"].startswith("s2_demo__tile_")
        assert r["region"] == "Indore prototype area"
        assert r["date"] == "2025-03-29"
        # Verify normalized sensor object
        assert isinstance(r["sensor"], dict)
        assert r["sensor"]["id"] == "s2"
        assert r["sensor"]["name"] == "Sentinel-2"
        assert r["sensor"]["tag"] == "S2"

        # Verify real local preview asset exists and returns 200
        preview_resp = client.get(r["thumbnail_url"])
        assert preview_resp.status_code == 200
        assert preview_resp.headers["content-type"].startswith("image/")
        assert len(preview_resp.content) > 1000


def test_demo_image_search_retrieves_and_normalizes_sensor():
    """Verify demo image query returns 3 results with normalized sensor objects."""
    client = TestClient(app)
    response = client.post(
        "/api/demo/search/image",
        json={"scene_id": "s2_demo__tile_000000", "sensors": ["s2", "s1", "l8"], "top_k": 24},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "demo-prepared"
    results = data["results"]
    assert len(results) == 3

    for r in results:
        assert r["id"].startswith("s2_demo__tile_")
        assert isinstance(r["sensor"], dict)
        assert r["sensor"]["id"] == "s2"
        assert r["sensor"]["name"] == "Sentinel-2"
        assert r["sensor"]["tag"] == "S2"

        preview_resp = client.get(r["thumbnail_url"])
        assert preview_resp.status_code == 200


def test_demo_sensor_filters_and_aliasing():
    """Verify backend filtering supports both short IDs ('s2') and long names ('sentinel-2')."""
    client = TestClient(app)

    # Filtering by 's2' includes all 4
    resp_s2 = client.post(
        "/api/demo/search/text",
        json={"query": "Newly constructed buildings and infrastructure development", "sensors": ["s2"]},
    )
    assert len(resp_s2.json()["results"]) == 4

    # Filtering by 'sentinel-2' includes all 4
    resp_s2_alias = client.post(
        "/api/demo/search/text",
        json={"query": "Newly constructed buildings and infrastructure development", "sensors": ["sentinel-2"]},
    )
    assert len(resp_s2_alias.json()["results"]) == 4

    # Filtering by 's1' or 'l8' excludes the S2 results
    resp_s1 = client.post(
        "/api/demo/search/text",
        json={"query": "Newly constructed buildings and infrastructure development", "sensors": ["s1"]},
    )
    assert len(resp_s1.json()["results"]) == 0


def test_normal_non_demo_search_remains_unchanged(monkeypatch):
    """Verify standard /api/search/text endpoint operates normally."""
    client = TestClient(app)
    response = client.post(
        "/api/search/text",
        json={"query": "quarry river excavation", "sensors": ["s2"], "top_k": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["query_type"] == "text"
    for r in data["results"]:
        assert isinstance(r["sensor"], dict)
        assert r["sensor"]["id"] == "s2"
        assert r["sensor"]["tag"] == "S2"
