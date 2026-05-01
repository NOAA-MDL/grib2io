"""
Unit tests for the grib2io CLI entry point.

Tests cover:
- ``grib2io kerchunk`` with a real GRIB2 test file, verifying JSON output
- ``--output-format parquet`` option
- ``--filters`` option with key=value pairs
- Error cases: no files, invalid format, invalid filter syntax

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import json
import os

import pytest

from grib2io.cli.main import main
from grib2io.cli.kerchunk import _parse_filters

INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gfs_jpeg_path():
    """Absolute path to the gfs.jpeg.grib2 test file."""
    return os.path.join(INPUT_DATA, "gfs.jpeg.grib2")


@pytest.fixture
def gfs_complex_path():
    """Absolute path to the gfs.complex.grib2 test file."""
    return os.path.join(INPUT_DATA, "gfs.complex.grib2")


@pytest.fixture
def tmp_output(tmp_path):
    """Return a helper that builds output paths inside a temp directory."""
    def _make(name):
        return str(tmp_path / name)
    return _make


# ===========================================================================
# JSON output tests (Requirements 7.1, 7.2)
# ===========================================================================


class TestKerchunkJsonOutput:
    """Test ``grib2io kerchunk`` producing JSON output."""

    def test_json_output_created(self, gfs_jpeg_path, tmp_output):
        """kerchunk subcommand creates a valid JSON reference file.

        Validates: Requirements 7.1, 7.2
        """
        out = tmp_output("refs.json")
        main(["kerchunk", "--output", out, gfs_jpeg_path])

        assert os.path.isfile(out), f"JSON output not created at {out}"

        with open(out) as f:
            data = json.load(f)

        assert data["version"] == 1
        assert "refs" in data
        assert ".zgroup" in data["refs"]

    def test_json_output_default_format(self, gfs_jpeg_path, tmp_output):
        """Default output format is JSON when --output-format is omitted.

        Validates: Requirement 7.2
        """
        out = tmp_output("default.json")
        main(["kerchunk", "--output", out, gfs_jpeg_path])

        with open(out) as f:
            data = json.load(f)

        assert data["version"] == 1

    def test_json_output_contains_variable_refs(self, gfs_jpeg_path, tmp_output):
        """JSON output contains .zarray and .zattrs for at least one variable."""
        out = tmp_output("refs.json")
        main(["kerchunk", "--output", out, gfs_jpeg_path])

        with open(out) as f:
            data = json.load(f)

        refs = data["refs"]
        zarray_keys = [k for k in refs if k.endswith("/.zarray")]
        assert len(zarray_keys) > 0, "No variable .zarray keys in output"

    def test_multiple_files(self, gfs_jpeg_path, gfs_complex_path, tmp_output):
        """kerchunk subcommand accepts multiple GRIB2 files.

        Validates: Requirement 7.1
        """
        out = tmp_output("multi.json")
        main(["kerchunk", "--output", out, gfs_jpeg_path, gfs_complex_path])

        assert os.path.isfile(out)
        with open(out) as f:
            data = json.load(f)

        assert data["version"] == 1
        assert len(data["refs"]) > 1


# ===========================================================================
# Parquet output tests (Requirement 7.3)
# ===========================================================================


def _has_parquet_engine():
    """Check if a Parquet engine is available."""
    try:
        import fastparquet  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        pass
    return False


@pytest.mark.skipif(
    not _has_parquet_engine(),
    reason="Parquet engine (fastparquet or pyarrow) not installed",
)
class TestKerchunkParquetOutput:
    """Test ``grib2io kerchunk --output-format parquet``."""

    def test_parquet_output_created(self, gfs_jpeg_path, tmp_output):
        """--output-format parquet creates a Parquet reference directory.

        Validates: Requirement 7.3
        """
        out = tmp_output("refs_parquet")
        main([
            "kerchunk",
            "--output-format", "parquet",
            "--output", out,
            gfs_jpeg_path,
        ])

        assert os.path.isdir(out), f"Parquet output directory not created at {out}"

        contents = os.listdir(out)
        parq_files = [f for f in contents if f.endswith(".parq")]
        assert len(parq_files) > 0, f"No .parq files found. Contents: {contents}"


# ===========================================================================
# Filters tests (Requirement 7.4)
# ===========================================================================


class TestKerchunkFilters:
    """Test ``grib2io kerchunk --filters key=value``."""

    def test_filters_applied(self, gfs_jpeg_path, tmp_output):
        """--filters restricts which messages appear in the manifest.

        Validates: Requirement 7.4
        """
        # Generate without filters
        out_all = tmp_output("all.json")
        main(["kerchunk", "--output", out_all, gfs_jpeg_path])

        with open(out_all) as f:
            data_all = json.load(f)

        # Generate with a filter that selects a specific variable
        out_filtered = tmp_output("filtered.json")
        main([
            "kerchunk",
            "--filters", "shortName=TMP",
            "--output", out_filtered,
            gfs_jpeg_path,
        ])

        with open(out_filtered) as f:
            data_filtered = json.load(f)

        # Filtered output should have fewer or equal refs
        assert len(data_filtered["refs"]) <= len(data_all["refs"])

        # Filtered output should still be a valid manifest
        assert data_filtered["version"] == 1
        assert ".zgroup" in data_filtered["refs"]

    def test_filters_multiple_key_value_pairs(self, tmp_output):
        """Multiple key=value filters can be provided.

        Validates: Requirement 7.4
        """
        gfs_path = os.path.join(INPUT_DATA, "gfs.t00z.pgrb2.1p00.f024")
        out = tmp_output("multi_filter.json")
        main([
            "kerchunk",
            "--filters", "shortName=TMP", "typeOfFirstFixedSurface=100",
            "--output", out,
            gfs_path,
        ])

        assert os.path.isfile(out)
        with open(out) as f:
            data = json.load(f)

        assert data["version"] == 1


# ===========================================================================
# _parse_filters unit tests
# ===========================================================================


class TestParseFilters:
    """Unit tests for the _parse_filters helper."""

    def test_empty_filters(self):
        assert _parse_filters(None) == {}
        assert _parse_filters([]) == {}

    def test_single_string_filter(self):
        result = _parse_filters(["shortName=TMP"])
        assert result == {"shortName": "TMP"}

    def test_numeric_value_conversion(self):
        result = _parse_filters(["level=500"])
        assert result == {"level": 500}
        assert isinstance(result["level"], int)

    def test_float_value_conversion(self):
        result = _parse_filters(["value=1.5"])
        assert result == {"value": 1.5}
        assert isinstance(result["value"], float)

    def test_multiple_filters(self):
        result = _parse_filters(["shortName=TMP", "level=500"])
        assert result == {"shortName": "TMP", "level": 500}

    def test_invalid_filter_exits(self):
        """Filter without '=' causes sys.exit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            _parse_filters(["badfilter"])
        assert exc_info.value.code == 2

    def test_empty_key_exits(self):
        """Filter with empty key (e.g. '=value') causes sys.exit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            _parse_filters(["=value"])
        assert exc_info.value.code == 2

    def test_value_with_equals(self):
        """Filter value containing '=' is handled correctly."""
        result = _parse_filters(["key=val=ue"])
        assert result == {"key": "val=ue"}


# ===========================================================================
# Error case tests (Requirement 7.5)
# ===========================================================================


class TestKerchunkErrors:
    """Test CLI error handling."""

    def test_no_files_exits_with_code_2(self):
        """No files provided prints usage and exits with code 2.

        Validates: Requirement 7.5
        """
        with pytest.raises(SystemExit) as exc_info:
            main(["kerchunk"])
        assert exc_info.value.code == 2

    def test_no_subcommand_exits_with_code_2(self):
        """No subcommand prints help and exits with code 2."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_invalid_output_format_exits_with_code_2(self):
        """Invalid --output-format exits with code 2.

        Validates: Requirement 7.5
        """
        with pytest.raises(SystemExit) as exc_info:
            main([
                "kerchunk",
                "--output-format", "csv",
                "tests/input_data/gfs.jpeg.grib2",
            ])
        assert exc_info.value.code == 2

    def test_invalid_filter_syntax_exits_with_code_2(self, gfs_jpeg_path):
        """Invalid --filters syntax exits with code 2.

        Validates: Requirement 7.5
        """
        with pytest.raises(SystemExit) as exc_info:
            main([
                "kerchunk",
                "--filters", "badfilter",
                "--output", "/dev/null",
                gfs_jpeg_path,
            ])
        assert exc_info.value.code == 2

    def test_nonexistent_file_raises_error(self, tmp_output):
        """Non-existent GRIB2 file returns non-zero exit code."""
        out = tmp_output("out.json")
        result = main([
            "kerchunk",
            "--output", out,
            "/nonexistent/path/file.grib2",
        ])
        assert result == 2


# ===========================================================================
# main() dispatcher tests
# ===========================================================================


class TestMainDispatcher:
    """Test the top-level main() dispatcher."""

    def test_main_kerchunk_dispatches(self, gfs_jpeg_path, tmp_output):
        """main() dispatches 'kerchunk' subcommand correctly."""
        out = tmp_output("dispatch.json")
        main(["kerchunk", "--output", out, gfs_jpeg_path])
        assert os.path.isfile(out)

    def test_main_unknown_command_exits(self):
        """main() with unknown subcommand exits with code 2."""
        with pytest.raises(SystemExit) as exc_info:
            main(["unknown_command"])
        assert exc_info.value.code == 2
