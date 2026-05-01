"""
Unit tests for JSON and Parquet serialization of Kerchunk reference manifests.

Tests cover:
- JSON output with a known manifest, verifying file contents parse correctly
- Parquet output, verifying structure is valid
- Error handling for inaccessible output paths and malformed files

Requirements: 2.1, 2.2, 2.3, 2.4
"""

import json
import os
import tempfile

import fsspec
import pytest

from grib2io.kerchunk import ReferenceGenerator

INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")

# Small test files suitable for serialization tests
SMALL_TEST_FILES = [
    "gfs.jpeg.grib2",
    "gfs.complex.grib2",
]


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
    gen = ReferenceGenerator([gfs_jpeg_path])
    return gen.generate()


# ===========================================================================
# JSON Serialization Tests (Requirement 2.1, 2.3)
# ===========================================================================


class TestJsonSerialization:
    """Tests for to_json() serialization."""

    def test_json_output_is_valid_json(self, gfs_jpeg_path):
        """to_json() produces a valid JSON file that can be parsed."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        gen.generate()

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)

            with open(json_path) as f:
                loaded = json.load(f)

            assert isinstance(loaded, dict)
            assert "version" in loaded
            assert loaded["version"] == 1
            assert "refs" in loaded
            assert isinstance(loaded["refs"], dict)
        finally:
            os.unlink(json_path)

    def test_json_output_contains_expected_keys(self, manifest, gfs_jpeg_path):
        """JSON output contains .zgroup, variable .zarray/.zattrs, and chunk refs."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        gen._manifest = manifest

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)

            with open(json_path) as f:
                loaded = json.load(f)

            refs = loaded["refs"]

            # Must have .zgroup
            assert ".zgroup" in refs
            zgroup = json.loads(refs[".zgroup"])
            assert zgroup["zarr_format"] == 2

            # Must have at least one variable with .zarray and .zattrs
            zarray_keys = [k for k in refs if k.endswith("/.zarray")]
            assert len(zarray_keys) > 0, "No .zarray keys found"

            for zarray_key in zarray_keys:
                var_name = zarray_key.rsplit("/.zarray", 1)[0]
                zattrs_key = f"{var_name}/.zattrs"
                assert zattrs_key in refs, f"Missing .zattrs for {var_name}"

                # Verify .zarray is valid JSON with required fields
                zarray = json.loads(refs[zarray_key])
                assert "shape" in zarray
                assert "chunks" in zarray
                assert "dtype" in zarray
                assert "compressor" in zarray

                # Verify .zattrs is valid JSON
                zattrs = json.loads(refs[zattrs_key])
                assert "_ARRAY_DIMENSIONS" in zattrs
        finally:
            os.unlink(json_path)

    def test_json_round_trip_via_fsspec(self, gfs_jpeg_path):
        """JSON output can be loaded via fsspec reference filesystem and
        produces the same keys as the original manifest.

        Validates: Requirement 2.3
        """
        gen = ReferenceGenerator([gfs_jpeg_path])
        manifest = gen.generate()

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)

            # Load via fsspec
            fs = fsspec.filesystem("reference", fo=json_path)
            store = fs.get_mapper("")

            loaded_keys = set(store.keys())
            original_keys = set(manifest["refs"].keys())

            assert loaded_keys == original_keys

            # Verify metadata values are structurally equivalent
            for key in original_keys:
                if key.endswith((".zarray", ".zattrs", ".zgroup")):
                    orig_val = json.loads(manifest["refs"][key])
                    loaded_val = json.loads(store[key])
                    assert orig_val == loaded_val, (
                        f"Metadata mismatch for {key}"
                    )
        finally:
            os.unlink(json_path)

    def test_json_auto_generates_manifest(self, gfs_jpeg_path):
        """to_json() auto-generates the manifest if generate() was not called."""
        gen = ReferenceGenerator([gfs_jpeg_path])

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)

            with open(json_path) as f:
                loaded = json.load(f)

            assert loaded["version"] == 1
            assert len(loaded["refs"]) > 0
        finally:
            os.unlink(json_path)

    def test_json_multi_file_manifest(self, gfs_jpeg_path, gfs_complex_path):
        """JSON output from multi-file manifest contains refs from both files."""
        gen = ReferenceGenerator([gfs_jpeg_path, gfs_complex_path])
        gen.generate()

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as tmp:
            json_path = tmp.name

        try:
            gen.to_json(json_path)

            with open(json_path) as f:
                loaded = json.load(f)

            # Should have refs pointing to both files
            uris = set()
            for key, value in loaded["refs"].items():
                if isinstance(value, list) and len(value) == 3:
                    uris.add(value[0])

            # Both file URIs should be present
            assert len(uris) >= 1, "Expected refs from at least one file"
        finally:
            os.unlink(json_path)


# ===========================================================================
# Parquet Serialization Tests (Requirement 2.2, 2.4)
# ===========================================================================


def _has_parquet_engine():
    """Check if a Parquet engine (fastparquet or pyarrow) is available."""
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
class TestParquetSerialization:
    """Tests for to_parquet() serialization."""

    def test_parquet_output_creates_directory(self, gfs_jpeg_path):
        """to_parquet() creates an output directory with Parquet files."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = os.path.join(tmpdir, "refs")
            gen.to_parquet(parquet_path)

            assert os.path.isdir(parquet_path), (
                f"Parquet output directory not created at {parquet_path}"
            )

            # Should contain at least one .parq file
            contents = os.listdir(parquet_path)
            parq_files = [f for f in contents if f.endswith(".parq")]
            assert len(parq_files) > 0, (
                f"No .parq files found in {parquet_path}. "
                f"Contents: {contents}"
            )

    def test_parquet_output_structure(self, gfs_jpeg_path):
        """Parquet output directory has expected structure."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = os.path.join(tmpdir, "refs")
            gen.to_parquet(parquet_path)

            contents = os.listdir(parquet_path)

            # Should have .zmetadata file
            assert ".zmetadata" in contents, (
                f".zmetadata not found. Contents: {contents}"
            )

            # .zmetadata should be valid JSON
            with open(os.path.join(parquet_path, ".zmetadata")) as f:
                zmetadata = json.load(f)
            assert isinstance(zmetadata, dict)

    def test_parquet_auto_generates_manifest(self, gfs_jpeg_path):
        """to_parquet() auto-generates the manifest if generate() was not called."""
        gen = ReferenceGenerator([gfs_jpeg_path])

        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = os.path.join(tmpdir, "refs")
            gen.to_parquet(parquet_path)

            assert os.path.isdir(parquet_path)
            contents = os.listdir(parquet_path)
            assert len(contents) > 0


# ===========================================================================
# Error Handling Tests (Requirement 2.4)
# ===========================================================================


class TestErrorHandling:
    """Tests for error handling in ReferenceGenerator."""

    def test_file_not_found_raises_error(self):
        """FileNotFoundError raised for non-existent GRIB2 file."""
        with pytest.raises(FileNotFoundError, match="GRIB2 file not found"):
            ReferenceGenerator(["/nonexistent/path/to/file.grib2"])

    def test_multiple_files_one_missing_raises_error(self, gfs_jpeg_path):
        """FileNotFoundError raised when one file in a list is missing."""
        with pytest.raises(FileNotFoundError, match="GRIB2 file not found"):
            ReferenceGenerator([
                gfs_jpeg_path,
                "/nonexistent/path/to/file.grib2",
            ])

    def test_json_inaccessible_output_path(self, gfs_jpeg_path):
        """Error raised when JSON output path is not writable."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        gen.generate()

        with pytest.raises((OSError, PermissionError)):
            gen.to_json("/nonexistent_dir/subdir/output.json")

    def test_parquet_inaccessible_output_path(self, gfs_jpeg_path):
        """Error raised when Parquet output path is not writable."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        gen.generate()

        with pytest.raises((OSError, PermissionError, Exception)):
            gen.to_parquet("/nonexistent_dir/subdir/output_parquet")

    def test_single_file_path_string(self, gfs_jpeg_path):
        """ReferenceGenerator accepts a single file path as a string."""
        gen = ReferenceGenerator(gfs_jpeg_path)
        manifest = gen.generate()
        assert manifest["version"] == 1
        assert len(manifest["refs"]) > 0

    def test_manifest_property_before_generate(self, gfs_jpeg_path):
        """manifest property is None before generate() is called."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        assert gen.manifest is None

    def test_manifest_property_after_generate(self, gfs_jpeg_path):
        """manifest property returns the manifest after generate() is called."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        result = gen.generate()
        assert gen.manifest is result
        assert gen.manifest["version"] == 1
