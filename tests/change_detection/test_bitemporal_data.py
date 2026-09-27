import csv

import numpy as np
import pytest
import torch

from pipeline.change_detection.bitemporal_data import (
    BitemporalSample,
    S2MTCPDataset,
    inventory_s2mtcp_metadata,
    normalize_rgb8_for_bit,
    supervised_rgb_sample,
    unlabeled_temporal_sample,
)


def test_rgb8_normalization_is_explicit_rgb_to_minus1_plus1():
    rgb = np.array([[[255, 127, 0], [0, 127, 255]]], dtype=np.uint8)
    result = normalize_rgb8_for_bit(rgb)
    assert result.shape == (3, 1, 2)
    assert result.dtype == torch.float32
    torch.testing.assert_close(result[:, 0, 0], torch.tensor([1.0, 127 / 127.5 - 1, -1.0]))
    torch.testing.assert_close(result[:, 0, 1], torch.tensor([-1.0, 127 / 127.5 - 1, 1.0]))


def test_rgb8_normalization_rejects_implicit_scaling():
    with pytest.raises(ValueError, match="8-bit"):
        normalize_rgb8_for_bit(np.zeros((3, 4, 3), dtype=np.uint16))


def test_supervised_rgb_adapter_preserves_alignment_and_binary_mask():
    t1 = np.zeros((5, 7, 3), dtype=np.uint8)
    t1[..., 0] = 240
    t2 = t1.copy()
    mask = np.zeros((5, 7), dtype=np.uint8)
    mask[2, 3] = 1
    sample = supervised_rgb_sample(
        sample_id="HRSCD:scene-1", location="scene-1", split="train",
        t1_rgb=t1, t2_rgb=t2, change_mask=mask, resolution_m=0.5,
    )
    assert sample.dataset == "HRSCD"
    assert sample.t1.shape == (3, 5, 7)
    assert sample.height == 5 and sample.width == 7
    assert sample.change_mask[2, 3] == 1
    assert sample.metadata["model_channel_mapping"] == "R->red, G->green, B->blue"
    normalized = normalize_rgb8_for_bit(t1)
    torch.testing.assert_close(normalized[0], torch.full((5, 7), 240 / 127.5 - 1))


def test_unlabeled_pair_has_no_change_mask_and_keeps_source_pixels():
    t1 = np.arange(3 * 4 * 6, dtype=np.uint16).reshape(3, 4, 6)
    t2 = t1 + 2
    sample = unlabeled_temporal_sample(
        sample_id="S2MTCP:4", dataset="S2MTCP", location="city", t1=t1, t2=t2,
        sensor="Sentinel-2 L1C", split="unassigned", resolution_m=10,
    )
    assert sample.change_mask is None
    assert sample.metadata["pixel_registration"] == "unverified"
    np.testing.assert_array_equal(sample.t1, t1)
    np.testing.assert_array_equal(sample.t2, t2)


@pytest.mark.parametrize("mask", [np.zeros((2, 3), dtype=np.uint8), np.zeros((4, 2), dtype=np.uint8)])
def test_sample_rejects_mask_not_aligned_to_pair(mask):
    pair = np.zeros((3, 3, 2), dtype=np.uint8)
    with pytest.raises(ValueError, match="mask dimensions"):
        BitemporalSample("x", "x", "loc", pair, pair, mask, 3, 2, None, "sensor", "train", {})


def test_s2mtcp_inventory_keeps_a_b_unlabeled_and_inspects_real_array_headers(tmp_path):
    metadata = tmp_path / "metadata.csv"
    fields = ["im_idx", "pair_idx", "filename", "system_idx", "city", "city_ascii",
              "country", "lng", "lat", "date", "time"]
    with metadata.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"im_idx": "12", "pair_idx": key, "filename": f"12_{key}.npy",
             "system_idx": system, "city": "City", "city_ascii": "City", "country": "X",
             "lng": "1", "lat": "2", "date": date, "time": "010101"}
            for key, system, date in (("a", "S1", "20200101"), ("b", "S2", "20210101"))
        ])
    for key in ("a", "b"):
        np.save(tmp_path / f"12_{key}.npy", np.zeros((8, 9, 13), dtype=np.uint16))
    result = inventory_s2mtcp_metadata(metadata)
    record = result["records"][0]
    assert result["sample_count"] == 1
    assert record["change_mask"] is None
    assert record["distinct_acquisitions_by_metadata"] is True
    assert record["temporal_order"] == "a_before_b"
    assert [item["raw_shape"] for item in record["pair_images_a_b"]] == [[8, 9, 13], [8, 9, 13]]
    assert "unverified" in result["band_axis_order"]
    assert result["observed_channel_counts"] == {"13": 2}


def test_s2mtcp_inventory_rejects_missing_pair_member(tmp_path):
    metadata = tmp_path / "metadata.csv"
    metadata.write_text(
        "im_idx,pair_idx,filename,system_idx,city,city_ascii,country,lng,lat,date,time\n"
        "1,a,1_a.npy,s,City,City,X,0,0,20200101,0\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="exactly one a and one b"):
        inventory_s2mtcp_metadata(metadata)


def _write_s2_pair(root, *, pair_id="7", a_date="20200101", b_date="20210101",
                   a_time="010101", b_time="010101", mismatch=False):
    metadata = root / "metadata.csv"
    fields = ["im_idx", "pair_idx", "filename", "system_idx", "city", "city_ascii",
              "country", "lng", "lat", "date", "time"]
    with metadata.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"im_idx": pair_id, "pair_idx": key, "filename": f"{pair_id}_{key}.npy",
             "system_idx": f"S{key}", "city": "Test City", "city_ascii": "test-city",
             "country": "Test", "lng": "1", "lat": "2",
             "date": a_date if key == "a" else b_date,
             "time": a_time if key == "a" else b_time}
            for key in ("a", "b")
        ])
    shape_b = (5, 6, 14) if mismatch else (4, 6, 14)
    a = np.zeros((4, 6, 14), dtype=np.float64)
    b = np.ones(shape_b, dtype=np.float64)
    a[..., 13] = 1024  # Preserve undocumented channel values; do not reject them.
    np.save(root / f"{pair_id}_a.npy", a)
    np.save(root / f"{pair_id}_b.npy", b)
    return metadata


@pytest.mark.parametrize(
    ("a_date", "b_date", "expected_order"),
    [("20200101", "20210101", "a_before_b"),
     ("20210101", "20200101", "b_before_a"),
     ("20200101", "20200101", "same_timestamp_order_ambiguous")],
)
def test_s2mtcp_loader_preserves_14_channels_and_never_fabricates_mask(
    tmp_path, a_date, b_date, expected_order
):
    metadata = _write_s2_pair(tmp_path, a_date=a_date, b_date=b_date)
    dataset = S2MTCPDataset(metadata, tmp_path)
    sample = dataset[0]

    assert sample.sample_id == "S2MTCP:7"
    assert sample.location == "test-city"
    assert sample.change_mask is None
    assert sample.t1.shape == sample.t2.shape == (14, 4, 6)
    assert sample.t1.dtype == sample.t2.dtype == np.float32
    assert sample.metadata["chronological_order"] == expected_order
    assert sample.metadata["spectral_band_names_and_order"].startswith("not specified")
    assert np.all(sample.t1[13] == 1024) or np.all(sample.t2[13] == 1024)


def test_s2mtcp_loader_rejects_mismatched_pair_grid(tmp_path):
    metadata = _write_s2_pair(tmp_path, mismatch=True)
    dataset = S2MTCPDataset(metadata, tmp_path)
    with pytest.raises(ValueError, match="temporal dimensions differ"):
        dataset[0]


def test_staged_s2mtcp_representative_pairs_load_without_supervised_labels():
    from pathlib import Path

    root = Path("data/oscd/s2mtcp")
    metadata = root / "raw/S2MTCP_metadata.csv"
    array_root = root / "extracted/data_S21C"
    if not metadata.is_file() or not array_root.is_dir():
        pytest.skip("Official S2MTCP archive is not staged in this environment")
    dataset = S2MTCPDataset(metadata, array_root)
    for pair_id in ("0", "77"):
        index = next(i for i, (key, _) in enumerate(dataset.records) if key == pair_id)
        sample = dataset[index]
        assert sample.sample_id == f"S2MTCP:{pair_id}"
        assert sample.t1.shape == sample.t2.shape
        assert sample.t1.shape[0] == 14
        assert sample.change_mask is None
        assert sample.metadata["pixel_registration"] == "unverified"
