import numpy as np
import pytest
from PIL import Image

from halftone import HalftoneConfig, halftone


def _solid(value: int, size: tuple[int, int] = (64, 64)) -> Image.Image:
    return Image.new("L", size, value)


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


@pytest.mark.parametrize("bad", [{"cell_size": 0}, {"scale": 0}, {"max_dot": 0}, {"gamma": 0}])
def test_invalid_config_rejected(bad):
    with pytest.raises(ValueError):
        HalftoneConfig(**bad)
