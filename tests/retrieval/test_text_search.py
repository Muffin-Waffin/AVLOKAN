from __future__ import annotations

import pytest


def test_text_search_returns_ranked_metadata(retrieval_setup):
    retriever, records, _ = retrieval_setup
    response = retriever.search_text("urban area", top_k=3)
    assert response["query_type"] == "text"
    assert [item["tile_id"] for item in response["results"]] == ["tile-0", "tile-1", "tile-2"]
    scores = [item["score"] for item in response["results"]]
    assert scores == sorted(scores, reverse=True)
    first = response["results"][0]
    assert first["path"] == records[0].tile_path
    assert first["sensor"] == "sentinel-2"
    assert first["acquisition_datetime"] == records[0].acquisition_datetime
    assert first["bounds"] == list(records[0].bounds)
    assert first["crs"] == records[0].crs
    assert first["resolution"] == list(records[0].resolution)


def test_top_k_limited_to_available_eligible_tiles(retrieval_setup):
    retriever, _, _ = retrieval_setup
    assert len(retriever.search_text("vegetation", top_k=2)["results"]) == 2
    assert len(retriever.search_text("vegetation", top_k=10)["results"]) == 3


@pytest.mark.parametrize("query", ["", "  ", None])
def test_empty_text_query_rejected(retrieval_setup, query):
    retriever, _, _ = retrieval_setup
    with pytest.raises(ValueError, match="must not be empty"):
        retriever.search_text(query)


def test_invalid_top_k_rejected(retrieval_setup):
    retriever, _, _ = retrieval_setup
    with pytest.raises(ValueError, match="top_k"):
        retriever.search_text("water", top_k=0)


def test_response_includes_timing_and_score_diagnostics(retrieval_setup):
    retriever, _, _ = retrieval_setup
    response = retriever.search_text("water")
    assert set(response["timings"]) == {
        "query_embedding_ms", "image_preprocessing_ms", "faiss_search_ms",
        "metadata_lookup_ms", "total_ms",
    }
    assert response["diagnostics"]["score_distribution"]["max"] == response["results"][0]["score"]
