"""Exercise GRIB2 I/O using only the installed package and fixture files."""

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import grib2io
import numpy as np


def read_message(path):
    with grib2io.open(path, use_index=False, save_index=False) as source:
        message = source[0]
        values = message.data.copy()
    assert values.shape == message.shape
    assert np.isfinite(values).any()
    return message, values


def check_round_trip(path, original, template, values):
    section5 = np.array([values.size, template, 0, 0, 0, 0, 0], dtype=np.int64)
    if template == 42:
        # CCSDS flags, block size, and reference sample interval.
        section5 = np.append(section5, [8, 16, 128])
    message = grib2io.Grib2Message(
        original.section0.copy(), original.section1.copy(), None,
        original.section3.copy(), original.section4.copy(), section5,
    )
    message.data = values
    message.pack()
    with grib2io.open(path, mode="w") as output:
        output.write(message)
    decoded, decoded_values = read_message(path)
    assert int(decoded.drtn) == template
    np.testing.assert_array_equal(decoded_values, values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--core-only", action="store_true")
    args = parser.parse_args()

    assert Path(grib2io.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert grib2io.has_interpolation is False
    try:
        grib2io.interpolate(None, 0, None, None)
    except ImportError as error:
        assert "NCEPLIBS-ip library not found" in str(error)
    else:
        raise AssertionError("Interpolation should report the missing library")

    original, data = read_message(args.fixtures / "gfs.complex.grib2")
    # Integer-valued nonconstant data makes exact round-trip comparison possible.
    values = (np.arange(data.size, dtype=np.float32) % 32).reshape(data.shape)
    with TemporaryDirectory() as directory:
        path = Path(directory)
        check_round_trip(path / "simple.grib2", original, 0, values)
        if not args.core_only:
            assert grib2io.has_jpeg_support and grib2io.has_png_support and grib2io.has_aec_support
            for name, template in (("jpeg", 40), ("png", 41)):
                message, _ = read_message(args.fixtures / f"gfs.{name}.grib2")
                assert int(message.drtn) == template
            check_round_trip(path / "aec.grib2", original, 42, values)


if __name__ == "__main__":
    main()
