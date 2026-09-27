import numpy as np

from scripts.calibrate_change_detection import (
    confusion_metrics,
    postprocess_probability,
    select_global_configuration,
)


def test_thresholding_is_binary_deterministic_preserves_shape_and_input():
    probability = np.array([[0.2, 0.5, 0.9], [0.1, 0.6, 0.4]], dtype=np.float32)
    original = probability.copy()
    first = postprocess_probability(probability, threshold=0.5)
    second = postprocess_probability(probability, threshold=0.5)
    np.testing.assert_array_equal(first, [[0, 1, 1], [0, 1, 0]])
    np.testing.assert_array_equal(first, second)
    assert first.shape == probability.shape
    assert set(np.unique(first)) <= {0, 1}
    np.testing.assert_array_equal(probability, original)


def test_component_filtering_uses_8_connectivity_and_minimum_area():
    probability = np.zeros((5, 5), dtype=np.float32)
    probability[0, 0] = 0.9
    probability[1, 1] = 0.9  # diagonal neighbor: same 8-connected component
    probability[4, 4] = 0.9  # isolated one-pixel component
    original = probability.copy()

    retained = postprocess_probability(
        probability, threshold=0.5, min_component_area=2,
    )
    assert retained.sum() == 2
    assert retained[0, 0] == retained[1, 1] == 1
    assert retained[4, 4] == 0
    np.testing.assert_array_equal(probability, original)


def test_3x3_closing_fills_small_hole_without_changing_input_or_dimensions():
    binary = np.zeros((7, 7), dtype=np.float32)
    binary[2:5, 2:5] = 0.9
    binary[3, 3] = 0.0
    original = binary.copy()
    closed = postprocess_probability(binary, threshold=0.5, morphology="closing_3x3")
    assert closed[3, 3] == 1
    assert closed.shape == binary.shape
    assert set(np.unique(closed)) <= {0, 1}
    np.testing.assert_array_equal(binary, original)


def test_metrics_are_pixel_count_confusion_metrics():
    prediction = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    target = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    result = confusion_metrics(prediction, target)
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 1, 1, 1)
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["iou"] == 1 / 3
    assert result["predicted_changed_percent"] == 50.0
    assert result["ground_truth_changed_percent"] == 50.0


def test_global_selection_uses_pooled_f1_and_deterministic_tie_break():
    candidates = [
        {"threshold": 0.70, "min_component_area": 0, "morphology": "closing_3x3",
         "pooled": {"f1": 0.8}},
        {"threshold": 0.80, "min_component_area": 16, "morphology": "none",
         "pooled": {"f1": 0.8}},
        {"threshold": 0.85, "min_component_area": 0, "morphology": "none",
         "pooled": {"f1": 0.8}},
        {"threshold": 0.90, "min_component_area": 0, "morphology": "none",
         "pooled": {"f1": 0.7}},
    ]
    selected = select_global_configuration(candidates)
    assert selected["threshold"] == 0.85
    assert selected["min_component_area"] == 0
    assert selected["morphology"] == "none"
