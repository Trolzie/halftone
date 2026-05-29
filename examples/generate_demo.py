"""Generate the demo images used in the README.

Creates a synthetic grayscale source (a radial gradient with a couple of shapes
so you can see how tone maps to dot size) and a synthetic color source (a hue
sweep, saturated ink swatches and a neutral gray ramp), then renders them at a
few screen settings. Run from the repo root:  python examples/generate_demo.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from halftone import HalftoneConfig, halftone, halftone_cmyk

HERE = Path(__file__).parent


def make_source(size: int = 480) -> Image.Image:
    """A radial gradient (dark center -> light edges) with two overlaid shapes."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = size / 2.0
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    grad = np.clip(dist / (size * 0.62), 0.0, 1.0) * 255.0
    img = Image.fromarray(grad.astype(np.uint8), mode="L")

    draw = ImageDraw.Draw(img)
    draw.ellipse([size * 0.12, size * 0.12, size * 0.40, size * 0.40], fill=20)
    draw.rectangle([size * 0.60, size * 0.62, size * 0.88, size * 0.88], fill=235)
    return img


def make_color_source(size: int = 480) -> Image.Image:
    """A color test image that exercises every ink and the rosette colour mix.

    Top: a full-saturation hue sweep (smooth colour -> rosette mixing). Middle:
    saturated R/G/B/C/M/Y swatches (so you can see which ink fires for each).
    Bottom: a neutral gray ramp (which full GCR carries on the black screen).
    """
    rgb = np.zeros((size, size, 3), dtype=np.uint8)

    top = int(size * 0.45)
    hue = np.tile(np.linspace(0, 255, size, dtype=np.uint8), (top, 1))
    val = np.repeat(np.linspace(255, 165, top, dtype=np.uint8)[:, None], size, axis=1)
    sat = np.full((top, size), 255, dtype=np.uint8)
    hsv = np.stack([hue, sat, val], axis=-1)
    rgb[:top] = np.asarray(Image.fromarray(hsv, mode="HSV").convert("RGB"))

    mid = int(size * 0.72)
    swatches = [
        (225, 35, 35),   # red
        (35, 195, 70),   # green
        (45, 85, 220),   # blue
        (0, 190, 200),   # cyan
        (210, 45, 170),  # magenta
        (240, 220, 35),  # yellow
    ]
    band = rgb[top:mid]
    seg = size // len(swatches)
    for i, color in enumerate(swatches):
        band[:, i * seg : (i + 1) * seg] = color
    band[:, len(swatches) * seg :] = swatches[-1]

    ramp = np.linspace(0, 255, size, dtype=np.uint8)
    rgb[mid:] = ramp[None, :, None]
    return Image.fromarray(rgb, mode="RGB")


def main() -> None:
    src = make_source()
    src.save(HERE / "source.png")

    variants = {
        "halftone_fine": HalftoneConfig(cell_size=4),
        "halftone_coarse": HalftoneConfig(cell_size=10),
        "halftone_angle0": HalftoneConfig(cell_size=6, angle=0.0),
    }
    for name, cfg in variants.items():
        halftone(src, cfg).save(HERE / f"{name}.png")
        print(f"wrote {name}.png")

    color_src = make_color_source()
    color_src.save(HERE / "source_color.png")
    halftone_cmyk(color_src, HalftoneConfig(cell_size=6)).save(HERE / "demo_color.png")
    print("wrote demo_color.png")


if __name__ == "__main__":
    main()
