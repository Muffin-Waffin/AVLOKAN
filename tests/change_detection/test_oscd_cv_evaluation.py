import numpy as np

from scripts.evaluate_oscd_cv5_baseline import (
    _best_threshold,
    discrimination_auc,
    probability_distribution,
)


def test_discrimination_auc_perfect_separation_and_tied_scores():
    roc_auc, pr_auc = discrimination_auc(
        np.array([0.1, 0.2, 0.8, 0.9]),
        np.array([0, 0, 1, 1]),
    )
    assert roc_auc == 1.0
    assert pr_auc == 1.0

    roc_auc, pr_auc = discrimination_auc(
        np.array([0.5, 0.5, 0.5, 0.5]),
        np.array([0, 0, 1, 1]),
    )
    assert roc_auc == 0.5
    assert pr_auc == 0.5


def test_probability_distribution_reports_requested_separation_fields():
    result = probability_distribution(np.array([0.1, 0.3, 0.5, 0.9]))
    assert result["mean"] == 0.45
    assert result["median"] == 0.4
    assert np.isclose(result["p90"], 0.78)
    assert np.isclose(result["p95"], 0.84)
    assert result["fraction_ge_0_25"] == 0.75
    assert result["fraction_ge_0_50"] == 0.5
    assert result["fraction_ge_0_75"] == 0.25


def test_best_threshold_ties_resolve_to_higher_threshold():
    rows = [
        {"threshold": 0.25, "f1": 0.5},
        {"threshold": 0.50, "f1": 0.5},
        {"threshold": 0.75, "f1": 0.4},
    ]
    assert _best_threshold(rows)["threshold"] == 0.50
