from __future__ import annotations

import numpy as np
import pytest

from pipeline.change_detection.postprocessing import (
    CandidateFilteringConfig,
    analyze_candidates,
    postprocess_probability,
    PostprocessingConfig,
)


def test_candidate_extraction_statistics_score_and_stable_ranking():
    probability = np.zeros((8, 9), dtype=np.float32)
    mask = np.zeros_like(probability, dtype=np.uint8)
    mask[1:3, 1:3] = 1
    probability[1:3, 1:3] = 0.97
    mask[4:6, 5:7] = 1
    probability[4:6, 5:7] = 0.99
    output, candidates, accounting, _ = analyze_candidates(
        probability, mask, threshold=0.96,
    )
    assert np.array_equal(output, mask)
    assert candidates[0]["rank"] == 1
    assert candidates[0]["area_pixels"] == 4
    assert candidates[0]["mean_probability"] == pytest.approx(0.99)
    assert candidates[0]["candidate_score"] == pytest.approx(0.99)
    assert candidates[0]["bbox_pixels"] == {
        "xmin": 5, "ymin": 4, "xmax_exclusive": 7, "ymax_exclusive": 6,
    }
    assert candidates[1]["rank"] == 2
    assert accounting == {
        "raw_component_count": 2, "components_removed": 0,
        "components_retained": 2, "pixels_removed": 0, "pixels_retained": 8,
    }


def test_edge_filter_removes_only_touching_component_and_accounts_pixels():
    probability = np.ones((6, 7), dtype=np.float32) * 0.98
    mask = np.zeros_like(probability, dtype=np.uint8)
    mask[0:2, 1:3] = 1
    mask[3:5, 4:6] = 1
    output, candidates, stats, _ = analyze_candidates(
        probability, mask, threshold=0.96,
        config=CandidateFilteringConfig(reject_edge_components=True),
    )
    assert output.sum() == 4
    assert stats["raw_component_count"] == 2
    assert stats["components_removed"] == 1
    assert stats["pixels_removed"] == 4
    assert stats["components_retained"] == 1
    retained = next(item for item in candidates if item["retained"])
    rejected = next(item for item in candidates if not item["retained"])
    assert rejected["touches_image_edge"]
    assert rejected["rejection_reasons"] == ["image_edge"]
    assert retained["rank"] == 1


def test_valid_fraction_filter_is_explicit_and_threshold_validated():
    probability = np.full((4, 4), 0.99, dtype=np.float32)
    mask = np.ones((4, 4), dtype=np.uint8)
    valid = np.zeros((4, 4), dtype=bool)
    valid[:2] = True
    output, candidates, stats, _ = analyze_candidates(
        probability, mask, threshold=0.96, valid_mask=valid,
        config=CandidateFilteringConfig(min_valid_fraction=0.75),
    )
    assert output.sum() == 0
    assert candidates[0]["valid_fraction"] == pytest.approx(0.5)
    assert candidates[0]["invalid_fraction"] == pytest.approx(0.5)
    assert candidates[0]["rejection_reasons"] == ["valid_fraction"]
    assert stats["pixels_removed"] == 16
    with pytest.raises(ValueError, match="min_valid_fraction"):
        CandidateFilteringConfig(min_valid_fraction=1.5)
    with pytest.raises(ValueError, match="edge_margin_pixels"):
        CandidateFilteringConfig(edge_margin_pixels=-1)


def test_candidate_geometry_connectivity_and_deterministic_ties():
    probability = np.full((4, 4), 0.98, dtype=np.float32)
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[0, 0] = mask[1, 1] = 1
    mask[3, 3] = 1
    _, candidates, _, _ = analyze_candidates(probability, mask, threshold=0.96)
    # Diagonal pixels are 8-connected; equal scores preserve row-major component IDs.
    assert len(candidates) == 2
    assert [item["component_id"] for item in candidates] == [1, 2]
    assert candidates[0]["fraction_above_threshold"] == 1.0
    assert candidates[0]["edge_distance_pixels"] == 0


def test_phase6_area_filter_remains_unchanged():
    probability = np.zeros((6, 6), dtype=np.float32)
    probability[1, 1:3] = 0.99
    probability[4, 4] = 0.99
    actual = postprocess_probability(probability, PostprocessingConfig(0.96, 2, "none"))
    expected = np.zeros((6, 6), dtype=np.uint8)
    expected[1, 1:3] = 1
    np.testing.assert_array_equal(actual, expected)
