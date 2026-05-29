"""Core halftone rendering.

Reproduces the classic analog newspaper halftone: a photograph's continuous
gray tones are approximated by a regular grid of black dots whose *size* varies
with local darkness. Big dots in the shadows, tiny dots in the highlights. Seen
from a distance, your eye blends them back into smooth tone.

The grid is rotated to a screen angle (45 degrees is the traditional choice for
a single-color screen, because a 45-degree dot pattern is the least obtrusive to
the human eye) before sampling, then rotated back at the end.

For color, :func:`halftone_cmyk` separates the image into cyan, magenta, yellow
and black inks, screens each at its own rosette angle, and composites the four
screens back to an RGB image -- a visual simulation of four-color process
printing (not color-managed prepress output).
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
        angle: Screen angle in degrees for the monochrome :func:`halftone` path.
            45 is the classic single-screen angle. (Ignored by the color path,
            which uses ``cmyk_angles``.)
        gamma: Tone curve applied to darkness before sizing the dots. >1 lightens
            midtones (smaller dots), <1 darkens them. 1.0 leaves tone untouched.
        max_dot: Maximum dot diameter as a multiple of cell_size. At full
            darkness the dot diameter is ``max_dot * cell_size``. Values above 1
            let neighbouring dots overlap so that shadows can fill in to solid
            ink. The area-linear "ideal" value is ~1.128 (= sqrt(4/pi)); the
            default of 1.4 biases toward richer blacks, as real ink does.
        ink: Grayscale value of the dots for the monochrome path (0 = black).
        background: Grayscale value of the paper (255 = white).
        gcr: Gray-component replacement for the color path, in [0, 1]. Controls
            how much of a color's achromatic (gray) content is carried by the
            black screen instead of an equal mix of C, M and Y. 1.0 (default) is
            full black generation: neutrals and shadows print as clean black.
            Lower values leave more gray in the CMY inks for warmer, richer
            shadows. (Ignored by the monochrome path.)
        cmyk_angles: Screen angles in degrees for the (C, M, Y, K) screens of the
            color path. The default (15, 75, 0, 45) is the classic rosette: the
            30-degree separations between the strong inks minimise moire, and
            yellow takes the 0-degree slot because it is the least visible ink.
            (Ignored by the monochrome path.)
    """

    cell_size: int = 6
    scale: int = 4
    angle: float = 45.0
    gamma: float = 1.0
    max_dot: float = 1.4
    ink: int = 0
    background: int = 255
    gcr: float = 1.0
    cmyk_angles: tuple[float, float, float, float] = (15.0, 75.0, 0.0, 45.0)

    def __post_init__(self) -> None:
        if self.cell_size < 1:
            raise ValueError("cell_size must be >= 1")
        if self.scale < 1:
            raise ValueError("scale must be >= 1")
        if self.max_dot <= 0:
            raise ValueError("max_dot must be > 0")
        if self.gamma <= 0:
            raise ValueError("gamma must be > 0")
        if not 0.0 <= self.gcr <= 1.0:
            raise ValueError("gcr must be between 0 and 1")
        if len(tuple(self.cmyk_angles)) != 4:
            raise ValueError("cmyk_angles must have exactly 4 values (C, M, Y, K)")


def _screen(
    source: Image.Image,
    *,
    angle: float,
    cell: int,
    scale: int,
    gamma: float,
    max_dot: float,
    ink: int,
    background: int,
) -> Image.Image:
    """Screen one grayscale tone image into a single-ink halftone.

    ``source`` is a grayscale (``"L"``) image where *dark = more ink*, exactly
    like a black-and-white photograph. The screen is rotated to ``angle``, a grid
    of ``cell``-pixel cells is walked, and one dot per cell is drawn with its area
    proportional to the cell's darkness. Dots are drawn on a ``scale``x
    supersampled canvas and shrunk back for smooth edges, then the rotation is
    undone and the result cropped to the source size.

    Returns a new ``"L"`` image the same size as ``source``.
    """
    original_size = source.size  # (width, height)

    # Rotate to the screen angle. expand=True keeps every pixel; the corners are
    # padded with the paper colour so they don't bleed ink into the sampling.
    rotated = source.rotate(
        angle, expand=True, resample=Image.BICUBIC, fillcolor=background
    )
    arr = np.asarray(rotated, dtype=np.float32) / 255.0  # 0 = black, 1 = white
    height, width = arr.shape

    canvas = Image.new("L", (width * scale, height * scale), background)
    draw = ImageDraw.Draw(canvas)

    for top in range(0, height, cell):
        for left in range(0, width, cell):
            block = arr[top : top + cell, left : left + cell]
            darkness = 1.0 - float(block.mean())  # 0 = paper, 1 = solid ink
            if gamma != 1.0:
                darkness = darkness**gamma
            if darkness <= 0.0:
                continue

            # Dot AREA should be proportional to darkness (area is what the eye
            # integrates), so the diameter scales with sqrt(darkness).
            diameter = (darkness**0.5) * max_dot * cell * scale
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
                fill=ink,
            )

    # Shrink back down: this is where the supersampled dots gain smooth edges.
    canvas = canvas.resize((width, height), resample=Image.LANCZOS)

    # Undo the screen rotation and crop back to the original frame.
    canvas = canvas.rotate(
        -angle, expand=True, resample=Image.BICUBIC, fillcolor=background
    )
    rotated_w, rotated_h = canvas.size
    left = (rotated_w - original_size[0]) // 2
    top = (rotated_h - original_size[1]) // 2
    return canvas.crop((left, top, left + original_size[0], top + original_size[1]))


def halftone(image: Image.Image, config: HalftoneConfig | None = None) -> Image.Image:
    """Render ``image`` as a classic black-and-white halftone.

    Args:
        image: Any PIL image. It is converted to grayscale internally.
        config: Screen settings. Defaults to :class:`HalftoneConfig`.

    Returns:
        A new grayscale (``"L"``) image the same size as the input.
    """
    cfg = config or HalftoneConfig()
    return _screen(
        image.convert("L"),
        angle=cfg.angle,
        cell=cfg.cell_size,
        scale=cfg.scale,
        gamma=cfg.gamma,
        max_dot=cfg.max_dot,
        ink=cfg.ink,
        background=cfg.background,
    )


def _rgb_to_cmyk(
    image: Image.Image, gcr: float = 1.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Separate an image into C, M, Y, K ink-amount maps in [0, 1].

    PIL's built-in ``convert("CMYK")`` sets K=0 (no black generation), so we
    separate by hand. ``gcr`` (gray-component replacement) scales how much of the
    achromatic content is pulled into the black channel: at 1.0, every gray that
    *can* be replaced by black is, so neutrals print as clean K with little CMY.

    Returns four ``(H, W)`` float32 arrays where 1.0 means full ink coverage.
    """
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    k = gcr * (1.0 - np.maximum(np.maximum(r, g), b))
    denom = 1.0 - k
    # Guard the divide at pure black (k -> 1, denom -> 0): there CMY must be 0.
    safe = denom > 1e-6
    inv = np.where(safe, 1.0 / np.where(safe, denom, 1.0), 0.0)
    c = np.clip((1.0 - r - k) * inv, 0.0, 1.0)
    m = np.clip((1.0 - g - k) * inv, 0.0, 1.0)
    y = np.clip((1.0 - b - k) * inv, 0.0, 1.0)
    return c, m, y, np.clip(k, 0.0, 1.0)


def halftone_cmyk(
    image: Image.Image, config: HalftoneConfig | None = None
) -> Image.Image:
    """Render ``image`` as a four-color (CMYK) process halftone.

    The image is separated into cyan, magenta, yellow and black inks (see
    :func:`_rgb_to_cmyk`), each screened at its own rosette angle from
    ``config.cmyk_angles``, and the four ink screens are composited back to RGB
    with a subtractive (multiply) model. The result is a *visual simulation* of
    four-color process printing -- it reproduces the rosette, the screen angles
    and the black-driven shadows, but it is composited in sRGB/display space and
    is not color-managed prepress output.

    Args:
        image: Any PIL image. It is converted to RGB internally.
        config: Screen settings. Defaults to :class:`HalftoneConfig`.

    Returns:
        A new ``"RGB"`` image the same size as the input.
    """
    cfg = config or HalftoneConfig()
    c, m, y, k = _rgb_to_cmyk(image, cfg.gcr)
    angle_c, angle_m, angle_y, angle_k = cfg.cmyk_angles

    def coverage(channel: np.ndarray, angle: float) -> np.ndarray:
        # Each ink channel (high = more ink) becomes a grayscale tone image where
        # heavy ink reads as dark, so it screens exactly like a B&W photo. The
        # rendered screen is then read back as ink coverage in [0, 1].
        tone = Image.fromarray(
            np.round((1.0 - channel) * 255.0).astype(np.uint8), mode="L"
        )
        screen = _screen(
            tone,
            angle=angle,
            cell=cfg.cell_size,
            scale=cfg.scale,
            gamma=cfg.gamma,
            max_dot=cfg.max_dot,
            ink=0,
            background=255,
        )
        return np.clip(1.0 - np.asarray(screen, dtype=np.float32) / 255.0, 0.0, 1.0)

    cov_c = coverage(c, angle_c)
    cov_m = coverage(m, angle_m)
    cov_y = coverage(y, angle_y)
    cov_k = coverage(k, angle_k)

    # Subtractive ink model: each ink removes its complementary light from the
    # paper, and the black screen darkens all three channels. Overlapping dots at
    # different angles multiply, which is what synthesises the rosette colour mix.
    red = 255.0 * (1.0 - cov_c) * (1.0 - cov_k)
    green = 255.0 * (1.0 - cov_m) * (1.0 - cov_k)
    blue = 255.0 * (1.0 - cov_y) * (1.0 - cov_k)
    rgb = np.clip(np.stack([red, green, blue], axis=-1), 0.0, 255.0).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")
