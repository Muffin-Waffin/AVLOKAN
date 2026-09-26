"""Small runtime device selector with a reliable CPU fallback."""
from __future__ import annotations


def select_device(device: str = "auto"):
    import torch

    value = device.lower()
    if value == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if value == "cpu":
        return torch.device("cpu")
    if value == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")
        return torch.device("cuda")
    raise ValueError("device must be one of: auto, cpu, cuda")

