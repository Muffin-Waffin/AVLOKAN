from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from pipeline.embeddings.cache import EmbeddingCache
from pipeline.embeddings.device import select_device
from pipeline.embeddings.image_encoder import read_sentinel2_rgb
from pipeline.embeddings.normalization import normalize_embeddings
from pipeline.indexing.incremental_index import IncrementalIndex


def test_device_auto_has_cpu_fallback():
    assert select_device("auto").type in {"cpu", "cuda"}
    assert select_device("cpu").type == "cpu"


def test_normalization_returns_float32_unit_vectors_without_mutation():
    source = np.array([[3, 4], [0, 2]], dtype=np.float64)
    result = normalize_embeddings(source)
    assert result.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(result, axis=1), 1.0)
    np.testing.assert_array_equal(source, [[3, 4], [0, 2]])
    assert normalize_embeddings(result) is not None


def test_normalization_rejects_zero_and_nonfinite():
    with pytest.raises(ValueError):
        normalize_embeddings(np.zeros(3))
    with pytest.raises(ValueError):
        normalize_embeddings(np.array([1, np.nan]))


def test_sentinel2_rgb_preprocessing_uses_b04_b03_b02(tmp_path: Path):
    path = tmp_path / "tile.tif"
    data = np.zeros((4, 8, 8), dtype=np.float32)
    data[0] = 0.1  # B02 blue
    data[1] = 0.5  # B03 green
    data[2] = 0.9  # B04 red
    data[3] = 0.0  # B08 must not enter RGB conversion
    with rasterio.open(path, "w", driver="GTiff", width=8, height=8, count=4,
                       dtype="float32", crs="EPSG:32643", transform=from_origin(0, 80, 10, 10)) as dst:
        dst.write(data)
    pixel = np.asarray(read_sentinel2_rgb(path))[0, 0]
    np.testing.assert_array_equal(pixel, [230, 128, 26])


def test_embedding_cache_provenance_and_reload(tmp_path: Path):
    cache = EmbeddingCache(tmp_path, "RemoteCLIP-ViT-B-32")
    vector = normalize_embeddings(np.array([1, 2, 3], dtype=np.float32))[0]
    cache.put("tile-a", "checkpoint-hash", vector, source_fingerprint="file:1:2")
    loaded = cache.get("tile-a", "checkpoint-hash", expected_dimension=3,
                       source_fingerprint="file:1:2")
    np.testing.assert_array_equal(loaded, vector)
    assert cache.get("tile-a", "other-checkpoint") is None
    assert cache.get("tile-a", "checkpoint-hash", source_fingerprint="changed") is None
    metadata = json.loads(next(cache.root.glob("*.json")).read_text())
    assert metadata["normalized"] is True
    assert metadata["embedding_dtype"] == "float32"


def test_normalized_vectors_integrate_with_phase3_faiss(tmp_path: Path):
    index = IncrementalIndex(tmp_path / "embeddings.index", dimension=3)
    vectors = normalize_embeddings(np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32))
    index.add_embeddings(vectors, ["tile-real-a", "tile-real-b"])
    result = index.search(vectors[0], k=1)
    assert result[0]["tile_id"] == "tile-real-a"
    loaded = IncrementalIndex(tmp_path / "embeddings.index", dimension=3)
    assert loaded.size() == 2
    assert loaded.search(vectors[1], k=1)[0]["tile_id"] == "tile-real-b"


@pytest.mark.integration
def test_official_remoteclip_encodes_real_tile_and_text(tmp_path: Path):
    checkpoint = Path("models/remoteclip/RemoteCLIP-ViT-B-32.pt")
    tile_dir = Path("data/processed/phase2_validation/tiles/s2_demo")
    if not checkpoint.is_file() or not tile_dir.is_dir():
        pytest.skip("local RemoteCLIP checkpoint and Phase 2 tile data are required")
    from pipeline.embeddings.image_encoder import ImageEncoder
    from pipeline.embeddings.remoteclip import RemoteCLIPAdapter

    tile = next(tile_dir.glob("*.tif"))
    adapter = RemoteCLIPAdapter(checkpoint, device="cpu")
    image_encoder = ImageEncoder(adapter)
    image = image_encoder.encode_image(tile)
    image_repeat = image_encoder.encode_image(tile)
    text = adapter.encode_text("urban area")
    assert adapter.embedding_dim == image.shape[0] == text.shape[0]
    assert image.dtype == text.dtype == np.float32
    assert np.linalg.norm(image) == pytest.approx(1.0, abs=1e-5)
    assert np.linalg.norm(text) == pytest.approx(1.0, abs=1e-5)
    np.testing.assert_allclose(image, image_repeat, atol=1e-6, rtol=1e-6)

    from pipeline.indexing.tile_catalog import TileCatalog
    catalog = TileCatalog("data/catalog/tiles.json")
    record = next(item for item in catalog.list_tiles() if Path(item.tile_path).resolve() == tile.resolve())
    index = IncrementalIndex(tmp_path / "real-tile.index", dimension=adapter.embedding_dim)
    index.add_embeddings(image, [record.tile_id])
    reloaded = IncrementalIndex(tmp_path / "real-tile.index", dimension=adapter.embedding_dim)
    assert reloaded.search(image, k=1)[0]["tile_id"] == record.tile_id
