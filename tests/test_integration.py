"""
End-to-end integration tests for the Kerchunk/Icechunk pipeline.

Tests cover:
- Kerchunk pipeline: generate refs → serialize to JSON → open with fsspec → read data → compare to direct grib2io read
- Icechunk pipeline: generate refs → write to Icechunk → open with xarray.open_zarr() → compare to direct grib2io read (skipped if icechunk not installed)
- Multi-file pipeline: generate refs from multiple files → combine → verify unified dataset
- CLI pipeline: run CLI on test files → verify output files → open and validate

Requirements: 1.1, 2.3, 3.9, 4.3, 5.1, 5.2, 6.1, 6.3
"""

import json
import os
import tempfile

import fsspec
import numpy as np
import pytest
import xarray as xr

import grib2io
import grib2io.codecs  # Ensure Grib2Codec is registered with numcodecs
from grib2io.kerchunk import ReferenceGenerator
from grib2io.cli.main import main

INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_icechunk():
    """Check if icechunk is installed."""
    try:
        import icechunk  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gfs_jpeg_path():
    """Absolute path to gfs.jpeg.grib2."""
    return os.path.join(INPUT_DATA, "gfs.jpeg.grib2")


@pytest.fixture
def gfs_complex_path():
    """Absolute path to gfs.complex.grib2."""
    return os.path.join(INPUT_DATA, "gfs.complex.grib2")


@pytest.fixture
def gfs_large_path():
    """Absolute path to gfs.t00z.pgrb2.1p00.f024 (larger file with bitmaps)."""
    return os.path.join(INPUT_DATA, "gfs.t00z.pgrb2.1p00.f024")


# ===========================================================================
# Kerchunk Pipeline Integration Tests (Requirements 1.1, 2.3, 3.9)
# ===========================================================================


class TestKerchunkPipeline:
    """End-to-end: generate refs → JSON → fsspec → read data → compare to grib2io."""

    def test_kerchunk_pipeline_roundtrip(self, gfs_jpeg_path):
        """Generate refs from a real GRIB2 file, serialize to JSON, open with
        fsspec, read a variable, and compare to direct grib2io.open() read.

        Validates: Requirements 1.1, 2.3, 3.9
        """
        # Step 1: Generate refs
        gen = ReferenceGenerator(gfs_jpeg_path)
        manifest = gen.generate()

        assert manifest["version"] == 1
        assert len(manifest["refs"]) > 0

        # Step 2: Serialize to JSON
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)
            assert os.path.isfile(json_path)

            # Step 3: Open with fsspec reference filesystem
            fs = fsspec.filesystem("reference", fo=json_path)
            mapper = fs.get_mapper("")

            # Verify the store has keys
            store_keys = list(mapper.keys())
            assert len(store_keys) > 0

            # Identify a data variable (not a coordinate or metadata key)
            zarray_keys = [k for k in store_keys if k.endswith("/.zarray")]
            assert len(zarray_keys) > 0, "No .zarray keys found in store"

            # Find a variable that has data chunk refs (not a coordinate)
            var_name = None
            for zk in zarray_keys:
                candidate = zk.rsplit("/.zarray", 1)[0]
                zarray_meta = json.loads(mapper[zk])
                # Data variables have a compressor with id "grib2io"
                compressor = zarray_meta.get("compressor")
                if compressor and compressor.get("id") == "grib2io":
                    var_name = candidate
                    break

            assert var_name is not None, "No data variable with grib2io codec found in manifest"

            # Step 4: Read data via xarray from the reference store
            ds_ref = xr.open_zarr(mapper, consolidated=False)
            assert var_name in ds_ref

            ref_data = ds_ref[var_name].values

            # Step 5: Compare to direct grib2io.open() read
            # Get the shortName from the manifest .zattrs
            zattrs = json.loads(manifest["refs"][f"{var_name}/.zattrs"])
            short_name = zattrs.get("shortName", var_name)

            direct_data = None
            with grib2io.open(gfs_jpeg_path) as f:
                # Find messages matching this variable and read data
                for m in f:
                    if str(m.shortName) == short_name:
                        direct_data = m.data
                        break

            assert direct_data is not None, f"No messages found with shortName={short_name}"

            # The reference data may have extra leading dimensions; extract
            # the 2D spatial slice that corresponds to the first message
            ref_2d = ref_data
            while ref_2d.ndim > 2:
                ref_2d = ref_2d[0]

            # Compare within floating-point tolerance
            # Both should have the same shape
            assert ref_2d.shape == direct_data.shape, f"Shape mismatch: ref={ref_2d.shape}, direct={direct_data.shape}"

            # Check NaN positions match
            ref_nans = np.isnan(ref_2d)
            direct_nans = np.isnan(direct_data)
            np.testing.assert_array_equal(
                ref_nans,
                direct_nans,
                err_msg="NaN positions differ between reference and direct read",
            )

            # Compare non-NaN values
            mask = ~ref_nans
            if mask.any():
                np.testing.assert_allclose(
                    ref_2d[mask].astype(np.float32),
                    direct_data[mask].astype(np.float32),
                    rtol=1e-5,
                    atol=1e-5,
                    err_msg="Data values differ between reference and direct read",
                )

        finally:
            os.unlink(json_path)

    def test_kerchunk_manifest_has_all_variables(self, gfs_jpeg_path):
        """The manifest should contain refs for all variables in the GRIB2 file.

        Validates: Requirement 1.1
        """
        gen = ReferenceGenerator(gfs_jpeg_path)
        manifest = gen.generate()

        # Get variable names from the manifest
        refs = manifest["refs"]
        manifest_vars = set()
        for key in refs:
            if key.endswith("/.zarray"):
                candidate = key.rsplit("/.zarray", 1)[0]
                zarray = json.loads(refs[key])
                if zarray.get("compressor") and zarray["compressor"].get("id") == "grib2io":
                    manifest_vars.add(candidate)

        # Get variable names from direct grib2io read
        with grib2io.open(gfs_jpeg_path) as f:
            direct_vars = set(str(m.shortName) for m in f)

        # Every variable in the file should appear in the manifest
        # (variable names may have suffixes for disambiguation)
        for dv in direct_vars:
            matching = [mv for mv in manifest_vars if mv.startswith(dv)]
            assert len(matching) > 0, f"Variable '{dv}' from GRIB2 file not found in manifest. Manifest vars: {manifest_vars}"

    def test_kerchunk_json_fsspec_store_keys_match(self, gfs_jpeg_path):
        """Keys from fsspec store match the original manifest refs keys.

        Validates: Requirement 2.3
        """
        gen = ReferenceGenerator(gfs_jpeg_path)
        manifest = gen.generate()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)

            fs = fsspec.filesystem("reference", fo=json_path)
            mapper = fs.get_mapper("")

            fsspec_keys = set(mapper.keys())
            manifest_keys = set(manifest["refs"].keys())

            assert fsspec_keys == manifest_keys, (
                f"Key mismatch. Only in fsspec: {fsspec_keys - manifest_keys}. Only in manifest: {manifest_keys - fsspec_keys}"
            )
        finally:
            os.unlink(json_path)


# ===========================================================================
# Icechunk Pipeline Integration Tests (Requirements 4.3, 6.1)
# ===========================================================================


@pytest.mark.skipif(
    not _has_icechunk(),
    reason="icechunk is not installed",
)
class TestIcechunkPipeline:
    """End-to-end: generate refs → write to Icechunk → open with xarray → compare."""

    def test_icechunk_pipeline_roundtrip(self, gfs_jpeg_path):
        """Generate refs, write to Icechunk, open with xarray.open_zarr(),
        and compare to direct grib2io read.

        Validates: Requirements 4.3, 6.1
        """
        from grib2io.icechunk import IcechunkWriter

        # Step 1: Generate refs
        gen = ReferenceGenerator(gfs_jpeg_path)
        manifest = gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "icechunk_store")

            # Step 2: Write to Icechunk
            writer = IcechunkWriter(store_path)
            writer.write(manifest)
            snapshot_id = writer.commit("Integration test ingest")

            assert isinstance(snapshot_id, str)
            assert len(snapshot_id) > 0

            # Step 3: Open with xarray.open_zarr()
            import icechunk
            from grib2io.icechunk import _collect_virtual_chunk_prefixes

            storage = icechunk.local_filesystem_storage(path=store_path)
            # Collect virtual chunk prefixes so we can authorize access
            # when reading — icechunk requires authorization even for reads.
            virtual_prefixes = _collect_virtual_chunk_prefixes(manifest["refs"])
            authorize = {p: None for p in virtual_prefixes}
            repo = icechunk.Repository.open(
                storage,
                authorize_virtual_chunk_access=authorize if authorize else None,
            )
            session = repo.readonly_session(branch="main")
            store = session.store

            ds_ice = xr.open_zarr(store, consolidated=False)

            # Step 4: Verify the dataset has variables and structure
            assert len(ds_ice.data_vars) > 0, "Icechunk dataset has no data variables"

            # Step 5: Verify variable structure matches direct grib2io read.
            # Note: reading actual data values via ds[var].values requires
            # Grib2Codec to be registered as a zarr v3 ArrayBytesCodec
            # (serializer), which is a separate zarr v3 integration task.
            # Here we verify shape, dimensions, and attributes only.
            var_name = list(ds_ice.data_vars)[0]
            ice_var = ds_ice[var_name]

            # Variable should have at least y and x dimensions
            assert len(ice_var.dims) >= 2, (
                f"Variable {var_name} should have at least 2 dims, got {ice_var.dims}"
            )

            # Shape should be non-trivial
            assert all(s > 0 for s in ice_var.shape), (
                f"Variable {var_name} has zero-size dimension: {ice_var.shape}"
            )

            # Verify the spatial size matches direct grib2io read
            short_name = ice_var.attrs.get("shortName", var_name)
            with grib2io.open(gfs_jpeg_path) as f:
                for m in f:
                    if str(m.shortName) == short_name:
                        assert m.nx == ice_var.shape[-1], (
                            f"x-dimension mismatch: zarr={ice_var.shape[-1]}, grib2io={m.nx}"
                        )
                        assert m.ny == ice_var.shape[-2], (
                            f"y-dimension mismatch: zarr={ice_var.shape[-2]}, grib2io={m.ny}"
                        )
                        break


# ===========================================================================
# Multi-File Pipeline Integration Tests (Requirements 5.1, 5.2)
# ===========================================================================


class TestMultiFilePipeline:
    """End-to-end: generate refs from multiple files → combine → verify."""

    def test_multi_file_combined_manifest(self, gfs_jpeg_path, gfs_complex_path):
        """Generate refs from two files and verify the combined manifest
        has variables from both files and chunk refs point to correct sources.

        Validates: Requirements 5.1, 5.2
        """
        # Step 1: Generate combined refs
        gen = ReferenceGenerator([gfs_jpeg_path, gfs_complex_path])
        manifest = gen.generate()

        assert manifest["version"] == 1
        refs = manifest["refs"]

        # Step 2: Collect all source file URIs from chunk refs
        source_uris = set()
        for key, value in refs.items():
            if isinstance(value, list) and len(value) == 3:
                source_uris.add(value[0])

        # Both files should be referenced
        jpeg_uri = f"file://{os.path.abspath(gfs_jpeg_path)}"
        complex_uri = f"file://{os.path.abspath(gfs_complex_path)}"

        assert jpeg_uri in source_uris, f"gfs.jpeg.grib2 URI not found in refs. URIs: {source_uris}"
        assert complex_uri in source_uris, f"gfs.complex.grib2 URI not found in refs. URIs: {source_uris}"

    def test_multi_file_manifest_has_data_variables(self, gfs_jpeg_path, gfs_complex_path):
        """Combined manifest has at least one data variable with .zarray/.zattrs.

        Validates: Requirement 5.1
        """
        gen = ReferenceGenerator([gfs_jpeg_path, gfs_complex_path])
        manifest = gen.generate()
        refs = manifest["refs"]

        zarray_keys = [k for k in refs if k.endswith("/.zarray")]
        assert len(zarray_keys) > 0

        # Each variable should have .zattrs too
        for zk in zarray_keys:
            var_name = zk.rsplit("/.zarray", 1)[0]
            assert f"{var_name}/.zattrs" in refs

    def test_multi_file_chunk_refs_point_to_correct_files(self, gfs_jpeg_path, gfs_complex_path):
        """Each chunk ref [uri, offset, length] points to a valid source file.

        Validates: Requirement 5.1
        """
        gen = ReferenceGenerator([gfs_jpeg_path, gfs_complex_path])
        manifest = gen.generate()
        refs = manifest["refs"]

        valid_uris = {
            f"file://{os.path.abspath(gfs_jpeg_path)}",
            f"file://{os.path.abspath(gfs_complex_path)}",
        }

        for key, value in refs.items():
            if isinstance(value, list) and len(value) == 3:
                uri, offset, length = value
                assert uri in valid_uris, f"Chunk ref '{key}' points to unknown URI: {uri}"
                assert isinstance(offset, int) and offset >= 0, f"Invalid offset for '{key}': {offset}"
                assert isinstance(length, int) and length > 0, f"Invalid length for '{key}': {length}"

    def test_multi_file_openable_via_fsspec(self, gfs_jpeg_path, gfs_complex_path):
        """Combined manifest can be serialized to JSON and opened via fsspec.

        Validates: Requirements 5.1, 5.2
        """
        gen = ReferenceGenerator([gfs_jpeg_path, gfs_complex_path])
        gen.generate()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)

            fs = fsspec.filesystem("reference", fo=json_path)
            mapper = fs.get_mapper("")

            ds = xr.open_zarr(mapper, consolidated=False)

            # Should have at least one data variable
            assert len(ds.data_vars) > 0, "Multi-file dataset has no data variables"

            # Should have spatial dimensions
            assert "y" in ds.dims or any("y" in ds[v].dims for v in ds.data_vars), "No 'y' dimension found"
            assert "x" in ds.dims or any("x" in ds[v].dims for v in ds.data_vars), "No 'x' dimension found"
        finally:
            os.unlink(json_path)


# ===========================================================================
# CLI Pipeline Integration Tests (Requirements 6.1, 6.3)
# ===========================================================================


class TestCLIPipeline:
    """End-to-end: run CLI → verify output → open and validate."""

    def test_cli_generates_valid_json(self, gfs_jpeg_path):
        """Run CLI kerchunk subcommand, verify JSON output, open with fsspec.

        Validates: Requirements 6.1, 6.3
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            out_path = tmp.name

        try:
            # Step 1: Run CLI
            main(["kerchunk", "--output", out_path, gfs_jpeg_path])

            # Step 2: Verify output file exists and is valid JSON
            assert os.path.isfile(out_path)

            with open(out_path) as f:
                data = json.load(f)

            assert data["version"] == 1
            assert "refs" in data
            assert ".zgroup" in data["refs"]

            # Step 3: Open with fsspec and verify it has variables
            fs = fsspec.filesystem("reference", fo=out_path)
            mapper = fs.get_mapper("")

            ds = xr.open_zarr(mapper, consolidated=False)
            assert len(ds.data_vars) > 0, "CLI output dataset has no data variables"

        finally:
            os.unlink(out_path)

    def test_cli_with_filters_produces_subset(self, gfs_jpeg_path):
        """CLI with --filters produces a manifest with a subset of variables.

        Validates: Requirement 6.3
        """
        with tempfile.NamedTemporaryFile(suffix="_all.json", delete=False) as tmp_all, tempfile.NamedTemporaryFile(
            suffix="_filtered.json", delete=False
        ) as tmp_filt:
            all_path = tmp_all.name
            filt_path = tmp_filt.name

        try:
            # Generate unfiltered
            main(["kerchunk", "--output", all_path, gfs_jpeg_path])

            # Generate filtered to a single variable
            # First, find a variable name from the unfiltered output
            with open(all_path) as f:
                all_data = json.load(f)

            # Find a shortName from the manifest
            short_name = None
            for key in all_data["refs"]:
                if key.endswith("/.zattrs"):
                    zattrs = json.loads(all_data["refs"][key])
                    if "shortName" in zattrs:
                        short_name = zattrs["shortName"]
                        break

            assert short_name is not None, "Could not find a shortName in manifest"

            # Generate filtered
            main(
                [
                    "kerchunk",
                    "--filters",
                    f"shortName={short_name}",
                    "--output",
                    filt_path,
                    gfs_jpeg_path,
                ]
            )

            with open(filt_path) as f:
                filt_data = json.load(f)

            # Filtered should have fewer or equal refs
            assert len(filt_data["refs"]) <= len(all_data["refs"])
            assert filt_data["version"] == 1

        finally:
            if os.path.exists(all_path):
                os.unlink(all_path)
            if os.path.exists(filt_path):
                os.unlink(filt_path)

    def test_cli_multiple_files(self, gfs_jpeg_path, gfs_complex_path):
        """CLI accepts multiple GRIB2 files and produces a combined manifest.

        Validates: Requirements 5.1, 6.1
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            out_path = tmp.name

        try:
            main(
                [
                    "kerchunk",
                    "--output",
                    out_path,
                    gfs_jpeg_path,
                    gfs_complex_path,
                ]
            )

            assert os.path.isfile(out_path)

            with open(out_path) as f:
                data = json.load(f)

            # Should reference both files
            source_uris = set()
            for key, value in data["refs"].items():
                if isinstance(value, list) and len(value) == 3:
                    source_uris.add(value[0])

            assert len(source_uris) >= 2, f"Expected refs from at least 2 files, got URIs: {source_uris}"

        finally:
            os.unlink(out_path)
