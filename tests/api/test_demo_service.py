from __future__ import annotations

from fastapi.testclient import TestClient

from pipeline.api.app import ROOT, create_app
import yaml


def _client(tmp_path):
    settings = yaml.safe_load((ROOT / "configs/api.yaml").read_text(encoding="utf-8"))
    settings["database"] = str(tmp_path / "demo.sqlite")
    change = yaml.safe_load((ROOT / "configs/change_detection.yaml").read_text(encoding="utf-8"))
    settings["analysis_output_directory"] = change["output_directory"]
    config = tmp_path / "api.yaml"
    config.write_text(yaml.safe_dump(settings), encoding="utf-8")
    app = create_app(config)
    client = TestClient(app)
    client.__enter__()
    return client


def test_demo_end_to_end_data_routes_and_idempotent_review(tmp_path, monkeypatch):
    monkeypatch.setenv("AVLOKAN_DEMO_MODE", "true")
    client = _client(tmp_path)
    try:
        assert client.get("/api/demo/status").json()["enabled"] is True
        query = "Newly constructed buildings and infrastructure development"
        search = client.post("/api/demo/search/text", json={"query": query, "sensors": ["s2"], "top_k": 4})
        assert search.status_code == 200
        assert [x["id"] for x in search.json()["results"]] == [f"s2_demo__tile_{i:06d}" for i in range(4)]
        assert search.json()["external_network"] is False
        filtered = client.post("/api/demo/search/text", json={"query": query, "sensors": ["s2"],
            "date_from": "2025-03-30", "top_k": 8})
        assert filtered.json()["results"] == []
        assert len(client.post("/api/demo/search/text", json={"query": query, "sensors": ["s2"],
            "region": "indore"}).json()["results"]) == 4
        assert client.post("/api/demo/search/text", json={"query": query, "sensors": ["s1"]}).json()["results"] == []
        assert client.post("/api/demo/search/text", json={"query": "arbitrary imagery"}).status_code == 422

        image = client.post("/api/demo/search/image", json={"scene_id": "s2_demo__tile_000000", "sensors": ["s2"]})
        assert image.status_code == 200 and len(image.json()["results"]) == 3
        assert client.get("/api/demo/similar-sites", params={"scene_id": "s2_demo__tile_000000"}).json()["sites"]
        assert client.get("/api/demo/investigation").json()["investigation_id"] == "demo-indore-20250329-20250324"
        assert [x["date"] for x in client.get("/api/demo/timeline").json()["observations"]] == ["2025-03-24", "2025-03-29"]
        assert client.get("/api/demo/evidence").json()["change_type_source"] == "Demo interpretation; not a classifier prediction"
        assert client.get("/api/demo/provenance").json()["classification"].startswith("mixed REAL")

        analysis = client.get("/api/demo/analysis")
        assert analysis.status_code == 200 and analysis.json()["demo_saved_result"]
        assert analysis.json()["statistics"]["changed_pixels"] == 1968
        for kind in ("probability_preview", "raw_mask_preview", "candidate_mask_preview", "t1_preview", "t2_preview"):
            response = client.get(f"/api/demo/artifacts/{kind}")
            assert response.status_code == 200 and response.headers["content-type"].startswith("image/")
        review = {"candidate_id": "1201535bfe3a41b189653b8533253146:2", "decision": "confirm", "analyst": "Demo Analyst"}
        first = client.post("/api/demo/review", json=review).json()
        again = client.post("/api/demo/review", json=review).json()
        assert first == again
        assert client.get("/api/demo/audit").json()["decision"] == first
        audit = client.get("/api/audit").json()
        assert audit["integrity"]["intact"] and any("demo decision confirm" in x["detail"] for x in audit["items"])
        exported = client.get("/api/demo/export").json()
        assert exported["analysis"]["analysis_id"] == analysis.json()["analysis_id"]
        assert exported["review"]["decision"] == first
        assert client.post("/api/demo/reset").json()["reset"]
        assert client.get("/api/demo/audit").json()["decision"] is None
    finally:
        client.close()


def test_demo_endpoints_are_unavailable_when_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("AVLOKAN_DEMO_MODE", raising=False)
    client = _client(tmp_path)
    try:
        assert client.get("/api/demo/status").json()["enabled"] is False
        assert client.get("/api/demo/analysis").status_code == 404
    finally:
        client.close()
