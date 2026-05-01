"""
Command-Line Interface for grib2io
===================================

Provides the ``grib2io`` CLI entry point with subcommands for common
operations.  Currently supports:

- ``grib2io kerchunk`` — Generate Kerchunk reference manifests from GRIB2
  files.

Usage
-----
::

    grib2io kerchunk [--output-format json|parquet]
                     [--output PATH]
                     [--filters key=value ...]
                     FILE [FILE ...]
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional


def _parse_filters(raw_filters: Optional[List[str]]) -> dict:
    """Parse ``key=value`` filter strings into a dictionary.

    Parameters
    ----------
    raw_filters : list of str or None
        Each element should be ``"key=value"``.

    Returns
    -------
    dict
        Parsed filter dictionary.

    Raises
    ------
    SystemExit
        If any filter string does not contain exactly one ``=``.
    """
    if not raw_filters:
        return {}

    filters: dict = {}
    for item in raw_filters:
        if "=" not in item:
            print(
                f"error: invalid filter syntax '{item}'. "
                "Expected format: key=value",
                file=sys.stderr,
            )
            sys.exit(2)
        key, _, value = item.partition("=")
        if not key:
            print(
                f"error: invalid filter syntax '{item}'. "
                "Key must not be empty. Expected format: key=value",
                file=sys.stderr,
            )
            sys.exit(2)
        # Try to convert numeric values
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass  # keep as string
        filters[key] = value
    return filters


def kerchunk_cli(args: Optional[List[str]] = None) -> None:
    """CLI handler for the ``grib2io kerchunk`` subcommand.

    Parameters
    ----------
    args : list of str, optional
        Argument list to parse.  Defaults to ``sys.argv`` when *None*.
    """
    parser = argparse.ArgumentParser(
        prog="grib2io kerchunk",
        description="Generate Kerchunk reference manifests from GRIB2 files.",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "parquet"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Output file path. Defaults to 'references.json' or 'references.parquet'.",
    )
    parser.add_argument(
        "--filters",
        nargs="+",
        metavar="key=value",
        help="Filter GRIB2 messages by metadata attributes (e.g. --filters shortName=TMP level=500).",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="One or more GRIB2 file paths.",
    )

    parsed = parser.parse_args(args)

    # Validate: at least one file is required
    if not parsed.files:
        parser.print_usage(sys.stderr)
        print("error: the following arguments are required: FILE", file=sys.stderr)
        sys.exit(2)

    # Parse filters
    filters = _parse_filters(parsed.filters)

    # Determine output path
    output_path = parsed.output
    if output_path is None:
        if parsed.output_format == "json":
            output_path = "references.json"
        else:
            output_path = "references.parquet"

    # Import here to keep CLI module lightweight and avoid import-time
    # dependency on numcodecs/kerchunk when just running --help.
    from grib2io.kerchunk import ReferenceGenerator

    gen = ReferenceGenerator(parsed.files, filters=filters if filters else None)
    gen.generate()

    if parsed.output_format == "json":
        gen.to_json(output_path)
    else:
        gen.to_parquet(output_path)

    print(f"Reference manifest written to: {output_path}")


def main(args: Optional[List[str]] = None) -> None:
    """Top-level CLI dispatcher for ``grib2io``.

    Delegates to subcommand handlers based on the first positional
    argument.

    Parameters
    ----------
    args : list of str, optional
        Argument list to parse.  Defaults to ``sys.argv[1:]`` when *None*.
    """
    parser = argparse.ArgumentParser(
        prog="grib2io",
        description="grib2io command-line tools.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Register the 'kerchunk' subcommand
    subparsers.add_parser(
        "kerchunk",
        help="Generate Kerchunk reference manifests from GRIB2 files.",
        add_help=False,  # kerchunk_cli handles its own --help
    )

    # Parse only the first argument to determine the subcommand
    parsed, remaining = parser.parse_known_args(args)

    if parsed.command == "kerchunk":
        kerchunk_cli(remaining)
    else:
        parser.print_help(sys.stderr)
        sys.exit(2)
