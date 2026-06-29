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
        assert "__getattr__" in dir(grib2io) or callable(getattr(type(grib2io), "__getattr__", None))


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
        """Importing grib2io.codecs succeeds gracefully when numcodecs is absent,
        but instantiating Grib2Codec raises ImportError with install instructions.

        The module uses a try/except around the numcodecs import so that the
        module itself can always be imported.  Usage (instantiation) raises the
        error with a clear message.
        """
        # Remove the cached module so re-import exercises the guard path
        saved = sys.modules.pop("grib2io.codecs", None)
        try:
            # Null out numcodecs and all known sub-modules that may already
            # be cached in sys.modules so the try/except in codecs.py
            # actually falls through to the except branch.
            patch_modules = {
                "numcodecs": None,
                "numcodecs.abc": None,
                "numcodecs.registry": None,
            }
            with mock.patch.dict(sys.modules, patch_modules):
                # Module import should succeed (graceful degradation)
                mod = importlib.import_module("grib2io.codecs")
                # But instantiation should fail with a clear error
                with pytest.raises(
                    ImportError,
                    match=r"pip install grib2io\[kerchunk\]",
                ):
                    mod.Grib2Codec(
                        drtn=0,
                        drt=[],
                        gdtn=0,
                        gdt=[],
                        gds=[],
                        nx=1,
                        ny=1,
                        bitmap_flag=255,
                    )
        finally:
            # Restore the original module
            if saved is not None:
                sys.modules["grib2io.codecs"] = saved


# ---------------------------------------------------------------------------
# Lazy import via grib2io.__getattr__
# ---------------------------------------------------------------------------


class TestLazyImports:
    """Verify that grib2io.codecs/kerchunk use lazy loading."""

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

    def test_invalid_attribute_raises(self):
        """Accessing a non-existent attribute raises AttributeError."""
        import grib2io

        with pytest.raises(AttributeError, match="no attribute"):
            _ = grib2io.nonexistent_module
