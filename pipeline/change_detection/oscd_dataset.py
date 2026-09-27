"""Verified loader and inventory builder for the staged raw OSCD release."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable
import warnings

import numpy as np
import rasterio
import torch
from PIL import Image
from rasterio.errors import NotGeoreferencedWarning


OSCD_BANDS = (
    "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08",
    "B8A", "B09", "B10", "B11", "B12",
)
BIT_RGB_BANDS = ("B04", "B03", "B02")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OSCD_ROOT = PROJECT_ROOT / "data/oscd/raw/extracted"
DEFAULT_SPLITS_PATH = PROJECT_ROOT / "data/oscd/splits.json"


class OSCDDataError(ValueError):
    """Raised when the staged OSCD files or split metadata are inconsistent."""


def normalize_bit_dn(images: torch.Tensor, *, quantification_value: float) -> torch.Tensor:
    """Apply the shared OSCD-to-BIT DN scaling exactly once."""
    if not np.isfinite(quantification_value) or quantification_value <= 0:
        raise ValueError("quantification_value must be finite and greater than zero")
    reflectance = torch.clamp(images / float(quantification_value), 0.0, 1.0)
    return reflectance.mul(2.0).sub(1.0).contiguous()


@dataclass(frozen=True)
class OSCDSample:
    """One original, unresized OSCD pair and its binary target mask.

    ``images`` is float32 raw Sentinel-2 DN with shape [T=2, C=3, H, W],
    channel order B04/B03/B02. ``mask`` is int64 class IDs [H, W] (0/1).
    Apply radiometric scaling/normalization explicitly with ``bit_inputs``.
    """

    images: torch.Tensor
    mask: torch.Tensor
    location_id: str
    split: str
    official_split: str
    metadata: dict[str, Any]

    def bit_inputs(self, *, quantification_value: float) -> tuple[torch.Tensor, torch.Tensor]:
        """Return normalized T1/T2 [1,3,H,W] tensors without resizing.

        OSCD rectified images contain integer Sentinel-2 DN and no scale tags.
        The quantification value is therefore explicit and recorded by callers;
        10000 is the usual Sentinel-2 L1C quantification value.
        """
        normalized = normalize_bit_dn(self.images, quantification_value=quantification_value)
        return normalized[0:1], normalized[1:2]


def _project_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _comma_ids(path: Path) -> list[str]:
    values = [value.strip() for value in path.read_text(encoding="utf-8").replace("\n", ",").split(",")]
    result = [value for value in values if value]
    if len(result) != len(set(result)):
        raise OSCDDataError(f"Duplicate location IDs in {path}")
    return result


def load_split_manifest(root: str | Path = DEFAULT_OSCD_ROOT,
                        splits_path: str | Path = DEFAULT_SPLITS_PATH) -> dict[str, Any]:
    """Load and validate official and development splits against extracted files."""
    root, splits_path = Path(root), Path(splits_path)
    image_root = root / "Onera Satellite Change Detection dataset - Images"
    if not image_root.is_dir():
        raise OSCDDataError(f"OSCD image directory is missing: {image_root}")
    if not splits_path.is_file():
        raise OSCDDataError(f"OSCD split manifest is missing: {splits_path}")
    manifest = json.loads(splits_path.read_text(encoding="utf-8"))
    official_train = set(_comma_ids(image_root / "train.txt"))
    official_test = set(_comma_ids(image_root / "test.txt"))
    manifest_train = set(manifest.get("official_train", []))
    train, validation, test = (set(manifest.get(key, [])) for key in ("train", "validation", "test"))
    if manifest_train != official_train:
        raise OSCDDataError("Manifest official_train roster differs from the image archive train.txt")
    if test != official_test:
        raise OSCDDataError("Manifest test roster differs from the image archive test.txt")
    if train & validation or train | validation != official_train:
        raise OSCDDataError("Train and validation must partition exactly the 14 official training locations")
    if (train | validation) & test:
        raise OSCDDataError("An official test location appears in train or validation")
    image_locations = {path.name for path in image_root.iterdir() if path.is_dir()}
    if image_locations != official_train | official_test:
        raise OSCDDataError("Image location directories do not match official train/test rosters")
    for official, label_name in ((official_train, "Train Labels"), (official_test, "Test Labels")):
        label_root = root / f"Onera Satellite Change Detection dataset - {label_name}"
        labels = {path.name for path in label_root.iterdir() if path.is_dir()}
        if labels != official:
            raise OSCDDataError(f"{label_name} locations differ from the official split list")
    return manifest


def _inspect_image_time(folder: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not folder.is_dir():
        raise OSCDDataError(f"Missing rectified image directory: {folder}")
    files = {path.stem.upper(): path for path in folder.glob("*.tif")}
    if set(files) != set(OSCD_BANDS):
        raise OSCDDataError(
            f"Expected exactly the 13 named OSCD bands in {folder}; "
            f"missing={sorted(set(OSCD_BANDS) - set(files))}, extra={sorted(set(files) - set(OSCD_BANDS))}"
        )
    base: dict[str, Any] | None = None
    profiles: dict[str, dict[str, Any]] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        for band in OSCD_BANDS:
            path = files[band]
            with rasterio.open(path) as src:
                profile = {
                    "width": src.width,
                    "height": src.height,
                    "crs": src.crs.to_string() if src.crs else None,
                    "transform": tuple(src.transform),
                    "resolution": tuple(src.res),
                    "dtype": src.dtypes[0],
                    "nodata": src.nodata,
                    "count": src.count,
                }
            if profile["count"] != 1:
                raise OSCDDataError(f"Expected one channel in {path}, got {profile['count']}")
            if base is None:
                base = profile
            elif any(profile[key] != base[key] for key in ("width", "height", "crs", "transform", "dtype", "nodata")):
                raise OSCDDataError(f"OSCD band grid/profile mismatch in {path}")
            profiles[band] = {**profile, "path": _project_relative(path)}
    assert base is not None
    return base, profiles


def _label_path(root: Path, official_split: str, location_id: str) -> Path:
    folder_name = "Train Labels" if official_split == "train" else "Test Labels"
    return root / f"Onera Satellite Change Detection dataset - {folder_name}" / location_id / "cm" / f"{location_id}-cm.tif"


def _read_mask(path: Path) -> tuple[np.ndarray, list[int], str, str, int]:
    if not path.is_file():
        raise OSCDDataError(f"Missing OSCD mask: {path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with rasterio.open(path) as src:
            if src.count != 1 or src.dtypes[0] != "uint8":
                raise OSCDDataError(f"Expected a single-band uint8 OSCD label TIFF: {path}")
            values = src.read(1)
    unique = np.unique(values).astype(int).tolist()
    if not set(unique) <= {1, 2}:
        raise OSCDDataError(f"Unexpected OSCD TIFF label values in {path}: {unique}")

    # The PNG is documented as a visualization, and aguasclaras is RGB with
    # antialiased values. Confirm that its >127 rendering agrees with the
    # categorical TIFF, but never use its interpolated values as training labels.
    png_path = path.with_name("cm.png")
    with Image.open(png_path) as image:
        png_mode = image.mode
        png_gray = np.asarray(image.convert("L"), dtype=np.uint8)
    if png_gray.shape != values.shape or not np.array_equal(png_gray > 127, values == 2):
        raise OSCDDataError(f"OSCD visualization PNG and categorical TIFF disagree for {path.parent.parent.name}")
    return values, unique, str(values.dtype), png_mode, int(np.unique(png_gray).size)


def _inspect_native_time(folder: Path) -> dict[str, dict[str, Any]]:
    """Inventory original unrectified band grids, which retain native metadata."""
    result: dict[str, dict[str, Any]] = {}
    for band in OSCD_BANDS:
        matches = list(folder.glob(f"*_{band}.tif"))
        if len(matches) != 1:
            raise OSCDDataError(f"Expected one native {band} TIFF in {folder}, found {len(matches)}")
        path = matches[0]
        with rasterio.open(path) as src:
            result[band] = {
                "path": _project_relative(path),
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "crs": src.crs.to_string() if src.crs else None,
                "resolution": list(src.res),
                "dtype": src.dtypes[0],
                "nodata": src.nodata,
            }
    return result


def build_oscd_inventory(
    root: str | Path = DEFAULT_OSCD_ROOT,
    splits_path: str | Path = DEFAULT_SPLITS_PATH,
) -> dict[str, Any]:
    """Inspect all locations and return a serializable, validated inventory."""
    root = Path(root)
    manifest = load_split_manifest(root, splits_path)
    split_for = {location: "train" for location in manifest["train"]}
    split_for.update({location: "validation" for location in manifest["validation"]})
    split_for.update({location: "test" for location in manifest["test"]})
    official_for = {location: "train" for location in manifest["official_train"]}
    official_for.update({location: "test" for location in manifest["test"]})
    image_root = root / "Onera Satellite Change Detection dataset - Images"
    records: list[dict[str, Any]] = []
    for location_id in sorted(split_for):
        location_root = image_root / location_id
        t1, bands_t1 = _inspect_image_time(location_root / "imgs_1_rect")
        t2, bands_t2 = _inspect_image_time(location_root / "imgs_2_rect")
        native_t1 = _inspect_native_time(location_root / "imgs_1")
        native_t2 = _inspect_native_time(location_root / "imgs_2")
        if any(t1[key] != t2[key] for key in ("width", "height", "crs", "transform", "dtype", "nodata")):
            raise OSCDDataError(f"T1/T2 rectified image grids differ for {location_id}")
        mask_path = _label_path(root, official_for[location_id], location_id)
        mask, mask_values, mask_dtype, png_mode, png_gray_levels = _read_mask(mask_path)
        if mask.shape != (t1["height"], t1["width"]):
            raise OSCDDataError(
                f"Mask dimensions {mask.shape} do not match {location_id} imagery "
                f"{(t1['height'], t1['width'])}"
            )
        dates_path = location_root / "dates.txt"
        if not dates_path.is_file():
            raise OSCDDataError(f"Missing dates.txt for {location_id}")
        date_lines = [line.strip().split(":", 1)[-1].strip() for line in dates_path.read_text().splitlines() if line.strip()]
        if len(date_lines) != 2:
            raise OSCDDataError(f"Expected two acquisition dates for {location_id}, got {date_lines}")
        records.append({
            "location_id": location_id,
            "split": split_for[location_id],
            "official_split": official_for[location_id],
            "t1_path": _project_relative(location_root / "imgs_1_rect"),
            "t2_path": _project_relative(location_root / "imgs_2_rect"),
            "mask_path": _project_relative(mask_path),
            "t1_date": date_lines[0],
            "t2_date": date_lines[1],
            "width": t1["width"],
            "height": t1["height"],
            "channel_count": len(OSCD_BANDS),
            "channel_names": list(OSCD_BANDS),
            "selected_bit_bands": list(BIT_RGB_BANDS),
            "crs": t1["crs"],
            "transform": list(t1["transform"]) if t1["crs"] else None,
            "resolution": list(t1["resolution"]) if t1["crs"] else None,
            "nominal_rectified_resolution_m": 10,
            "dtype": t1["dtype"],
            "nodata": t1["nodata"],
            "rectified_registered_pair": True,
            "rectified_band_profiles_t1": bands_t1,
            "rectified_band_profiles_t2": bands_t2,
            "native_band_profiles_t1": native_t1,
            "native_band_profiles_t2": native_t2,
            "mask_width": int(mask.shape[1]),
            "mask_height": int(mask.shape[0]),
            "mask_format": "single-band TIFF",
            "mask_dtype": mask_dtype,
            "mask_unique_values": mask_values,
            "mask_class_mapping": {"1": 0, "2": 1},
            "visualization_png_mode": png_mode,
            "visualization_png_grayscale_levels": png_gray_levels,
            "visualization_png_mapping_verified": "grayscale > 127 agrees with TIFF value 2",
        })
    return {
        "dataset": "Onera Satellite Change Detection (OSCD)",
        "root": _project_relative(root),
        "format_note": "13 separate named single-band TIFFs per date, in both native imgs_1/imgs_2 and registered imgs_1_rect/imgs_2_rect folders; categorical labels are single-band TIFFs",
        "mask_note": "Observed TIFF class values are 1=no change and 2=change (unlike the archive README's stated 0/1); loader maps them to 0/1. Visualization PNG >127 agrees with TIFF value 2 for all locations.",
        "source_split_file": _project_relative(image_root / "train.txt"),
        "validation_policy": manifest["validation_policy"],
        "counts": {key: len(manifest[key]) for key in ("train", "validation", "test")},
        "locations": records,
    }


class OSCDDataset:
    """Small map-style loader returning registered OSCD pairs without resizing."""

    def __init__(
        self,
        root: str | Path = DEFAULT_OSCD_ROOT,
        *,
        split: str = "train",
        locations: Iterable[str] | None = None,
        splits_path: str | Path = DEFAULT_SPLITS_PATH,
    ) -> None:
        if split not in {"train", "validation", "test"}:
            raise ValueError("split must be 'train', 'validation', or 'test'")
        self.root = Path(root)
        self.split = split
        self.manifest = load_split_manifest(self.root, splits_path)
        requested = list(self.manifest[split]) if locations is None else list(locations)
        if len(requested) != len(set(requested)):
            raise OSCDDataError(f"Duplicate location IDs in requested {split} roster")
        allowed = set(self.manifest["test"] if split == "test" else self.manifest["official_train"])
        if not set(requested) <= allowed:
            invalid = sorted(set(requested) - allowed)
            raise OSCDDataError(
                f"Requested {split} roster contains locations outside its allowed official split: {invalid}"
            )
        self.location_ids = requested

    def __len__(self) -> int:
        return len(self.location_ids)

    def read_window(
        self, location_id: str, *, row: int, col: int, height: int, width: int
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
        """Read just one registered RGB pair/mask window as raw DN and binary labels."""
        if location_id not in self.location_ids:
            raise OSCDDataError(f"Location {location_id!r} is not part of the {self.split!r} split")
        if min(row, col) < 0 or min(height, width) <= 0:
            raise ValueError("Window offsets must be nonnegative and dimensions positive")
        image_root = self.root / "Onera Satellite Change Detection dataset - Images" / location_id
        t1_dir, t2_dir = image_root / "imgs_1_rect", image_root / "imgs_2_rect"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            t1_bands, t2_bands = [], []
            reference = None
            for band in BIT_RGB_BANDS:
                pair_arrays, pair_profiles = [], []
                for folder in (t1_dir, t2_dir):
                    path = folder / f"{band}.tif"
                    with rasterio.open(path) as src:
                        if src.count != 1:
                            raise OSCDDataError(f"Expected a single-band named OSCD input: {path}")
                        profile = (src.width, src.height, src.crs, src.transform, src.dtypes[0])
                        pair_profiles.append(profile)
                        if reference is not None and profile != reference:
                            raise OSCDDataError(f"OSCD temporal/channel grid mismatch for {location_id}: {path}")
                        reference = profile if reference is None else reference
                        if row + height > src.height or col + width > src.width:
                            raise ValueError(f"Requested window exceeds registered image bounds for {location_id}")
                        pair_arrays.append(src.read(1, window=rasterio.windows.Window(col, row, width, height)))
                if pair_profiles[0] != pair_profiles[1]:
                    raise OSCDDataError(f"T1/T2 grid mismatch for {location_id}, band {band}")
                t1_bands.append(pair_arrays[0])
                t2_bands.append(pair_arrays[1])

        official_split = "test" if location_id in set(self.manifest["test"]) else "train"
        mask_path = _label_path(self.root, official_split, location_id)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            with rasterio.open(mask_path) as src:
                if src.count != 1 or (src.width, src.height) != (reference[0], reference[1]):
                    raise OSCDDataError(f"Mask grid mismatch for {location_id}")
                raw_mask = src.read(1, window=rasterio.windows.Window(col, row, width, height))
        if not set(np.unique(raw_mask).tolist()) <= {1, 2}:
            raise OSCDDataError(f"Unexpected categorical mask values for {location_id}")
        dates_path = image_root / "dates.txt"
        dates = [line.strip().split(":", 1)[-1].strip()
                 for line in dates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(dates) != 2:
            raise OSCDDataError(f"Expected two dates in {dates_path}")
        images = torch.from_numpy(np.ascontiguousarray(np.stack([
            np.stack(t1_bands), np.stack(t2_bands),
        ]).astype(np.float32, copy=False)))
        target = torch.from_numpy(np.ascontiguousarray(raw_mask == 2)).long()
        metadata = {
            "location_id": location_id, "split": self.split, "official_split": official_split,
            "dates": dates, "bands": list(BIT_RGB_BANDS), "row": row, "col": col,
            "height": height, "width": width,
        }
        return images, target, metadata

    def __getitem__(self, index: int) -> OSCDSample:
        location_id = self.location_ids[index]
        official_split = "test" if location_id in set(self.manifest["test"]) else "train"
        image_root = self.root / "Onera Satellite Change Detection dataset - Images" / location_id
        t1_dir, t2_dir = image_root / "imgs_1_rect", image_root / "imgs_2_rect"
        t1_grid, _ = _inspect_image_time(t1_dir)
        t2_grid, _ = _inspect_image_time(t2_dir)
        if any(t1_grid[key] != t2_grid[key] for key in ("width", "height", "crs", "transform", "dtype", "nodata")):
            raise OSCDDataError(f"T1/T2 rectified image grids differ for {location_id}")
        native_profiles = {
            "t1": _inspect_native_time(image_root / "imgs_1"),
            "t2": _inspect_native_time(image_root / "imgs_2"),
        }
        t1_arrays, t2_arrays = [], []
        profiles: dict[str, Any] = {}
        reference_profile: dict[str, Any] | None = None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", NotGeoreferencedWarning)
            for band in BIT_RGB_BANDS:
                paths = (t1_dir / f"{band}.tif", t2_dir / f"{band}.tif")
                pair_profiles = []
                arrays = []
                for path in paths:
                    if not path.is_file():
                        raise OSCDDataError(f"Missing required {band} input for {location_id}: {path}")
                    with rasterio.open(path) as src:
                        if src.count != 1:
                            raise OSCDDataError(f"Expected one band in {path}")
                        arrays.append(src.read(1))
                        pair_profiles.append({
                            "width": src.width, "height": src.height,
                            "crs": src.crs.to_string() if src.crs else None,
                            "transform": tuple(src.transform), "resolution": tuple(src.res),
                            "dtype": src.dtypes[0],
                            "nodata": src.nodata,
                        })
                if pair_profiles[0] != pair_profiles[1]:
                    raise OSCDDataError(f"T1/T2 grid mismatch for {location_id} band {band}")
                if reference_profile is not None and pair_profiles[0] != reference_profile:
                    raise OSCDDataError(f"RGB channel grid mismatch for {location_id} band {band}")
                profiles[band] = pair_profiles[0]
                if reference_profile is None:
                    reference_profile = pair_profiles[0]
                t1_arrays.append(arrays[0])
                t2_arrays.append(arrays[1])
        reference = profiles[BIT_RGB_BANDS[0]]
        if any(array.shape != (reference["height"], reference["width"])
               for array in [*t1_arrays, *t2_arrays]):
            raise OSCDDataError(f"Selected RGB array dimensions differ for {location_id}")
        t1 = np.stack(t1_arrays).astype(np.float32, copy=False)
        t2 = np.stack(t2_arrays).astype(np.float32, copy=False)

        mask_path = _label_path(self.root, official_split, location_id)
        mask_raw, mask_values, mask_dtype, png_mode, png_gray_levels = _read_mask(mask_path)
        if mask_raw.shape != (reference["height"], reference["width"]):
            raise OSCDDataError(f"Mask dimensions do not match image pair for {location_id}")
        mask = torch.from_numpy(np.ascontiguousarray(mask_raw == 2)).long()
        dates_path = image_root / "dates.txt"
        dates = [line.strip().split(":", 1)[-1].strip() for line in dates_path.read_text().splitlines() if line.strip()]
        if len(dates) != 2:
            raise OSCDDataError(f"Expected two dates in {dates_path}")
        metadata = {
            "t1_band_paths": {band: _project_relative(t1_dir / f"{band}.tif") for band in BIT_RGB_BANDS},
            "t2_band_paths": {band: _project_relative(t2_dir / f"{band}.tif") for band in BIT_RGB_BANDS},
            "mask_path": _project_relative(mask_path),
            "dates": dates,
            "bands": list(BIT_RGB_BANDS),
            "original_band_count": len(OSCD_BANDS),
            "width": reference["width"], "height": reference["height"],
            "crs": reference["crs"],
            "transform": list(reference["transform"]) if reference["crs"] else None,
            "resolution": list(reference["resolution"]) if reference["crs"] else None,
            "nominal_rectified_resolution_m": 10,
            "dtype_on_disk": reference["dtype"], "nodata": reference["nodata"],
            "native_band_profiles": native_profiles,
            "mask_format": "single-band TIFF", "mask_dtype": mask_dtype,
            "mask_unique_values": mask_values,
            "mask_class_mapping": {"1": 0, "2": 1},
            "visualization_png_mode": png_mode,
            "visualization_png_grayscale_levels": png_gray_levels,
            "image_layout": "separate single-band TIFFs in imgs_1_rect/imgs_2_rect",
            "georeferencing_note": "Rectified TIFFs have no CRS/geotransform; registration and nominal 10 m grid are documented by OSCD README.",
            "bit_normalization": "explicit bit_inputs(quantification_value=10000), clip reflectance to [0,1], then map to [-1,1]",
        }
        return OSCDSample(
            images=torch.from_numpy(np.ascontiguousarray(np.stack([t1, t2]))),
            mask=mask,
            location_id=location_id,
            split=self.split,
            official_split=official_split,
            metadata=metadata,
        )
