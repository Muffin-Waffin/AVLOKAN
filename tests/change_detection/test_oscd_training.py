from collections import Counter
from pathlib import Path

import pytest
import numpy as np
import torch

from pipeline.change_detection.oscd_training import (
    OSCDPatchDataset,
    apply_geometric_augmentation,
    dry_run,
    generate_patch_coordinates,
    LossAccumulator,
    load_training_config,
    make_location_folds,
    masked_weighted_bce_dice,
    training_device,
)
from pipeline.change_detection.oscd_dataset import (
    DEFAULT_OSCD_ROOT, OSCDDataError, load_split_manifest, normalize_bit_dn,
)


pytestmark = pytest.mark.skipif(
    not DEFAULT_OSCD_ROOT.is_dir(), reason="staged OSCD archive is not present"
)
CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs/oscd_bit_training.yaml"


def test_auto_selects_cuda_when_available(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert training_device("auto") == torch.device("cuda")


def test_auto_selects_cpu_when_cuda_unavailable(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert training_device("auto") == torch.device("cpu")


def test_explicit_cpu_is_not_changed_by_cuda_availability(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert training_device("cpu") == torch.device("cpu")


def test_explicit_cuda_fails_clearly_when_unavailable(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="explicitly requested.*no CPU fallback"):
        training_device("cuda")


def _training_dataset(*, augmentation=True):
    config = load_training_config(CONFIG_PATH)
    manifest = load_split_manifest(config["data"]["root"], config["data"]["splits"])
    fold = make_location_folds(
        manifest["official_train"], manifest["test"],
        n_splits=config["cross_validation"]["n_splits"],
        seed=config["cross_validation"]["seed"],
    )[config["cross_validation"]["fold"]]
    return OSCDPatchDataset(
        split="train",
        locations=fold["train"],
        patch_size=config["patch"]["patch_size"],
        patch_stride=config["patch"]["patch_stride"],
        quantification_value=config["input"]["quantification_value"],
        augmentation=augmentation,
        seed=config["training"]["seed"],
        root=config["data"]["root"],
        splits_path=config["data"]["splits"],
    )


def test_patch_coordinates_are_deterministic_row_major_and_cover_scene():
    coords = generate_patch_coordinates(257, 513, 256)
    assert coords == [(0, 0), (0, 256), (0, 512), (256, 0), (256, 256), (256, 512)]
    covered = sum(min(256, 257-r) * min(256, 513-c) for r, c in coords)
    assert covered == 257 * 513


def test_overlapping_patch_grid_is_deterministic_covers_scene_and_overlaps():
    coords = generate_patch_coordinates(257, 513, 256, stride=128)
    assert coords == generate_patch_coordinates(257, 513, 256, stride=128)
    assert len(coords) == 15
    coverage = torch.zeros((257, 513), dtype=torch.int16)
    for row, col in coords:
        coverage[row:min(row + 256, 257), col:min(col + 256, 513)] += 1
    assert torch.all(coverage >= 1)
    assert torch.any(coverage > 1)


def test_five_location_folds_partition_only_official_training_roster():
    manifest = load_split_manifest()
    folds = make_location_folds(manifest["official_train"], manifest["test"], n_splits=5, seed=42)
    assert len(folds) == 5
    assert set().union(*(set(fold["train"]) | set(fold["validation"]) for fold in folds)) == set(manifest["official_train"])
    validation_occurrences = [location for fold in folds for location in fold["validation"]]
    assert len(validation_occurrences) == 14
    assert set(validation_occurrences) == set(manifest["official_train"])
    for fold in folds:
        assert not set(fold["train"]) & set(fold["validation"])
        assert set(fold["train"]) | set(fold["validation"]) == set(manifest["official_train"])
        assert not (set(fold["train"]) | set(fold["validation"])) & set(manifest["test"])
    assert folds == make_location_folds(manifest["official_train"], manifest["test"], n_splits=5, seed=42)


def test_official_test_location_is_rejected_for_training_dataset():
    with pytest.raises(OSCDDataError, match="outside its allowed official split"):
        OSCDPatchDataset(split="train", locations=["brasilia"])


def test_real_oscd_patch_counts_at_nonoverlap_and_stride_128():
    manifest = load_split_manifest()
    common = {"split": "train", "locations": manifest["official_train"],
              "patch_size": 256, "augmentation": False}
    nonoverlap = OSCDPatchDataset(patch_stride=256, **common)
    overlap = OSCDPatchDataset(patch_stride=128, **common)
    assert len(nonoverlap) == 150
    assert len(overlap) == 496
    assert Counter(row[0] for row in overlap.samples) == {
        "abudhabi": 49, "aguasclaras": 20, "beihai": 56, "beirut": 90,
        "bercy": 12, "bordeaux": 20, "cupertino": 56, "hongkong": 30,
        "mumbai": 35, "nantes": 25, "paris": 16, "pisa": 42,
        "rennes": 15, "saclay_e": 30,
    }


@pytest.mark.parametrize("transform", [
    "identity", "horizontal_flip", "vertical_flip", "rotate_90", "rotate_180", "rotate_270",
])
def test_geometric_augmentation_keeps_pair_mask_and_validity_aligned(transform):
    t1 = torch.arange(9).reshape(1, 3, 3).float()
    t2 = t1 + 100
    target = (t1[0].to(torch.int64) % 2)
    valid = torch.ones((3, 3), dtype=torch.bool)
    outputs = apply_geometric_augmentation(t1, t2, target, valid, transform)
    op = {
        "identity": lambda x: x,
        "horizontal_flip": lambda x: torch.flip(x, (-1,)),
        "vertical_flip": lambda x: torch.flip(x, (-2,)),
        "rotate_90": lambda x: torch.rot90(x, 1, (-2, -1)),
        "rotate_180": lambda x: torch.rot90(x, 2, (-2, -1)),
        "rotate_270": lambda x: torch.rot90(x, 3, (-2, -1)),
    }[transform]
    for actual, source in zip(outputs, (t1, t2, target, valid)):
        torch.testing.assert_close(actual, op(source))
    assert set(outputs[2].unique().tolist()) <= {0, 1}


def test_validation_dataset_rejects_augmentation_and_train_choice_is_reproducible():
    with pytest.raises(ValueError, match="only for training"):
        OSCDPatchDataset(split="validation", locations=["abudhabi"], augmentation=True)
    first, second = _training_dataset(), _training_dataset()
    first.set_epoch(3)
    second.set_epoch(3)
    assert first[0]["metadata"]["augmentation"] == second[0]["metadata"]["augmentation"]


def test_real_patch_reads_named_rgb_normalizes_once_and_masks_padding():
    dataset = _training_dataset(augmentation=False)
    location_index = [i for i, item in enumerate(dataset.samples) if item[0] == "rennes"][-1]
    location, row, col, valid_h, valid_w = dataset.samples[location_index]
    sample = dataset[location_index]
    assert location == "rennes" and sample["metadata"]["split"] == "train"
    assert sample["metadata"]["dates"] and sample["metadata"]["bands"] == ["B04", "B03", "B02"]
    assert sample["t1"].shape == sample["t2"].shape == (3, 256, 256)
    assert sample["target"].shape == sample["valid"].shape == (256, 256)
    assert int(sample["valid"].sum()) == valid_h * valid_w
    assert not sample["valid"][valid_h:, :].any()
    assert not sample["valid"][:, valid_w:].any()
    assert set(sample["target"].unique().tolist()) <= {0, 1}

    raw, _, _ = dataset.source.read_window(location, row=row, col=col,
                                            height=valid_h, width=valid_w)
    padded = np.pad(raw.numpy(), ((0, 0), (0, 0), (0, 256-valid_h), (0, 256-valid_w)), mode="reflect")
    expected = normalize_bit_dn(torch.from_numpy(padded.copy()), quantification_value=10000)
    torch.testing.assert_close(sample["t1"], expected[0])
    torch.testing.assert_close(sample["t2"], expected[1])


def test_masked_weighted_bce_excludes_invalid_pixels_and_matches_weight():
    logits = torch.zeros((1, 2, 2, 3), requires_grad=True)
    target = torch.tensor([[[1, 0, 0], [0, 1, 1]]])
    valid = torch.tensor([[[1, 1, 0], [1, 0, 0]]], dtype=torch.bool)
    loss = masked_weighted_bce_dice(logits, target, valid)
    expected_bce = torch.log(torch.tensor(2.0)) * (46.46 + 1 + 1) / 3
    torch.testing.assert_close(loss["bce"], expected_bce)

    altered = logits.detach().clone()
    altered[:, 1, :, 2] = 1000
    altered[:, 1, 1, 1:] = 1000
    other = masked_weighted_bce_dice(altered, target, valid)
    torch.testing.assert_close(loss["bce"], other["bce"])
    torch.testing.assert_close(loss["dice"], other["dice"])
    assert loss["valid_pixels"] == 3


def test_zero_positive_patch_has_finite_dice_and_gradients():
    logits = torch.randn((1, 2, 16, 16), requires_grad=True)
    target = torch.zeros((1, 16, 16))
    valid = torch.ones_like(target, dtype=torch.bool)
    loss = masked_weighted_bce_dice(logits, target, valid)
    assert torch.isfinite(loss["bce"]) and torch.isfinite(loss["dice"]) and torch.isfinite(loss["total"])
    loss["total"].backward()
    assert logits.grad is not None and torch.isfinite(logits.grad).all()


def test_validation_loss_accumulator_aggregates_pixels_not_patch_averages():
    accumulator = LossAccumulator()
    accumulator.bce_sum = 8.0
    accumulator.valid_pixels = 4
    accumulator.intersection = 1.0
    accumulator.probability_sum = 2.0
    accumulator.target_sum = 2.0
    report = accumulator.report(bce_weight=0.5, dice_weight=0.5, smooth=1.0)
    assert report["bce"] == 2.0
    assert report["dice"] == 1.0 - 3.0 / 5.0
    assert report["total"] == pytest.approx(0.5 * 2.0 + 0.5 * 0.4)
    assert report["valid_pixels"] == 4


def test_auto_device_dry_run_performs_exactly_one_finite_optimizer_step():
    config = load_training_config(CONFIG_PATH)
    result = dry_run(config)
    assert result["input_shape"] == [3, 256, 256]
    assert result["raw_logits_shape"] == [1, 2, 256, 256]
    assert result["aligned_logits_shape"] == [1, 2, 256, 256]
    assert result["finite_gradients"] is True
    assert result["gradient_tensors"] > 0
    assert result["optimizer_parameter_updated"] is True
    assert result["patch"]["augmentation"] in {
        "identity", "horizontal_flip", "vertical_flip", "rotate_90", "rotate_180", "rotate_270",
    }
    assert all(torch.isfinite(torch.tensor(result[key]))
               for key in ("bce", "dice", "total"))
