"""Sentinel-1 SAR fallback analysis, multi-sensor agreement, and fusion evidence scoring."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import io
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
import rasterio
from rasterio.windows import from_bounds


SAR_DEFAULT_RASTER = Path("data/processed/sar/aoi_test/s1_aoi_terrain_corrected.tif")
SAR_ACQUISITION_TIMESTAMP = "2025-03-27T00:54:06Z"
SAR_SENSOR = "Sentinel-1"
SAR_PLATFORM = "Sentinel-1A"
SAR_MODE = "IW GRD High Resolution"
SAR_POLARIZATIONS = ["VV", "VH"]
SAR_PROVENANCE = (
    "CDSE L1 GRDH (2025-03-27T00:54:06Z) -> ESA SNAP precise orbit -> "
    "radiometric calibration to Sigma0 -> Range-Doppler Terrain Correction "
    "with SRTM 1-arcsec DEM onto EPSG:32643 at 10m spatial resolution."
)


@dataclass(frozen=True)
class SAREvidenceMetrics:
    mean_vv_db: float
    mean_vh_db: float
    mean_vv_evidence: float
    mean_vh_evidence: float
    mean_sar_evidence: float
    level: str  # "HIGH" or "LOW"


@dataclass(frozen=True)
class CandidateEvidenceScore:
    component_id: int
    optical_probability: float
    optical_level: str
    sar_evidence: float
    sar_level: str
    sensor_agreement: str
    data_quality: float
    evidence_score: float
    is_corroborated: bool
    formula: str
    calibration_status: str


def compute_sar_window_evidence(
    sar_path: str | Path,
    bounds: tuple[float, float, float, float] | list[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Read terrain-corrected SAR data for a geographic bounding box in EPSG:32643.

    Returns:
        vv_raw: 2D linear intensity
        vh_raw: 2D linear intensity
        e_vv: 2D normalized VV evidence in [0, 1]
        e_vh: 2D normalized VH evidence in [0, 1]
        e_sar: 2D SAR change evidence in [0, 1]
    """
    sar_file = Path(sar_path)
    if not sar_file.is_file():
        raise FileNotFoundError(f"SAR terrain-corrected raster not found: {sar_file}")

    with rasterio.open(sar_file) as src:
        win = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], src.transform)
        vv_raw = src.read(1, window=win).astype(np.float32)
        vh_raw = src.read(2, window=win).astype(np.float32)

    # Convert linear intensity to decibels with safe epsilon
    vv_db = 10.0 * np.log10(np.maximum(vv_raw, 1e-7))
    vh_db = 10.0 * np.log10(np.maximum(vh_raw, 1e-7))

    # Physical normalization:
    # VV typical dynamic range: -25 dB (bare soil/water) to -3 dB (double-bounce urban/rough)
    # VH typical dynamic range: -32 dB (smooth ground) to -10 dB (vegetation/complex scatterers)
    e_vv = np.clip((vv_db - (-25.0)) / ((-3.0) - (-25.0)), 0.0, 1.0).astype(np.float32)
    e_vh = np.clip((vh_db - (-32.0)) / ((-10.0) - (-32.0)), 0.0, 1.0).astype(np.float32)

    # SAR change/structural evidence combines double-bounce VV intensity (65%) with cross-pol VH (35%)
    e_sar = np.clip(0.65 * e_vv + 0.35 * e_vh, 0.0, 1.0).astype(np.float32)

    return vv_raw, vh_raw, e_vv, e_vh, e_sar


def compute_sensor_agreement(
    optical_prob: np.ndarray,
    sar_evidence: np.ndarray,
    optical_threshold: float = 0.70,
    sar_threshold: float = 0.55,
) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    """Compute pixel-level multi-sensor agreement between optical probability and SAR evidence.

    Returns:
        spatial_agreement: continuous metric [0, 1] (harmonic mean of optical and SAR)
        categorical_agreement: uint8 map:
            3 = HIGH AGREEMENT (High Optical & High SAR)
            2 = OPTICAL-ONLY (High Optical & Low SAR)
            1 = SAR-ONLY (Low Optical & High SAR)
            0 = NO STRONG EVIDENCE (Low Optical & Low SAR)
        counts: dictionary of pixel counts per category
    """
    opt = np.clip(optical_prob, 0.0, 1.0).astype(np.float32)
    sar = np.clip(sar_evidence, 0.0, 1.0).astype(np.float32)

    # Continuous harmonic agreement: 2 * (opt * sar) / (opt + sar + eps)
    spatial_agreement = (2.0 * opt * sar / (opt + sar + 1e-6)).astype(np.float32)

    high_opt = opt >= optical_threshold
    high_sar = sar >= sar_threshold

    categorical = np.zeros(opt.shape, dtype=np.uint8)
    categorical[high_opt & high_sar] = 3  # High Agreement
    categorical[high_opt & ~high_sar] = 2  # Optical Only
    categorical[~high_opt & high_sar] = 1  # SAR Only
    categorical[~high_opt & ~high_sar] = 0  # No Strong Evidence

    counts = {
        "high_agreement": int(np.count_nonzero(categorical == 3)),
        "optical_only": int(np.count_nonzero(categorical == 2)),
        "sar_only": int(np.count_nonzero(categorical == 1)),
        "no_strong_evidence": int(np.count_nonzero(categorical == 0)),
    }

    return spatial_agreement, categorical, counts


def compute_candidate_fusion_score(
    mean_optical_prob: float,
    mean_sar_evidence: float,
    data_quality: float = 1.0,
    optical_threshold: float = 0.70,
    sar_threshold: float = 0.55,
) -> tuple[str, str, str, float]:
    """Calculate deterministic fusion evidence score and agreement categorization.

    Formula:
        score = 0.45 * optical + 0.25 * sar + 0.15 * agreement_factor + 0.15 * quality

    Returns:
        optical_level ("HIGH" / "LOW"),
        sar_level ("HIGH" / "LOW"),
        agreement_label ("HIGH AGREEMENT" / "OPTICAL-ONLY" / "SAR-ONLY" / "NO STRONG EVIDENCE"),
        evidence_score (float in 0..100)
    """
    e_opt = float(np.clip(mean_optical_prob, 0.0, 1.0))
    e_sar = float(np.clip(mean_sar_evidence, 0.0, 1.0))
    q = float(np.clip(data_quality, 0.0, 1.0))

    opt_level = "HIGH" if e_opt >= optical_threshold else "LOW"
    sar_level = "HIGH" if e_sar >= sar_threshold else "LOW"

    if opt_level == "HIGH" and sar_level == "HIGH":
        agreement_label = "HIGH AGREEMENT"
    elif opt_level == "HIGH":
        agreement_label = "OPTICAL-ONLY"
    elif sar_level == "HIGH":
        agreement_label = "SAR-ONLY"
    else:
        agreement_label = "NO STRONG EVIDENCE"

    # Harmonic agreement term
    agreement_factor = 2.0 * e_opt * e_sar / (e_opt + e_sar + 1e-6)

    score_pct = round(100.0 * (0.45 * e_opt + 0.25 * e_sar + 0.15 * agreement_factor + 0.15 * q), 1)
    return opt_level, sar_level, agreement_label, score_pct


def render_sar_preview(array_2d: np.ndarray, colormap: str = "sar_evidence") -> bytes:
    """Render a 2D float array in [0, 1] as a PNG preview image."""
    height, width = array_2d.shape
    norm = np.clip(array_2d, 0.0, 1.0).astype(np.float32)

    rgba = np.zeros((height, width, 4), dtype=np.uint8)

    if colormap == "sar_grayscale":
        # Standard SAR radar backscatter display (monochrome)
        intensity = (norm * 255.0).astype(np.uint8)
        rgba[..., 0] = intensity
        rgba[..., 1] = intensity
        rgba[..., 2] = intensity
        rgba[..., 3] = 255
    elif colormap == "sar_evidence":
        # Radar change evidence colormap: dark slate to cyan to bright amber
        stops = (
            (0.0, (18, 30, 49)),
            (0.35, (41, 98, 126)),
            (0.55, (46, 175, 170)),
            (0.75, (230, 160, 40)),
            (1.0, (255, 230, 100)),
        )
        for channel in range(3):
            rgba[..., channel] = np.interp(
                norm,
                [stop[0] for stop in stops],
                [stop[1][channel] for stop in stops],
            ).astype(np.uint8)
        rgba[..., 3] = 240
    elif colormap == "sensor_agreement":
        # Categorical sensor agreement map:
        # 3 (High Agreement) -> Vibrant Emerald Teal (#2ECC71)
        # 2 (Optical Only)   -> Amber / Gold (#F39C12)
        # 1 (SAR Only)       -> Deep Violet (#9B59B6)
        # 0 (Low / None)     -> Transparent / Subtle Slate
        cat = array_2d.astype(np.uint8)
        rgba[cat == 3] = (46, 204, 113, 230)  # High agreement
        rgba[cat == 2] = (243, 156, 18, 200)  # Optical only
        rgba[cat == 1] = (155, 89, 182, 190)  # SAR only
        rgba[cat == 0] = (20, 24, 30, 0)      # Transparent background

    output = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(output, format="PNG", optimize=True)
    return output.getvalue()
