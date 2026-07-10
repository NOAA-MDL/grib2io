from __future__ import annotations

import argparse
import sys

import grib2io


class ReadIndicesFromStdin(argparse.Action):
    """Action class for "-i" flag"""

    def __call__(self, parser, namespace, values, option_string=None):
        # Error if no stdin
        if sys.stdin.isatty():
            parser.error(f"{option_string} requires piped stdin (no input detected).")

        # Read from stdin
        data = sys.stdin.read()
        indices = [int(line.split(":")[0]) for line in data.split("\n")[:-1]]

        # Write into a attribute
        setattr(namespace, "indices", indices)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "ls",
        help="List (inventory) messages in a GRIB2 file",
        description="Inventory messages in a GRIB2 file",
    )
    p.add_argument("path", help="GRIB2 file")
    p.add_argument(
        "-i",
        "--stdin",
        dest="indices",
        action=ReadIndicesFromStdin,
        nargs=0,
        default=[],
        help="Read grib2io ls output from stdin",
    )
    p.add_argument(
        "-o",
        "--output",
        dest="output",
        metavar="FILE",
        type=str,
        default=None,
        help="Write selected GRIB2 messages to FILE.",
    )

    p.set_defaults(func=cmd_ls)


def cmd_ls(args: argparse.Namespace) -> int:
    # Open GRIB2 file.
    try:
        g = grib2io.open(args.path, mode="r", use_index=True, save_index=False)
    except Exception as e:
        print(f"grib2io: failed to open {args.path!r}: {e}", file=sys.stderr)
        return 2

    if args.output is not None:
        output = grib2io.open(args.output, mode="w")

    # Iterate messages.
    for msg in g[args.indices]:
        print(msg, flush=True)
        # Add any per message action below.
        if args.output:
            output.write(msg)

    if args.output is not None:
        output.close()

    g.close()
    return 0
