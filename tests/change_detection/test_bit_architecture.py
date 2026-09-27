from pipeline.change_detection.bit import BITArchitecture, DilatedBasicBlock


def test_bit_resnet_supports_official_dilated_output_stride():
    model = BITArchitecture()
    assert isinstance(model.resnet.layer3[0], DilatedBasicBlock)
    assert model.resnet.layer3[1].conv2.dilation == (2, 2)
    assert model.resnet.layer4[1].conv2.dilation == (4, 4)
    assert model.resnet.layer3[0].conv1.weight.shape == (256, 128, 3, 3)
