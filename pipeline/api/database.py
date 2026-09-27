"""Small SQLite store for API-created AOIs, analyses, review actions, and audit events."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApiDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS aois (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, lat REAL NOT NULL,
                lng REAL NOT NULL, radius_km REAL NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, pair_id TEXT NOT NULL,
                result_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_candidates (
                id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, component_id INTEGER NOT NULL,
                status TEXT NOT NULL, candidate_json TEXT NOT NULL, created_at TEXT NOT NULL,
                decided_at TEXT, decision_by TEXT, FOREIGN KEY(analysis_id) REFERENCES analyses(id)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL,
                payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS review_status_idx ON review_candidates(status, created_at);
            CREATE INDEX IF NOT EXISTS audit_action_idx ON audit_events(action, seq);
            """)

    def append_audit(self, action: str, detail: str, payload: dict[str, Any] | None = None) -> dict:
        payload = payload or {}
        timestamp, event_id = utc_now(), uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
            previous = row["event_hash"] if row else "0" * 64
            body = {"id": event_id, "timestamp": timestamp, "action": action,
                    "detail": detail, "payload": payload, "previous_hash": previous}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            db.execute(
                "INSERT INTO audit_events(id,timestamp,action,detail,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
                (event_id, timestamp, action, detail, json.dumps(payload, sort_keys=True), previous, digest),
            )
        return {**body, "event_hash": digest, "h": digest, "t": timestamp}

    def list_audit(self, action: str | None = None, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            if action and action != "all":
                rows = db.execute(
                    "SELECT * FROM audit_events WHERE action=? ORDER BY seq DESC LIMIT ?", (action.upper(), limit)
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM audit_events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        output = []
        for row in reversed(rows):
            output.append({
                "id": row["id"], "timestamp": row["timestamp"], "t": row["timestamp"],
                "action": row["action"], "detail": row["detail"],
                "payload": json.loads(row["payload_json"]), "previous_hash": row["previous_hash"],
                "event_hash": row["event_hash"], "h": row["event_hash"],
            })
        return output

    @staticmethod
    def verify_audit(events: list[dict]) -> bool:
        previous = "0" * 64
        for event in events:
            body = {"id": event["id"], "timestamp": event["timestamp"], "action": event["action"],
                    "detail": event["detail"], "payload": event["payload"], "previous_hash": previous}
            expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if event["previous_hash"] != previous or event["event_hash"] != expected:
                return False
            previous = event["event_hash"]
        return True
