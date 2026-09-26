from __future__ import annotations

import pytest


def test_image_search_returns_ranked_results(retrieval_setup):
    retriever, _, paths = retrieval_setup
    response = retriever.search_image(paths[0], top_k=2)
    assert response["query_type"] == "image"
    assert [item["tile_id"] for item in response["results"]] == ["tile-2", "tile-1"]
    assert response["timings"]["image_preprocessing_ms"] >= 0


def test_query_tile_is_indicated_and_excluded_only_when_requested(retrieval_setup):
    retriever, _, paths = retrieval_setup
    included = retriever.search_image(paths[0], top_k=3)
    assert included["query_tile_id"] == "tile-0"
    assert included["results"][0]["is_query_tile"] is False
    assert any(item["is_query_tile"] for item in included["results"])

    excluded = retriever.search_image(paths[0], top_k=3, exclude_query_tile=True)
    assert excluded["query_tile_excluded"] is True
    assert all(not item["is_query_tile"] for item in excluded["results"])
    assert "tile-0" not in [item["tile_id"] for item in excluded["results"]]


def test_missing_image_rejected(retrieval_setup, tmp_path):
    retriever, _, _ = retrieval_setup
    with pytest.raises(FileNotFoundError, match="does not exist"):
        retriever.search_image(tmp_path / "missing.tif")
