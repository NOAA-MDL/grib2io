"""
``grib2io kerchunk`` subcommand
================================

Generate Kerchunk reference manifests from GRIB2 files.
"""

from __future__ import annotations

import argparse
import sys


def _parse_filters(raw_filters: list[str] | None) -> dict:
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


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``kerchunk`` subcommand."""
    p = subparsers.add_parser(
        "kerchunk",
        help="Generate Kerchunk reference manifests from GRIB2 files",
        description="Generate Kerchunk reference manifests from GRIB2 files.",
    )
    p.add_argument(
        "--output-format",
        choices=["json", "parquet"],
        default="json",
        help="Output format (default: json).",
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Output file path. Defaults to 'references.json' or 'references.parquet'.",
    )
    p.add_argument(
        "--filters",
        nargs="+",
        metavar="key=value",
        help="Filter GRIB2 messages by metadata attributes (e.g. --filters shortName=TMP level=500).",
    )
    p.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="One or more GRIB2 file paths.",
    )
    p.set_defaults(func=cmd_kerchunk)


def cmd_kerchunk(args: argparse.Namespace) -> int:
    """Execute the ``kerchunk`` subcommand."""
    # Parse filters
    filters = _parse_filters(args.filters)

    # Determine output path
    output_path = args.output
    if output_path is None:
        if args.output_format == "json":
            output_path = "references.json"
        else:
            output_path = "references.parquet"

    # Import here to keep CLI module lightweight and avoid import-time
    # dependency on numcodecs/kerchunk when just running --help.
    from grib2io.kerchunk import ReferenceGenerator

    try:
        gen = ReferenceGenerator(args.files, filters=filters if filters else None)
        gen.generate()

        if args.output_format == "json":
            gen.to_json(output_path)
        else:
            gen.to_parquet(output_path)

        print(f"Reference manifest written to: {output_path}")
        return 0
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
