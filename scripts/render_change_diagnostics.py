"""Render a Pillow-only four-panel engineering diagnostic for Phase 6."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio
from PIL import Image, ImageDraw


def _read(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as src:
        values = src.read(1, masked=True)
    data = np.asarray(values.data, dtype=np.float32)
    valid = ~np.ma.getmaskarray(values) & np.isfinite(data)
    return data, valid


def _rgb(path: Path, style: str) -> tuple[Image.Image, str]:
    values, valid = _read(path)
    if style == "ndvi":
        low, high = -1.0, 1.0
        scaled = np.clip((values - low) / (high - low), 0, 1)
        # Brown -> yellow -> green for low to high vegetation index.
        stops = np.array([[120, 72, 35], [238, 220, 120], [25, 130, 55]], dtype=np.float32)
        color = _interpolate(stops, scaled)
        scale_text = "scale: -1 to +1 (brown to green)"
    elif style == "delta":
        valid_abs = np.abs(values[valid])
        limit = float(np.percentile(valid_abs, 98)) if valid_abs.size else 1.0
        limit = max(limit, 1e-6)
        scaled = np.clip(values / limit, -1, 1)
        color = np.empty((*values.shape, 3), dtype=np.float32)
        negative = scaled < 0
        # Negative changes blue, zero white, positive changes red.
        color[:] = 255
        amount = np.abs(scaled)[..., None]
        target = np.where(negative[..., None], np.array([35, 80, 190]), np.array([200, 45, 35]))
        color = color * (1 - amount) + target * amount
        scale_text = f"scale: +/-{limit:.4g} (98th percentile; blue decrease, red increase)"
    elif style == "probability":
        valid_values = values[valid]
        high = float(np.percentile(valid_values, 99)) if valid_values.size else 1.0
        high = max(high, 1e-8)
        scaled = np.clip(values / high, 0, 1)
        color = _interpolate(
            np.array([[20, 20, 55], [30, 110, 170], [250, 220, 80]], dtype=np.float32),
            scaled,
        )
        scale_text = f"scale: 0 to p99={high:.4g} (display stretch)"
    else:
        raise ValueError(f"Unknown diagnostic style: {style}")
    color[~valid] = 0
    return Image.fromarray(np.clip(color, 0, 255).astype(np.uint8), mode="RGB"), scale_text


def _interpolate(stops: np.ndarray, x: np.ndarray) -> np.ndarray:
    positions = x * (len(stops) - 1)
    left = np.minimum(positions.astype(np.int32), len(stops) - 2)
    fraction = (positions - left)[..., None]
    return stops[left] * (1 - fraction) + stops[left + 1] * fraction


def render(ndvi_t1: Path, ndvi_t2: Path, delta: Path, probability: Path, output: Path) -> Path:
    panels = [
        ("NDVI T1", ndvi_t1, "ndvi"),
        ("NDVI T2", ndvi_t2, "ndvi"),
        ("Delta NDVI = T2 - T1", delta, "delta"),
        ("BIT change probability", probability, "probability"),
    ]
    rendered = []
    grid = None
    for title, path, style in panels:
        with rasterio.open(path) as src:
            this_grid = (src.width, src.height, src.crs, src.transform)
        if grid is None:
            grid = this_grid
        elif this_grid != grid:
            raise ValueError(f"Diagnostic raster grid mismatch: {path}")
        image, scale = _rgb(path, style)
        rendered.append((title, image, scale))

    width, height = rendered[0][1].size
    header = 38
    canvas = Image.new("RGB", (width * 2, (height + header) * 2), "white")
    draw = ImageDraw.Draw(canvas)
    for i, (title, image, scale) in enumerate(rendered):
        x, y = (i % 2) * width, (i // 2) * (height + header)
        draw.text((x + 8, y + 3), title, fill="black")
        draw.text((x + 8, y + 19), scale, fill="black")
        canvas.paste(image, (x, y + header))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndvi-t1", type=Path, required=True)
    parser.add_argument("--ndvi-t2", type=Path, required=True)
    parser.add_argument("--delta", type=Path, required=True)
    parser.add_argument("--bit-probability", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(render(args.ndvi_t1, args.ndvi_t2, args.delta, args.bit_probability, args.output))


if __name__ == "__main__":
    main()
