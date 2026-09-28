"""Deterministic, local SIH demo data and idempotent review state."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
from pathlib import Path
from typing import Any
import os

from fastapi import HTTPException, Query
from fastapi.responses import FileResponse


class DemoService:
    def __init__(self, root: Path, state_path: Path):
        self.root = root
        self.data = root / "data" / "demo"
        self.state_path = state_path
        self._lock = threading.Lock()

    def load(self, name: str) -> Any:
        return json.loads((self.data / f"{name}.json").read_text(encoding="utf-8"))

    def read_state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"decision": None, "audit": []}

    def decide(self, investigation_id: str, candidate_id: str, decision: str, analyst: str) -> dict:
        if decision not in {"confirm", "reject"}:
            raise ValueError("decision must be confirm or reject")
        with self._lock:
            state = self.read_state()
            prior = state.get("decision")
            if prior and prior["decision"] == decision:
                return prior
            event = {
                "investigation_id": investigation_id, "candidate_id": candidate_id,
                "decision": decision, "timestamp": datetime.now(timezone.utc).isoformat(),
                "analyst": analyst, "evidence_reference": self.load("config")["analysis_id"],
            }
            state["decision"] = event
            state.setdefault("audit", []).append(event)
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            return event


def register_demo_routes(app, root: Path, database, raster_preview, artifact_preview) -> None:
    """Register gated local demo routes; no model or retrieval pipeline runs here."""
    service = DemoService(root, root / "data" / "demo" / "runtime" / "state.json")

    def require_enabled():
        if os.environ.get("AVLOKAN_DEMO_MODE", "false").strip().lower() not in {"1", "true", "yes", "on"}:
            raise HTTPException(404, "Demo Mode is disabled")

    def active_config():
        return service.load("config")

    @app.get("/api/demo/status")
    def demo_status():
        enabled = os.environ.get("AVLOKAN_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
        return {"enabled": enabled, "mode": "SIH deterministic demo" if enabled else "normal application"}

    @app.post("/api/demo/search/text")
    def demo_text_search(request: dict):
        require_enabled()
        prepared = service.load("search_results")
        if str(request.get("query", "")).strip().casefold() != prepared["query"].casefold():
            raise HTTPException(422, "Demo Mode supports only the prepared demonstration query")
        return _filter_results(prepared["results"], request)

    @app.post("/api/demo/search/image")
    def demo_image_search(request: dict):
        require_enabled()
        prepared = service.load("image_search_results")
        if request.get("scene_id") != prepared["query_scene"]:
            raise HTTPException(422, "Select the official locally stored demo image")
        return _filter_results(prepared["results"], request)

    @app.get("/api/demo/similar-sites")
    def demo_similar_sites(scene_id: str = Query(...)):
        require_enabled()
        if scene_id != active_config()["demo_image_scene"]:
            raise HTTPException(404, "No prepared similar-site result for this scene")
        return service.load("similar_sites")

    @app.get("/api/demo/investigation")
    def demo_investigation():
        require_enabled()
        return service.load("investigation")

    @app.get("/api/demo/timeline")
    def demo_timeline():
        require_enabled()
        return service.load("timeline")

    @app.get("/api/demo/evidence")
    def demo_evidence():
        require_enabled()
        return service.load("evidence")

    @app.get("/api/demo/provenance")
    def demo_provenance():
        require_enabled()
        return service.load("provenance")

    @app.get("/api/demo/analysis")
    def demo_analysis():
        require_enabled()
        config = active_config()
        metadata_path = (root / config["analysis_metadata"]).resolve()
        if not metadata_path.is_relative_to((root / "data" / "processed").resolve()) or not metadata_path.is_file():
            raise HTTPException(404, "Saved demo analysis metadata is unavailable")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        analysis_id = config["analysis_id"]
        candidate_rows = metadata.get("candidates", [])
        return {
            "analysis_id": analysis_id, "timestamp": metadata["timestamp"], "pair_id": metadata["pair_id"],
            "name": "Indore demo investigation", "aoi_id": None,
            "temporal": {"t1_scene_id": config["t1_id"], "t2_scene_id": config["t2_id"],
                         "t1_date": metadata["t1_acquisition_timestamp"], "t2_date": metadata["t2_acquisition_timestamp"],
                         "t1_role": "T1", "t2_role": "T2"},
            "sensor": metadata["sensor"],
            "spatial": {"crs": metadata["crs"], "transform": metadata["transform"],
                        "width": metadata["width"], "height": metadata["height"], "bbox": metadata["bounding_box"],
                        "bbox_wgs84": list(__import__("rasterio.warp", fromlist=["transform_bounds"]).transform_bounds(
                            metadata["crs"], "EPSG:4326", *metadata["bounding_box"], densify_pts=21))},
            "model": {"name": metadata["model_name"], "checkpoint_role": metadata["checkpoint_role"],
                      "checkpoint_sha256": metadata["checkpoint_sha256"]},
            "threshold": metadata["threshold"], "statistics": metadata["statistics"],
            "temporal_embedding_similarity": metadata.get("temporal_embedding_similarity"),
            "candidates": [{**item, "id": f"{analysis_id}:{item['component_id']}", "analysis_id": analysis_id}
                           for item in candidate_rows], "candidate_count": len(candidate_rows),
            "filtering_statistics": metadata["filtering_statistics"], "timings_seconds": metadata["timings_seconds"],
            "artifacts": {kind: f"/api/demo/artifacts/{kind}" for kind in
                          ("probability", "raw_mask", "candidate_mask", "metadata", "t1_preview", "t2_preview")},
            "demo_saved_result": True,
        }

    @app.get("/api/demo/artifacts/{kind}")
    def demo_artifact(kind: str):
        require_enabled()
        valid_kinds = {
            "probability", "raw_mask", "candidate_mask", "metadata", "t1_preview", "t2_preview",
            "probability_preview", "raw_mask_preview", "candidate_mask_preview",
            "sar_vv_preview", "sar_vh_preview", "sar_evidence_preview", "agreement_preview"
        }
        if kind not in valid_kinds:
            raise HTTPException(404, "Unknown demo artifact")
        cfg = active_config()
        metadata_path = (root / cfg["analysis_metadata"]).resolve()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if kind in {"t1_preview", "t2_preview"}:
            source = (root / cfg["t1_path" if kind == "t1_preview" else "t2_path"]).resolve()
            return raster_preview(source)
        if kind in {"sar_vv_preview", "sar_vh_preview", "sar_evidence_preview", "agreement_preview"}:
            from fastapi.responses import Response
            import rasterio
            from pipeline.change_detection.sar_fallback import (
                SAR_DEFAULT_RASTER, compute_sar_window_evidence,
                compute_sensor_agreement, render_sar_preview
            )
            bounds = metadata["bounding_box"]
            _, _, e_vv, e_vh, e_sar = compute_sar_window_evidence(root / SAR_DEFAULT_RASTER, bounds)
            if kind == "sar_vv_preview":
                png_bytes = render_sar_preview(e_vv, "sar_grayscale")
            elif kind == "sar_vh_preview":
                png_bytes = render_sar_preview(e_vh, "sar_grayscale")
            elif kind == "sar_evidence_preview":
                png_bytes = render_sar_preview(e_sar, "sar_evidence")
            else:
                prob_path = Path(metadata["probability_raster"])
                if not prob_path.is_absolute():
                    prob_path = root / prob_path
                with rasterio.open(prob_path) as opt_src:
                    opt_prob = opt_src.read(1)
                _, cat_agr, _ = compute_sensor_agreement(opt_prob, e_sar)
                png_bytes = render_sar_preview(cat_agr, "sensor_agreement")
            return Response(png_bytes, media_type="image/png", headers={"X-AVLOKAN-Artifact-View": kind})
        key = {"probability": "probability_raster", "raw_mask": "raw_mask_raster",
               "candidate_mask": "candidate_mask_raster", "metadata": "metadata_path"}.get(kind.removesuffix("_preview"))
        source = Path(metadata[key]).resolve()
        processed = (root / "data" / "processed").resolve()
        if not source.is_relative_to(processed) or not source.is_file():
            raise HTTPException(404, "Saved demo artifact is unavailable")
        if kind.endswith("_preview"):
            validity_paths = [(root / cfg[key]).resolve() for key in ("t1_path", "t2_path")]
            return artifact_preview(source, kind, validity_paths)
        return FileResponse(source, media_type="application/json" if kind == "metadata" else "image/tiff")

    @app.get("/api/demo/sar-fallback")
    def demo_sar_fallback():
        require_enabled()
        cfg = active_config()
        metadata_path = (root / cfg["analysis_metadata"]).resolve()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        bounds = metadata["bounding_box"]
        from pipeline.change_detection.sar_fallback import (
            SAR_DEFAULT_RASTER, SAR_SENSOR, SAR_PLATFORM, SAR_ACQUISITION_TIMESTAMP,
            SAR_MODE, SAR_POLARIZATIONS, SAR_PROVENANCE,
            compute_sar_window_evidence, compute_candidate_fusion_score
        )
        vv_raw, vh_raw, e_vv, e_vh, e_sar = compute_sar_window_evidence(root / SAR_DEFAULT_RASTER, bounds)
        candidates_out = []
        for c in metadata.get("candidates", []):
            cid = c["component_id"]
            cb = c["bbox_coordinates"]
            _, _, _, _, c_sar = compute_sar_window_evidence(
                root / SAR_DEFAULT_RASTER,
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
                "vv_preview": "/api/demo/artifacts/sar_vv_preview",
                "vh_preview": "/api/demo/artifacts/sar_vh_preview",
                "sar_evidence_preview": "/api/demo/artifacts/sar_evidence_preview",
                "agreement_preview": "/api/demo/artifacts/agreement_preview",
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

    @app.get("/api/demo/sensor-agreement")
    def demo_sensor_agreement():
        require_enabled()
        fb = demo_sar_fallback()
        c2 = next((c for c in fb["candidates"] if c["component_id"] == 2), fb["candidates"][0] if fb["candidates"] else None)
        return {
            "optical": {
                "sensor": "Sentinel-2",
                "t1_date": "2025-03-24",
                "t2_date": "2025-03-29",
                "primary_candidate_level": c2["optical_level"] if c2 else "HIGH",
                "primary_candidate_prob": c2["optical_probability"] if c2 else 0.9861,
            },
            "sar": {
                "sensor": "Sentinel-1",
                "date": "2025-03-27",
                "primary_candidate_level": c2["sar_level"] if c2 else "HIGH",
                "primary_candidate_evidence": c2["sar_evidence"] if c2 else 0.5759,
            },
            "agreement_matrix": [
                {"optical": "HIGH", "sar": "HIGH", "agreement": "HIGH AGREEMENT", "meaning": "Corroborated physical change"},
                {"optical": "HIGH", "sar": "LOW",  "agreement": "OPTICAL-ONLY",   "meaning": "Spectral shift without radar verification"},
                {"optical": "LOW",  "sar": "HIGH", "agreement": "SAR-ONLY",       "meaning": "Radar backscatter anomaly without spectral shift"},
                {"optical": "LOW",  "sar": "LOW",  "agreement": "NO STRONG EVIDENCE", "meaning": "Baseline stability"}
            ],
            "primary_candidate": c2,
            "disclaimer": "Evidence score combines available optical, SAR and quality evidence. It is not a calibrated probability.",
            "formula": "0.45 * optical + 0.25 * sar + 0.15 * agreement + 0.15 * quality",
        }

    @app.get("/api/demo/indexing/status")
    def demo_indexing_status():
        require_enabled()
        from pipeline.indexing.incremental_index import IncrementalIndex
        from pipeline.indexing.tile_catalog import TileCatalog
        from pipeline.indexing.incremental_manager import get_incremental_status, ensure_baseline_backup
        index_path = (root / "data" / "index" / "remoteclip_vit_b32.index").resolve()
        mapping_path = (root / "data" / "index" / "remoteclip_vit_b32_ids.json").resolve()
        catalog_path = (root / "data" / "catalog" / "tiles.json").resolve()
        ensure_baseline_backup(index_path, mapping_path, catalog_path)
        index = IncrementalIndex(index_path)
        catalog = TileCatalog(catalog_path)
        return get_incremental_status(index, catalog)

    @app.post("/api/demo/indexing/incremental-ingest")
    def demo_incremental_ingest():
        require_enabled()
        import yaml
        from pipeline.indexing.incremental_index import IncrementalIndex
        from pipeline.indexing.tile_catalog import TileCatalog
        from pipeline.embeddings.remoteclip import RemoteCLIPAdapter
        from pipeline.embeddings.image_encoder import ImageEncoder
        from pipeline.indexing.incremental_manager import perform_incremental_ingest, ensure_baseline_backup
        index_path = (root / "data" / "index" / "remoteclip_vit_b32.index").resolve()
        mapping_path = (root / "data" / "index" / "remoteclip_vit_b32_ids.json").resolve()
        catalog_path = (root / "data" / "catalog" / "tiles.json").resolve()
        ensure_baseline_backup(index_path, mapping_path, catalog_path)
        index = IncrementalIndex(index_path)
        catalog = TileCatalog(catalog_path)
        cfg = yaml.safe_load((root / "configs" / "embeddings.yaml").read_text(encoding="utf-8"))
        adapter = RemoteCLIPAdapter((root / cfg["model"]["checkpoint"]).resolve(), device="cpu")
        encoder = ImageEncoder(adapter)
        retriever = getattr(app.state, "retriever", None)
        result = perform_incremental_ingest(index, catalog, encoder, retriever=retriever)
        database.append_audit("INGEST", f"Incrementally indexed {result.get('tile_id')}", result)
        return result

    @app.post("/api/demo/indexing/reset")
    def demo_indexing_reset():
        require_enabled()
        from pipeline.indexing.incremental_manager import reset_incremental_index
        index_path = (root / "data" / "index" / "remoteclip_vit_b32.index").resolve()
        mapping_path = (root / "data" / "index" / "remoteclip_vit_b32_ids.json").resolve()
        catalog_path = (root / "data" / "catalog" / "tiles.json").resolve()
        res = reset_incremental_index(index_path, mapping_path, catalog_path)
        if hasattr(app.state, "retriever"):
            app.state.retriever = None
        return res

    @app.post("/api/demo/review")
    def demo_review(request: dict):
        require_enabled()
        cfg = active_config()
        candidate_id = f"{cfg['analysis_id']}:2"
        if request.get("candidate_id") != candidate_id:
            raise HTTPException(404, "Demo candidate was not found")
        try:
            event = service.decide("demo-indore-20250329-20250324", candidate_id,
                                   request.get("decision"), str(request.get("analyst") or "Demo Analyst"))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with database.connect() as connection:
            exists = connection.execute("SELECT 1 FROM audit_events WHERE payload_json LIKE ? LIMIT 1",
                                        (f"%{event['timestamp']}%",)).fetchone()
        if not exists:
            database.append_audit("CONFIRMED" if event["decision"] == "confirm" else "REJECTED",
                                  f"{event['analyst']} recorded demo decision {event['decision']} for {candidate_id}",
                                  event)
        return event

    @app.get("/api/demo/audit")
    def demo_audit():
        require_enabled()
        return service.read_state()

    @app.get("/api/demo/export")
    def demo_export():
        require_enabled()
        database.append_audit("EXPORT", "Exported SIH demo investigation",
                              {"investigation_id": service.load("investigation")["investigation_id"]})
        return {"investigation": service.load("investigation"), "timeline": service.load("timeline"),
                "analysis": demo_analysis(), "evidence": service.load("evidence"),
                "provenance": service.load("provenance"), "review": service.read_state()}

    @app.post("/api/demo/reset")
    def demo_reset():
        require_enabled()
        with service._lock:
            service.state_path.unlink(missing_ok=True)
        return {"reset": True}


def _filter_results(results: list[dict], request: dict) -> dict:
    values = list(results)
    date_from, date_to = request.get("date_from"), request.get("date_to")
    sensors = request.get("sensors")
    region = request.get("region")
    if date_from:
        values = [row for row in values if row["date"] >= date_from]
    if date_to:
        values = [row for row in values if row["date"] <= date_to]
    if sensors:
        aliases = {
            "s2": "s2", "sentinel-2": "s2",
            "s1": "s1", "sentinel-1": "s1",
            "l8": "l8", "landsat": "l8",
            "bh": "bh", "bhuvan": "bh",
        }
        accepted = {aliases.get(str(x).lower(), str(x).lower()) for x in sensors}
        def match_sensor(row):
            s = row.get("sensor")
            sid = (s.get("id") if isinstance(s, dict) else str(s)).lower()
            return aliases.get(sid, sid) in accepted
        values = [row for row in values if match_sensor(row)]
    if request.get("min_similarity") is not None:
        values = [row for row in values if row["sim"] >= float(request["min_similarity"])]
    if region and region != "all":
        values = [row for row in values if row["region"].casefold().startswith(str(region).casefold())]
    if request.get("bbox"):
        west, south, east, north = request["bbox"]
        values = [row for row in values if west <= row["lng"] <= east and south <= row["lat"] <= north]

    sensor_map = {
        "sentinel-2": {"id": "s2", "name": "Sentinel-2", "tag": "S2"},
        "s2": {"id": "s2", "name": "Sentinel-2", "tag": "S2"},
        "sentinel-1": {"id": "s1", "name": "Sentinel-1 SAR", "tag": "S1"},
        "s1": {"id": "s1", "name": "Sentinel-1 SAR", "tag": "S1"},
        "landsat": {"id": "l8", "name": "Landsat C2", "tag": "L8"},
        "l8": {"id": "l8", "name": "Landsat C2", "tag": "L8"},
        "bhuvan": {"id": "bh", "name": "Bhuvan / ISRO", "tag": "BH"},
        "bh": {"id": "bh", "name": "Bhuvan / ISRO", "tag": "BH"},
    }
    formatted = []
    for row in values[:int(request.get("top_k", 24))]:
        item = dict(row)
        s = item.get("sensor")
        if isinstance(s, str):
            s_key = s.lower()
            item["sensor"] = sensor_map.get(s_key, {"id": s_key, "name": s, "tag": s.upper()})
        formatted.append(item)

    return {
        "query_type": "demo-prepared",
        "results": formatted,
        "warnings": ["DEMO SIMULATED ranking; source imagery and previews are real local data."],
        "timings": {"total_ms": 0},
        "external_network": False,
    }
