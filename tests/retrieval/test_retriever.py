from __future__ import annotations

from pathlib import Path

import pytest


def test_allowed_tile_ids_are_applied_in_faiss(retrieval_setup):
    retriever, _, _ = retrieval_setup
    response = retriever.search_text("urban", top_k=3, sensor="landsat")
    assert [item["tile_id"] for item in response["results"]] == ["tile-1"]
    assert response["results"][0]["rank"] == 1


def test_query_vector_passed_to_faiss_is_normalized(retrieval_setup, monkeypatch):
    import numpy as np

    retriever, _, _ = retrieval_setup
    original_search = retriever.faiss_index.search
    observed = {}

    def check_normalized(vector, k, *, allowed_tile_ids=None):
        observed["norm"] = float(np.linalg.norm(vector))
        observed["allowed"] = allowed_tile_ids
        return original_search(vector, k, allowed_tile_ids=allowed_tile_ids)

    monkeypatch.setattr(retriever.faiss_index, "search", check_normalized)
    retriever.search_text("normalized query")
    assert observed["norm"] == pytest.approx(1.0)
    assert observed["allowed"] == {"tile-0", "tile-1", "tile-2"}


@pytest.mark.integration
def test_real_remoteclip_text_image_and_index_integration():
    checkpoint = Path("models/remoteclip/RemoteCLIP-ViT-B-32.pt")
    index_path = Path("data/index/remoteclip_vit_b32.index")
    catalog_path = Path("data/catalog/tiles.json")
    if not all(path.is_file() for path in (checkpoint, index_path, catalog_path)):
        pytest.skip("local RemoteCLIP checkpoint, Phase 3 catalog, and Phase 4 index are required")

    from pipeline.embeddings.remoteclip import RemoteCLIPAdapter
    from pipeline.indexing.incremental_index import IncrementalIndex
    from pipeline.indexing.tile_catalog import TileCatalog
    from pipeline.retrieval.retriever import Retriever

    model = RemoteCLIPAdapter(checkpoint, device="cpu")
    retriever = Retriever(model, IncrementalIndex(index_path), TileCatalog(catalog_path))
    text_results = retriever.search_text("urban area", top_k=3)
    image_path = Path("data/processed/phase2_validation/tiles/s2_demo/tile_000000.tif")
    if not image_path.is_file():
        image_path = next(Path("data/processed/phase2_validation/tiles/s2_demo").glob("*.tif"))
    image_results = retriever.search_image(image_path, top_k=3)
    assert len(text_results["results"]) == 3
    assert len(image_results["results"]) == 3
    assert all(text_results["results"][i]["score"] >= text_results["results"][i + 1]["score"]
               for i in range(len(text_results["results"]) - 1))
    assert all(image_results["results"][i]["score"] >= image_results["results"][i + 1]["score"]
               for i in range(len(image_results["results"]) - 1))
