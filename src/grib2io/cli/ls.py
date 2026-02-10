from __future__ import annotations

import argparse
#import json
import sys
from typing import Any

import grib2io


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "ls",
        help="List (inventory) messages in a GRIB2 file",
        description="Inventory messages in a GRIB2 file",
    )
    p.add_argument("path", help="GRIB2 file")
    #p.add_argument("-l", "--long", action="store_true", help="Show more columns")
    #p.add_argument("--json", action="store_true", help="Output JSON Lines (one object per message)")
    p.set_defaults(func=cmd_ls)


def _safe_get(d: dict[str, Any], *keys: str, default: str = "") -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return default


def cmd_ls(args: argparse.Namespace) -> int:
    # If open() auto-indexes, then just opening will populate the dict.
    try:
        g = grib2io.open(args.path, mode="r", use_index=True, save_index=False)
    except Exception as e:
        print(f"grib2io: failed to open {args.path!r}: {e}", file=sys.stderr)
        return 2

    for msg in g:
        print(msg, flush=True)

#    # Assume your instance variable is something like `g.msgs` or `g.msg_dict`.
#    # Replace `g.msgs` with the real attribute name.
#    msg_index: dict[int, dict[str, Any]] = g.msgs  # <-- CHANGE THIS to your actual dict attribute
#
#    # Stable ordering by message number / offset
#    items = sorted(msg_index.items(), key=lambda kv: kv[0])
#
#    if args.json:
#        for msgnum, meta in items:
#            # ensure msgnum is included even if meta doesn't contain it
#            out = dict(meta)
#            out.setdefault("msgnum", msgnum)
#            print(json.dumps(out, default=str))
#        return 0
#
#    # Human table header
#    if args.long:
#        # Customize these columns to match what you actually store
#        header = f"{'msg':>6} {'discip':>5} {'cat':>3} {'num':>3} {'level':>10} {'vt':>20} {'name':<}"
#    else:
#        header = f"{'msg':>6} {'discip':>5} {'cat':>3} {'num':>3} {'name':<}"
#    print(header)
#
#    for msgnum, meta in items:
#        discip = _safe_get(meta, "discipline", default="")
#        cat = _safe_get(meta, "parameterCategory", "category", default="")
#        num = _safe_get(meta, "parameterNumber", "number", default="")
#        name = _safe_get(meta, "shortName", "name", "parameterName", default="")
#
#        if args.long:
#            level = _safe_get(meta, "typeOfFirstFixedSurface", "level", default="")
#            vt = _safe_get(meta, "validTime", "forecastTime", default="")
#            print(f"{msgnum:6d} {str(discip):>5} {str(cat):>3} {str(num):>3} {str(level):>10} {str(vt):>20} {name}")
#        else:
#            print(f"{msgnum:6d} {str(discip):>5} {str(cat):>3} {str(num):>3} {name}")

    return 0

