import numpy as np
import pytest
from PIL import Image

from halftone import HalftoneConfig, halftone, halftone_cmyk
from halftone.core import _rgb_to_cmyk


def _solid(value: int, size: tuple[int, int] = (64, 64)) -> Image.Image:
    return Image.new("L", size, value)


def _solid_rgb(color: tuple[int, int, int], size: tuple[int, int] = (64, 64)) -> Image.Image:
    return Image.new("RGB", size, color)


def test_output_matches_input_size_and_mode():
    src = _solid(128, (100, 70))
    out = halftone(src)
    assert out.size == (100, 70)
    assert out.mode == "L"


def test_white_input_stays_white():
    # No ink should be laid down on a blank white page.
    out = halftone(_solid(255))
    assert np.asarray(out).min() > 250


def test_black_input_is_mostly_ink():
    # A solid black source should fill in to (nearly) solid ink.
    out = halftone(_solid(0))
    assert np.asarray(out).mean() < 30


def test_darker_input_uses_more_ink():
    # Bigger dots for darker tone => lower mean brightness.
    light = np.asarray(halftone(_solid(200))).mean()
    dark = np.asarray(halftone(_solid(60))).mean()
    assert dark < light


def test_invert_swaps_ink_and_paper():
    cfg = HalftoneConfig(ink=255, background=0)
    out = halftone(_solid(255), cfg)  # white source on inverted screen -> black paper
    assert np.asarray(out).mean() < 30


def test_accepts_rgb_input():
    rgb = Image.new("RGB", (48, 48), (90, 90, 90))
    out = halftone(rgb)
    assert out.mode == "L"
    assert out.size == (48, 48)


@pytest.mark.parametrize(
    "bad",
    [
        {"cell_size": 0},
        {"scale": 0},
        {"max_dot": 0},
        {"gamma": 0},
        {"gcr": -0.1},
        {"gcr": 1.5},
        {"cmyk_angles": (1, 2, 3)},
    ],
)
def test_invalid_config_rejected(bad):
    with pytest.raises(ValueError):
        HalftoneConfig(**bad)


# --- CMYK separation -------------------------------------------------------


def _means(color: tuple[int, int, int], gcr: float = 1.0):
    c, m, y, k = _rgb_to_cmyk(_solid_rgb(color), gcr)
    return c.mean(), m.mean(), y.mean(), k.mean()


def test_separation_white_uses_no_ink():
    c, m, y, k = _means((255, 255, 255))
    assert max(c, m, y, k) < 0.02


def test_separation_black_is_pure_k():
    # Pure black goes entirely to the black screen; the divide guard keeps CMY=0.
    c, m, y, k = _means((0, 0, 0))
    assert k > 0.98
    assert max(c, m, y) < 0.02


def test_separation_neutral_gray_is_carried_by_black():
    # Full GCR pulls neutrals to black ink, not a C+M+Y mix.
    c, m, y, k = _means((128, 128, 128))
    assert k > 0.45
    assert max(c, m, y) < 0.02


@pytest.mark.parametrize(
    "color, fires",
    [
        ((255, 0, 0), {"m", "y"}),  # red = magenta + yellow
        ((0, 255, 0), {"c", "y"}),  # green = cyan + yellow
        ((0, 0, 255), {"c", "m"}),  # blue = cyan + magenta
        ((0, 255, 255), {"c"}),  # cyan
        ((255, 0, 255), {"m"}),  # magenta
        ((255, 255, 0), {"y"}),  # yellow
    ],
)
def test_separation_primaries_and_secondaries(color, fires):
    values = dict(zip("cmyk", _means(color)))
    for name, value in values.items():
        if name in fires:
            assert value > 0.9, f"{name} should fire for {color}"
        else:
            assert value < 0.02, f"{name} should be blank for {color}"


def test_gcr_zero_matches_naive_cmy():
    # With gcr=0 no black is generated; gray becomes an equal C+M+Y mix.
    c, m, y, k = _means((128, 128, 128), gcr=0.0)
    assert k < 0.01
    assert min(c, m, y) > 0.4


# --- CMYK halftone rendering ----------------------------------------------


def test_cmyk_output_matches_input_size_and_mode():
    out = halftone_cmyk(_solid_rgb((128, 128, 128), (100, 70)))
    assert out.size == (100, 70)
    assert out.mode == "RGB"


def test_cmyk_white_stays_white():
    out = halftone_cmyk(_solid_rgb((255, 255, 255)))
    assert np.asarray(out).min() > 250


def test_cmyk_black_is_mostly_ink():
    out = halftone_cmyk(_solid_rgb((0, 0, 0)))
    assert np.asarray(out).mean() < 30


def test_cmyk_red_stays_red():
    # Cyan and black never fire for pure red, so the red channel survives intact
    # while magenta/yellow screens darken green and blue.
    arr = np.asarray(halftone_cmyk(_solid_rgb((255, 0, 0)))).astype(np.float32)
    r, g, b = arr[..., 0].mean(), arr[..., 1].mean(), arr[..., 2].mean()
    assert r > 200
    assert r > g and r > b
