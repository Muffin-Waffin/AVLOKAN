"""Official RemoteCLIP ViT-B-32 adapter using OpenCLIP's public API."""
from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Sequence

import numpy as np
from PIL import Image

from pipeline.embeddings.device import select_device
from pipeline.embeddings.normalization import normalize_embeddings


MODEL_NAME = "RemoteCLIP-ViT-B-32"
OPENCLIP_ARCH = "ViT-B-32"
HF_REPO = "chendelong/RemoteCLIP"
CHECKPOINT_NAME = "RemoteCLIP-ViT-B-32.pt"
CHECKPOINT_SHA256 = "60014e395d930a3f2963d1d89c8522bf4ad56775571e4356e866864789af85c4"


class RemoteCLIPAdapter:
    """Loads the official checkpoint locally and exposes shared image/text features."""

    def __init__(
        self,
        checkpoint_path: str | Path = "models/remoteclip/RemoteCLIP-ViT-B-32.pt",
        *,
        device: str = "auto",
        fp16: bool = True,
    ) -> None:
        import open_clip
        import torch

        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError(
                f"RemoteCLIP checkpoint is missing: {self.checkpoint_path}. "
                "Run scripts/download_remoteclip.py first."
            )
        self.device = select_device(device)
        self.fp16 = bool(fp16 and self.device.type == "cuda")
        self.model_version = CHECKPOINT_SHA256
        started = perf_counter()
        model, _, self.preprocess = open_clip.create_model_and_transforms(
            OPENCLIP_ARCH,
            pretrained=None,
        )
        state = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        self.model = model.eval().to(self.device)
        self.tokenizer = open_clip.get_tokenizer(OPENCLIP_ARCH)
        self.load_seconds = perf_counter() - started
        model_dimension = getattr(model.visual, "output_dim", None)
        self.embedding_dim: int | None = int(model_dimension) if model_dimension is not None else None
        self.image_size = model.visual.image_size
        self.preprocessing_seconds = 0.0
        self.inference_seconds = 0.0

    def _encode_tensor(self, tensor, modality: str) -> np.ndarray:
        import torch

        tensor = tensor.to(self.device)
        autocast = torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
            enabled=self.fp16,
        ) if self.device.type == "cuda" else torch.autocast(device_type="cpu", enabled=False)
        started = perf_counter()
        with torch.inference_mode(), autocast:
            features = (self.model.encode_image(tensor) if modality == "image"
                        else self.model.encode_text(tensor))
        self.inference_seconds += perf_counter() - started
        result = normalize_embeddings(features.detach().float().cpu().numpy())
        dimension = int(result.shape[1])
        if self.embedding_dim is not None and self.embedding_dim != dimension:
            raise RuntimeError("RemoteCLIP image/text embedding dimensions differ")
        self.embedding_dim = dimension
        return result

    def encode_images(self, images: Sequence[Image.Image]) -> np.ndarray:
        import torch

        if not images:
            return np.empty((0, self.embedding_dim or 0), dtype=np.float32)
        started = perf_counter()
        batch = torch.stack([self.preprocess(image.convert("RGB")) for image in images])
        self.preprocessing_seconds += perf_counter() - started
        return self._encode_tensor(batch, "image")

    def encode_image(self, image: Image.Image) -> np.ndarray:
        return self.encode_images([image])[0]

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.embedding_dim or 0), dtype=np.float32)
        tokens = self.tokenizer(list(texts))
        return self._encode_tensor(tokens, "text")

    def encode_text(self, text: str) -> np.ndarray:
        return self.encode_texts([text])[0]
