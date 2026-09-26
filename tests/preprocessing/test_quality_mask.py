import numpy as np
import pytest

from pipeline.preprocessing.quality_mask import (
    QualityMaskError,
    apply_mask,
    calculate_mask_statistics,
    landsat_qa_pixel_mask,
    sentinel2_scl_mask,
)


def test_sentinel2_scl_masks_clouds_shadows_cirrus_and_snow():
    scl = np.array([
        [4, 5, 6, 7],
        [3, 8, 9, 10],
        [11, 0, 1, 4],
    ], dtype=np.uint8)

    mask = sentinel2_scl_mask(scl)

    expected = np.array([
        [True, True, True, True],
        [False, False, False, False],
        [False, False, False, True],
    ])

    np.testing.assert_array_equal(mask, expected)


def test_landsat_qa_pixel_masks_cloud_related_bits():
    qa = np.array([
        0,
        1 << 1,  # dilated cloud
        1 << 2,  # cirrus
        1 << 3,  # cloud
        1 << 4,  # cloud shadow
        1 << 5,  # snow
        (1 << 3) | (1 << 4),
    ], dtype=np.uint16)

    mask = landsat_qa_pixel_mask(qa)

    expected = np.array([
        True,
        False,
        False,
        False,
        False,
        False,
        False,
    ])

    np.testing.assert_array_equal(mask, expected)


def test_apply_mask():
    data = np.array([
        [1, 2],
        [3, 4],
    ], dtype=np.uint16)

    mask = np.array([
        [True, False],
        [False, True],
    ])

    result = apply_mask(data, mask)

    assert result.dtype == np.float32
    assert result[0, 0] == 1
    assert np.isnan(result[0, 1])
    assert np.isnan(result[1, 0])
    assert result[1, 1] == 4


def test_mask_statistics():
    mask = np.array([
        [True, True],
        [False, True],
    ])

    stats = calculate_mask_statistics(mask)

    assert stats.total_pixels == 4
    assert stats.valid_pixels == 3
    assert stats.masked_pixels == 1
    assert stats.valid_fraction == 0.75


def test_apply_mask_rejects_wrong_shape():
    data = np.ones((2, 4, 4), dtype=np.uint16)
    mask = np.ones((3, 3), dtype=bool)

    with pytest.raises(QualityMaskError):
        apply_mask(data, mask)
