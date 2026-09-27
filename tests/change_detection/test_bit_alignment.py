import pytest
import torch

from pipeline.change_detection.bit import BITDetector
from pipeline.change_detection.bit_alignment import align_bit_logits, align_categorical_mask
from pipeline.change_detection.oscd_dataset import DEFAULT_OSCD_ROOT, OSCDDataset


pytestmark = pytest.mark.skipif(
    not DEFAULT_OSCD_ROOT.is_dir(), reason="staged OSCD archive is not present"
)


@pytest.fixture(scope="module")
def detector():
    torch.set_num_threads(4)
    return BITDetector(device="cpu")


@pytest.mark.parametrize(("split", "location", "encoder_shape", "raw_shape"), [
    ("train", "bercy", (50, 45), (400, 360)),
    ("validation", "abudhabi", (100, 99), (800, 792)),
])
def test_real_oscd_bit_output_aligns_to_original_mask_grid(
    detector, split, location, encoder_shape, raw_shape
):
    dataset = OSCDDataset(split=split)
    sample = dataset[dataset.location_ids.index(location)]
    t1, t2 = sample.bit_inputs(quantification_value=10000)
    traces = {}

    def capture_encoder(_module, _inputs, output):
        traces["encoder"] = tuple(output.shape[-2:])

    def capture_logits(_module, _inputs, output):
        traces["logits"] = output.detach()

    hooks = [
        detector.model.resnet.layer3.register_forward_hook(capture_encoder),
        detector.model.classifier.register_forward_hook(capture_logits),
    ]
    result = detector.predict(t1, t2, target_shape=tuple(sample.mask.shape))
    for hook in hooks:
        hook.remove()

    assert traces["encoder"] == encoder_shape
    raw_logits = traces["logits"]
    assert tuple(raw_logits.shape) == (1, 2, *raw_shape)
    assert tuple(result["logits"].shape) == (1, 2, *sample.mask.shape)
    assert tuple(result["probability"].shape) == (1, *sample.mask.shape)
    assert tuple(result["probability"].shape[-2:]) == tuple(sample.mask.shape)
    assert torch.isfinite(result["logits"]).all()
    assert torch.isfinite(result["probability"]).all()
    assert result["probability"].min() >= 0 and result["probability"].max() <= 1
    assert set(sample.mask.unique().tolist()) <= {0, 1}

    aligned_again = align_bit_logits(raw_logits, tuple(sample.mask.shape))
    torch.testing.assert_close(result["logits"], aligned_again, rtol=0, atol=0)


def test_logits_and_categorical_mask_alignment_preserve_channels_and_classes():
    logits = torch.arange(2 * 3 * 4 * 5, dtype=torch.float32).reshape(2, 3, 4, 5)
    aligned = align_bit_logits(logits, (7, 9))
    assert aligned.shape == (2, 3, 7, 9)
    assert torch.equal(aligned, align_bit_logits(logits, (7, 9)))

    labels = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
    resized = align_categorical_mask(labels, (7, 9))
    assert resized.shape == (7, 9)
    assert set(resized.unique().tolist()) == {0, 1}
