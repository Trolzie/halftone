# Contributing

Thanks for your interest in improving **halftone**!

## Development setup

```bash
git clone https://github.com/Trolzie/halftone.git
cd halftone
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the tests

```bash
pytest
```

Please add or update tests in `tests/` for any behaviour change. The existing
tests in `tests/test_core.py` are a good template — they render solid-tone
images and assert on the resulting ink coverage.

## Regenerating the example images

```bash
python examples/generate_demo.py
```

## Code style

- Keep the public API small: `halftone()` and `HalftoneConfig` are the surface.
- Match the surrounding style — type hints, docstrings explaining the *why*.
- Prefer NumPy for per-pixel work and Pillow for drawing/compositing.

## Submitting changes

1. Open an issue describing the change if it's non-trivial.
2. Branch, commit, and open a pull request against `main`.
3. Make sure `pytest` passes.

## Ideas / roadmap

- Alternative dot shapes (lines, ellipses, squares).
- FM / stochastic screening as an option.
