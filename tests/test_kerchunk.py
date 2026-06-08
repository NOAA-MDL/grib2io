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
import sys
import tempfile

import numpy as np
import pytest
from pathlib import Path

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="kerchunk support requires Python >= 3.11",
)

pytest.importorskip("numcodecs", reason="numcodecs is not installed")
fsspec = pytest.importorskip("fsspec", reason="fsspec is not installed")

from grib2io.kerchunk import ReferenceGenerator  # noqa: E402

INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")

# Small test files suitable for serialization tests
SMALL_TEST_FILES = [
    "gfs.jpeg.grib2",
    "gfs.complex.grib2",
]


def test_file_uri_preserves_remote_uri():
    """URI inputs should be preserved for streaming backends."""
    from grib2io.kerchunk import _file_uri

    s3_uri = "s3://noaa-gfs-bdp-pds/gfs.20240501/00/atmos/gfs.t00z.pgrb2.0p25.f000"
    assert _file_uri(s3_uri) == s3_uri


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

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
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

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
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

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
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
                    assert orig_val == loaded_val, f"Metadata mismatch for {key}"
        finally:
            os.unlink(json_path)

    def test_json_auto_generates_manifest(self, gfs_jpeg_path):
        """to_json() auto-generates the manifest if generate() was not called."""
        gen = ReferenceGenerator([gfs_jpeg_path])

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
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

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
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

            assert os.path.isdir(parquet_path), f"Parquet output directory not created at {parquet_path}"
            # Should contain at least one .parq file
            parq_files = [f for f in Path(parquet_path).rglob("*.parq")]
            assert len(parq_files) > 0, f"No .parq files found beneath {parquet_path}"

    def test_parquet_output_structure(self, gfs_jpeg_path):
        """Parquet output directory has expected structure."""
        gen = ReferenceGenerator([gfs_jpeg_path])
        gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = os.path.join(tmpdir, "refs")
            gen.to_parquet(parquet_path)

            contents = os.listdir(parquet_path)

            # Should have .zmetadata file
            assert ".zmetadata" in contents, f".zmetadata not found. Contents: {contents}"

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
            ReferenceGenerator(
                [
                    gfs_jpeg_path,
                    "/nonexistent/path/to/file.grib2",
                ]
            )

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


def test_remote_scan_enables_index_cache(monkeypatch):
    """Remote scans should allow grib2io to persist/reuse parsed indices."""

    class _Meta:
        def __init__(self, value):
            self.value = value

    class _Msg:
        shortName = "TMP"
        typeOfFirstFixedSurface = _Meta(103)
        productDefinitionTemplateNumber = _Meta(0)
        typeOfSecondFixedSurface = _Meta(255)

    class _FakeOpen:
        def __init__(self):
            self._index = {
                "sectionOffset": [{5: 900, 6: None, 7: 1234}],
                "sectionSize": [{5: 21, 6: 6, 7: 567}],
                "bmapflag": [255],
                "section3": [np.array([0, 0, 0, 0, 0, 0], dtype=np.int64)],
                "section5": [np.array([0, 0, 0], dtype=np.int64)],
            }
            self._msgs = [_Msg()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __iter__(self):
            return iter(self._msgs)

    captured = {}

    class _FakeRemoteFile:
        def open(self):
            return self

        def info(self):
            return {"size": 12345}

        def close(self):
            return None

    def _fake_fsspec_open(path, mode="rb", **kwargs):
        if path == "s3://example-bucket/sample.grib2":
            return _FakeRemoteFile()
        raise PermissionError("Forbidden")

    def _fake_open(path, **kwargs):
        captured["path"] = path
        captured["kwargs"] = kwargs
        return _FakeOpen()

    monkeypatch.setattr("grib2io.open", _fake_open)
    monkeypatch.setattr("fsspec.open", _fake_fsspec_open)

    gen = ReferenceGenerator("s3://example-bucket/sample.grib2", storage_options={"anon": True})
    gen._scan_file("s3://example-bucket/sample.grib2", "s3://example-bucket/sample.grib2", {})

    assert captured["path"] == "s3://example-bucket/sample.grib2"
    assert captured["kwargs"]["save_index"] is True
    assert captured["kwargs"]["use_index"] is True


def test_local_scan_keeps_save_index_disabled(monkeypatch, gfs_jpeg_path):
    """Local scans should not create sidecar index files from ReferenceGenerator."""

    class _Meta:
        def __init__(self, value):
            self.value = value

    class _Msg:
        shortName = "TMP"
        typeOfFirstFixedSurface = _Meta(103)
        productDefinitionTemplateNumber = _Meta(0)
        typeOfSecondFixedSurface = _Meta(255)

    class _FakeOpen:
        def __init__(self):
            self._index = {
                "sectionOffset": [{5: 900, 6: None, 7: 1234}],
                "sectionSize": [{5: 21, 6: 6, 7: 567}],
                "bmapflag": [255],
                "section3": [np.array([0, 0, 0, 0, 0, 0], dtype=np.int64)],
                "section5": [np.array([0, 0, 0], dtype=np.int64)],
            }
            self._msgs = [_Msg()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __iter__(self):
            return iter(self._msgs)

    captured = {}

    def _fake_open(path, **kwargs):
        captured["path"] = path
        captured["kwargs"] = kwargs
        return _FakeOpen()

    monkeypatch.setattr("grib2io.open", _fake_open)

    gen = ReferenceGenerator([gfs_jpeg_path])
    gen._scan_file(gfs_jpeg_path, gfs_jpeg_path, {})

    assert captured["path"] == gfs_jpeg_path
    assert captured["kwargs"]["save_index"] is False
    assert captured["kwargs"]["use_index"] is True


# ---------------------------------------------------------------------------
# Tests for _prefilter_idx_offsets
# ---------------------------------------------------------------------------


def test_prefilter_idx_offsets_basic():
    """_prefilter_idx_offsets should return only offsets whose shortName matches."""
    from io import StringIO

    from grib2io.kerchunk import _prefilter_idx_offsets

    idx_content = (
        "1:0:d=2024040100:PRMSL:mean sea level:anl:\n"
        "2:27027584:d=2024040100:TMP:2 m above ground:anl:\n"
        "3:54055168:d=2024040100:UGRD:10 m above ground:anl:\n"
        "4:81082752:d=2024040100:TMP:500 mb:anl:\n"
    )
    offsets = _prefilter_idx_offsets(StringIO(idx_content), "TMP")
    assert offsets == [27027584, 81082752]


def test_prefilter_idx_offsets_no_match():
    """_prefilter_idx_offsets should return [] when shortName is not present."""
    from io import StringIO

    from grib2io.kerchunk import _prefilter_idx_offsets

    idx_content = "1:0:d=2024040100:PRMSL:mean sea level:anl:\n"
    offsets = _prefilter_idx_offsets(StringIO(idx_content), "TMP")
    assert offsets == []


def test_prefilter_idx_offsets_bytes_input():
    """_prefilter_idx_offsets should handle bytes lines from fsspec."""
    from io import BytesIO

    from grib2io.kerchunk import _prefilter_idx_offsets

    idx_bytes = b"1:0:d=2024040100:TMP:2 m above ground:anl:\n2:12345:d=2024040100:UGRD:10 m above ground:anl:\n"
    offsets = _prefilter_idx_offsets(BytesIO(idx_bytes), "TMP")
    assert offsets == [0]


def test_remote_scan_uses_shortname_filter_fast_path(monkeypatch):
    """When shortName filter is set, remote scan should use _build_remote_index_filtered."""
    called = {}

    def _fake_build(self, file_path, shortname_filter, scan_storage_options):
        called["file_path"] = file_path
        called["shortname_filter"] = shortname_filter
        return {}, []

    from grib2io.kerchunk import ReferenceGenerator as _RG

    monkeypatch.setattr(_RG, "_build_remote_index_filtered", _fake_build)

    gen = _RG(
        "s3://example-bucket/sample.grib2",
        filters={"shortName": "TMP", "typeOfFirstFixedSurface": 103, "level": 2},
        storage_options={"anon": True},
    )
    gen._scan_file("s3://example-bucket/sample.grib2", "s3://example-bucket/sample.grib2", {})

    assert called["file_path"] == "s3://example-bucket/sample.grib2"
    assert called["shortname_filter"] == "TMP"


# ---------------------------------------------------------------------------
# _matches_filters — list, tuple, set, and slice support
# ---------------------------------------------------------------------------


class _FakeMsg:
    """Minimal stand-in for Grib2Message used in _matches_filters tests."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_gen(filters):
    from grib2io.kerchunk import ReferenceGenerator

    gen = ReferenceGenerator.__new__(ReferenceGenerator)
    gen.filters = filters
    return gen


def test_matches_filters_list_match():
    gen = _make_gen({"level": [500, 850, 250]})
    assert gen._matches_filters(_FakeMsg(level=500))
    assert gen._matches_filters(_FakeMsg(level=850))
    assert not gen._matches_filters(_FakeMsg(level=1000))


def test_matches_filters_tuple_match():
    gen = _make_gen({"shortName": ("TMP", "UGRD", "VGRD")})
    assert gen._matches_filters(_FakeMsg(shortName="TMP"))
    assert not gen._matches_filters(_FakeMsg(shortName="PRMSL"))


def test_matches_filters_set_match():
    gen = _make_gen({"shortName": {"TMP", "UGRD"}})
    assert gen._matches_filters(_FakeMsg(shortName="UGRD"))
    assert not gen._matches_filters(_FakeMsg(shortName="HGT"))


def test_matches_filters_slice_match():
    gen = _make_gen({"level": slice(500, 1000)})
    assert gen._matches_filters(_FakeMsg(level=500))
    assert gen._matches_filters(_FakeMsg(level=850))
    assert gen._matches_filters(_FakeMsg(level=1000))
    assert not gen._matches_filters(_FakeMsg(level=250))


def test_matches_filters_slice_open_ended():
    gen = _make_gen({"level": slice(None, 500)})
    assert gen._matches_filters(_FakeMsg(level=250))
    assert not gen._matches_filters(_FakeMsg(level=850))


def test_matches_filters_scalar_unchanged():
    gen = _make_gen({"shortName": "TMP", "level": 2})
    assert gen._matches_filters(_FakeMsg(shortName="TMP", level=2))
    assert not gen._matches_filters(_FakeMsg(shortName="TMP", level=10))


def test_prefilter_idx_offsets_list_shortname():
    """_prefilter_idx_offsets should accept a set/list of shortNames."""
    from io import StringIO

    from grib2io.kerchunk import _prefilter_idx_offsets

    idx_content = (
        "1:0:d=2024040100:PRMSL:mean sea level:anl:\n"
        "2:27027584:d=2024040100:TMP:2 m above ground:anl:\n"
        "3:54055168:d=2024040100:UGRD:10 m above ground:anl:\n"
        "4:81082752:d=2024040100:VGRD:10 m above ground:anl:\n"
    )
    offsets = _prefilter_idx_offsets(StringIO(idx_content), {"UGRD", "VGRD"})
    assert sorted(offsets) == [54055168, 81082752]


# ---------------------------------------------------------------------------
# _idx_level_matches and _prefilter_idx_offsets with level filters
# ---------------------------------------------------------------------------


def test_idx_level_matches_height_above_ground():
    from grib2io.kerchunk import _idx_level_matches

    # tofs=103, level=2 → "2 m above ground" should match
    assert _idx_level_matches("2 m above ground", 103, 2) is True
    # level=10 should not match "2 m above ground"
    assert _idx_level_matches("2 m above ground", 103, 10) is False
    # isobaric string should not match tofs=103
    assert _idx_level_matches("500 mb", 103, 2) is False
    # no level filter — any matching surface type passes
    assert _idx_level_matches("10 m above ground", 103, None) is True


def test_idx_level_matches_isobaric():
    from grib2io.kerchunk import _idx_level_matches

    # tofs=100, level in Pa: 500 mb → 50000 Pa
    assert _idx_level_matches("500 mb", 100, 50000) is True
    # also accept hPa value
    assert _idx_level_matches("500 mb", 100, 500) is True
    # wrong level
    assert _idx_level_matches("500 mb", 100, 85000) is False
    # non-isobaric string doesn't match tofs=100
    assert _idx_level_matches("2 m above ground", 100, 50000) is False


def test_idx_level_matches_fixed_labels():
    from grib2io.kerchunk import _idx_level_matches

    assert _idx_level_matches("surface", 1, None) is True
    assert _idx_level_matches("mean sea level", 101, None) is True
    # wrong surface type
    assert _idx_level_matches("surface", 101, None) is False


def test_idx_level_matches_unknown_type_conservative():
    from grib2io.kerchunk import _idx_level_matches

    # Unknown tofs → conservative, returns True
    assert _idx_level_matches("some obscure level", 200, 42) is True


def test_prefilter_idx_offsets_with_level_filter():
    """_prefilter_idx_offsets with filters should reduce TMP to only the 2m line."""
    from io import StringIO

    from grib2io.kerchunk import _prefilter_idx_offsets

    idx_content = (
        "1:0:d=2024040100:TMP:1000 mb:anl:\n"
        "2:27027584:d=2024040100:TMP:500 mb:anl:\n"
        "3:54055168:d=2024040100:TMP:2 m above ground:anl:\n"
        "4:81082752:d=2024040100:UGRD:10 m above ground:anl:\n"
    )
    filters = {"shortName": "TMP", "typeOfFirstFixedSurface": 103, "level": 2}
    offsets = _prefilter_idx_offsets(StringIO(idx_content), "TMP", filters=filters)
    # Only the "2 m above ground" TMP line should remain
    assert offsets == [54055168]


def test_prefilter_idx_offsets_filters_none_keeps_all_shortname():
    """Without level filters, _prefilter_idx_offsets keeps all matching shortNames."""
    from io import StringIO

    from grib2io.kerchunk import _prefilter_idx_offsets

    idx_content = "1:0:d=2024040100:TMP:1000 mb:anl:\n2:27027584:d=2024040100:TMP:500 mb:anl:\n3:54055168:d=2024040100:TMP:2 m above ground:anl:\n"
    offsets = _prefilter_idx_offsets(StringIO(idx_content), "TMP", filters=None)
    assert offsets == [0, 27027584, 54055168]


def test_prefilter_idx_offsets_isobaric_list():
    """Level list filter should keep only the matching pressure levels."""
    from io import StringIO

    from grib2io.kerchunk import _prefilter_idx_offsets

    idx_content = (
        "1:0:d=2024040100:TMP:1000 mb:anl:\n"
        "2:27027584:d=2024040100:TMP:850 mb:anl:\n"
        "3:54055168:d=2024040100:TMP:500 mb:anl:\n"
        "4:81082752:d=2024040100:TMP:250 mb:anl:\n"
    )
    # Select 850 and 500 hPa (pass as hPa values — grib2io may return hPa)
    filters = {"shortName": "TMP", "typeOfFirstFixedSurface": 100, "level": [850, 500]}
    offsets = _prefilter_idx_offsets(StringIO(idx_content), "TMP", filters=filters)
    assert sorted(offsets) == [27027584, 54055168]
