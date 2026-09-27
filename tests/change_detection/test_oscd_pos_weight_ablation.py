import numpy as np
import pytest
import torch

from pipeline.change_detection import oscd_training
from scripts.run_oscd_pos_weight_ablation import (
    probability_group_stats,
    require_new_or_empty,
    screening_stop_reason,
    validate_probability_and_mask,
)


def test_requested_positive_weight_is_passed_to_bce_and_default_is_unchanged(monkeypatch):
    original = oscd_training.F.binary_cross_entropy_with_logits
    observed = []

    def capture(*args, **kwargs):
        observed.append(float(kwargs["pos_weight"].item()))
        return original(*args, **kwargs)

    monkeypatch.setattr(oscd_training.F, "binary_cross_entropy_with_logits", capture)
    logits = torch.zeros((1, 2, 2, 2), requires_grad=True)
    target = torch.tensor([[[1, 0], [0, 1]]])
    valid = torch.ones_like(target, dtype=torch.bool)
    oscd_training.masked_weighted_bce_dice(logits, target, valid, positive_weight=20)
    oscd_training.masked_weighted_bce_dice(logits, target, valid)
    assert observed[0] == 20.0
    assert observed[1] == pytest.approx(46.46)


def test_output_preflight_refuses_to_overwrite_existing_files(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    (output / "existing.pt").write_bytes(b"checkpoint")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        require_new_or_empty((output,))


def test_probability_mask_validation_checks_finite_binary_values_and_grid():
    probability = np.array([[0.1, 0.9], [0.2, 0.8]], dtype=np.float32)
    mask = probability >= 0.5
    validate_probability_and_mask(probability, mask, (2, 2))
    with pytest.raises(ValueError, match="dimensions"):
        validate_probability_and_mask(probability, mask, (1, 4))
    with pytest.raises(ValueError, match="finite"):
        validate_probability_and_mask(np.array([[np.nan]]), np.array([[0]]), (1, 1))
    with pytest.raises(ValueError, match="binary"):
        validate_probability_and_mask(np.array([[0.3]]), np.array([[2]]), (1, 1))


def test_probability_statistics_are_deterministic_and_grouped_by_truth():
    probability = np.array([[0.1, 0.7], [0.8, 0.95]], dtype=np.float32)
    target = np.array([[0, 1], [0, 1]], dtype=np.uint8)
    first = probability_group_stats(probability, target)
    second = probability_group_stats(probability.copy(), target.copy())
    assert first == second
    assert first["changed"]["mean"] == pytest.approx(0.825)
    assert first["unchanged"]["fraction_ge_0_90"] == 0.0


def test_screening_stop_rule_waits_until_epoch_three_then_stops_poor_precision_f1():
    metrics = {"precision": 0.05, "recall": 0.50, "f1": 0.10}
    assert screening_stop_reason(2, metrics) is None
    assert screening_stop_reason(3, metrics) is not None


def test_screening_stop_rule_allows_a_promising_epoch():
    metrics = {"precision": 0.30, "recall": 0.45, "f1": 0.35}
    assert screening_stop_reason(3, metrics) is None
