"""Thin orchestration of the Phase 4 encoders, FAISS, and tile catalog."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from time import perf_counter
from typing import Sequence

import numpy as np

from pipeline.embeddings.image_encoder import ImageEncoder
from pipeline.embeddings.normalization import normalize_embeddings
from pipeline.indexing.incremental_index import IncrementalIndex
from pipeline.indexing.tile_catalog import TileCatalog, TileMetadata
from pipeline.retrieval.filters import eligible_tiles


class Retriever:
    """Local RemoteCLIP-to-FAISS retrieval with metadata filters."""

    def __init__(self, model, faiss_index: IncrementalIndex, catalog: TileCatalog,
                 image_encoder: ImageEncoder | None = None) -> None:
        self.model = model
        self.faiss_index = faiss_index
        self.catalog = catalog
        self.image_encoder = image_encoder or ImageEncoder(model)

    def _search(
        self,
        query_vector: np.ndarray,
        *,
        query: str,
        query_type: str,
        top_k: int,
        sensor: str | None,
        date_from: str | date | datetime | None,
        date_to: str | date | datetime | None,
        bbox: Sequence[float] | None,
        bbox_crs: str | None = None,
        query_path: str | Path | None = None,
        exclude_query_tile: bool = False,
        total_started: float,
        query_embedding_ms: float,
        image_preprocessing_ms: float = 0.0,
    ) -> dict:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        metadata_started = perf_counter()
        eligible = eligible_tiles(
            self.catalog, sensor=sensor, date_from=date_from, date_to=date_to,
            bbox=bbox, bbox_crs=bbox_crs,
        )
        by_id = {record.tile_id: record for record in eligible}
        query_tile_id = None
        if query_path is not None:
            resolved_query = Path(query_path).resolve()
            query_tile_id = next(
                (record.tile_id for record in self.catalog.list_tiles()
                 if Path(record.tile_path).resolve() == resolved_query),
                None,
            )
        if exclude_query_tile and query_tile_id is not None:
            by_id.pop(query_tile_id, None)
        metadata_filter_ms = (perf_counter() - metadata_started) * 1000

        faiss_started = perf_counter()
        ranked = self.faiss_index.search(
            normalize_embeddings(query_vector),
            top_k,
            allowed_tile_ids=set(by_id),
        ) if by_id else []
        faiss_search_ms = (perf_counter() - faiss_started) * 1000

        lookup_started = perf_counter()
        results = []
        for rank, match in enumerate(ranked, start=1):
            record = by_id.get(match["tile_id"])
            if record is None:
                continue
            results.append(self._result(record, match["score"], rank,
                                        is_query_tile=record.tile_id == query_tile_id))
        metadata_lookup_ms = metadata_filter_ms + (perf_counter() - lookup_started) * 1000
        scores = [item["score"] for item in results]
        diagnostics = {
            "returned": len(results),
            "eligible_catalog_tiles": len(by_id),
            "indexed_eligible_tiles": sum(self.faiss_index.contains(tile_id) for tile_id in by_id),
            "score_distribution": ({
                "min": float(min(scores)),
                "max": float(max(scores)),
                "mean": float(np.mean(scores)),
            } if scores else None),
        }
        timings = {
            "query_embedding_ms": round(query_embedding_ms, 3),
            "image_preprocessing_ms": round(image_preprocessing_ms, 3),
            "faiss_search_ms": round(faiss_search_ms, 3),
            "metadata_lookup_ms": round(metadata_lookup_ms, 3),
            "total_ms": round((perf_counter() - total_started) * 1000, 3),
        }
        return {
            "query": query,
            "query_type": query_type,
            "query_tile_id": query_tile_id,
            "query_tile_excluded": bool(exclude_query_tile and query_tile_id is not None),
            "results": results,
            "diagnostics": diagnostics,
            "timings": timings,
        }

    @staticmethod
    def _result(record: TileMetadata, score: float, rank: int, *, is_query_tile: bool) -> dict:
        return {
            "rank": rank,
            "tile_id": record.tile_id,
            "score": float(score),
            "path": record.tile_path,
            "sensor": record.sensor,
            "acquisition_datetime": record.acquisition_datetime,
            "bounds": list(record.bounds),
            "crs": record.crs,
            "resolution": list(record.resolution),
            "is_query_tile": is_query_tile,
        }

    def search_text(
        self,
        query: str,
        top_k: int = 5,
        *,
        sensor: str | None = None,
        date_from: str | date | datetime | None = None,
        date_to: str | date | datetime | None = None,
        bbox: Sequence[float] | None = None,
        bbox_crs: str | None = None,
    ) -> dict:
        total_started = perf_counter()
        if not isinstance(query, str) or not query.strip():
            raise ValueError("text query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        started = perf_counter()
        vector = self.model.encode_text(query.strip())
        embedding_ms = (perf_counter() - started) * 1000
        return self._search(
            normalize_embeddings(vector), query=query.strip(), query_type="text", top_k=top_k,
            sensor=sensor, date_from=date_from, date_to=date_to, bbox=bbox, bbox_crs=bbox_crs,
            query_embedding_ms=embedding_ms, total_started=total_started,
        )

    def search_image(
        self,
        image_path: str | Path,
        top_k: int = 5,
        *,
        sensor: str | None = None,
        date_from: str | date | datetime | None = None,
        date_to: str | date | datetime | None = None,
        bbox: Sequence[float] | None = None,
        bbox_crs: str | None = None,
        exclude_query_tile: bool = False,
    ) -> dict:
        total_started = perf_counter()
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"query image does not exist: {path}")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        read_before = self.image_encoder.tile_read_seconds
        preprocess_before = getattr(self.model, "preprocessing_seconds", 0.0)
        started = perf_counter()
        vector = self.image_encoder.encode_image(path)
        embedding_ms = (perf_counter() - started) * 1000
        read_seconds = self.image_encoder.tile_read_seconds - read_before
        model_preprocess_seconds = getattr(self.model, "preprocessing_seconds", 0.0) - preprocess_before
        return self._search(
            normalize_embeddings(vector), query=str(path), query_type="image", top_k=top_k,
            sensor=sensor, date_from=date_from, date_to=date_to, bbox=bbox, bbox_crs=bbox_crs,
            query_path=path, exclude_query_tile=exclude_query_tile,
            query_embedding_ms=embedding_ms,
            image_preprocessing_ms=(read_seconds + model_preprocess_seconds) * 1000,
            total_started=total_started,
        )
