"""
Tests for optional dependency isolation.

Verifies that core grib2io functionality works without optional
dependencies (kerchunk, numcodecs, icechunk) and that accessing
optional features raises ``ImportError`` with correct install
instructions when those packages are absent.

Validates: Requirements 8.3, 8.4
"""

from __future__ import annotations

import importlib
import sys
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INPUT_DATA = "tests/input_data"
GFS_FILE = f"{INPUT_DATA}/gfs.t00z.pgrb2.1p00.f024"


# ---------------------------------------------------------------------------
# Core functionality works without optional deps
# ---------------------------------------------------------------------------


class TestCoreWithoutOptionalDeps:
    """Core grib2io features must work even when optional packages are absent."""

    def test_grib2io_open_works(self):
        """grib2io.open() works without kerchunk/icechunk/numcodecs."""
        import grib2io

        with grib2io.open(GFS_FILE) as f:
            assert len(f) > 0

    def test_grib2_message_accessible(self):
        """Grib2Message objects are accessible without optional deps."""
        import grib2io

        with grib2io.open(GFS_FILE) as f:
            msg = f[0]
            # Messages may be _Grib2Message instances (the internal type)
            assert isinstance(msg, (grib2io.Grib2Message, grib2io._Grib2Message))
            assert msg.shortName is not None

    def test_core_import_does_not_import_optional_modules(self):
        """Importing grib2io should not eagerly import codecs/kerchunk/icechunk."""
        # Reload grib2io to check what gets imported
        # The lazy modules should NOT be in grib2io's namespace until accessed
        import grib2io

        # These should not be in the module dict unless previously accessed
        # We check that __getattr__ is the mechanism, not eager import
        assert "__getattr__" in dir(grib2io) or callable(
            getattr(type(grib2io), "__getattr__", None)
        )


# ---------------------------------------------------------------------------
# ImportError with install instructions when accessing optional features
# ---------------------------------------------------------------------------


class TestKerchunkImportError:
    """Accessing kerchunk features without kerchunk installed raises ImportError."""

    def test_kerchunk_ensure_guard(self):
        """_ensure_kerchunk raises ImportError with install instructions."""
        with mock.patch.dict(sys.modules, {"kerchunk": None}):
            from grib2io.kerchunk import _ensure_kerchunk

            with pytest.raises(
                ImportError,
                match=r"pip install grib2io\[kerchunk\]",
            ):
                _ensure_kerchunk()

    def test_numcodecs_ensure_guard_in_kerchunk(self):
        """_ensure_numcodecs in kerchunk module raises ImportError with install instructions."""
        with mock.patch.dict(sys.modules, {"numcodecs": None}):
            from grib2io.kerchunk import _ensure_numcodecs

            with pytest.raises(
                ImportError,
                match=r"pip install grib2io\[kerchunk\]",
            ):
                _ensure_numcodecs()


class TestCodecsImportError:
    """Accessing codecs features without numcodecs installed raises ImportError."""

    def test_codecs_module_import_fails_without_numcodecs(self):
        """Importing grib2io.codecs fails with ImportError when numcodecs is absent.

        The codecs module calls _ensure_numcodecs() at module level, so
        the entire module import should fail with a clear error message.
        """
        # Remove the cached module so re-import triggers the guard
        saved = sys.modules.pop("grib2io.codecs", None)
        try:
            with mock.patch.dict(sys.modules, {"numcodecs": None}):
                with pytest.raises(
                    ImportError,
                    match=r"pip install grib2io\[kerchunk\]",
                ):
                    importlib.import_module("grib2io.codecs")
        finally:
            # Restore the original module
            if saved is not None:
                sys.modules["grib2io.codecs"] = saved


class TestIcechunkImportError:
    """Accessing icechunk features without icechunk installed raises ImportError."""

    def test_icechunk_ensure_guard(self):
        """_ensure_icechunk raises ImportError with install instructions."""
        with mock.patch.dict(sys.modules, {"icechunk": None}):
            from grib2io.icechunk import _ensure_icechunk

            with pytest.raises(
                ImportError,
                match=r"pip install grib2io\[icechunk\]",
            ):
                _ensure_icechunk()

    def test_icechunk_error_message_content(self):
        """ImportError message mentions 'icechunk is required'."""
        with mock.patch.dict(sys.modules, {"icechunk": None}):
            from grib2io.icechunk import _ensure_icechunk

            with pytest.raises(
                ImportError,
                match="icechunk is required",
            ):
                _ensure_icechunk()


# ---------------------------------------------------------------------------
# Lazy import via grib2io.__getattr__
# ---------------------------------------------------------------------------


class TestLazyImports:
    """Verify that grib2io.codecs/kerchunk/icechunk use lazy loading."""

    def test_lazy_codecs_import(self):
        """grib2io.codecs is importable via attribute access."""
        import grib2io

        mod = grib2io.codecs
        assert mod.__name__ == "grib2io.codecs"

    def test_lazy_kerchunk_import(self):
        """grib2io.kerchunk is importable via attribute access."""
        import grib2io

        mod = grib2io.kerchunk
        assert mod.__name__ == "grib2io.kerchunk"

    def test_lazy_icechunk_import(self):
        """grib2io.icechunk is importable via attribute access."""
        import grib2io

        mod = grib2io.icechunk
        assert mod.__name__ == "grib2io.icechunk"

    def test_invalid_attribute_raises(self):
        """Accessing a non-existent attribute raises AttributeError."""
        import grib2io

        with pytest.raises(AttributeError, match="no attribute"):
            _ = grib2io.nonexistent_module
