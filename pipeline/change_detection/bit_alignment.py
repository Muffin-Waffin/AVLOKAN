"""Explicit alignment from BIT's stride-rounded output grid to input pixels."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def align_bit_logits(logits: torch.Tensor, target_shape: tuple[int, int]) -> torch.Tensor:
    """Bilinearly map continuous class logits to the input/mask pixel grid.

    BIT's strided encoder rounds feature dimensions up, then the decoder
    upsamples by fixed factors. Interpolating logits (before softmax) to the
    original registered-image H/W aligns the full-frame prediction without
    cropping away edge pixels or resampling categorical labels.
    """
    if logits.ndim != 4 or logits.shape[1] < 2:
        raise ValueError(f"Expected [N,C>=2,H,W] logits, got {tuple(logits.shape)}")
    if not logits.is_floating_point():
        raise TypeError("BIT logits must be floating point")
    if len(target_shape) != 2 or any(int(size) <= 0 for size in target_shape):
        raise ValueError(f"target_shape must contain positive (height, width), got {target_shape}")
    size = (int(target_shape[0]), int(target_shape[1]))
    if logits.shape[-2:] == size:
        return logits
    aligned = F.interpolate(logits, size=size, mode="bilinear", align_corners=False)
    if not torch.isfinite(aligned).all():
        raise ValueError("Aligned BIT logits contain NaN or infinity")
    return aligned


def align_categorical_mask(mask: torch.Tensor, target_shape: tuple[int, int]) -> torch.Tensor:
    """Nearest-neighbor alignment for categorical masks; never interpolate labels bilinearly."""
    was_2d = mask.ndim == 2
    if was_2d:
        mask = mask[None, None]
    elif mask.ndim == 3:
        mask = mask[:, None]
    elif mask.ndim != 4 or mask.shape[1] != 1:
        raise ValueError(f"Expected [H,W], [N,H,W], or [N,1,H,W] mask, got {tuple(mask.shape)}")
    if len(target_shape) != 2 or any(int(size) <= 0 for size in target_shape):
        raise ValueError(f"target_shape must contain positive (height, width), got {target_shape}")
    aligned = F.interpolate(mask.float(), size=tuple(map(int, target_shape)), mode="nearest").to(mask.dtype)
    if was_2d:
        return aligned[0, 0]
    if mask.ndim == 3:
        return aligned[:, 0]
    return aligned
