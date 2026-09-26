from __future__ import annotations

import pytest

from pipeline.retrieval.filters import eligible_tiles


def test_sensor_filter_applied_before_faiss_ranking(retrieval_setup):
    retriever, _, _ = retrieval_setup
    response = retriever.search_text("urban", sensor="sentinel-2", top_k=5)
    assert {item["tile_id"] for item in response["results"]} == {"tile-0", "tile-2"}
    assert response["diagnostics"]["eligible_catalog_tiles"] == 2
    assert response["diagnostics"]["indexed_eligible_tiles"] == 2


def test_inclusive_date_filter(retrieval_setup):
    retriever, _, _ = retrieval_setup
    response = retriever.search_text("urban", date_from="2025-01-01", date_to="2025-06-01")
    assert [item["tile_id"] for item in response["results"]] == ["tile-0"]


def test_bbox_intersection_filter(retrieval_setup):
    retriever, _, _ = retrieval_setup
    response = retriever.search_text("water", bbox=[4, 4, 11, 11])
    assert {item["tile_id"] for item in response["results"]} == {"tile-0", "tile-2"}


def test_invalid_bbox_rejected(retrieval_setup):
    retriever, _, _ = retrieval_setup
    with pytest.raises(ValueError, match="bbox"):
        retriever.search_text("water", bbox=[4, 3, 2, 1])


def test_catalog_candidate_helper(retrieval_setup):
    retriever, _, _ = retrieval_setup
    records = eligible_tiles(retriever.catalog, sensor="landsat")
    assert [record.tile_id for record in records] == ["tile-1"]
