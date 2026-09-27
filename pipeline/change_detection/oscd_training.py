"""Deterministic OSCD patch input, masked loss, and minimal BIT trainer."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import time
from typing import Any
import warnings

import numpy as np
import rasterio
import torch
import torch.nn.functional as F
import yaml
from rasterio.errors import NotGeoreferencedWarning

from pipeline.change_detection.bit import BITDetector
from pipeline.change_detection.bit_alignment import align_bit_logits
from pipeline.change_detection.oscd_dataset import (
    BIT_RGB_BANDS,
    DEFAULT_OSCD_ROOT,
    DEFAULT_SPLITS_PATH,
    OSCDDataset,
    OSCDDataError,
    normalize_bit_dn,
)
from pipeline.embeddings.device import select_device


def generate_patch_coordinates(
    height: int, width: int, patch_size: int, stride: int | None = None,
) -> list[tuple[int, int]]:
    """Return deterministic row-major full-coverage patch offsets."""
    stride = patch_size if stride is None else stride
    if min(height, width, patch_size) <= 0:
        raise ValueError("height, width, and patch_size must be positive")
    if stride <= 0 or stride > patch_size:
        raise ValueError("stride must be positive and no greater than patch_size for full coverage")
    return [(row, col)
            for row in range(0, height, stride)
            for col in range(0, width, stride)]


def make_location_folds(
    official_train: list[str] | tuple[str, ...],
    official_test: list[str] | tuple[str, ...],
    *,
    n_splits: int = 5,
    seed: int = 42,
) -> list[dict[str, list[str]]]:
    """Create deterministic, location-disjoint folds from official-train IDs only."""
    roster = sorted(official_train)
    test = set(official_test)
    if len(roster) != len(set(roster)) or test & set(roster):
        raise OSCDDataError("Official train/test location rosters overlap or contain duplicates")
    if not 2 <= n_splits <= len(roster):
        raise ValueError("n_splits must be between 2 and the number of official training locations")
    shuffled = list(roster)
    random.Random(seed).shuffle(shuffled)
    validation_groups = [sorted(shuffled[index::n_splits]) for index in range(n_splits)]
    folds = []
    for validation in validation_groups:
        validation_set = set(validation)
        train = [location for location in roster if location not in validation_set]
        if set(train) & validation_set or (set(train) | validation_set) != set(roster):
            raise OSCDDataError("Generated fold does not partition official training locations")
        if (set(train) | validation_set) & test:
            raise OSCDDataError("Official test location leaked into a generated fold")
        folds.append({"train": train, "validation": validation})
    validation_occurrences = [loc for fold in folds for loc in fold["validation"]]
    if len(validation_occurrences) != len(roster) or set(validation_occurrences) != set(roster):
        raise OSCDDataError("Every official training location must validate exactly once")
    return folds


def apply_geometric_augmentation(
    t1: torch.Tensor, t2: torch.Tensor, target: torch.Tensor, valid: torch.Tensor,
    transform: str,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Apply one identical, value-preserving spatial transform to a temporal pair and labels."""
    transforms = {
        "identity": lambda value: value,
        "horizontal_flip": lambda value: torch.flip(value, dims=(-1,)),
        "vertical_flip": lambda value: torch.flip(value, dims=(-2,)),
        "rotate_90": lambda value: torch.rot90(value, 1, dims=(-2, -1)),
        "rotate_180": lambda value: torch.rot90(value, 2, dims=(-2, -1)),
        "rotate_270": lambda value: torch.rot90(value, 3, dims=(-2, -1)),
    }
    if transform not in transforms:
        raise ValueError(f"Unsupported geometric transform: {transform}")
    operation = transforms[transform]
    return tuple(operation(value).contiguous() for value in (t1, t2, target, valid))


class OSCDPatchDataset(torch.utils.data.Dataset):
    """Windowed, fixed-size OSCD patches; never materializes a full scene."""

    def __init__(
        self,
        *,
        split: str,
        locations: list[str],
        patch_size: int = 256,
        patch_stride: int | None = None,
        quantification_value: float = 10000.0,
        augmentation: bool = False,
        seed: int = 42,
        root: str | Path = DEFAULT_OSCD_ROOT,
        splits_path: str | Path = DEFAULT_SPLITS_PATH,
    ) -> None:
        if split not in {"train", "validation"}:
            raise ValueError("Training patches may use only 'train' or 'validation' split")
        if patch_size <= 0 or patch_size % 8:
            raise ValueError("patch_size must be positive and divisible by BIT's effective stride 8")
        patch_stride = patch_size if patch_stride is None else patch_stride
        if patch_stride <= 0 or patch_stride > patch_size:
            raise ValueError("patch_stride must be positive and no greater than patch_size")
        if augmentation and split != "train":
            raise ValueError("Geometric augmentation is permitted only for training patches")
        if not np.isfinite(quantification_value) or quantification_value <= 0:
            raise ValueError("quantification_value must be finite and positive")
        self.source = OSCDDataset(root, split=split, locations=locations, splits_path=splits_path)
        self.split = split
        self.patch_size = patch_size
        self.patch_stride = patch_stride
        self.quantification_value = float(quantification_value)
        self.augmentation = bool(augmentation)
        self.seed = int(seed)
        self.epoch = 0
        self.transforms = (
            "identity", "horizontal_flip", "vertical_flip",
            "rotate_90", "rotate_180", "rotate_270",
        )
        self.samples: list[tuple[str, int, int, int, int]] = []
        image_root = Path(root) / "Onera Satellite Change Detection dataset - Images"
        label_roots = {
            "train": Path(root) / "Onera Satellite Change Detection dataset - Train Labels",
            "validation": Path(root) / "Onera Satellite Change Detection dataset - Train Labels",
        }
        for location in locations:
            t1_b04 = image_root / location / "imgs_1_rect" / "B04.tif"
            t2_b04 = image_root / location / "imgs_2_rect" / "B04.tif"
            label = label_roots[split] / location / "cm" / f"{location}-cm.tif"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", NotGeoreferencedWarning)
                with rasterio.open(t1_b04) as first, rasterio.open(t2_b04) as second, rasterio.open(label) as mask:
                    shape = (first.height, first.width)
                    if (second.height, second.width) != shape or (mask.height, mask.width) != shape:
                        raise OSCDDataError(f"T1/T2/mask registered dimensions differ for {location}")
                    if first.count != 1 or second.count != 1 or mask.count != 1:
                        raise OSCDDataError(f"Expected single-band named inputs and mask for {location}")
            for row, col in generate_patch_coordinates(*shape, patch_size, patch_stride):
                valid_h = min(patch_size, shape[0] - row)
                valid_w = min(patch_size, shape[1] - col)
                self.samples.append((location, row, col, valid_h, valid_w))

    def __len__(self) -> int:
        return len(self.samples)

    def set_epoch(self, epoch: int) -> None:
        if epoch < 0:
            raise ValueError("epoch must be nonnegative")
        self.epoch = int(epoch)

    def __getitem__(self, index: int) -> dict[str, Any]:
        location, row, col, valid_h, valid_w = self.samples[index]
        raw_images, target, metadata = self.source.read_window(
            location, row=row, col=col, height=valid_h, width=valid_w,
        )
        pad_h, pad_w = self.patch_size - valid_h, self.patch_size - valid_w
        image_array = raw_images.numpy()
        if pad_h or pad_w:
            image_array = np.pad(
                image_array,
                ((0, 0), (0, 0), (0, pad_h), (0, pad_w)),
                mode="reflect",
            )
            target = F.pad(target, (0, pad_w, 0, pad_h), value=0)
        images = normalize_bit_dn(
            torch.from_numpy(np.ascontiguousarray(image_array)),
            quantification_value=self.quantification_value,
        )
        valid = torch.zeros((self.patch_size, self.patch_size), dtype=torch.bool)
        valid[:valid_h, :valid_w] = True
        transform = "identity"
        if self.augmentation:
            rng = random.Random(self.seed + self.epoch * len(self.samples) + index)
            transform = rng.choice(self.transforms)
            images[0], images[1], target, valid = apply_geometric_augmentation(
                images[0], images[1], target, valid, transform,
            )
        metadata.update({"row": row, "col": col, "valid_height": valid_h, "valid_width": valid_w})
        metadata["augmentation"] = transform
        return {
            "t1": images[0],
            "t2": images[1],
            "target": target,
            "valid": valid,
            "metadata": metadata,
        }


def masked_weighted_bce_dice(
    logits: torch.Tensor,
    target: torch.Tensor,
    valid: torch.Tensor,
    *,
    positive_weight: float = 46.46,
    bce_weight: float = 0.5,
    dice_weight: float = 0.5,
    smooth: float = 1.0,
) -> dict[str, torch.Tensor]:
    """Stable masked weighted BCE-with-logits + soft Dice for BIT's 2 logits."""
    if logits.ndim != 4 or logits.shape[1] != 2:
        raise ValueError(f"Expected BIT logits [N,2,H,W], got {tuple(logits.shape)}")
    if not logits.is_floating_point() or not torch.isfinite(logits).all():
        raise FloatingPointError("BIT logits must be finite floating-point values")
    if min(positive_weight, bce_weight, dice_weight, smooth) < 0 or smooth == 0:
        raise ValueError("Loss weights must be nonnegative and smooth must be positive")

    binary_logits = logits[:, 1] - logits[:, 0]
    if target.ndim == 4 and target.shape[1] == 1:
        target = target[:, 0]
    if valid.ndim == 4 and valid.shape[1] == 1:
        valid = valid[:, 0]
    if target.shape != binary_logits.shape or valid.shape != binary_logits.shape:
        raise ValueError("target/valid spatial shapes must match the BIT logits")
    target = target.to(device=logits.device, dtype=logits.dtype)
    valid = valid.to(device=logits.device, dtype=torch.bool)
    if not torch.isfinite(target).all() or not torch.all((target == 0) | (target == 1)):
        raise ValueError("target must contain only finite binary labels")
    valid_count = valid.sum()
    if valid_count.item() == 0:
        raise ValueError("A patch must contain at least one valid pixel")

    pixel_bce = F.binary_cross_entropy_with_logits(
        binary_logits,
        target,
        pos_weight=torch.tensor(positive_weight, dtype=logits.dtype, device=logits.device),
        reduction="none",
    )
    bce_sum = pixel_bce.masked_select(valid).sum()
    bce = bce_sum / valid_count.to(logits.dtype)
    probabilities = torch.sigmoid(binary_logits)
    valid_float = valid.to(logits.dtype)
    intersection = (probabilities * target * valid_float).sum()
    probability_sum = (probabilities * valid_float).sum()
    target_sum = (target * valid_float).sum()
    dice = 1.0 - (2.0 * intersection + smooth) / (probability_sum + target_sum + smooth)
    total = bce_weight * bce + dice_weight * dice
    components = {
        "total": total,
        "bce": bce,
        "dice": dice,
        "bce_sum": bce_sum,
        "valid_pixels": valid_count,
        "intersection": intersection,
        "probability_sum": probability_sum,
        "target_sum": target_sum,
    }
    if not all(torch.isfinite(value).all() for value in components.values()):
        raise FloatingPointError("Masked BCE/Dice loss produced a non-finite component")
    return components


@dataclass
class LossAccumulator:
    bce_sum: float = 0.0
    valid_pixels: int = 0
    intersection: float = 0.0
    probability_sum: float = 0.0
    target_sum: float = 0.0

    def add(self, components: dict[str, torch.Tensor]) -> None:
        self.bce_sum += float(components["bce_sum"].detach())
        self.valid_pixels += int(components["valid_pixels"].detach())
        self.intersection += float(components["intersection"].detach())
        self.probability_sum += float(components["probability_sum"].detach())
        self.target_sum += float(components["target_sum"].detach())

    def report(self, *, bce_weight: float, dice_weight: float, smooth: float = 1.0) -> dict[str, float]:
        if self.valid_pixels == 0:
            raise ValueError("Cannot aggregate an empty dataset")
        bce = self.bce_sum / self.valid_pixels
        dice = 1.0 - (2.0 * self.intersection + smooth) / (
            self.probability_sum + self.target_sum + smooth
        )
        return {"bce": bce, "dice": dice, "total": bce_weight * bce + dice_weight * dice,
                "valid_pixels": float(self.valid_pixels)}


def load_training_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Training configuration must be a YAML mapping")
    return config


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def training_device(requested: str = "auto") -> torch.device:
    """Resolve auto/cpu/cuda and reject explicit CUDA requests without CUDA."""
    try:
        return select_device(requested)
    except RuntimeError as exc:
        raise RuntimeError(
            "CUDA was explicitly requested for OSCD BIT training, but this Python "
            "environment reports torch.cuda.is_available() == False. Install/select "
            "a CUDA-enabled PyTorch environment; no CPU fallback was performed."
        ) from exc


def runtime_info(device: torch.device) -> dict[str, Any]:
    info: dict[str, Any] = {
        "selected_device": device.type,
        "torch_version": str(torch.__version__),
        "cuda_version": str(torch.version.cuda) if torch.version.cuda is not None else None,
    }
    if device.type == "cuda":
        props = torch.cuda.get_device_properties(device)
        info["gpu_name"] = props.name
        info["gpu_vram_gib"] = props.total_memory / (1024 ** 3)
    return info


def _select_and_report_runtime(requested: str) -> tuple[torch.device, dict[str, Any]]:
    try:
        device = training_device(requested)
    except RuntimeError:
        failure_info = {
            "requested_device": requested,
            "selected_device": None,
            "torch_version": str(torch.__version__),
            "cuda_version": str(torch.version.cuda) if torch.version.cuda is not None else None,
        }
        print(yaml.safe_dump({"runtime": failure_info}, sort_keys=True).strip(), flush=True)
        raise
    info = runtime_info(device)
    info["requested_device"] = requested
    print(yaml.safe_dump({"runtime": info}, sort_keys=True).strip(), flush=True)
    return device, info


def _cuda_memory_mib() -> dict[str, float] | None:
    if not torch.cuda.is_available():
        return None
    torch.cuda.synchronize()
    mib = float(1024 ** 2)
    return {
        "allocated_mib": torch.cuda.memory_allocated() / mib,
        "reserved_mib": torch.cuda.memory_reserved() / mib,
    }


def _resolve_cross_validation(config: dict[str, Any], root: Path, splits_path: Path):
    from pipeline.change_detection.oscd_dataset import load_split_manifest

    manifest = load_split_manifest(root, splits_path)
    cv = config["cross_validation"]
    folds = make_location_folds(
        manifest["official_train"], manifest["test"],
        n_splits=int(cv["n_splits"]), seed=int(cv["seed"]),
    )
    fold_index = int(cv["fold"])
    if not 0 <= fold_index < len(folds):
        raise ValueError(f"cross_validation.fold must be in [0, {len(folds) - 1}]")
    print(yaml.safe_dump({
        "location_cross_validation": {
            "seed": int(cv["seed"]),
            "selected_fold": fold_index,
            "folds": [
                {"fold": index, "train": fold["train"], "validation": fold["validation"]}
                for index, fold in enumerate(folds)
            ],
        }
    }, sort_keys=False).strip(), flush=True)
    return folds, fold_index


def _process_memory_mib() -> dict[str, float] | None:
    """Return Windows current/peak working set using the OS process API."""
    import ctypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    try:
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        ok = psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        mib = float(1024 ** 2)
        return {"working_set_mib": counters.WorkingSetSize / mib,
                "peak_working_set_mib": counters.PeakWorkingSetSize / mib}
    except (AttributeError, OSError):
        return None


def _make_datasets(
    config: dict[str, Any],
) -> tuple[OSCDPatchDataset, OSCDPatchDataset, int]:
    data = config["data"]
    patch = config["patch"]
    if tuple(config["input"]["bands"]) != BIT_RGB_BANDS:
        raise ValueError(f"BIT input bands must remain {BIT_RGB_BANDS}")
    folds, fold_index = _resolve_cross_validation(config, Path(data["root"]), Path(data["splits"]))
    selected = folds[fold_index]
    shared = {
        "patch_size": int(patch["patch_size"]),
        "quantification_value": float(config["input"]["quantification_value"]),
        "seed": int(config["training"]["seed"]),
        "root": Path(data["root"]),
        "splits_path": Path(data["splits"]),
    }
    if set(selected["train"]) & set(selected["validation"]):
        raise OSCDDataError("Selected CV fold has overlapping train/validation locations")
    train = OSCDPatchDataset(
        split="train", locations=selected["train"],
        patch_stride=int(patch["patch_stride"]),
        augmentation=bool(patch["augmentation"]["enabled"]), **shared,
    )
    validation = OSCDPatchDataset(
        split="validation", locations=selected["validation"],
        patch_stride=int(patch.get("validation_stride", patch["patch_size"])),
        augmentation=False, **shared,
    )
    return train, validation, fold_index


def _make_optimizer(model: torch.nn.Module, training: dict[str, Any]) -> torch.optim.Optimizer:
    if training["optimizer"].lower() != "adamw":
        raise ValueError("This trainer currently implements only the configured AdamW optimizer")
    return torch.optim.AdamW(
        model.parameters(), lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )


def _forward_patch(model: torch.nn.Module, sample: dict[str, Any], device: torch.device):
    t1 = sample["t1"].unsqueeze(0).to(device)
    t2 = sample["t2"].unsqueeze(0).to(device)
    target = sample["target"].unsqueeze(0).to(device)
    valid = sample["valid"].unsqueeze(0).to(device)
    if any(tensor.device.type != device.type for tensor in (t1, t2, target, valid)):
        raise RuntimeError(f"Batch transfer to {device.type} did not complete")
    raw_logits = model(t1, t2)
    logits = align_bit_logits(raw_logits, tuple(target.shape[-2:]))
    return raw_logits, logits, (target, valid), (t1, t2)


def dry_run(
    config: dict[str, Any],
    *,
    checkpoint: str | Path | None = None,
    device: str | None = None,
) -> dict[str, Any]:
    """Run exactly one backward/optimizer step on the resolved requested device."""
    started = time.perf_counter()
    training = config["training"]
    if int(training["batch_size"]) != 1:
        raise ValueError("The dry-run currently requires batch_size=1")
    requested_device = device or training.get("device", "auto")
    selected_device, environment = _select_and_report_runtime(requested_device)
    seed_everything(int(training["seed"]))
    torch.set_num_threads(int(training.get("cpu_threads", 4)))
    if selected_device.type == "cuda":
        torch.cuda.set_device(
            selected_device.index if selected_device.index is not None
            else torch.cuda.current_device()
        )
    train_data, _, _ = _make_datasets(config)
    sample = train_data[0]
    detector = BITDetector(checkpoint or config["model"]["checkpoint"], device=selected_device.type)
    model = detector.model.train()
    if next(model.parameters()).device.type != selected_device.type:
        raise RuntimeError("BIT parameters were not moved to the selected training device")
    loss_config = config["loss"]
    optimizer = _make_optimizer(model, training)
    before = _process_memory_mib()
    if selected_device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(selected_device)
    gpu_before = _cuda_memory_mib()
    before_parameter = next(model.parameters()).detach().clone()
    optimizer.zero_grad(set_to_none=True)
    raw_logits, logits, (target, valid), (t1, t2) = _forward_patch(model, sample, selected_device)
    if any(tensor.device.type != selected_device.type for tensor in (t1, t2, raw_logits, logits, target, valid)):
        raise RuntimeError("A model input/output or training target is not on the selected device")
    components = masked_weighted_bce_dice(logits, target, valid, **loss_config)
    if components["total"].device.type != selected_device.type:
        raise RuntimeError("Loss reduction did not remain on the selected device")
    components["total"].backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
    if not gradients or not all(torch.isfinite(grad).all() for grad in gradients):
        raise FloatingPointError("Dry-run gradients are missing or non-finite")
    optimizer.step()
    if selected_device.type == "cuda":
        torch.cuda.synchronize(selected_device)
    elapsed = time.perf_counter() - started
    if not all(torch.isfinite(parameter).all() for parameter in model.parameters()):
        raise FloatingPointError("Optimizer step produced non-finite model parameters")
    updated = not torch.equal(before_parameter, next(model.parameters()).detach())
    if not updated:
        raise RuntimeError("Optimizer step completed but the checked model parameter did not change")
    return {
        "location_id": sample["metadata"]["location_id"],
        "runtime": environment,
        "patch": sample["metadata"],
        "input_shape": list(sample["t1"].shape),
        "raw_logits_shape": list(raw_logits.shape),
        "aligned_logits_shape": list(logits.shape),
        "valid_pixels": int(components["valid_pixels"].detach()),
        "bce": float(components["bce"].detach()),
        "dice": float(components["dice"].detach()),
        "total": float(components["total"].detach()),
        "finite_gradients": True,
        "gradient_tensors": len(gradients),
        "optimizer_parameter_updated": updated,
        "model_device": str(next(model.parameters()).device),
        "input_device": str(selected_device),
        "logits_device": str(logits.device),
        "loss_device": str(components["total"].device),
        "memory_before_step": before,
        "memory_after_step": _process_memory_mib(),
        "gpu_memory_before_step": gpu_before,
        "gpu_memory_after_step": _cuda_memory_mib(),
        "dry_run_duration_seconds": elapsed,
        "checkpoint_sha256": detector.checkpoint_sha256,
    }


def _evaluate(
    model: torch.nn.Module,
    dataset: OSCDPatchDataset,
    config: dict[str, Any],
    device: torch.device,
) -> dict[str, float]:
    accumulator = LossAccumulator()
    loss_config = config["loss"]
    model.eval()
    with torch.no_grad():
        for index in range(len(dataset)):
            sample = dataset[index]
            _, logits, (target, valid), _ = _forward_patch(model, sample, device)
            accumulator.add(masked_weighted_bce_dice(logits, target, valid, **loss_config))
    return accumulator.report(
        bce_weight=loss_config["bce_weight"], dice_weight=loss_config["dice_weight"],
        smooth=loss_config["smooth"],
    )


def train(
    config: dict[str, Any], *, checkpoint: str | Path | None = None, device: str | None = None
) -> None:
    """Run configured training; invoke only without --dry-run by explicit user action."""
    training = config["training"]
    if int(training["batch_size"]) != 1:
        raise ValueError("Configured trainer currently supports batch_size=1 only")
    selected_device, _ = _select_and_report_runtime(device or training.get("device", "auto"))
    seed_everything(int(training["seed"]))
    torch.set_num_threads(int(training.get("cpu_threads", 4)))
    if selected_device.type == "cuda":
        torch.cuda.set_device(
            selected_device.index if selected_device.index is not None
            else torch.cuda.current_device()
        )
    train_data, validation_data, fold_index = _make_datasets(config)
    out_dir = Path(config["output"]["checkpoint_directory"]) / f"fold_{fold_index}"
    best_path, last_path = out_dir / "best_oscd_bit.pt", out_dir / "last_oscd_bit.pt"
    existing_outputs = [path for path in (best_path, last_path) if path.exists()]
    if existing_outputs:
        raise FileExistsError(
            "Refusing to overwrite existing OSCD checkpoints: "
            + ", ".join(str(path) for path in existing_outputs)
            + ". Choose a new checkpoint_directory or archive them first."
        )
    detector = BITDetector(checkpoint or config["model"]["checkpoint"], device=selected_device.type)
    model = detector.model
    optimizer = _make_optimizer(model, training)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_validation = float("inf")
    for epoch in range(1, int(training["epochs"]) + 1):
        model.train()
        train_data.set_epoch(epoch - 1)
        accumulator = LossAccumulator()
        for index in range(len(train_data)):
            sample = train_data[index]
            optimizer.zero_grad(set_to_none=True)
            _, logits, (target, valid), _ = _forward_patch(model, sample, selected_device)
            components = masked_weighted_bce_dice(logits, target, valid, **config["loss"])
            components["total"].backward()
            optimizer.step()
            accumulator.add(components)
        train_metrics = accumulator.report(
            bce_weight=config["loss"]["bce_weight"], dice_weight=config["loss"]["dice_weight"],
            smooth=config["loss"]["smooth"],
        )
        validation_metrics = _evaluate(model, validation_data, config, selected_device)
        record = {"epoch": epoch, "train": train_metrics, "validation": validation_metrics}
        print(yaml.safe_dump(record, sort_keys=True).strip(), flush=True)
        payload = {
            "model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch, "train_metrics": train_metrics,
            "validation_metrics": validation_metrics,
            "base_checkpoint": str(checkpoint or config["model"]["checkpoint"]),
            "base_checkpoint_sha256": detector.checkpoint_sha256,
            "config": config,
        }
        torch.save(payload, last_path)
        if validation_metrics["total"] < best_validation:
            best_validation = validation_metrics["total"]
            torch.save(payload, best_path)
