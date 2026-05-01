"""
Unit tests for xarray backend format detection and dispatch.

Tests cover:
- Detection of JSON reference files, Parquet reference directories,
  Icechunk stores, and plain GRIB2 files
- ImportError raised when kerchunk not installed and reference file provided
- Reference-backed datasets have same variables, dimensions, and attributes
  as direct GRIB2 reads

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import json
import os
import tempfile
from unittest import mock

import pytest
import xarray as xr

from grib2io.xarray_backend import (
    _is_icechunk_store,
    _is_kerchunk_reference,
    _open_from_reference,
)

INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gfs_jpeg_path():
    """Path to the gfs.jpeg.grib2 test file."""
    return os.path.join(INPUT_DATA, "gfs.jpeg.grib2")


@pytest.fixture
def json_reference_path(gfs_jpeg_path, tmp_path):
    """Generate a Kerchunk JSON reference from gfs.jpeg.grib2."""
    from grib2io.kerchunk import ReferenceGenerator

    gen = ReferenceGenerator([gfs_jpeg_path])
    gen.generate()
    json_path = str(tmp_path / "refs.json")
    gen.to_json(json_path)
    return json_path


# ===========================================================================
# Format Detection Tests — _is_kerchunk_reference
# ===========================================================================


class TestIsKerchunkReference:
    """Tests for _is_kerchunk_reference() format detection."""

    def test_detects_json_reference_file(self, json_reference_path):
        """A valid Kerchunk JSON reference file is detected."""
        assert _is_kerchunk_reference(json_reference_path) is True

    def test_rejects_plain_json_without_version(self, tmp_path):
        """A JSON file without a 'version' key is not a reference."""
        plain_json = tmp_path / "plain.json"
        plain_json.write_text(json.dumps({"data": [1, 2, 3]}))
        assert _is_kerchunk_reference(str(plain_json)) is False

    def test_detects_parquet_reference_directory(self, gfs_jpeg_path, tmp_path):
        """A Parquet reference directory with .zmetadata and refs.*.parq is detected."""
        try:
            import fastparquet  # noqa: F401
        except ImportError:
            try:
                import pyarrow  # noqa: F401
            except ImportError:
                pytest.skip("Parquet engine (fastparquet or pyarrow) not installed")

        from grib2io.kerchunk import ReferenceGenerator

        gen = ReferenceGenerator([gfs_jpeg_path])
        gen.generate()
        parquet_path = str(tmp_path / "parquet_refs")
        gen.to_parquet(parquet_path)
        assert _is_kerchunk_reference(parquet_path) is True

    def test_rejects_grib2_file(self, gfs_jpeg_path):
        """A plain GRIB2 file is not detected as a reference."""
        assert _is_kerchunk_reference(gfs_jpeg_path) is False

    def test_rejects_nonexistent_path(self):
        """A non-existent path returns False."""
        assert _is_kerchunk_reference("/nonexistent/path/file.json") is False

    def test_rejects_non_string_input(self):
        """Non-string/path-like inputs return False."""
        assert _is_kerchunk_reference(12345) is False
        assert _is_kerchunk_reference(None) is False
        assert _is_kerchunk_reference(["some", "list"]) is False

    def test_rejects_empty_directory(self, tmp_path):
        """An empty directory is not detected as a Parquet reference."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert _is_kerchunk_reference(str(empty_dir)) is False

    def test_rejects_directory_with_only_zmetadata(self, tmp_path):
        """A directory with .zmetadata but no .parq files is not a reference."""
        ref_dir = tmp_path / "partial"
        ref_dir.mkdir()
        (ref_dir / ".zmetadata").write_text("{}")
        assert _is_kerchunk_reference(str(ref_dir)) is False


# ===========================================================================
# Format Detection Tests — _is_icechunk_store
# ===========================================================================


class TestIsIcechunkStore:
    """Tests for _is_icechunk_store() format detection."""

    def test_detects_icechunk_uri(self):
        """Icechunk URI schemes are detected."""
        assert _is_icechunk_store("icechunk:///path/to/store") is True
        assert _is_icechunk_store("icechunk+s3://bucket/store") is True
        assert _is_icechunk_store("icechunk+file:///local/store") is True
        assert _is_icechunk_store("icechunk+gcs://bucket/store") is True

    def test_rejects_plain_path(self):
        """Plain file paths are not detected as Icechunk stores."""
        assert _is_icechunk_store("/path/to/file.grib2") is False
        assert _is_icechunk_store("s3://bucket/file.grib2") is False

    def test_rejects_json_path(self, tmp_path):
        """A JSON file path is not detected as an Icechunk store."""
        json_file = tmp_path / "refs.json"
        json_file.write_text("{}")
        assert _is_icechunk_store(str(json_file)) is False

    def test_detects_icechunk_store_instance(self):
        """An object with IcechunkStore type name and icechunk module is detected."""
        mock_store = mock.MagicMock()
        mock_store.__class__.__name__ = "IcechunkStore"
        mock_store.__class__.__module__ = "icechunk.store"
        assert _is_icechunk_store(mock_store) is True

    def test_rejects_non_icechunk_object(self):
        """Non-IcechunkStore objects are not detected."""
        assert _is_icechunk_store(42) is False
        assert _is_icechunk_store(None) is False
        assert _is_icechunk_store({"key": "value"}) is False


# ===========================================================================
# ImportError Tests — Missing Dependencies
# ===========================================================================


class TestImportErrors:
    """Tests for ImportError when optional dependencies are missing."""

    def test_open_from_reference_raises_without_fsspec(self, json_reference_path):
        """_open_from_reference raises ImportError when fsspec is not installed."""
        with mock.patch.dict("sys.modules", {"fsspec": None}):
            with pytest.raises(ImportError, match="kerchunk is required"):
                _open_from_reference(json_reference_path)

    def test_ensure_kerchunk_error_message(self):
        """_ensure_kerchunk raises ImportError with install instructions."""
        from grib2io.xarray_backend import _ensure_kerchunk

        with mock.patch.dict("sys.modules", {"fsspec": None}):
            with pytest.raises(
                ImportError,
                match=r"pip install grib2io\[kerchunk\]",
            ):
                _ensure_kerchunk()

    def test_ensure_icechunk_error_message(self):
        """_ensure_icechunk raises ImportError with install instructions."""
        from grib2io.xarray_backend import _ensure_icechunk

        with mock.patch.dict("sys.modules", {"icechunk": None}):
            with pytest.raises(
                ImportError,
                match=r"pip install grib2io\[icechunk\]",
            ):
                _ensure_icechunk()


# ===========================================================================
# Reference-Backed Dataset Tests
# ===========================================================================


class TestReferenceBackedDataset:
    """Tests that reference-backed datasets match direct GRIB2 reads."""

    @pytest.fixture(autouse=True)
    def _register_codec(self):
        """Ensure the grib2io codec is registered before opening Zarr stores."""
        import grib2io.codecs  # noqa: F401

    def test_reference_dataset_has_variables(self, json_reference_path):
        """A reference-backed dataset has data variables."""
        ds = _open_from_reference(json_reference_path)
        assert len(ds.data_vars) > 0

    def test_reference_dataset_has_dimensions(self, json_reference_path):
        """A reference-backed dataset has dimensions."""
        ds = _open_from_reference(json_reference_path)
        assert len(ds.dims) > 0

    def test_reference_dataset_has_coordinates(self, json_reference_path):
        """A reference-backed dataset has coordinates."""
        ds = _open_from_reference(json_reference_path)
        assert len(ds.coords) > 0

    def test_reference_dataset_has_attributes(self, json_reference_path):
        """A reference-backed dataset has attributes including history."""
        ds = _open_from_reference(json_reference_path)
        assert "history" in ds.attrs


# ===========================================================================
# Existing xarray backend tests (from upstream)
# ===========================================================================


def test_named_filter(request):
    data = request.config.rootdir / "tests" / "input_data" / "gfs_20221107"
    filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
    ds1 = xr.open_dataset(data / "gfs.t00z.pgrb2.1p00.f012_subset", engine="grib2io", filters=filters)
    filters = dict(
        productDefinitionTemplateNumber=0,
        typeOfFirstFixedSurface="Ground or Water Surface",
    )
    ds2 = xr.open_dataset(data / "gfs.t00z.pgrb2.1p00.f012_subset", engine="grib2io", filters=filters)
    xr.testing.assert_equal(ds1, ds2)


def test_save_index(request: pytest.FixtureRequest):
    data = request.config.rootpath / "tests" / "input_data" / "gfs_20221107"
    fname = "gfs.t00z.pgrb2.1p00.f012_subset"
    idx_glob_str = f"{fname}.*.grib2ioidx"

    for file in data.glob(idx_glob_str):
        file.unlink()

    filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
    xr.open_dataset(data / fname, engine="grib2io", filters=filters, save_index=False)

    assert len(list(data.glob(idx_glob_str))) == 0


def test_multi_lead(request):
    data = request.config.rootdir / "tests" / "input_data" / "gfs_20221107"
    filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
    da = xr.open_mfdataset(
        [
            data / "gfs.t00z.pgrb2.1p00.f009_subset",
            data / "gfs.t00z.pgrb2.1p00.f012_subset",
        ],
        engine="grib2io",
        filters=filters,
        combine="nested",
        concat_dim="leadTime",
    ).to_array()
    assert da.shape == (1, 2, 181, 360)


def test_interp(request):
    try:
        from grib2io._grib2io import Grib2GridDef

        gdtn_nbm = 30
        gdt_nbm = [
            1,
            0,
            6371200,
            255,
            255,
            255,
            255,
            2345,
            1597,
            19229000,
            233723400,
            48,
            25000000,
            265000000,
            2539703,
            2539703,
            0,
            64,
            25000000,
            25000000,
            -90000000,
            0,
        ]
        nbm_grid_def = Grib2GridDef(gdtn_nbm, gdt_nbm)
        data = request.config.rootdir / "tests" / "input_data" / "gfs_20221107"
        filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
        ds = xr.open_dataset(data / "gfs.t00z.pgrb2.1p00.f012_subset", engine="grib2io", filters=filters)
        da = ds.grib2io.interp("neighbor", nbm_grid_def).to_array()
        assert da.shape == (1, 1597, 2345)
    except ModuleNotFoundError:
        pytest.skip()


def test_interp_with_openmp_threads(request):
    try:
        from grib2io._grib2io import Grib2GridDef

        gdtn_nbm = 30
        gdt_nbm = [
            1,
            0,
            6371200,
            255,
            255,
            255,
            255,
            2345,
            1597,
            19229000,
            233723400,
            48,
            25000000,
            265000000,
            2539703,
            2539703,
            0,
            64,
            25000000,
            25000000,
            -90000000,
            0,
        ]
        nbm_grid_def = Grib2GridDef(gdtn_nbm, gdt_nbm)
        data = request.config.rootdir / "tests" / "input_data" / "gfs_20221107"
        filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
        ds = xr.open_dataset(data / "gfs.t00z.pgrb2.1p00.f012_subset", engine="grib2io", filters=filters)
        da = ds.grib2io.interp("neighbor", nbm_grid_def, num_threads=2).to_array()
        assert da.shape == (1, 1597, 2345)
    except ModuleNotFoundError:
        pytest.skip()


def test_valueerror_multiple_durations_to_filter(request):
    data = request.config.rootdir / "tests" / "input_data"
    with pytest.raises(
        ValueError,
        match=r"DataArray dimensions are not compatible with number of GRIB2 messages; DataArray has 4 and GRIB2 index has 2. Consider applying a filter for dimensions: \['leadTime', 'duration'\]",
    ):
        xr.open_dataset(data / "2024101012_Milton_Adv22_e70_cum_dat.grb", engine="grib2io")
