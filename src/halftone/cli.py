"""Command-line interface for the halftone renderer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from halftone.core import HalftoneConfig, halftone, halftone_cmyk


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="halftone",
        description="Turn an image into a classic halftone print, mono or CMYK color.",
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
        help="screen angle in degrees, monochrome only (default: %(default)s)",
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

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--invert",
        action="store_true",
        help="monochrome: white ink on black paper instead of black on white",
    )
    mode.add_argument(
        "--color",
        action="store_true",
        help="four-color CMYK process halftone (RGB output) instead of monochrome",
    )

    parser.add_argument(
        "--gcr",
        type=float,
        default=HalftoneConfig.gcr,
        help="color: gray-component replacement 0-1; lower keeps richer CMY shadows "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--cmyk-angles",
        type=float,
        nargs=4,
        metavar=("C", "M", "Y", "K"),
        default=list(HalftoneConfig.cmyk_angles),
        help="color: the four rosette screen angles in degrees (default: %(default)s)",
    )
    return parser


def _default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_halftone.png")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        config = HalftoneConfig(
            cell_size=args.cell_size,
            scale=args.scale,
            angle=args.angle,
            gamma=args.gamma,
            max_dot=args.max_dot,
            ink=255 if args.invert else 0,
            background=0 if args.invert else 255,
            gcr=args.gcr,
            cmyk_angles=tuple(args.cmyk_angles),
        )
        with Image.open(args.input) as image:
            result = halftone_cmyk(image, config) if args.color else halftone(image, config)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = args.output or _default_output(args.input)
    result.save(output)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
