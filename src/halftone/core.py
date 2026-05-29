"""Core halftone rendering.

Reproduces the classic analog newspaper halftone: a photograph's continuous
gray tones are approximated by a regular grid of black dots whose *size* varies
with local darkness. Big dots in the shadows, tiny dots in the highlights. Seen
from a distance, your eye blends them back into smooth tone.

The grid is rotated to a screen angle (45 degrees is the traditional choice for
a single-color screen, because a 45-degree dot pattern is the least obtrusive to
the human eye) before sampling, then rotated back at the end.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw


@dataclass
class HalftoneConfig:
    """Settings controlling the look of the halftone screen.

    Attributes:
        cell_size: Spacing between dot centers, measured in source pixels. This
            is the screen frequency: smaller cells -> finer screen -> more, smaller
            dots. Coarse newspaper screens use large cells; magazines use small.
        scale: Supersampling factor. Dots are drawn on a canvas this many times
            larger than the source, then shrunk back down with Lanczos
            resampling, which gives the dots smooth, anti-aliased edges.
        angle: Screen angle in degrees. 45 is the classic single-screen angle.
        gamma: Tone curve applied to darkness before sizing the dots. >1 lightens
            midtones (smaller dots), <1 darkens them. 1.0 leaves tone untouched.
        max_dot: Maximum dot diameter as a multiple of cell_size. At full
            darkness the dot diameter is ``max_dot * cell_size``. Values above 1
            let neighbouring dots overlap so that shadows can fill in to solid
            ink. The area-linear "ideal" value is ~1.128 (= sqrt(4/pi)); the
            default of 1.4 biases toward richer blacks, as real ink does.
        ink: Grayscale value of the dots (0 = black).
        background: Grayscale value of the paper (255 = white).
    """

    cell_size: int = 6
    scale: int = 4
    angle: float = 45.0
    gamma: float = 1.0
    max_dot: float = 1.4
    ink: int = 0
    background: int = 255

    def __post_init__(self) -> None:
        if self.cell_size < 1:
            raise ValueError("cell_size must be >= 1")
        if self.scale < 1:
            raise ValueError("scale must be >= 1")
        if self.max_dot <= 0:
            raise ValueError("max_dot must be > 0")
        if self.gamma <= 0:
            raise ValueError("gamma must be > 0")


def halftone(image: Image.Image, config: HalftoneConfig | None = None) -> Image.Image:
    """Render ``image`` as a classic black-and-white halftone.

    Args:
        image: Any PIL image. It is converted to grayscale internally.
        config: Screen settings. Defaults to :class:`HalftoneConfig`.

    Returns:
        A new grayscale (``"L"``) image the same size as the input.
    """
    cfg = config or HalftoneConfig()

    gray = image.convert("L")
    original_size = gray.size  # (width, height)

    # Rotate to the screen angle. expand=True keeps every pixel; the corners are
    # padded with the paper colour so they don't bleed ink into the sampling.
    rotated = gray.rotate(
        cfg.angle, expand=True, resample=Image.BICUBIC, fillcolor=cfg.background
    )
    arr = np.asarray(rotated, dtype=np.float32) / 255.0  # 0 = black, 1 = white
    height, width = arr.shape

    cell = cfg.cell_size
    scale = cfg.scale

    canvas = Image.new("L", (width * scale, height * scale), cfg.background)
    draw = ImageDraw.Draw(canvas)

    for top in range(0, height, cell):
        for left in range(0, width, cell):
            block = arr[top : top + cell, left : left + cell]
            darkness = 1.0 - float(block.mean())  # 0 = paper, 1 = solid ink
            if cfg.gamma != 1.0:
                darkness = darkness**cfg.gamma
            if darkness <= 0.0:
                continue

            # Dot AREA should be proportional to darkness (area is what the eye
            # integrates), so the diameter scales with sqrt(darkness).
            diameter = (darkness**0.5) * cfg.max_dot * cell * scale
            radius = diameter / 2.0

            center_x = (left + cell / 2.0) * scale
            center_y = (top + cell / 2.0) * scale
            draw.ellipse(
                [
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                ],
                fill=cfg.ink,
            )

    # Shrink back down: this is where the supersampled dots gain smooth edges.
    canvas = canvas.resize((width, height), resample=Image.LANCZOS)

    # Undo the screen rotation and crop back to the original frame.
    canvas = canvas.rotate(
        -cfg.angle, expand=True, resample=Image.BICUBIC, fillcolor=cfg.background
    )
    rotated_w, rotated_h = canvas.size
    left = (rotated_w - original_size[0]) // 2
    top = (rotated_h - original_size[1]) // 2
    return canvas.crop((left, top, left + original_size[0], top + original_size[1]))
