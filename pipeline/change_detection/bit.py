"""Official BIT-CD BASE_Transformer adapter with explicit checkpoint validation."""
from __future__ import annotations

import hashlib
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F
from torchvision.models import resnet18

from pipeline.embeddings.device import select_device
from pipeline.change_detection.help_funcs import Transformer, TransformerDecoder, TwoLayerConv2d

BIT_MODEL_NAME = "BIT-CD BASE_Transformer (base_transformer_pos_s4_dd8)"
BIT_CHECKPOINT = Path("models/bit/BIT_LEVIR/best_ckpt.pt")
BIT_CHECKPOINT_SHA256 = "c159ba76143447f58c9f367ce8126a0014f2e4ba218cdb97cca173952c38cb3b"


class BITArchitecture(nn.Module):
    """State-dict-compatible official BIT-CD model (3-channel, 2-class)."""
    def __init__(self):
        super().__init__()
        self.resnet = resnet18(weights=None, replace_stride_with_dilation=[False, True, True])
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
        self.transformer_decoder = TransformerDecoder(32, 8, 8, 64, 64, 0, softmax=True)

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
                f"BIT checkpoint is missing: {path}. Place the official BIT-CD LEVIR best_ckpt.pt there; "
                "the model will not run with random weights."
            )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != BIT_CHECKPOINT_SHA256:
            raise RuntimeError(f"BIT checkpoint SHA-256 mismatch for {path}: {digest}")
        self.device = select_device(device)
        self.model = BITArchitecture()
        # The hash pins this file to the trusted official checkpoint before loading its legacy container.
        container = torch.load(path, map_location="cpu", weights_only=False)
        state = container.get("model_G_state_dict")
        if not isinstance(state, dict):
            raise RuntimeError("Checkpoint has no model_G_state_dict (not an official BIT-CD training checkpoint)")
        self.model.load_state_dict(state, strict=True)
        self.model.eval().to(self.device)
        self.checkpoint_path = path
        self.checkpoint_sha256 = digest

    @torch.inference_mode()
    def predict(self, t1: torch.Tensor, t2: torch.Tensor, *, threshold: float = 0.5):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        t1, t2 = t1.to(self.device), t2.to(self.device)
        logits = self.model(t1, t2)
        probability = torch.softmax(logits.float(), dim=1)[:, 1]
        mask = probability >= threshold
        return {"logits": logits, "probability": probability, "mask": mask}
