"""Create a reproducible, label-free inspection report for staged S2MTCP."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import numpy as np
from scipy.fft import fft2, ifft2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.change_detection.bitemporal_data import S2MTCPDataset, inventory_s2mtcp_metadata


def _percentiles(values: np.ndarray) -> dict[str, float]:
    finite = values[np.isfinite(values)]
    if not finite.size:
        return {key: float("nan") for key in ("min", "max", "mean", "median", "p90", "p95", "p99")}
    p = np.percentile(finite, [50, 90, 95, 99])
    return {"min": float(finite.min()), "max": float(finite.max()), "mean": float(finite.mean()),
            "median": float(p[0]), "p90": float(p[1]), "p95": float(p[2]), "p99": float(p[3])}


def _phase_shift(reference: np.ndarray, moving: np.ndarray) -> tuple[float, float, float]:
    """Return subpixel row/column shift to apply to moving, plus peak/mean response."""
    a, b = reference.astype(np.float64, copy=False), moving.astype(np.float64, copy=False)
    if a.shape != b.shape or a.ndim != 2:
        raise ValueError("Phase correlation requires equal 2D grids")
    if float(a.std()) < 1e-8 or float(b.std()) < 1e-8:
        return float("nan"), float("nan"), 0.0
    a = np.clip((a - np.mean(a)) / (np.std(a) + 1e-12), -5, 5)
    b = np.clip((b - np.mean(b)) / (np.std(b) + 1e-12), -5, 5)
    window = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    cross = fft2(a * window) * np.conj(fft2(b * window))
    cross /= np.maximum(np.abs(cross), 1e-12)
    corr = ifft2(cross).real
    peak = np.unravel_index(np.argmax(corr), corr.shape)
    offsets = []
    for axis, center in enumerate(peak):
        before = list(peak)
        after = list(peak)
        before[axis] = (center - 1) % corr.shape[axis]
        after[axis] = (center + 1) % corr.shape[axis]
        left, middle, right = corr[tuple(before)], corr[peak], corr[tuple(after)]
        denom = left - 2.0 * middle + right
        subpixel = 0.0 if abs(denom) < 1e-12 else 0.5 * (left - right) / denom
        coordinate = float(center) + float(subpixel)
        if coordinate > corr.shape[axis] / 2:
            coordinate -= corr.shape[axis]
        offsets.append(coordinate)
    response = float(corr[peak] / (np.mean(np.abs(corr)) + 1e-12))
    return offsets[0], offsets[1], response


def _pair_analysis(sample) -> dict:
    a, b = sample.t1[:13], sample.t2[:13]
    h, w = a.shape[-2:]
    shifts, correlations, maes, normalized_differences = [], [], [], []
    channel_ranges = []
    for channel in range(13):
        x, y = a[channel].astype(np.float64), b[channel].astype(np.float64)
        shift = _phase_shift(x, y)
        shifts.append(shift)
        correlations.append(float(np.corrcoef(x.ravel(), y.ravel())[0, 1]))
        maes.append(float(np.mean(np.abs(x - y))))
        nd = (y - x) / (np.abs(x) + np.abs(y) + 1e-8)
        normalized_differences.append(nd)
        channel_ranges.append({"channel_index": channel, "a": _percentiles(x), "b": _percentiles(y),
                              "finite_fraction_a": float(np.isfinite(x).mean()),
                              "finite_fraction_b": float(np.isfinite(y).mean()),
                              "zero_fraction_a": float((x == 0).mean()),
                              "zero_fraction_b": float((y == 0).mean())})
    shift_array = np.asarray(shifts)
    nd_all = np.concatenate([item.ravel() for item in normalized_differences])
    absolute_nd = np.abs(nd_all)
    active_a, active_b = a.ravel(), b.ravel()
    relative_mae = float(np.mean(np.abs(active_a - active_b)) /
                         (np.mean((np.abs(active_a) + np.abs(active_b)) / 2) + 1e-8))
    return {
        "sample_id": sample.sample_id, "location": sample.location,
        "country": sample.metadata["country"], "shape_hw": [h, w],
        "pair_members_a_b": sample.metadata["pair_members_a_b"],
        "t1_t2_dates": sample.metadata["t1_t2_dates"],
        "chronological_order": sample.metadata["chronological_order"],
        "pairwise_channel_pearson_median": float(np.median(correlations)),
        "pairwise_channel_pearson_range": [float(np.min(correlations)), float(np.max(correlations))],
        "per_channel_mean_absolute_difference_median": float(np.median(maes)),
        "relative_mae_first_13_channels": relative_mae,
        "normalized_difference_t2_minus_t1": _percentiles(nd_all),
        "fraction_abs_normalized_difference_ge_0_5": float(np.mean(absolute_nd >= 0.5)),
        "fraction_abs_normalized_difference_ge_0_8": float(np.mean(absolute_nd >= 0.8)),
        "phase_correlation": {
            "meaning": "estimated pixel shift to apply to b/t2 to align to a/t1; no warp applied",
            "channel_median_shift_row_col": [float(np.nanmedian(shift_array[:, 0])),
                                              float(np.nanmedian(shift_array[:, 1]))],
            "channel_shift_min_row_col": [float(np.nanmin(shift_array[:, 0])),
                                           float(np.nanmin(shift_array[:, 1]))],
            "channel_shift_max_row_col": [float(np.nanmax(shift_array[:, 0])),
                                           float(np.nanmax(shift_array[:, 1]))],
            "channel_median_peak_to_mean_response": float(np.median(shift_array[:, 2])),
            "channel_shifts": [{"channel_index": i, "row": float(s[0]), "col": float(s[1]),
                                "peak_to_mean_response": float(s[2])} for i, s in enumerate(shifts)],
        },
        "trailing_channel_13": {
            "a_min": float(sample.t1[13].min()), "a_max": float(sample.t1[13].max()),
            "b_min": float(sample.t2[13].min()), "b_max": float(sample.t2[13].max()),
            "a_unique_values": np.unique(sample.t1[13]).tolist()[:32],
            "b_unique_values": np.unique(sample.t2[13]).tolist()[:32],
        },
        "per_channel_value_summary": channel_ranges,
    }


def inspect(metadata: Path, array_root: Path, *, representative_count: int = 24) -> dict:
    inventory = inventory_s2mtcp_metadata(metadata, array_root=array_root, scan_values=False)
    dataset = S2MTCPDataset(metadata, array_root)
    all_names = {path.name for path in array_root.glob("*.npy")}
    referenced = {row["filename"] for _, members in dataset.records for row in members.values()}
    records = []
    shapes, dtypes, trailing_nonzero, pair_grid_mismatch = {}, {}, [], []
    widths, heights = [], []
    for pair_id, members in dataset.records:
        pair_headers = []
        for key in ("a", "b"):
            array = np.load(array_root / members[key]["filename"], mmap_mode="r", allow_pickle=False)
            shape, dtype = tuple(array.shape), str(array.dtype)
            shapes["x".join(map(str, shape))] = shapes.get("x".join(map(str, shape)), 0) + 1
            dtypes[dtype] = dtypes.get(dtype, 0) + 1
            heights.append(shape[0] if len(shape) == 3 else -1)
            widths.append(shape[1] if len(shape) == 3 else -1)
            if len(shape) != 3 or shape[-1] != 14:
                raise ValueError(f"Unexpected S2MTCP array layout {shape}: {members[key]['filename']}")
            if np.any(array[..., 13] != 0):
                trailing_nonzero.append(members[key]["filename"])
            pair_headers.append(shape)
        if pair_headers[0] != pair_headers[1]:
            pair_grid_mismatch.append(pair_id)
    ids = np.linspace(0, len(dataset) - 1, min(representative_count, len(dataset)), dtype=int)
    selected = [dataset[int(index)] for index in sorted(set(ids.tolist()))]
    analyses = [_pair_analysis(sample) for sample in selected]
    dates = []
    order_counts = {"a_before_b": 0, "b_before_a": 0, "same_timestamp": 0}
    same_acquisition = 0
    for _, members in dataset.records:
        first, second = dataset._timestamp(members["a"]), dataset._timestamp(members["b"])
        dates.append(abs((first - second).days))
        if first < second:
            order_counts["a_before_b"] += 1
        elif second < first:
            order_counts["b_before_a"] += 1
        else:
            order_counts["same_timestamp"] += 1
        if members["a"].get("system_idx") == members["b"].get("system_idx"):
            same_acquisition += 1
    # Individual channels sometimes lock onto unrelated texture. Aggregate
    # channel-median shifts per pair, rather than letting one band dominate.
    pair_shifts = np.asarray([analysis["phase_correlation"]["channel_median_shift_row_col"]
                              for analysis in analyses], dtype=float)
    pair_responses = np.asarray([analysis["phase_correlation"]["channel_median_peak_to_mean_response"]
                                 for analysis in analyses], dtype=float)
    displacement_norm = np.linalg.norm(pair_shifts, axis=1)
    normalized_diffs = np.asarray([a["fraction_abs_normalized_difference_ge_0_5"] for a in analyses])
    valid_days = np.sort(np.asarray(dates, dtype=float))
    return {
        "dataset": "S2MTCP", "archive_member_root": "data_S21C/",
        "metadata_pair_count": len(dataset), "metadata_row_count": 2 * len(dataset),
        "metadata_files_referenced": len(referenced), "extracted_npy_files": len(all_names),
        "unreferenced_extracted_files": sorted(all_names - referenced),
        "missing_metadata_files": sorted(referenced - all_names),
        "format": "NumPy NPY; HWC; float64",
        "channel_count": 14, "trailing_channel_13_nonzero_files": trailing_nonzero,
        "channel_semantics": "14th channel is nonzero in some files; meaning is undocumented in the archive README and must remain uninterpreted",
        "resolution_m": 10, "crs_or_transform": None,
        "image_dimensions": {"height_min": int(min(heights)), "height_max": int(max(heights)),
                             "width_min": int(min(widths)), "width_max": int(max(widths)),
                             "unique_shape_count": len(shapes), "shape_counts": shapes,
                             "within_pair_grid_mismatch_count": len(pair_grid_mismatch),
                             "within_pair_grid_mismatch_ids": pair_grid_mismatch},
        "dtype_counts": dtypes,
        "range_and_consistency_sample_count": len(analyses),
        "representative_pair_sampling": "evenly spaced by numeric metadata index across the sorted 1,520 pairs",
        "representative_value_ranges_nodata_similarity_registration": analyses,
        "pair_metadata": {
            "pairs_with_identical_system_idx": same_acquisition,
            "date_order_counts": order_counts,
            "date_gap_days_min_median_max": [float(valid_days[0]), float(np.median(valid_days)),
                                               float(valid_days[-1])],
            "same_day_count": sum(1 for days in dates if days == 0),
            "chronological_order_can_be_established": True,
            "a_b_label_is_chronological": False,
        },
        "registration_aggregate_over_sampled_pairs": {
            "method": "windowed Fourier phase correlation on channels 0..12; per-pair channel-median shift; shift means offset to apply T2 toward T1",
            "no_alignment_warp_applied": True,
            "sampled_pair_count": int(len(pair_shifts)),
            "row_shift_min_median_max": [float(np.min(pair_shifts[:, 0])),
                                           float(np.median(pair_shifts[:, 0])),
                                           float(np.max(pair_shifts[:, 0]))],
            "column_shift_min_median_max": [float(np.min(pair_shifts[:, 1])),
                                              float(np.median(pair_shifts[:, 1])),
                                              float(np.max(pair_shifts[:, 1]))],
            "shift_magnitude_median_max_pixels": [float(np.median(displacement_norm)),
                                                    float(np.max(displacement_norm))],
            "pairs_magnitude_over_1px": int(np.count_nonzero(displacement_norm > 1)),
            "pairs_magnitude_over_2px": int(np.count_nonzero(displacement_norm > 2)),
            "peak_to_mean_response_median": float(np.median(pair_responses)),
            "interpretation": "heuristic only; seasonal/spectral changes and weak texture can bias estimates; no geospatial truth or registration correction is inferred",
        },
        "normalized_difference_extreme_fraction_median_over_sampled_pairs": float(np.median(normalized_diffs)),
        "inventory": inventory,
        "interpretation_note": "Unlabeled descriptive diagnostics only; no supervised metrics or no-change assumption.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--array-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--representatives", type=int, default=24)
    args = parser.parse_args()
    report = inspect(args.metadata, args.array_root, representative_count=args.representatives)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "metadata_pair_count", "extracted_npy_files", "unreferenced_extracted_files",
        "image_dimensions", "dtype_counts", "pair_metadata", "registration_aggregate_over_sampled_pairs",
    )}, indent=2))


if __name__ == "__main__":
    main()
