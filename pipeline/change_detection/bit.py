"""Official BIT-CD BASE_Transformer adapter with explicit checkpoint validation."""
from __future__ import annotations

import hashlib
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F
from torchvision.models.resnet import BasicBlock, ResNet, conv3x3

from pipeline.embeddings.device import select_device
from pipeline.change_detection.help_funcs import Transformer, TransformerDecoder, TwoLayerConv2d
from pipeline.change_detection.bit_alignment import align_bit_logits

BIT_MODEL_NAME = "BIT-CD BASE_Transformer (base_transformer_pos_s4_dd8)"
BIT_CHECKPOINT = Path("models/bit/BIT_LEVIR/best_ckpt.pt")
BIT_CHECKPOINT_SHA256 = "c159ba76143447f58c9f367ce8126a0014f2e4ba218cdb97cca173952c38cb3b"


class DilatedBasicBlock(BasicBlock):
    """Torchvision BasicBlock with the dilation support used by official BIT.

    Recent torchvision releases reject dilation in BasicBlock even though the
    BIT ResNet-18 configuration replaces the final two strides with dilation.
    The block has the same parameters and state-dict keys; only its convolutions
    honor the dilation already supplied by ``ResNet._make_layer``.
    """

    def __init__(
        self, inplanes, planes, stride=1, downsample=None, groups=1,
        base_width=64, dilation=1, norm_layer=None,
    ):
        nn.Module.__init__(self)
        if groups != 1 or base_width != 64:
            raise ValueError("BasicBlock only supports groups=1 and base_width=64")
        norm_layer = nn.BatchNorm2d if norm_layer is None else norm_layer
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = norm_layer(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes, dilation=dilation)
        self.bn2 = norm_layer(planes)
        self.downsample = downsample
        self.stride = stride


class BITArchitecture(nn.Module):
    """State-dict-compatible official BIT-CD model (3-channel, 2-class)."""
    def __init__(self):
        super().__init__()
        # BIT's official base_transformer_pos_s4_dd8 configuration uses output
        # stride 8. The custom BasicBlock preserves torchvision's ResNet layout
        # and checkpoint keys while enabling its historical dilated stages.
        self.resnet = ResNet(
            DilatedBasicBlock, [2, 2, 2, 2],
            replace_stride_with_dilation=[False, True, True],
        )
        self.relu = nn.ReLU()
        self.upsamplex2 = nn.Upsample(scale_factor=2)
        self.upsamplex4 = nn.Upsample(scale_factor=4, mode="bilinear")
        self.classifier = TwoLayerConv2d(32, 2)
        self.resnet_stages_num = 4
        self.if_upsample_2x = True
        self.conv_pred = nn.Conv2d(256, 32, kernel_size=3, padding=1)
        self.output_sigmoid = False
        self.sigmoid = nn.Sigmoid()
        self.token_len = 4
        self.conv_a = nn.Conv2d(32, self.token_len, kernel_size=1, bias=False)
        self.tokenizer = True
        self.token_trans = True
        self.with_decoder = True
        self.with_pos = "learned"
        self.pos_embedding = nn.Parameter(torch.randn(1, 8, 32))
        self.with_decoder_pos = None
        self.enc_depth, self.dec_depth = 1, 8
        self.dim_head, self.decoder_dim_head = 64, 64
        self.transformer = Transformer(32, 1, 8, 64, 64, 0)
        # The official checkpoint's cross-attention projections are [64, 32],
        # which encode one 64-dimensional head (not eight heads).
        self.transformer_decoder = TransformerDecoder(32, 8, 1, 64, 64, 0, softmax=True)

    def forward_single(self, x):
        x = self.resnet.maxpool(self.resnet.relu(self.resnet.bn1(self.resnet.conv1(x))))
        x = self.resnet.layer1(x)
        x = self.resnet.layer2(x)
        x = self.resnet.layer3(x)
        return self.conv_pred(self.upsamplex2(x))

    def _tokens(self, x):
        b, c, _, _ = x.shape
        attention = torch.softmax(self.conv_a(x).reshape(b, self.token_len, -1), dim=-1)
        return torch.einsum("bln,bcn->blc", attention, x.reshape(b, c, -1))

    def _decode(self, x, tokens):
        b, c, h, w = x.shape
        flat = x.permute(0, 2, 3, 1).reshape(b, h * w, c)
        decoded = self.transformer_decoder(flat, tokens)
        return decoded.reshape(b, h, w, c).permute(0, 3, 1, 2)

    def forward(self, x1, x2):
        f1, f2 = self.forward_single(x1), self.forward_single(x2)
        t1, t2 = self._tokens(f1), self._tokens(f2)
        tokens = self.transformer(torch.cat([t1, t2], dim=1) + self.pos_embedding)
        t1, t2 = tokens.chunk(2, dim=1)
        f1, f2 = self._decode(f1, t1), self._decode(f2, t2)
        return self.classifier(self.upsamplex4(torch.abs(f1 - f2)))


class BITDetector:
    def __init__(self, checkpoint_path: str | Path = BIT_CHECKPOINT, *, device: str = "cpu"):
        path = Path(checkpoint_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"BIT checkpoint is missing: {path}. Configure an existing BIT checkpoint; "
                "the model will not run with random weights."
            )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.device = select_device(device)
        self.model = BITArchitecture()
        container = torch.load(path, map_location="cpu", weights_only=False)
        if digest == BIT_CHECKPOINT_SHA256:
            # Keep the official upstream artifact pinned to its verified digest.
            state = container.get("model_G_state_dict")
        else:
            # AVLOKAN OSCD checkpoints store the same architecture as a strict
            # state dict inside a training provenance container.
            state = container.get("model_state_dict") if isinstance(container, dict) else None
            base_hash = container.get("base_checkpoint_sha256") if isinstance(container, dict) else None
            if not isinstance(state, dict) or base_hash != BIT_CHECKPOINT_SHA256:
                raise RuntimeError(
                    f"Unsupported BIT checkpoint {path}: expected the pinned official LEVIR checkpoint "
                    "or an AVLOKAN fine-tuned checkpoint with verified base_checkpoint_sha256 metadata"
                )
        if not isinstance(state, dict):
            raise RuntimeError(f"Checkpoint has no compatible BIT model state: {path}")
        try:
            self.model.load_state_dict(state, strict=True)
        except RuntimeError as exc:
            raise RuntimeError(
                "Official BIT checkpoint could not be loaded strictly into the configured "
                f"BIT architecture; refusing to run with partial or random weights: {exc}"
            ) from exc
        self.model.eval().to(self.device)
        self.checkpoint_path = path
        self.checkpoint_sha256 = digest
        self.model_config = (
            container.get("config") if isinstance(container, dict) else None
        )
        del container

    @torch.inference_mode()
    def predict(
        self,
        t1: torch.Tensor,
        t2: torch.Tensor,
        *,
        threshold: float = 0.5,
        target_shape: tuple[int, int] | None = None,
    ):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        t1, t2 = t1.to(self.device), t2.to(self.device)
        logits = self.model(t1, t2)
        if target_shape is not None:
            logits = align_bit_logits(logits, target_shape)
        probability = torch.softmax(logits.float(), dim=1)[:, 1]
        mask = probability >= threshold
        return {"logits": logits, "probability": probability, "mask": mask}
