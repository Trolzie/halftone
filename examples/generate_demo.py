"""Generate the demo images used in the README.

Creates a synthetic source image (a radial gradient with a couple of shapes so
you can see how tone maps to dot size) and renders it at a few screen settings.
Run from the repo root:  python examples/generate_demo.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from halftone import HalftoneConfig, halftone

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


if __name__ == "__main__":
    main()
