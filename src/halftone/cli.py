"""Command-line interface for the halftone renderer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from halftone.core import HalftoneConfig, halftone


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="halftone",
        description="Turn an image into a classic black-and-white halftone print.",
    )
    parser.add_argument("input", type=Path, help="path to the source image")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output path (default: <input>_halftone.png next to the source)",
    )
    parser.add_argument(
        "-c",
        "--cell-size",
        type=int,
        default=HalftoneConfig.cell_size,
        metavar="PX",
        help="dot spacing in source pixels; smaller = finer screen (default: %(default)s)",
    )
    parser.add_argument(
        "-s",
        "--scale",
        type=int,
        default=HalftoneConfig.scale,
        help="supersampling factor for smooth dot edges (default: %(default)s)",
    )
    parser.add_argument(
        "-a",
        "--angle",
        type=float,
        default=HalftoneConfig.angle,
        metavar="DEG",
        help="screen angle in degrees (default: %(default)s)",
    )
    parser.add_argument(
        "-g",
        "--gamma",
        type=float,
        default=HalftoneConfig.gamma,
        help="tone curve; >1 lightens midtones, <1 darkens (default: %(default)s)",
    )
    parser.add_argument(
        "--max-dot",
        type=float,
        default=HalftoneConfig.max_dot,
        help="max dot diameter as a multiple of cell size (default: %(default)s)",
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="white ink on black paper instead of black on white",
    )
    return parser


def _default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_halftone.png")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    config = HalftoneConfig(
        cell_size=args.cell_size,
        scale=args.scale,
        angle=args.angle,
        gamma=args.gamma,
        max_dot=args.max_dot,
        ink=255 if args.invert else 0,
        background=0 if args.invert else 255,
    )

    try:
        with Image.open(args.input) as image:
            result = halftone(image, config)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = args.output or _default_output(args.input)
    result.save(output)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
