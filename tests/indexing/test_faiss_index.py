import numpy as np
import pytest

from pipeline.indexing.faiss_index import FaissIndexError, FaissVectorIndex
from pipeline.indexing.incremental_index import IncrementalIndex
from pipeline.indexing.index_manager import IndexManager


def test_create_add_cosine_search_and_id_mapping():
    index = FaissVectorIndex.create_index(4)
    original = np.array([[2, 0, 0, 0], [0, 5, 0, 0]], dtype=np.float32)
    index.add(original, ["tile_a", "tile_b"])
    assert index.size() == 2
    assert index.dimension() == 4
    np.testing.assert_array_equal(original, [[2, 0, 0, 0], [0, 5, 0, 0]])
    hits = index.search(np.array([4, 0, 0, 0], dtype=np.float32), k=5)
    assert [hit["tile_id"] for hit in hits] == ["tile_a", "tile_b"]
    assert hits[0]["score"] == pytest.approx(1.0)


def test_reject_duplicate_ids_vector_dimensions_and_zero_vectors():
    index = FaissVectorIndex(3)
    index.add(np.array([[1, 0, 0]], dtype=np.float32), ["tile_a"])
    with pytest.raises(FaissIndexError, match="duplicate"):
        index.add(np.array([[0, 1, 0]], dtype=np.float32), ["tile_a"])
    with pytest.raises(FaissIndexError, match="shape"):
        index.add(np.ones((1, 4), dtype=np.float32), ["tile_b"])
    with pytest.raises(FaissIndexError, match="zero"):
        index.add(np.zeros((1, 3), dtype=np.float32), ["tile_b"])
    with pytest.raises(FaissIndexError, match="dimension"):
        index.search(np.ones(2, dtype=np.float32), k=1)


def test_save_load_and_search_after_reload(tmp_path):
    path = tmp_path / "avlokan.index"
    index = FaissVectorIndex(4)
    index.add(np.eye(4, dtype=np.float32)[:3], ["tile_a", "tile_b", "tile_c"])
    index.save(path)
    assert path.exists()
    assert (tmp_path / "avlokan_ids.json").exists()
    loaded = FaissVectorIndex.load(path)
    assert loaded.size() == 3
    assert loaded.dimension() == 4
    assert loaded.search(np.array([0, 0, 1, 0], dtype=np.float32), 1)[0]["tile_id"] == "tile_c"


def test_incremental_addition_persists_without_rebuilding(tmp_path):
    path = tmp_path / "incremental.index"
    index = IncrementalIndex(path, dimension=4)
    index.add_embeddings(np.eye(4, dtype=np.float32)[:2], ["tile_a", "tile_b"])
    index = IncrementalIndex(path)
    index.add_embeddings(np.eye(4, dtype=np.float32)[2:], ["tile_c", "tile_d"])
    reloaded = IncrementalIndex(path)
    assert reloaded.size() == 4
    assert reloaded.search(np.array([0, 0, 0, 1], dtype=np.float32), 1)[0]["tile_id"] == "tile_d"


def test_incremental_rejects_dimension_mismatch_and_manager_interface(tmp_path):
    path = tmp_path / "manager.index"
    manager = IndexManager(path, dimension=2)
    manager.index_embeddings(np.array([[1, 0]], dtype=np.float32), ["tile_x"])
    with pytest.raises(ValueError, match="dimension"):
        IncrementalIndex(path, dimension=3)
    assert manager.search(np.array([1, 0], dtype=np.float32), 1)[0]["tile_id"] == "tile_x"
