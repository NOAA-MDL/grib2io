from __future__ import annotations

import argparse
import sys

from .create_index import add_parser as add_create_index_parser
from .kerchunk import add_parser as add_kerchunk_parser
from .ls import add_parser as add_ls_parser

COMMANDS = {"create-index", "kerchunk", "ls"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="grib2io", description="Command line utilities for grib2io")
    sub = p.add_subparsers(dest="command", required=True)

    add_ls_parser(sub)
    add_create_index_parser(sub)
    add_kerchunk_parser(sub)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dispatch
    if args.command in COMMANDS:
        return args.func(args)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
