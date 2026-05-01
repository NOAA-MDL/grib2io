from __future__ import annotations

import argparse
import sys

import grib2io


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "create-index",
        help="Create a grib2io-formatted GRIB2 index file",
        description="Create a grib2io-formatted GRIB2 index file",
    )
    p.add_argument("path", help="GRIB2 file")
    p.set_defaults(func=cmd_create_index)


def cmd_create_index(args: argparse.Namespace) -> int:

    # Open GRIB2 file.
    try:
        _ = grib2io.open(args.path, mode="r", use_index=False, save_index=True)
    except Exception as e:
        print(f"grib2io: failed to open {args.path!r}: {e}", file=sys.stderr)
        return 2

    return 0
