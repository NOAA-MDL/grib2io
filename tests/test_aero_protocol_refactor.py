import pytest
import xarray as xr
import numpy as np
import datetime
import os
from unittest.mock import MagicMock, patch

# Note: We use mocking for low-level grib2io components to test xarray_backend logic
# without requiring the full C-library environment.

@pytest.fixture
def mock_grib2io_backend():
    with patch("grib2io.tables.get_value_from_table") as mock_lookup, \
         patch("grib2io.tables.get_table") as mock_get_table:
        mock_lookup.side_effect = lambda val, tbl: f"PTYPE_{val}"
        mock_get_table.return_value = {}
        yield mock_lookup, mock_get_table

def test_ptype_vectorization_and_laziness(mock_grib2io_backend):
    """
    STEP 2: The Proof (Double-Check Test)
    Verify that PTYPE decoding works for both Eager (NumPy) and Lazy (Dask) data.
    Includes check for variable-length string truncation.
    """
    from grib2io.xarray_backend import _decode_ptype
    mock_lookup, _ = mock_grib2io_backend

    # Setup mock to return variable length strings
    # '1' -> 'Short', '2' -> 'VeryLongString'
    mock_lookup.side_effect = lambda val, tbl: "Short" if str(val) == "1" else "VeryLongString"

    # 1. Eager check (NumPy)
    eager_data = np.array([1, 2])
    decoded_eager = _decode_ptype(eager_data)
    assert decoded_eager.dtype == np.dtypes.StringDType or isinstance(decoded_eager.dtype, np.dtypes.StringDType)
    assert decoded_eager[1] == "VeryLongString"
    assert decoded_eager[0] == "Short"

    # 2. Lazy check (Dask)
    import dask.array as da
    lazy_data = da.from_array(eager_data, chunks=2)
    da_ptype = xr.DataArray(lazy_data, dims="x", name="threshold_lower_limit")

    # Apply _decode_ptype via apply_ufunc (simulating parse_data_model)
    decoded_lazy = xr.apply_ufunc(
        _decode_ptype,
        da_ptype,
        dask="parallelized",
        output_dtypes=[np.dtypes.StringDType],
    )

    assert decoded_lazy.chunks is not None
    assert decoded_lazy.dtype == np.dtypes.StringDType or isinstance(decoded_lazy.dtype, np.dtypes.StringDType)

    # Verify result identity
    assert (decoded_lazy.compute().values == decoded_eager).all()

def test_scientific_provenance_initialization():
    """
    Verify that scientific provenance (history) is initialized during data load.
    """
    import pandas as pd
    # We mock the entire open_dataset process to check if history is added
    from grib2io.xarray_backend import GribBackendEntrypoint

    engine = GribBackendEntrypoint()

    # Mocking internal calls to avoid I/O
    with patch("grib2io.open"), \
         patch("grib2io.xarray_backend.msgs_from_index"), \
         patch("grib2io.xarray_backend.parse_grib_index") as mock_parse, \
         patch("grib2io.xarray_backend.make_variables") as mock_make, \
         patch("grib2io.xarray_backend.build_da_without_coords") as mock_build, \
         patch("grib2io.xarray_backend.assign_xr_meta") as mock_assign:

        mock_parse.return_value = (MagicMock(), {}, {}, {})
        mock_make.return_value = ([pd.DataFrame({"shortName": ["TMP"]})], {}, {})

        mock_da = xr.DataArray([1.0], name="TMP")
        mock_build.return_value = mock_da

        mock_ds = xr.Dataset({"TMP": mock_da})
        mock_assign.return_value = mock_ds

        ds = engine.open_dataset("dummy.grib2")

        assert "history" in ds.attrs
        assert "Initialized via grib2io.open_dataset" in ds.attrs["history"]
        assert "UTC" in ds.attrs["history"]

def test_scientific_provenance_transformation():
    """
    Verify that provenance is preserved and updated during transformations.
    """
    from grib2io.xarray_backend import parse_data_model

    ds = xr.Dataset({"TMP": (("y", "x"), np.random.rand(2, 2))})
    ds.TMP.attrs["typeOfFirstFixedSurface"] = ("Surface", "m")
    ds.TMP.attrs["units"] = "m"
    ds.attrs["history"] = "Original history\n"

    with patch("grib2io.tables.get_table") as mock_get_table:
        mock_get_table.return_value = {}
        ds_transformed = parse_data_model(ds, "nws-viz")

    assert "history" in ds_transformed.attrs
    assert "Parsed to data model nws-viz" in ds_transformed.attrs["history"]
    assert "Original history" in ds_transformed.attrs["history"]
