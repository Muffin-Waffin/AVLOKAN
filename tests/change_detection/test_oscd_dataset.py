import numpy as np
import pytest
import rasterio
import torch

from pipeline.change_detection.oscd_dataset import (
    BIT_RGB_BANDS,
    DEFAULT_OSCD_ROOT,
    OSCDDataset,
    build_oscd_inventory,
    load_split_manifest,
)


pytestmark = pytest.mark.skipif(
    not DEFAULT_OSCD_ROOT.is_dir(), reason="staged OSCD archive is not present"
)


def test_inventory_covers_real_registered_oscd_pairs_and_named_bands():
    inventory = build_oscd_inventory()
    assert len(inventory["locations"]) == 24
    assert inventory["counts"] == {"train": 11, "validation": 3, "test": 10}
    locations = {row["location_id"]: row for row in inventory["locations"]}
    assert locations["abudhabi"]["selected_bit_bands"] == list(BIT_RGB_BANDS)
    assert locations["abudhabi"]["channel_names"] == [
        "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08",
        "B8A", "B09", "B10", "B11", "B12",
    ]
    assert locations["abudhabi"]["crs"] is None
    assert locations["abudhabi"]["nominal_rectified_resolution_m"] == 10
    assert set(locations["abudhabi"]["mask_unique_values"]) <= {1, 2}
    assert locations["abudhabi"]["mask_class_mapping"] == {"1": 0, "2": 1}
    assert locations["abudhabi"]["native_band_profiles_t1"]["B04"]["crs"]


@pytest.mark.parametrize(("split", "location"), [("train", "bercy"), ("validation", "abudhabi")])
def test_real_oscd_sample_loads_named_rgb_and_aligned_mask(split, location):
    manifest = load_split_manifest()
    dataset = OSCDDataset(split=split)
    sample = dataset[dataset.location_ids.index(location)]
    assert sample.location_id == location
    assert sample.split == split
    assert sample.official_split == "train"
    assert tuple(sample.images.shape[:2]) == (2, 3)
    assert sample.images.dtype == torch.float32
    assert sample.mask.shape == sample.images.shape[-2:]
    assert set(sample.mask.unique().tolist()) <= {0, 1}
    assert sample.metadata["bands"] == ["B04", "B03", "B02"]
    assert sample.metadata["original_band_count"] == 13
    assert sample.metadata["crs"] is None
    assert sample.metadata["dates"] and len(sample.metadata["dates"]) == 2
    assert location in manifest[split]

    image_root = DEFAULT_OSCD_ROOT / "Onera Satellite Change Detection dataset - Images" / location
    for channel, band in enumerate(BIT_RGB_BANDS):
        with rasterio.open(image_root / "imgs_1_rect" / f"{band}.tif") as src:
            np.testing.assert_array_equal(sample.images[0, channel].numpy(), src.read(1))
        with rasterio.open(image_root / "imgs_2_rect" / f"{band}.tif") as src:
            np.testing.assert_array_equal(sample.images[1, channel].numpy(), src.read(1))

    t1, t2 = sample.bit_inputs(quantification_value=10000)
    assert tuple(t1.shape) == tuple(t2.shape) == (1, 3, *sample.images.shape[-2:])
    assert t1.dtype == t2.dtype
    assert t1.is_floating_point() and t2.is_floating_point()
    assert t1.min() >= -1 and t1.max() <= 1


def test_official_test_locations_are_excluded_from_development_splits():
    manifest = load_split_manifest()
    official_test = set(manifest["test"])
    assert not (official_test & set(manifest["train"]))
    assert not (official_test & set(manifest["validation"]))
    assert set(OSCDDataset(split="test").location_ids) == official_test
