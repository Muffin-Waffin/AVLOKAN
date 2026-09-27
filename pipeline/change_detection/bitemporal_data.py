"""Dataset-neutral bitemporal samples and explicit sensor preprocessing.

This module deliberately does not impose a shared radiometric scale on
Sentinel-2 DN and 8-bit aerial RGB. Dataset adapters must choose the relevant
conversion explicitly before passing tensors to BIT.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch


@dataclass(frozen=True)
class BitemporalSample:
    """One aligned pair in native pixel coordinates.

    T1/T2 are channel-first arrays in the source dataset's original value
    domain. ``change_mask`` is binary (0/1) when supervised, and exactly
    ``None`` for unlabeled data such as S2MTCP. No implicit resizing occurs.
    ``resolution_m`` may be absent; registered OSCD arrays have no meaningful
    CRS/geotransform, so their nominal scale is descriptive only.
    """

    sample_id: str
    dataset: str
    location: str
    t1: np.ndarray
    t2: np.ndarray
    change_mask: np.ndarray | None
    height: int
    width: int
    resolution_m: float | None
    sensor: str
    split: str
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        first, second = np.asarray(self.t1), np.asarray(self.t2)
        if first.ndim != 3 or second.ndim != 3:
            raise ValueError("T1 and T2 must be channel-first arrays [C,H,W]")
        if first.shape != second.shape:
            raise ValueError(f"T1/T2 shape mismatch: {first.shape} != {second.shape}")
        if first.shape[-2:] != (self.height, self.width):
            raise ValueError("Declared sample dimensions do not match T1/T2 arrays")
        if self.change_mask is not None:
            mask = np.asarray(self.change_mask)
            if mask.shape != (self.height, self.width):
                raise ValueError("Change mask dimensions do not match T1/T2")
            values = np.unique(mask)
            if not np.isin(values, (0, 1)).all():
                raise ValueError(f"change_mask must be binary 0/1, got {values.tolist()}")
        if not self.sample_id or not self.dataset or not self.sensor or not self.split:
            raise ValueError("sample_id, dataset, sensor, and split must be non-empty")


def normalize_rgb8_for_bit(image: np.ndarray) -> torch.Tensor:
    """Convert HWC uint8 RGB to CHW float32 [-1,1], without S2 scaling.

    Input order is explicitly R,G,B and output channels preserve that order.
    This is not a conversion to Sentinel-2 reflectance or DN.
    """
    values = np.asarray(image)
    if values.ndim != 3 or values.shape[-1] != 3:
        raise ValueError("Expected an HxWx3 RGB image")
    if values.dtype != np.uint8:
        raise ValueError(f"Expected 8-bit RGB, got {values.dtype}; refusing implicit rescaling")
    chw = np.ascontiguousarray(values.transpose(2, 0, 1))
    tensor = torch.from_numpy(chw).to(dtype=torch.float32).div_(127.5).sub_(1.0)
    return tensor


def supervised_rgb_sample(
    *, sample_id: str, location: str, split: str,
    t1_rgb: np.ndarray, t2_rgb: np.ndarray, change_mask: np.ndarray,
    resolution_m: float | None, metadata: dict[str, Any] | None = None,
) -> BitemporalSample:
    """Build an HRSCD-style supervised RGB sample after source files are read.

    File discovery/decoding is intentionally kept outside this constructor
    until the official HRSCD archive's actual layout has been inspected.
    """
    t1 = np.asarray(t1_rgb)
    t2 = np.asarray(t2_rgb)
    mask = np.asarray(change_mask)
    if t1.ndim != 3 or t1.shape[-1] != 3 or t2.shape != t1.shape:
        raise ValueError("Expected spatially aligned HWC RGB T1/T2 arrays")
    if t1.dtype != np.uint8 or t2.dtype != np.uint8:
        raise ValueError("HRSCD RGB inputs must be verified uint8; no implicit scaling")
    if mask.shape != t1.shape[:2]:
        raise ValueError("HRSCD change mask must match the native image grid")
    if not np.isin(np.unique(mask), (0, 1)).all():
        raise ValueError("HRSCD change mask must contain only 0=no-change, 1=change")
    height, width = mask.shape
    return BitemporalSample(
        sample_id=sample_id, dataset="HRSCD", location=location,
        t1=np.ascontiguousarray(t1.transpose(2, 0, 1)),
        t2=np.ascontiguousarray(t2.transpose(2, 0, 1)),
        change_mask=mask.astype(np.uint8, copy=False), height=height, width=width,
        resolution_m=resolution_m, sensor="IGN BD ORTHO RGB", split=split,
        metadata={**(metadata or {}), "source_channel_order": "RGB",
                  "model_channel_mapping": "R->red, G->green, B->blue",
                  "normalization": "uint8 / 127.5 - 1", "crs_georeferencing": "preserve-source-if-present"},
    )


def unlabeled_temporal_sample(
    *, sample_id: str, dataset: str, location: str,
    t1: np.ndarray, t2: np.ndarray, sensor: str, split: str,
    resolution_m: float | None, metadata: dict[str, Any] | None = None,
) -> BitemporalSample:
    """Represent an unlabeled pair without inventing a no-change target."""
    first, second = np.asarray(t1), np.asarray(t2)
    if first.ndim != 3 or first.shape != second.shape:
        raise ValueError("Unlabeled temporal arrays must share [C,H,W] shape")
    height, width = first.shape[-2:]
    return BitemporalSample(
        sample_id=sample_id, dataset=dataset, location=location,
        t1=first, t2=second, change_mask=None, height=height, width=width,
        resolution_m=resolution_m, sensor=sensor, split=split,
        metadata={**(metadata or {}), "supervision": "unlabeled", "pixel_registration": "unverified"},
    )


def adapt_oscd_sample(sample: Any, *, quantification_value: float = 10000.0) -> BitemporalSample:
    """Bridge the existing OSCD loader without changing its bands/normalizer."""
    first, second = sample.bit_inputs(quantification_value=quantification_value)
    t1 = first[0].detach().cpu().numpy()
    t2 = second[0].detach().cpu().numpy()
    mask = sample.mask.detach().cpu().numpy().astype(np.uint8, copy=False)
    height, width = mask.shape
    metadata = dict(sample.metadata)
    metadata.update({"bands": ["B04", "B03", "B02"],
                     "normalization": f"raw DN / {quantification_value:g}, clip [0,1], map [-1,1]",
                     "pixel_coordinates": True, "crs_georeferencing": "not meaningful for registered OSCD"})
    return BitemporalSample(
        sample_id=f"OSCD:{sample.location_id}", dataset="OSCD", location=sample.location_id,
        t1=t1, t2=t2, change_mask=mask, height=height, width=width,
        resolution_m=10.0, sensor="Sentinel-2", split=sample.split, metadata=metadata,
    )


def inventory_s2mtcp_metadata(
    metadata_csv: str | Path, *, array_root: str | Path | None = None,
    scan_values: bool = True,
) -> dict[str, Any]:
    """Inventory S2MTCP pair metadata and optionally inspect existing NPYs.

    It records pair dates and source metadata but never asserts pixelwise
    registration or synthesizes labels. Array shape is reported verbatim;
    axis order must be established from actual files before preprocessing.
    """
    metadata_csv = Path(metadata_csv)
    array_root = Path(array_root) if array_root is not None else metadata_csv.parent
    groups: dict[str, list[dict[str, str]]] = {}
    with metadata_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if not row.get("im_idx") or row.get("pair_idx") not in {"a", "b"}:
                raise ValueError("S2MTCP metadata requires im_idx and pair_idx a/b")
            groups.setdefault(row["im_idx"], []).append(row)
    records = []
    referenced_files: set[str] = set()
    shape_counts: dict[str, int] = {}
    dtype_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    for im_idx, rows in sorted(groups.items(), key=lambda item: int(item[0])):
        by_pair = {row["pair_idx"]: row for row in rows}
        if len(rows) != 2 or set(by_pair) != {"a", "b"}:
            raise ValueError(f"S2MTCP im_idx={im_idx} must have exactly one a and one b record")
        pair = []
        for key in ("a", "b"):
            row = by_pair[key]
            entry: dict[str, Any] = {
                "pair_idx": key,
                "filename": row.get("filename"),
                "date": row.get("date"),
                "time": row.get("time"),
                "system_idx": row.get("system_idx"),
            }
            file_path = array_root / str(row.get("filename", ""))
            referenced_files.add(file_path.name)
            entry["path"] = file_path.as_posix()
            if file_path.is_file():
                array = np.load(file_path, mmap_mode="r", allow_pickle=False)
                if not np.issubdtype(array.dtype, np.number):
                    raise ValueError(f"Non-numeric S2MTCP array: {file_path}")
                shape_key = "x".join(map(str, array.shape))
                shape_counts[shape_key] = shape_counts.get(shape_key, 0) + 1
                dtype_counts[str(array.dtype)] = dtype_counts.get(str(array.dtype), 0) + 1
                if array.ndim == 3:
                    channel_key = str(array.shape[-1])
                    channel_counts[channel_key] = channel_counts.get(channel_key, 0) + 1
                entry.update({"exists": True, "raw_shape": list(array.shape), "dtype": str(array.dtype),
                              "finite": bool(np.isfinite(array).all()) if scan_values else None,
                              "finite_scanned": scan_values})
            else:
                entry["exists"] = False
            pair.append(entry)
        first, second = by_pair["a"], by_pair["b"]
        first_time = S2MTCPDataset._timestamp(first)
        second_time = S2MTCPDataset._timestamp(second)
        if first_time < second_time:
            temporal_order = "a_before_b"
        elif second_time < first_time:
            temporal_order = "b_before_a"
        else:
            temporal_order = "same_timestamp_order_ambiguous"
        distinct_acquisitions = (
            first.get("system_idx") != second.get("system_idx")
            or first.get("date") != second.get("date")
            or first.get("time") != second.get("time")
        )
        if first.get("city_ascii") != second.get("city_ascii") or first.get("country") != second.get("country"):
            raise ValueError(f"S2MTCP a/b metadata location mismatch for im_idx={im_idx}")
        records.append({
            "sample_id": f"S2MTCP:{im_idx}", "dataset": "S2MTCP", "location": first.get("city_ascii"),
            "city": first.get("city"), "country": first.get("country"),
            "coordinates_lon_lat": [first.get("lng"), first.get("lat")],
            "pair_images_a_b": pair, "change_mask": None,
            "change_mask_available": False,
            "distinct_acquisitions_by_metadata": distinct_acquisitions,
            "temporal_order": temporal_order,
            "pixel_registration": "not guaranteed; source states no geometric corrections",
            "resolution_m": 10,
            "sensor": "Sentinel-2 Level-1C",
            "split": "unassigned_unlabeled",
        })
    actual_files = {path.name for path in array_root.glob("*.npy")}
    unreferenced_files = sorted(actual_files - referenced_files)
    return {
        "dataset": "S2MTCP", "source_metadata": metadata_csv.as_posix(),
        "sample_count": len(records), "metadata_row_count": sum(map(len, groups.values())),
        "array_root": array_root.as_posix(), "archive_internal_root": array_root.name,
        "referenced_array_count": len(referenced_files), "actual_npy_file_count": len(actual_files),
        "unreferenced_npy_files": unreferenced_files,
        "shape_counts": shape_counts, "dtype_counts": dtype_counts,
        "observed_channel_counts": channel_counts,
        "observed_array_layout": "extracted files are HxWx14; the final dimension is channel-like",
        "band_axis_order": "channel positions observed; spectral band names/order are undocumented and unverified",
        "supervised_masks": False,
        "normalization": "not applied by inventory",
        "records": records,
    }


class S2MTCPDataset:
    """Read actual S2MTCP NPY pairs in chronological order when timestamps allow.

    The loader preserves all 14 stored channels, exposes no change mask, and
    does not resample, normalize, register, or label the source arrays.
    """

    def __init__(self, metadata_csv: str | Path, array_root: str | Path):
        self.metadata_csv = Path(metadata_csv)
        self.array_root = Path(array_root)
        groups: dict[str, dict[str, dict[str, str]]] = {}
        with self.metadata_csv.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                key, pair = row.get("im_idx"), row.get("pair_idx")
                if not key or pair not in {"a", "b"} or pair in groups.setdefault(key, {}):
                    raise ValueError(f"Invalid or duplicate S2MTCP metadata row: {row}")
                groups[key][pair] = row
        self.records = []
        for key, members in sorted(groups.items(), key=lambda item: int(item[0])):
            if set(members) != {"a", "b"}:
                raise ValueError(f"S2MTCP pair {key} does not have exactly members a and b")
            for member, row in members.items():
                path = self.array_root / row["filename"]
                if not path.is_file():
                    raise FileNotFoundError(f"S2MTCP array is missing: {path}")
            if members["a"].get("city_ascii") != members["b"].get("city_ascii"):
                raise ValueError(f"S2MTCP a/b location metadata mismatch for pair {key}")
            self.records.append((key, members))

    def __len__(self) -> int:
        return len(self.records)

    @staticmethod
    def _timestamp(row: dict[str, str]) -> datetime:
        return datetime.strptime(row["date"] + row["time"].zfill(6), "%Y%m%d%H%M%S")

    def __getitem__(self, index: int) -> BitemporalSample:
        pair_id, members = self.records[index]
        a_row, b_row = members["a"], members["b"]
        a_time, b_time = self._timestamp(a_row), self._timestamp(b_row)
        if a_time < b_time:
            first_key, second_key, order = "a", "b", "a_before_b"
        elif b_time < a_time:
            first_key, second_key, order = "b", "a", "b_before_a"
        else:
            first_key, second_key, order = "a", "b", "same_timestamp_order_ambiguous"
        arrays = []
        for key in (first_key, second_key):
            path = self.array_root / members[key]["filename"]
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            if array.ndim != 3 or array.shape[-1] != 14:
                raise ValueError(f"Expected observed S2MTCP HxWx14 array, got {array.shape} in {path}")
            if not np.issubdtype(array.dtype, np.number) or not np.isfinite(array).all():
                raise ValueError(f"S2MTCP array contains non-numeric or non-finite values: {path}")
            arrays.append(np.ascontiguousarray(array.transpose(2, 0, 1), dtype=np.float32))
        if arrays[0].shape != arrays[1].shape:
            raise ValueError(f"S2MTCP temporal dimensions differ for pair {pair_id}: {arrays[0].shape} vs {arrays[1].shape}")
        height, width = arrays[0].shape[-2:]
        return unlabeled_temporal_sample(
            sample_id=f"S2MTCP:{pair_id}", dataset="S2MTCP", location=a_row.get("city_ascii") or pair_id,
            t1=arrays[0], t2=arrays[1], sensor="Sentinel-2 Level-1C", split="unassigned_unlabeled",
            resolution_m=10.0,
            metadata={
                "height": height, "width": width, "channel_layout": "HWC in source; returned CHW",
                "stored_channel_count": 14, "trailing_channel_semantics": "undocumented; preserved unchanged",
                "spectral_band_names_and_order": "not specified by official file README; do not map by guess",
                "pair_members_a_b": {key: members[key]["filename"] for key in ("a", "b")},
                "a_b_system_indices": {key: members[key].get("system_idx") for key in ("a", "b")},
                "t1_t2_dates": [self._timestamp(members[key]).isoformat() for key in (first_key, second_key)],
                "chronological_order": order,
                "city": a_row.get("city"), "country": a_row.get("country"),
                "coordinates_lon_lat": [a_row.get("lng"), a_row.get("lat")],
                "pixel_registration": "not asserted by loader; no warp applied",
                "normalization": "not applied; source values preserved as float32",
            },
        )


def write_inventory(inventory: dict[str, Any], output: str | Path) -> None:
    """Write a JSON inventory without copying or transforming source data."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
