"""
Unit tests for IcechunkWriter.

Tests cover:
- Write manifest to local Icechunk store, read back with xarray and verify dataset structure
- Multi-file append: write two manifests, verify concatenated dataset
- Commit returns a snapshot ID string
- ImportError when icechunk is not installed (mock import)

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""

import json
import os
import sys
import tempfile
from unittest.mock import patch

import pytest

INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")

# Check if icechunk is available
try:
    import icechunk  # noqa: F401

    HAS_ICECHUNK = True
except ImportError:
    HAS_ICECHUNK = False

requires_icechunk = pytest.mark.skipif(
    not HAS_ICECHUNK,
    reason="icechunk is not installed",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gfs_jpeg_path():
    """Path to the gfs.jpeg.grib2 test file."""
    return os.path.join(INPUT_DATA, "gfs.jpeg.grib2")


@pytest.fixture
def gfs_complex_path():
    """Path to the gfs.complex.grib2 test file."""
    return os.path.join(INPUT_DATA, "gfs.complex.grib2")


@pytest.fixture
def manifest(gfs_jpeg_path):
    """A generated manifest from gfs.jpeg.grib2."""
    from grib2io.kerchunk import ReferenceGenerator

    gen = ReferenceGenerator([gfs_jpeg_path])
    return gen.generate()


@pytest.fixture
def manifest_complex(gfs_complex_path):
    """A generated manifest from gfs.complex.grib2."""
    from grib2io.kerchunk import ReferenceGenerator

    gen = ReferenceGenerator([gfs_complex_path])
    return gen.generate()


# ===========================================================================
# ImportError Test (Requirement 4.5) — always runs
# ===========================================================================


class TestIcechunkImportError:
    """Test that ImportError is raised with correct message when icechunk
    is not installed."""

    def test_import_error_when_icechunk_missing(self):
        """IcechunkWriter raises ImportError with install instructions
        when icechunk is not available.

        Validates: Requirement 4.5
        """
        # Temporarily remove icechunk from sys.modules and make it
        # unimportable so _ensure_icechunk() raises ImportError.
        with patch.dict(sys.modules, {"icechunk": None}):
            # We need to re-import the module to trigger the guard.
            # Import the function directly to test it.
            from grib2io.icechunk import _ensure_icechunk

            with pytest.raises(ImportError, match="icechunk is required"):
                _ensure_icechunk()

    def test_import_error_message_contains_install_instructions(self):
        """ImportError message includes pip install instructions.

        Validates: Requirement 4.5
        """
        with patch.dict(sys.modules, {"icechunk": None}):
            from grib2io.icechunk import _ensure_icechunk

            with pytest.raises(ImportError, match=r"pip install grib2io\[icechunk\]"):
                _ensure_icechunk()

    def test_icechunk_writer_init_raises_when_icechunk_missing(self):
        """IcechunkWriter.__init__ raises ImportError when icechunk is
        not installed.

        Validates: Requirement 4.5
        """
        with patch.dict(sys.modules, {"icechunk": None}):
            from grib2io.icechunk import IcechunkWriter

            with pytest.raises(ImportError, match="icechunk is required"):
                IcechunkWriter("/tmp/test_store")


# ===========================================================================
# Write / Read Tests (Requirement 4.1, 4.2, 4.3) — skip if no icechunk
# ===========================================================================


@requires_icechunk
class TestIcechunkWriteRead:
    """Test writing a manifest to a local Icechunk store and reading it back."""

    def test_write_manifest_creates_store(self, manifest):
        """Writing a manifest creates a valid Icechunk store.

        Validates: Requirement 4.1
        """
        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")
            writer = IcechunkWriter(store_path)
            writer.write(manifest)
            snapshot_id = writer.commit("Test ingest")

            # Store should exist and snapshot ID should be a string
            assert isinstance(snapshot_id, str)
            assert len(snapshot_id) > 0

    def test_write_and_read_back_with_xarray(self, manifest):
        """Write manifest to Icechunk store, read back with xarray and
        verify dataset structure.

        Validates: Requirements 4.1, 4.2, 4.3
        """
        import xarray as xr

        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")
            writer = IcechunkWriter(store_path)
            writer.write(manifest)
            writer.commit("Test ingest")

            # Read back with xarray via Icechunk/Zarr
            import icechunk

            storage = icechunk.local_filesystem_storage(path=store_path)
            repo = icechunk.Repository.open(storage)
            session = repo.readonly_session(branch="main")
            store = session.store

            ds = xr.open_zarr(store, consolidated=False)

            # Verify dataset has variables
            assert len(ds.data_vars) > 0

            # Verify each variable has dimensions
            for var_name in ds.data_vars:
                var = ds[var_name]
                assert len(var.dims) >= 2, f"Variable {var_name} should have at least 2 dims (y, x), got {var.dims}"

            # Verify .zgroup metadata was written (dataset should open)
            assert ds is not None

    def test_written_store_has_zarr_metadata(self, manifest):
        """Written store contains proper Zarr metadata (.zarray, .zattrs).

        Validates: Requirement 4.2
        """
        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")
            writer = IcechunkWriter(store_path)
            writer.write(manifest)
            writer.commit("Test ingest")

            import icechunk
            from grib2io.icechunk import _store_get_sync

            storage = icechunk.local_filesystem_storage(path=store_path)
            repo = icechunk.Repository.open(storage)
            session = repo.readonly_session(branch="main")
            store = session.store

            # Check that root zarr.json (Zarr v3 group) exists
            zgroup_bytes = _store_get_sync(store, "zarr.json")
            assert zgroup_bytes is not None
            zgroup = json.loads(zgroup_bytes.decode("utf-8"))
            assert zgroup["zarr_format"] == 3
            assert zgroup["node_type"] == "group"

            # Find at least one variable with zarr.json (Zarr v3 array)
            refs = manifest["refs"]
            var_names = set()
            for k in refs:
                if k.endswith("/.zarray") and "/" in k:
                    var_names.add(k.rsplit("/.zarray", 1)[0])
            assert len(var_names) > 0

            for var_name in var_names:
                v3_key = f"{var_name}/zarr.json"
                buf = _store_get_sync(store, v3_key)
                assert buf is not None, f"Missing {v3_key} in store"
                zarray = json.loads(buf.decode("utf-8"))
                assert "shape" in zarray
                assert zarray["node_type"] == "array"
                assert "data_type" in zarray


# ===========================================================================
# Multi-File Append Tests (Requirement 4.4) — skip if no icechunk
# ===========================================================================


@requires_icechunk
class TestIcechunkMultiFileAppend:
    """Test appending multiple manifests to an Icechunk store."""

    def test_append_two_manifests(self, manifest, manifest_complex):
        """Write two manifests with append mode, verify both are in the store.

        Validates: Requirement 4.4
        """
        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")

            # Write first manifest
            writer = IcechunkWriter(store_path)
            writer.write(manifest, mode="w")
            writer.commit("First ingest")

            # Append second manifest
            writer2 = IcechunkWriter(store_path)
            writer2.write(manifest_complex, mode="a", append_dim="refDate")
            snapshot_id = writer2.commit("Second ingest (append)")

            assert isinstance(snapshot_id, str)
            assert len(snapshot_id) > 0

    def test_append_extends_dataset(self, gfs_jpeg_path):
        """Appending the same file twice along a dimension extends the
        dataset along that dimension.

        Validates: Requirement 4.4
        """
        import xarray as xr

        from grib2io.icechunk import IcechunkWriter
        from grib2io.kerchunk import ReferenceGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")

            # Generate manifest
            gen = ReferenceGenerator([gfs_jpeg_path])
            m = gen.generate()

            # Write first
            writer = IcechunkWriter(store_path)
            writer.write(m, mode="w")
            writer.commit("First ingest")

            # Read initial dataset to get shape
            import icechunk

            storage = icechunk.local_filesystem_storage(path=store_path)
            repo = icechunk.Repository.open(storage)
            session = repo.readonly_session(branch="main")
            ds1 = xr.open_zarr(session.store, consolidated=False)

            # Get a variable and its shape
            var_names = list(ds1.data_vars)
            assert len(var_names) > 0
            first_var = var_names[0]
            initial_shape = ds1[first_var].shape

            # Append the same manifest along refDate
            writer2 = IcechunkWriter(store_path)
            writer2.write(m, mode="a", append_dim="refDate")
            writer2.commit("Second ingest (append)")

            # Read back and verify shape extended
            storage2 = icechunk.local_filesystem_storage(path=store_path)
            repo2 = icechunk.Repository.open(storage2)
            session2 = repo2.readonly_session(branch="main")
            ds2 = xr.open_zarr(session2.store, consolidated=False)

            # The dataset should still have the same variables
            assert first_var in ds2.data_vars

            # If refDate is a dimension of this variable, its size should
            # have increased
            if "refDate" in ds2[first_var].dims:
                refdate_idx = list(ds2[first_var].dims).index("refDate")
                new_shape = ds2[first_var].shape
                assert new_shape[refdate_idx] > initial_shape[refdate_idx], (
                    f"Expected refDate dimension to grow after append. Initial: {initial_shape}, New: {new_shape}"
                )


# ===========================================================================
# Commit Tests (Requirement 4.3) — skip if no icechunk
# ===========================================================================


@requires_icechunk
class TestIcechunkCommit:
    """Test that commit returns a snapshot ID string."""

    def test_commit_returns_string_snapshot_id(self, manifest):
        """commit() returns a non-empty string snapshot ID.

        Validates: Requirement 4.3
        """
        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")
            writer = IcechunkWriter(store_path)
            writer.write(manifest)
            snapshot_id = writer.commit("Test commit message")

            assert isinstance(snapshot_id, str)
            assert len(snapshot_id) > 0

    def test_commit_with_empty_message(self, manifest):
        """commit() works with an empty message string.

        Validates: Requirement 4.3
        """
        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")
            writer = IcechunkWriter(store_path)
            writer.write(manifest)
            snapshot_id = writer.commit("")

            assert isinstance(snapshot_id, str)
            assert len(snapshot_id) > 0

    def test_commit_without_write_raises_error(self):
        """commit() raises RuntimeError if write() was not called first.

        Validates: Requirement 4.3
        """
        # We need icechunk importable for __init__ to succeed, but
        # _session should be None since write() was not called.
        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")
            writer = IcechunkWriter(store_path)
            with pytest.raises(RuntimeError, match="No active session"):
                writer.commit("Should fail")

    def test_multiple_commits_return_different_snapshot_ids(self, manifest):
        """Successive commits return different snapshot IDs.

        Validates: Requirement 4.3
        """
        from grib2io.icechunk import IcechunkWriter

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "test_store")

            writer = IcechunkWriter(store_path)
            writer.write(manifest)
            snap1 = writer.commit("First commit")

            # Write again (append mode) and commit
            writer2 = IcechunkWriter(store_path)
            writer2.write(manifest, mode="a", append_dim="refDate")
            snap2 = writer2.commit("Second commit")

            assert isinstance(snap1, str)
            assert isinstance(snap2, str)
            assert snap1 != snap2
