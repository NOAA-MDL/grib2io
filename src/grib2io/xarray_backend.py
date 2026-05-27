"""
grib2io Backend Engine for Xarray
=================================
grib2io provides a Xarray backend entrypoint for decoding many GRIB2 messages
from a single file or many files and represented as Xarray DataArray objects and
collected along common coordinates as Datasets and DataTrees.

.. warning::

   The ``grib2io.xarray_backend`` engine API is **experimental**.
   Its interface and behavior may change in future releases,
   which could affect backward compatibility.

   Users are encouraged to treat this backend as subject to change
   and to pin their ``grib2io`` version if depending on its current
   implementation details.
"""

from grib2io._grib2io import _data
from grib2io import Grib2Message, Grib2GridDef, msgs_from_index, tables, templates
from grib2io.utils.spatial import snap_to_nearest_cell_center
import grib2io
from xarray.backends.locks import SerializableLock
from xarray.core import indexing
from xarray.backends import (
    BackendArray,
    BackendEntrypoint,
)
from copy import copy
from dataclasses import dataclass, field, astuple
import datetime
import glob
import itertools
import json
import logging
import os
import re
import textwrap
import typing
from numpy.typing import NDArray
import warnings

from . import tables

import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path
from pyproj import CRS

# Check if xarray version supports DataTree
_HAS_DATATREE = hasattr(xr, "DataTree")

# Check for NumPy 2.0+ StringDType
_HAS_STRINGDTYPE = hasattr(np, "dtypes") and hasattr(np.dtypes, "StringDType")

_logger = logging.getLogger(__name__)

_LOCK = SerializableLock()

_LEVEL_NAME_MAPPING = grib2io.tables.get_table("4.5.grib2io.level.name")

_TREE_HIERARCHY_LEVELS = [
    "typeOfFirstFixedSurface",
    "valueOfFirstFixedSurface",
    "productDefinitionTemplateNumber",
    "perturbationNumber",
    "leadTime",
    "duration",
    "percentileValue",
    "typeOfProbability",
    "thresholdLowerLimit",
    "thresholdUpperLimit",
]


def _decode_ptype(values: np.ndarray) -> np.ndarray:
    """
    Decode numeric precipitation type codes into human-readable strings.

    Parameters
    ----------
    values : np.ndarray
        Array of numeric precipitation type codes.

    Returns
    -------
    np.ndarray
        Array of decoded precipitation type strings.
    """
    return _decode_code(values, "4.201")


def _decode_code(values: np.ndarray, table: str) -> np.ndarray:
    """
    Decode numeric codes into human-readable strings using a GRIB2 table.

    Parameters
    ----------
    values : np.ndarray
    Array of numeric codes.
    table : str
    The GRIB2 table to use for decoding (e.g., "4.201").

    Returns
    -------
    np.ndarray
    Array of decoded string definitions.
    """

    def _lookup(val):
        res = tables.get_value_from_table(str(int(val)), table)
        if isinstance(res, list):
            return str(res[0])
        return str(res)

    # Pass otypes to avoid string truncation based on the first element
    # Use StringDType if available (NumPy 2.0+), otherwise fallback to object
    if _HAS_STRINGDTYPE:
        vlookup = np.vectorize(_lookup, otypes=[np.dtypes.StringDType])
    else:
        vlookup = np.vectorize(_lookup, otypes=[object])
    return vlookup(values)


AVAILABLE_NON_GEO_COORDS = [
    "duration",
    "leadTime",
    "percentileValue",
    "perturbationNumber",
    "refDate",
    "thresholdLowerLimit",
    "thresholdUpperLimit",
    "valueOfFirstFixedSurface",
    "valueOfSecondFixedSurface",
    "typeOfAerosol",
    "constituentType",
    "sourceSinkIndicator",
    "firstWavelength",
    "secondWavelength",
    "firstSizeOfAerosol",
    "secondSizeOfAerosol",
    "scaledValueOfFirstWavelength",
    "scaledValueOfSecondWavelength",
    "scaledValueOfCentralWaveNumber",
    "scaledValueOfFirstSize",
    "scaledValueOfSecondSize",
]
"""Available non-geographic coordinate names."""

AVAILABLE_NON_GEO_DIMS = [
    "duration",
    "leadTime",
    "percentileValue",
    "perturbationNumber",
    "refDate",
    "threshold",
    "level",
    "typeOfAerosol",
    "constituentType",
    "sourceSinkIndicator",
    "firstWavelength",
    "secondWavelength",
    "firstSizeOfAerosol",
    "secondSizeOfAerosol",
]
"""Available non-geographic dimension names."""

# Lookup table to define surface types that should be parsed as vertical coordinates
VERTICAL_COORDINATE_SURFACES = [
    "Ground or Water Surface",
    "Isothermal Level",
    "Specified radius from the centre of the Sun",
    "Isobaric Surface",
    "Mean Sea Level",
    "Specific Altitude Above Mean Sea Level",
    "Specified Height Level Above Ground",
    "Sigma Level",
    "Hybrid Level",
    "Depth Below Land Surface",
    "Isentropic (theta) Level",
    "Level at Specified Pressure Difference from Ground to Level",
    "Potential Vorticity Surface",
    "Eta Level",
    "Logarithmic Hybrid Level",
    "Sigma height level",
    "Hybrid Height Level",
    "Hybrid Pressure Level",
    "Soil level",
    "Sea-ice level",
    "Depth Below Sea Level",
    "Depth Below Water Surface",
    "Ocean Model Level",
    "Ocean level defined by water density (sigma-theta) difference from near-surface to level",
    "Ocean level defined by water potential temperature difference from near-surface to level",
    "Ocean level defined by vertical eddy diffusivity difference from near-surface to level",
    "Ocean level defined by water density (rho) difference from near-surface to level",
]
"""
Lookup table to define surface types that should be parsed as vertical coordinates
when `data_model="nws-viz"`.
"""


def parse_data_model(ds: xr.Dataset, data_model: str) -> xr.Dataset:
    """
    Normalize a GRIB2-derived Dataset to a target data model (currently ``"nws-viz"``).

    When ``data_model == "nws-viz"``, this function converts coordinate and
    variable names to snake_case, derives CF-like metadata, promotes select
    GRIB-derived quantities to coordinates, optionally swaps dimensions, and
    standardizes units/attributes. If ``data_model`` is anything else, the
    input dataset is returned unchanged.

    Parameters
    ----------
    ds : xarray.Dataset
        GRIB2-derived dataset whose variables and attributes follow the
        conventions emitted by ``grib2io``. Expected to contain GRIB-related
        attributes such as ``typeOfFirstFixedSurface``,
        ``typeOfSecondFixedSurface``, and (for probabilistic variables)
        ``typeOfProbability``.
    data_model : str
        Target data model name. Only the value ``"nws-viz"`` triggers
        transformations.

    Returns
    -------
    xarray.Dataset
        A new dataset with:
        * Selected coordinates renamed:
          ``refDate -> forecast_reference_time``,
          ``leadTime -> lead_time``,
          ``validDate -> time``,
          ``percentileValue -> percentile``,
          ``thresholdLowerLimit -> threshold_lower_limit``,
          ``thresholdUpperLimit -> threshold_upper_limit``.
        * Vertical coordinates derived from
          ``valueOfFirstFixedSurface`` / ``valueOfSecondFixedSurface`` and their
          corresponding ``typeOf*FixedSurface`` definitions. New coordinate
          names are generated from the surface definition (lowercased, spaces
          to underscores, punctuation removed). If the name already exists, a
          ``"_2"`` suffix is appended.
        * Possible dimension swaps:
          ``level -> <derived_vertical_coord>`` when present; and for
          probabilistic variables, ``threshold -> threshold_lower_limit`` or
          ``threshold -> threshold_upper_limit`` when
          ``typeOfProbability`` indicates the appropriate semantics.
        * Variable names lowercased; dataset- and variable-level attributes
          converted to snake_case (except GRIB section attributes which are
          normalized to ``grib...``).
        * CF-adjacent metadata populated: ``standard_name`` and
          ``cell_methods`` are set via the shortname→CF lookup table.
        * Percent units normalized from ``"%"`` to ``"percent"`` on coordinates.
        * For precipitation type (``PTYPE``) thresholds, numeric codes are
          decoded to strings (GRIB2 Table 4.201) in relevant attrs/coords.

    Notes
    -----
    - Precipitation type decoding uses GRIB2 Table 4.201 via
      ``tables.get_value_from_table(code, "4.201")`` and returns a NumPy
      array with ``np.dtypes.StringDType``.
    - CF-related lookups are performed using
      ``tables.get_table("shortname_to_cf")``.
    - Vertical coordinate surface names are validated against
      ``VERTICAL_COORDINATE_SURFACES`` before promotion to coordinates.

    Warnings
    --------
    This function assumes the presence of certain GRIB-derived attributes on the
    first data variable (e.g., ``typeOfFirstFixedSurface``,
    ``typeOfSecondFixedSurface``, and possibly ``typeOfProbability``).
    If these are absent or malformed, errors (e.g., ``KeyError``) may occur.

    Examples
    --------
    >>> ds2 = parse_data_model(ds, "nws-viz")
    >>> list(ds2.coords)
    ['forecast_reference_time', 'lead_time', 'time', 'percentile', ...]
    """
    # convert coordinates and attributes to CF if requested
    if data_model == "nws-viz":
        # define regex to convert to snake case
        pattern = re.compile(r"(?<!^)(?=[A-Z])")

        # check for coordinates and rename
        for coord in ds.coords:
            if coord == "refDate":
                ds = ds.rename({"refDate": "forecast_reference_time"})

            elif coord == "leadTime":
                ds = ds.rename({"leadTime": "lead_time"})

            elif coord == "validDate":
                ds = ds.rename({"validDate": "time"})

            elif coord == "percentileValue":
                ds = ds.rename({"percentileValue": "percentile"})

            elif coord == "perturbationNumber":
                ds = ds.rename({"perturbationNumber": "perturbation"})
                ds["perturbation"].attrs["long_name"] = "Ensemble Perturbation Number"

            elif coord == "thresholdLowerLimit":
                ds = ds.rename({"thresholdLowerLimit": "threshold_lower_limit"})
                ds["threshold_lower_limit"].attrs["long_name"] = "Threshold Lower Limit"
                ds["threshold_lower_limit"].attrs["units"] = ds[list(ds.data_vars.keys())[0]].attrs["units"]

                if "PTYPE" in ds.data_vars:
                    ds["threshold_lower_limit"] = xr.apply_ufunc(
                        _decode_ptype,
                        ds["threshold_lower_limit"],
                        dask="parallelized",
                        output_dtypes=[np.dtypes.StringDType] if _HAS_STRINGDTYPE else [object],
                    )

                # check if thresholdLowerLimit should be a dimension coordinate
                if "threshold" in ds.dims:
                    var_key = list(ds.data_vars.keys())[0]
                    prob_types = [
                        "Probability of event below lower limit",
                        "Probability of event above lower limit",
                        "Probability of event equal to lower limit",
                        "Probability of event between upper and lower limits (the range includes lower limit but not the upper limit)",
                    ]
                    if ds[var_key].attrs["typeOfProbability"] in prob_types:
                        ds = ds.swap_dims({"threshold": "threshold_lower_limit"})

            elif coord == "thresholdUpperLimit":
                ds = ds.rename({"thresholdUpperLimit": "threshold_upper_limit"})
                ds["threshold_upper_limit"].attrs["long_name"] = "Threshold Upper Limit"
                ds["threshold_upper_limit"].attrs["units"] = ds[list(ds.data_vars.keys())[0]].attrs["units"]

                if "PTYPE" in ds.data_vars:
                    ds["threshold_upper_limit"] = xr.apply_ufunc(
                        _decode_ptype,
                        ds["threshold_upper_limit"],
                        dask="parallelized",
                        output_dtypes=[np.dtypes.StringDType] if _HAS_STRINGDTYPE else [object],
                    )

                if "threshold" in ds.dims:
                    var_key = list(ds.data_vars.keys())[0]
                    prob_types = [
                        "Probability of event below upper limit",
                        "Probability of event above upper limit",
                    ]
                    if ds[var_key].attrs["typeOfProbability"] in prob_types:
                        ds = ds.swap_dims({"threshold": "threshold_upper_limit"})

            elif coord == "typeOfAerosol":
                ds = ds.rename({"typeOfAerosol": "aerosol_type"})
                ds["aerosol_type"].attrs["long_name"] = "Aerosol Type"
                ds["aerosol_type"] = xr.apply_ufunc(
                    _decode_code,
                    ds["aerosol_type"],
                    "4.233",
                    dask="parallelized",
                    output_dtypes=[np.dtypes.StringDType] if _HAS_STRINGDTYPE else [object],
                )

            elif coord == "constituentType":
                ds = ds.rename({"constituentType": "constituent_type"})
                ds["constituent_type"].attrs["long_name"] = "Chemical Constituent Type"
                ds["constituent_type"] = xr.apply_ufunc(
                    _decode_code,
                    ds["constituent_type"],
                    "4.230",
                    dask="parallelized",
                    output_dtypes=[np.dtypes.StringDType] if _HAS_STRINGDTYPE else [object],
                )

            elif coord == "sourceSinkIndicator":
                ds = ds.rename({"sourceSinkIndicator": "source_sink_indicator"})
                ds["source_sink_indicator"].attrs["long_name"] = "Source/Sink Indicator"
                ds["source_sink_indicator"] = xr.apply_ufunc(
                    _decode_code,
                    ds["source_sink_indicator"],
                    "4.238",
                    dask="parallelized",
                    output_dtypes=[np.dtypes.StringDType] if _HAS_STRINGDTYPE else [object],
                )

            elif coord == "firstWavelength":
                ds = ds.rename({"firstWavelength": "first_wavelength"})
                ds["first_wavelength"].attrs["long_name"] = "First Wavelength"
                ds["first_wavelength"].attrs["units"] = "m"

            elif coord == "secondWavelength":
                ds = ds.rename({"secondWavelength": "second_wavelength"})
                ds["second_wavelength"].attrs["long_name"] = "Second Wavelength"
                ds["second_wavelength"].attrs["units"] = "m"

            elif coord == "firstSizeOfAerosol":
                ds = ds.rename({"firstSizeOfAerosol": "first_size_of_aerosol"})
                ds["first_size_of_aerosol"].attrs["long_name"] = "First Size of Aerosol"
                ds["first_size_of_aerosol"].attrs["units"] = "m"

            elif coord == "secondSizeOfAerosol":
                ds = ds.rename({"secondSizeOfAerosol": "second_size_of_aerosol"})
                ds["second_size_of_aerosol"].attrs["long_name"] = "Second Size of Aerosol"
                ds["second_size_of_aerosol"].attrs["units"] = "m"

            elif coord == "scaledValueOfFirstWavelength":
                ds = ds.rename({"scaledValueOfFirstWavelength": "scaled_first_wavelength"})
                ds["scaled_first_wavelength"].attrs["long_name"] = "Scaled Value of First Wavelength"

            elif coord == "scaledValueOfSecondWavelength":
                ds = ds.rename({"scaledValueOfSecondWavelength": "scaled_second_wavelength"})
                ds["scaled_second_wavelength"].attrs["long_name"] = "Scaled Value of Second Wavelength"

            elif coord == "scaledValueOfCentralWaveNumber":
                ds = ds.rename({"scaledValueOfCentralWaveNumber": "scaled_central_wave_number"})
                ds["scaled_central_wave_number"].attrs["long_name"] = "Scaled Value of Central Wave Number"

            elif coord == "scaledValueOfFirstSize":
                ds = ds.rename({"scaledValueOfFirstSize": "scaled_first_size"})
                ds["scaled_first_size"].attrs["long_name"] = "Scaled Value of First Size"

            elif coord == "scaledValueOfSecondSize":
                ds = ds.rename({"scaledValueOfSecondSize": "scaled_second_size"})
                ds["scaled_second_size"].attrs["long_name"] = "Scaled Value of Second Size"

            # If the dataset has valueOfFirstFixedSurface as a coordinate
            elif coord == "valueOfFirstFixedSurface":
                # Get the valueOfFirstFixedSurface coordinate
                da = ds.valueOfFirstFixedSurface

                # Get the definition and units from typeOfFirstFixedSurface
                var_key = list(ds.data_vars.keys())[0]
                definition, units = ds[var_key].attrs["typeOfFirstFixedSurface"]

                if definition in VERTICAL_COORDINATE_SURFACES:
                    # Convert definition to lowercase and replace spaces with underscores
                    key = definition.lower().replace(" ", "_")

                    # remove special characters
                    key = re.sub(r"[^a-z0-9_]", "", key)

                    # Add units and grib_name attributes
                    da.attrs["units"] = units
                    da.attrs["grib_name"] = [
                        "valueOfFirstFixedSurface",
                        "typeOfFirstFixedSurface",
                    ]

                    # Assign the coordinate with the new key name
                    ds = ds.assign_coords({key: da})

                    # If valueOfFirstFixedSurface is a dimension, swap it with the new key
                    if "level" in ds.dims:
                        ds = ds.swap_dims({"level": key})

                # Remove the original coordinates
                del ds["valueOfFirstFixedSurface"]

            # If the dataset has valueOfSecondFixedSurface as a coordinate
            elif coord == "valueOfSecondFixedSurface":
                # Get the valueOfSecondFixedSurface coordinate
                da = ds.valueOfSecondFixedSurface

                # Get the definition and units from typeOfSecondFixedSurface
                var_key = list(ds.data_vars.keys())[0]
                definition, units = ds[var_key].attrs["typeOfSecondFixedSurface"]

                if definition in VERTICAL_COORDINATE_SURFACES:
                    # Convert definition to lowercase and replace spaces with underscores
                    key = definition.lower().replace(" ", "_")

                    # remove special characters
                    key = re.sub(r"[^a-z0-9_]", "", key)

                    # check if key is already in coords
                    if key in ds.coords:
                        key = key + "_2"

                    # Add units and grib_name attributes
                    da.attrs["units"] = units
                    da.attrs["grib_name"] = [
                        "valueOfSecondFixedSurface",
                        "typeOfSecondFixedSurface",
                    ]

                    # Assign the coordinate with the new key name
                    ds = ds.assign_coords({key: da})

                # Remove the original coordinates
                del ds["valueOfSecondFixedSurface"]
            else:
                # change coord name to snake case
                new_coord_name = pattern.sub("_", coord).lower()
                ds = ds.rename({coord: new_coord_name})

        # convert all attributes and variable names to snake case
        for var in ds.data_vars:
            da = ds[var]
            record = tables.get_table("shortname_to_cf").get(da.name)
            da.attrs["standard_name"] = "unknown" if record is None else record["cf_standard_name"]
            da.attrs["cell_methods"] = "unknown" if record is None else record["cf_cell_methods"]

            ds[var] = da

            # rename variable
            new_var_name = var.lower()
            ds = ds.rename({var: new_var_name})

            # remove attr for typeOfFirstFixedSurface (applied as coordinate above)
            if "typeOfFirstFixedSurface" in ds[new_var_name].attrs:
                definition, units = ds[new_var_name].attrs["typeOfFirstFixedSurface"]
                ds[new_var_name].attrs["typeOfFirstFixedSurface"] = f"{definition} ({units})"

            if "typeOfSecondFixedSurface" in ds[new_var_name].attrs:
                definition, units = ds[new_var_name].attrs["typeOfSecondFixedSurface"]
                ds[new_var_name].attrs["typeOfSecondFixedSurface"] = f"{definition} ({units})"

            ds[new_var_name].attrs.pop("percentileValue", None)

            if "threshold_lower_limit" in ds.coords:
                ds[new_var_name].attrs.pop("thresholdLowerLimit", None)

            if "threshold_upper_limit" in ds.coords:
                ds[new_var_name].attrs.pop("thresholdUpperLimit", None)

            for attr in list(ds[new_var_name].attrs.keys()):
                # skip grib section attrs
                if "GRIB2IO_section" in attr:
                    # replace GRIB2IO with grib in attr
                    new_attr_name = attr.replace("GRIB2IO", "grib")
                else:
                    # change attr name to snake case
                    new_attr_name = pattern.sub("_", attr).lower()

                # update new attr name for specific CF names
                if new_attr_name == "full_name":
                    new_attr_name = "long_name"

                # change % to percent
                if attr == "units" and ds[new_var_name].attrs[attr] == "%":
                    ds[new_var_name].attrs[attr] = "percent"

                if new_var_name == "ptype" and "threshold" in new_attr_name:
                    value = ds[new_var_name].attrs.pop(attr)
                    ds[new_var_name].attrs[attr] = _decode_ptype(value)
                else:
                    # change attr name in attrs
                    ds[new_var_name].attrs[new_attr_name] = ds[new_var_name].attrs.pop(attr)

        # change dataset attrs to snake case
        for attr in list(ds.attrs.keys()):
            # change attr name to snake case
            new_attr_name = pattern.sub("_", attr).lower()

            # change attr name in attrs
            ds.attrs[new_attr_name] = ds.attrs.pop(attr)

        # change % to percent
        for coord in ds.coords:
            if "units" in ds[coord].attrs and ds[coord].attrs["units"] == "%":
                ds[coord].attrs["units"] = "percent"

        # Update history for provenance
        history = ds.attrs.get("history", "")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ds.attrs["history"] = f"{now}: Parsed to data model {data_model}\n{history}"

    # Update history for provenance
    history = ds.attrs.get("history", "")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ds.attrs["history"] = f"{now}: Normalized to {data_model} data model\n{history}"

    return ds


# ---------------------------------------------------------------------------
# Lazy import guards for optional dependencies
# ---------------------------------------------------------------------------


def _ensure_kerchunk():
    """Raise ``ImportError`` if *kerchunk* / *fsspec* reference support is not available."""
    try:
        import fsspec  # noqa: F401
    except ImportError:
        raise ImportError("kerchunk is required for reference generation. Install with: pip install grib2io[kerchunk]")


def _ensure_icechunk():
    """Raise ``ImportError`` if *icechunk* is not available."""
    try:
        import icechunk  # noqa: F401
    except ImportError:
        raise ImportError("icechunk is required for virtual store support. Install with: pip install grib2io[icechunk]")


# ---------------------------------------------------------------------------
# Format detection helpers
# ---------------------------------------------------------------------------


def _is_kerchunk_reference(filename_or_obj) -> bool:
    """Detect whether *filename_or_obj* is a Kerchunk reference file.

    Detection logic:
    - **JSON reference**: path is a string ending with ``.json`` and the file
      contains a ``"version"`` key at the top level.
    - **Parquet reference**: path is a string pointing to a directory that
      contains a ``.zmetadata`` file and at least one ``refs.*.parq`` file
      beneath the directory:

      my_dataset.parq/
      |-- .zmetadata          <-- Consolidated metadata
      |--  var1/
           |--  refs.0.parq   <-- Parquet chunk references for variable 1
      |--  var2/
           |--  refs.0.parq   <-- Parquet chunk references for variable 2

    """
    if not isinstance(filename_or_obj, (str, os.PathLike)):
        return False

    path = str(filename_or_obj)

    # JSON reference detection
    if path.endswith(".json"):
        try:
            with open(path) as f:
                data = json.load(f)
            return isinstance(data, dict) and "version" in data
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False

    # Parquet reference detection
    if os.path.isdir(path):
        has_zmetadata = os.path.isfile(os.path.join(path, ".zmetadata"))
        has_parq = any(Path(path).rglob("refs.*.parq"))
        return has_zmetadata and has_parq

    return False


def _is_icechunk_store(filename_or_obj) -> bool:
    """Detect whether *filename_or_obj* is an Icechunk store."""
    # Check for IcechunkStore instance
    type_name = type(filename_or_obj).__name__
    type_module = type(filename_or_obj).__module__ or ""
    if "IcechunkStore" in type_name and "icechunk" in type_module:
        return True

    if isinstance(filename_or_obj, (str, os.PathLike)):
        path = str(filename_or_obj)
        icechunk_schemes = ("icechunk://", "icechunk+s3://", "icechunk+file://", "icechunk+gcs://")
        if path.startswith(icechunk_schemes):
            return True
        if os.path.isdir(path):
            # Check for Icechunk v2 directory indicators
            if os.path.exists(os.path.join(path, "repo")) and os.path.exists(os.path.join(path, "snapshots")):
                return True
    return False


def _open_from_reference(filename_or_obj, data_model=None, drop_variables=None, chunks=None, **kwargs) -> xr.Dataset:
    """Open a Kerchunk reference file as an xarray Dataset."""
    _ensure_kerchunk()
    import fsspec
    import grib2io.codecs  # noqa: F401

    fs = fsspec.filesystem("reference", fo=str(filename_or_obj))
    mapper = fs.get_mapper("")

    open_kwargs = {"consolidated": False}
    if chunks is not None:
        open_kwargs["chunks"] = chunks
    if drop_variables is not None:
        open_kwargs["drop_variables"] = drop_variables

    open_kwargs.update(kwargs)

    ds = xr.open_zarr(mapper, **open_kwargs)

    if data_model is not None:
        ds = parse_data_model(ds, data_model)

    history = ds.attrs.get("history", "")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ds.attrs["history"] = f"{now}: Initialized via grib2io xarray backend from Kerchunk reference {filename_or_obj}\n{history}"

    return ds


def _open_from_icechunk(
    filename_or_obj,
    data_model=None,
    drop_variables=None,
    chunks=None,
    branch="main",
    **kwargs,
) -> xr.Dataset:
    """Open an Icechunk store as an xarray Dataset."""
    _ensure_icechunk()
    import icechunk
    import grib2io.codecs  # noqa: F401

    if hasattr(filename_or_obj, "get") and hasattr(filename_or_obj, "set"):
        # Assume it's already a store-like object
        store = filename_or_obj
    else:
        uri = str(filename_or_obj)
        if uri.startswith("icechunk+s3://"):
            storage = icechunk.storage.s3_storage(uri.replace("icechunk+s3://", "s3://"))
        elif uri.startswith("icechunk+gcs://"):
            storage = icechunk.storage.gcs_storage(uri.replace("icechunk+gcs://", "gcs://"))
        elif uri.startswith("icechunk+file://"):
            local_path = uri.replace("icechunk+file://", "")
            storage = icechunk.storage.local_filesystem_storage(path=local_path)
        elif uri.startswith("icechunk://"):
            local_path = uri.replace("icechunk://", "")
            storage = icechunk.storage.local_filesystem_storage(path=local_path)
        elif "://" in uri:
            # Fallback for other URI schemes
            storage = icechunk.storage.local_filesystem_storage(path=uri)
        else:
            storage = icechunk.storage.local_filesystem_storage(path=uri)

        repo = icechunk.Repository.open(storage)
        session = repo.readonly_session(branch)
        store = session.store

    open_kwargs = {"consolidated": False}
    if chunks is not None:
        open_kwargs["chunks"] = chunks
    if drop_variables is not None:
        open_kwargs["drop_variables"] = drop_variables

    open_kwargs.update(kwargs)

    ds = xr.open_zarr(store, **open_kwargs)

    if data_model is not None:
        ds = parse_data_model(ds, data_model)

    history = ds.attrs.get("history", "")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ds.attrs["history"] = f"{now}: Initialized via grib2io xarray backend from Icechunk store {filename_or_obj}\n{history}"

    return ds


class GribBackendEntrypoint(BackendEntrypoint):
    """
    xarray backend engine entrypoint for opening and decoding grib2 files.

    .. warning::

       This backend is experimental and the API/behavior may change without
       backward compatibility.
    """

    def open_dataset(
        self,
        filename_or_obj,
        drop_variables=None,
        save_index=True,
        filters=None,
        data_model=None,
        chunks=None,
        branch="main",
        use_icechunk=False,
        storage_options=None,
        max_workers=None,
        network_timeout=120,
        max_concurrent_requests=32,
        max_scan_attempts=3,
        store_path=None,
    ) -> xr.Dataset:
        """
        Read and parse metadata from a GRIB2 file.

        Parameters
        ----------
        filename_or_obj : str or file-like
            GRIB2 file to be opened. Can be a local path, a remote URI, a
            Kerchunk reference, or an Icechunk store.
        drop_variables : list of str, optional
            List of variables to exclude from the dataset.
        save_index : bool, optional
            Whether to save the GRIB2 index to a file (default is True).
        filters : dict, optional
            Filter GRIB2 messages to a single hypercube. Dictionary keys can
            be any GRIB2 metadata attribute name.
        data_model : str, optional
            Parse GRIB metadata following a defined data model convention
            (e.g., "nws-viz").
        chunks : int, dict or 'auto', optional
            If chunks is provided, it is used to load the dataset into a
            dask-backed dataset.
        branch : str, optional
            Icechunk branch to open (only for Icechunk stores). Defaults to "main".
        use_icechunk : bool, optional
            If True, use the Icechunk virtual store path for robust remote
            data access. Recommended for large numbers of remote files or
            unreliable networks. Defaults to False.
        storage_options : dict, optional
            Extra options passed to the storage backend (e.g. fsspec or Icechunk).
        max_workers : int, optional
            Number of threads for parallel manifest scanning.
        network_timeout : int, optional
            HTTP stream timeout in seconds for remote reads. Defaults to 120.
        max_concurrent_requests : int, optional
            Maximum concurrent HTTP requests for remote reads. Defaults to 32.
        max_scan_attempts : int, optional
            Maximum attempts to scan remote GRIB2 files. Defaults to 3.
        store_path : str, optional
            Filesystem path for the temporary Icechunk repository.

        Returns
        -------
        xarray.Dataset
            Xarray dataset of GRIB2 messages.
        """
        if filters is None:
            filters = {}

        # --- Use Icechunk virtual store path if requested ---
        if use_icechunk:
            from .icechunk import open_grib2

            return open_grib2(
                filename_or_obj,
                storage_options=storage_options,
                filters=filters,
                store_path=store_path,
                max_workers=max_workers,
                network_timeout=network_timeout,
                max_concurrent_requests=max_concurrent_requests,
                max_scan_attempts=max_scan_attempts,
                data_model=data_model,
                drop_variables=drop_variables,
                chunks=chunks,
            )

        # --- Format detection: Kerchunk reference or Icechunk store ---
        if _is_kerchunk_reference(filename_or_obj):
            return _open_from_reference(
                filename_or_obj,
                data_model=data_model,
                drop_variables=drop_variables,
                chunks=chunks,
            )
        if _is_icechunk_store(filename_or_obj):
            return _open_from_icechunk(
                filename_or_obj,
                data_model=data_model,
                drop_variables=drop_variables,
                chunks=chunks,
                branch=branch,
            )

        with grib2io.open(filename_or_obj, save_index=save_index, _xarray_backend=True) as f:
            file_index = pd.DataFrame(f._index)
            file_index = file_index.assign(msg=list(f))

        ds = _open_dataset_from_index(
            file_index,
            filename_or_obj,
            filters,
            data_model,
            drop_variables=drop_variables,
            chunks=chunks,
        )

        # Update history for provenance
        history = ds.attrs.get("history", "")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ds.attrs["history"] = f"{now}: Initialized via grib2io.open_dataset from {filename_or_obj}\n{history}"

        return ds

    def open_datatree(
        self,
        filename_or_obj,
        drop_variables=None,
        save_index=True,
        filters=None,
        stack_vertical=False,
        chunks=None,
    ) -> typing.Any:
        """
        Open a GRIB2 file as an xarray DataTree.

        Parameters
        ----------
        filename : str
            Path to the GRIB2 file.
        drop_variables : list, optional
            List of variables to exclude.
        filters : dict, optional
            Filter criteria for GRIB2 messages.
        stack_vertical : bool, optional
            If True, organize the tree with vertical layers stacked in a single dataset.
        chunks : int, dict or 'auto', optional
            If chunks is provided, it is used to load the dataset into a
            dask-backed dataset.

        Returns
        -------
        xarray.DataTree
            A hierarchical DataTree representation of the GRIB2 data.
        """
        if not _HAS_DATATREE:
            raise ImportError("xarray version does not support DataTree functionality.")

        if filters is None:
            filters = {}

        # Open the file without any filters first to get all messages
        with grib2io.open(filename_or_obj, save_index=save_index, _xarray_backend=True) as f:
            file_index = pd.DataFrame(f._index)
            file_index = file_index.assign(msg=list(f))

        # Build tree structure from GRIB messages with specified options
        tree = build_datatree_from_grib(
            filename_or_obj,
            file_index,
            filters,
            stack_vertical=stack_vertical,
            drop_variables=drop_variables,
            chunks=chunks,
        )

        # Update history for provenance
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        history = f"{now}: Initialized via grib2io.open_datatree\n"

        def _add_history(node):
            if node.ds is not None:
                node.ds.attrs["history"] = history + node.ds.attrs.get("history", "")
            for child in node.children.values():
                _add_history(child)

        _add_history(tree)

        # Put warning here so it is the last message from likely other Xarray warnings.
        warnings.warn(
            "grib2io’s xarray backend DataTree support is experimental. The DataTree structure or attributes may change in future releases.",
            UserWarning,
            stacklevel=2,
        )

        return tree


class GribBackendArray(BackendArray):
    """
    BackendArray implementation for GRIB2 data.
    """

    def __init__(self, array: "OnDiskArray", lock: SerializableLock):
        """
        Initialize the GribBackendArray.

        Parameters
        ----------
        array : OnDiskArray
            The on-disk array object.
        lock : SerializableLock
            The lock to use for thread-safe access.
        """
        self.array = array
        self.shape = array.shape
        self.dtype = np.dtype(array.dtype)
        self.lock = lock

    def __getitem__(self, key: xr.core.indexing.ExplicitIndexer) -> np.typing.ArrayLike:
        return xr.core.indexing.explicit_indexing_adapter(
            key,
            self.shape,
            indexing.IndexingSupport.BASIC,
            self._raw_getitem,
        )

    def _raw_getitem(self, key: tuple) -> np.ndarray:
        """
        Implement thread-safe access to data on disk.

        Parameters
        ----------
        key : tuple
            The indexing key.

        Returns
        -------
        np.ndarray
            The indexed array.
        """
        with self.lock:
            return self.array[key]


class Grid:
    def __new__(cls, section3):
        gdtn = section3[4]
        Gdt = templates.gdt_class_by_gdtn(gdtn)

        @dataclass
        class _Grid(Gdt):
            section3: NDArray = field(init=True, repr=True)
            # Section 3 looked up common attributes.  Other looked up attributes are available according
            # to the Grid Definition Template.
            gridDefinitionSection: NDArray = field(init=False, repr=False, default=templates.GridDefinitionSection())
            sourceOfGridDefinition: int = field(init=False, repr=False, default=templates.SourceOfGridDefinition())
            numberOfDataPoints: int = field(init=False, repr=False, default=templates.NumberOfDataPoints())
            interpretationOfListOfNumbers: templates.Grib2Metadata = field(
                init=False,
                repr=False,
                default=templates.InterpretationOfListOfNumbers(),
            )
            gridDefinitionTemplateNumber: templates.Grib2Metadata = field(init=False, repr=False, default=templates.GridDefinitionTemplateNumber())
            gridDefinitionTemplate: list = field(init=False, repr=False, default=templates.GridDefinitionTemplate())
            _earthparams: dict = field(init=False, repr=False, default=templates.EarthParams())
            _dxsign: float = field(init=False, repr=False, default=templates.DxSign())
            _dysign: float = field(init=False, repr=False, default=templates.DySign())
            _llscalefactor: float = field(init=False, repr=False, default=templates.LLScaleFactor())
            _lldivisor: float = field(init=False, repr=False, default=templates.LLDivisor())
            _xydivisor: float = field(init=False, repr=False, default=templates.XYDivisor())
            shapeOfEarth: templates.Grib2Metadata = field(init=False, repr=False, default=templates.ShapeOfEarth())
            earthShape: str = field(init=False, repr=False, default=templates.EarthShape())
            earthRadius: float = field(init=False, repr=False, default=templates.EarthRadius())
            earthMajorAxis: float = field(init=False, repr=False, default=templates.EarthMajorAxis())
            earthMinorAxis: float = field(init=False, repr=False, default=templates.EarthMinorAxis())
            resolutionAndComponentFlags: list = field(init=False, repr=False, default=templates.ResolutionAndComponentFlags())
            ny: int = field(init=False, repr=False, default=templates.Ny())
            nx: int = field(init=False, repr=False, default=templates.Nx())
            scanModeFlags: list = field(init=False, repr=False, default=templates.ScanModeFlags())
            projParameters: dict = field(init=False, repr=False, default=templates.ProjParameters())

            def __post_init__(self):
                self.gdtn = self.section3[4]

        grid = _Grid(section3)
        return grid


def exclusive_slice_to_inclusive(item: slice):
    """
    Convert a slice with exclusive stop to an inclusive slice.

    If the slice has a step, the stop is reduced by the step, so that both
    interpretations would yield the same result.

    The means that [start, stop) is converted to [start, stop - step].

    Parameters
    ----------
    item
        The slice to convert.

    Returns
    -------
    slice
        The converted slice.
    """
    # return the None slice
    if item.start is None and item.stop is None and item.step is None:
        return item
    if not isinstance(item, slice):
        raise ValueError(f"item must be a slice; it was of type {type(item)}")
    # if step is None, it's one
    step = 1 if item.step is None else item.step
    if item.stop < item.start or step < 1:
        raise ValueError(f"slice {item} not accounted for")
    # handle case where slice has one item
    if abs(item.stop - item.start) == step:
        return [item.start]
    # other cases require reducing the stop by the step
    s = slice(item.start, item.stop - step, step)
    return s


class Validator:
    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"
        self.name = name

    def __get__(self, obj, objtype=None):
        try:
            value = getattr(obj, self.private_name)
        except AttributeError:
            value = None
        return value


class PdIndex(Validator):
    def __set__(self, obj, value):
        try:
            value = pd.Index(value)
        except TypeError:
            value = pd.Index([value])
        setattr(obj, self.private_name, value)


def _asarray_tuplesafe(values: typing.Any) -> np.ndarray:
    """
    Convert values to a numpy array of at most 1-dimension and preserve tuples.

    Adapted from ``pandas.core.common._asarray_tuplesafe``.

    Parameters
    ----------
    values : any
        The values to convert.

    Returns
    -------
    np.ndarray
        The converted numpy array.
    """
    if isinstance(values, tuple):
        result = np.empty(1, dtype=object)
        result[0] = values
    else:
        result = np.asarray(values)
        if result.ndim == 2:
            result = np.empty(len(values), dtype=object)
            result[:] = values

    return result


def array_safe_eq(a: typing.Any, b: typing.Any) -> bool:
    """
    Check if a and b are equal, even if they are numpy arrays.

    Parameters
    ----------
    a : any
        First object to compare.
    b : any
        Second object to compare.

    Returns
    -------
    bool
        True if equal, False otherwise.
    """
    if a is b:
        return True
    if hasattr(a, "equals"):
        return a.equals(b)
    if hasattr(a, "all") and hasattr(b, "all"):
        return a.shape == b.shape and (a == b).all()
    if hasattr(a, "all") or hasattr(b, "all"):
        return False
    try:
        return a == b
    except TypeError:
        return NotImplementedError


def dc_eq(dc1: typing.Any, dc2: typing.Any) -> bool:
    """
    Check if two dataclasses which hold numpy arrays are equal.

    Parameters
    ----------
    dc1 : any
        First dataclass to compare.
    dc2 : any
        Second dataclass to compare.

    Returns
    -------
    bool
        True if equal, False otherwise.
    """
    if dc1 is dc2:
        return True
    if dc1.__class__ is not dc2.__class__:
        return NotImplementedError
    t1 = astuple(dc1)
    t2 = astuple(dc2)
    return all(array_safe_eq(a1, a2) for a1, a2 in zip(t1, t2))


def coords_from_cube(cube: dict) -> typing.Dict[str, xr.Variable]:
    """
    Create a dictionary of xarray Variables from a cube definition.

    Parameters
    ----------
    cube : dict
        Dimension cube definition.

    Returns
    -------
    dict of str to xarray.Variable
        Coordinates for the Dataset/DataArray.
    """
    keys = list(cube.keys())
    keys.remove("x")
    keys.remove("y")
    coords = dict()
    for k in keys:
        if k is not None:
            if len(cube[k]) > 1:
                coords[k] = xr.Variable(dims=k, data=cube[k], attrs=dict(grib_name=k))
            elif len(cube[k]) == 1:
                coords[k] = xr.Variable(dims=tuple(), data=cube[k][0], attrs=dict(grib_name=k))
    return coords


@dataclass
class OnDiskArray:
    """
    On-disk array representation for GRIB2 messages.
    """

    file_name: typing.Union[str, typing.List[str]]
    index: pd.DataFrame = field(repr=False)
    cube: dict = field(repr=False)
    shape: typing.Tuple[int, ...] = field(init=False)
    ndim: int = field(init=False)
    geo_ndim: int = field(init=False)
    dtype: str = "float32"

    def __post_init__(self):
        # multiple grids not allowed so can just use first
        geo_shape = (self.index.iloc[0].ny, self.index.iloc[0].nx)

        self.geo_shape = geo_shape
        self.geo_ndim = len(geo_shape)

        if len(self.index) == 1:
            self.shape = geo_shape
        else:
            if self.index.index.nlevels == 1:
                self.shape = tuple([len(self.index.index)]) + geo_shape
            else:
                self.shape = tuple([len(i) for i in self.index.index.levels]) + geo_shape
        self.ndim = len(self.shape)

        cols = ["msg", "sectionOffset"]
        if "file_index" in self.index.columns:
            cols.append("file_index")
        self.index = self.index[cols]

    def __getitem__(self, item: tuple) -> np.ndarray:
        """
        Retrieve data from disk for the specified slices.

        Parameters
        ----------
        item : tuple
            The slicing tuple.

        Returns
        -------
        np.ndarray
            The retrieved data array.
        """
        # dimensions not in index are internal to tdlpack records; 2 dims for
        # grids; 1 dim for stations

        index_slicer = item[: -self.geo_ndim]
        # maintain all multindex levels
        index_slicer = tuple([[i] if isinstance(i, int) else i for i in index_slicer])

        # pandas loc slicing is inclusive, therefore convert slices into
        # explicit lists
        index_slicer_inclusive = tuple([exclusive_slice_to_inclusive(i) if isinstance(i, slice) else i for i in index_slicer])

        # get records selected by item in new index dataframe
        if len(index_slicer_inclusive) == 1:
            index = self.index.loc[index_slicer_inclusive]
        elif len(index_slicer_inclusive) > 1:
            index = self.index.loc[index_slicer_inclusive, :]
        else:
            index = self.index
        index = index.set_index(index.index)

        # set miloc to new relative locations in sub array
        index["miloc"] = list(zip(*[index.index.unique(level=dim).get_indexer(index.index.get_level_values(dim)) for dim in index.index.names]))

        if len(index_slicer_inclusive) == 1:
            array_field_shape = tuple([len(index.index)]) + self.geo_shape
        elif len(index_slicer_inclusive) > 1:
            array_field_shape = index.index.levshape + self.geo_shape
        else:
            array_field_shape = self.geo_shape

        array_field = np.full(array_field_shape, fill_value=np.nan, dtype="float32")

        if "file_index" in index.columns:
            for file_idx, group in index.groupby("file_index"):
                filename = self.file_name[file_idx] if isinstance(self.file_name, list) else self.file_name
                with open(filename, mode="rb") as filehandle:
                    for key, row in group.iterrows():
                        bitmap_offset = None if pd.isna(row["sectionOffset"][6]) else int(row["sectionOffset"][6])
                        values = _data(filehandle, row.msg, bitmap_offset, row["sectionOffset"][7])

                        if len(index_slicer_inclusive) >= 1:
                            array_field[row.miloc] = values
                        else:
                            array_field = values
        else:
            with open(self.file_name, mode="rb") as filehandle:
                for key, row in index.iterrows():
                    bitmap_offset = None if pd.isna(row["sectionOffset"][6]) else int(row["sectionOffset"][6])
                    values = _data(filehandle, row.msg, bitmap_offset, row["sectionOffset"][7])

                    if len(index_slicer_inclusive) >= 1:
                        array_field[row.miloc] = values
                    else:
                        array_field = values

        # handle geo dim slicing
        array_field = array_field[(Ellipsis,) + item[-self.geo_ndim :]]

        # squeeze array dimensions expressed as integer
        for i, it in reversed(list(enumerate(item[: -self.geo_ndim]))):
            if isinstance(it, int):
                array_field = array_field[(slice(None, None, None),) * i + (0,)]

        return array_field


def dims_to_shape(d: dict) -> tuple:
    """
    Convert dimension metadata to a shape tuple.

    Parameters
    ----------
    d : dict
        Dimension metadata dictionary.

    Returns
    -------
    tuple
        Shape tuple.
    """
    if "nx" in d:
        t = (d["ny"], d["nx"])
    else:
        t = (d["nsta"],)
    return t


def filter_index(index: pd.DataFrame, k: str, v: typing.Any) -> pd.DataFrame:
    """
    Filter a GRIB2 index DataFrame by a key-value pair.

    Supports slice and vectorized-indexing similar to xarray's ``sel``.

    Parameters
    ----------
    index : pandas.DataFrame
        The GRIB2 index DataFrame to filter.
    k : str
        Column name to filter by.
    v : any
        Value(s) or slice to filter for.

    Returns
    -------
    pandas.DataFrame
        Filtered index.
    """
    if isinstance(v, slice):
        index = index.set_index(k)
        index = index.loc[v]
        index = index.reset_index()
    else:
        label = (
            v
            if getattr(v, "ndim", 1) > 1  # vectorized-indexing
            else _asarray_tuplesafe(v)
        )
        if label.ndim == 0:
            # see https://github.com/pydata/xarray/pull/4292 for details
            label_value = label[()] if label.dtype.kind in "mM" else label.item()
            try:
                indexer = pd.Index(index[k]).get_loc(label_value)
                if isinstance(indexer, int):
                    index = index.iloc[[indexer]]
                else:
                    index = index.iloc[indexer]
            except KeyError:
                index = index.iloc[[]]
        else:
            indexer = pd.Index(index[k]).get_indexer_for(np.ravel(v))
            index = index.iloc[indexer[indexer >= 0]]

    return index


def parse_grib_index(
    index: pd.DataFrame,
    filters: typing.Mapping[str, typing.Any] = dict(),
) -> typing.Tuple[pd.DataFrame, typing.Dict[str, typing.List[str]], dict, typing.Dict[str, dict]]:
    """
    Apply filters.

    Evaluate remaining dimensions based on pdtn and parse each out.

    Parameters
    ----------
    index
        Pandas DataFrame containing the GRIB2 message index.
    filters
        Filter GRIB2 messages to single hypercube. Dict keys can be any
        GRIB2 metadata attribute name.

    Returns
    -------
    index
        Modified Pandas DataFrame with added GRIB2 metadata columns.
    dim_coords
        List of GRIB2 attributes that will be used for coordinates and/or dimensions.
    attrs
        Dict of metadata attributes (non-coordinates, non-geo)
    """

    # make a copy of filters, remove filters as they are applied
    filters = copy(filters)

    for k, v in filters.items():
        if k not in index.columns:
            kwarg = {k: index.msg.apply(lambda msg: getattr(msg, k))}
            index = index.assign(**kwarg)
        # adopt parts of xarray's sel logic  so that filters behave similarly
        # allowed to filter to nothing to make empty dataset
        index = filter_index(index, k, v)

    if len(index) == 0:
        return index, list(), dict(), dict()

    dim_coords = dict()  # key=name of dim, value=list of coord names
    attrs = dict()
    coord_attrs = dict()

    # expand index
    index = index.assign(shortName=index.msg.apply(lambda msg: msg.shortName))
    index = index.assign(nx=index.msg.apply(lambda msg: msg.nx))
    index = index.assign(ny=index.msg.apply(lambda msg: msg.ny))
    index = index.astype({"ny": "int", "nx": "int"})

    # apply common filters(to all definition templates) to reduce dataset to
    # single cube
    # ensure only one of each of the below exists after filters applied
    required_uniques = [
        "productDefinitionTemplateNumber",
        "typeOfGeneratingProcess",
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
    ]

    def meta_check(index, attrs, meta):
        """
        add meta to the datframe index
        check that there is a single type
        add the type to attrs

        returns index, attrs
        """
        index = index.assign(**{meta: index.msg.apply(lambda msg: getattr(msg, meta))})

        unique = index[meta].unique()
        if len(index[meta].unique()) > 1:
            raise ValueError(f"filter to a single {meta}; found: {[str(i) for i in unique]}")
        value = unique.item()
        if isinstance(value, grib2io.templates.Grib2Metadata):
            value = value.definition

        # None is returned if no value found,
        # check and change to string None
        if value is None:
            value = "None"

        attrs[meta] = value
        return index, attrs

    for meta in required_uniques:
        index, attrs = meta_check(index, attrs, meta)

    pdtn = index.productDefinitionTemplateNumber.iloc[0].value

    # determine which non geo dimensions can be created from data by this point
    # the index is filtered down to a single type for all required_uniques

    # Dim Name     # matching dim_name for using this data as index coordinate
    dim_coords["refDate"] = ["refDate"]
    coord_attrs["refDate"] = dict(standard_name="forecast_reference_time")
    #   dim_coords["refDate"] = ["refDate", "hour"] # non dim name matching items in list are used as non-index coordinates

    dim_coords["leadTime"] = ["leadTime"]
    coord_attrs["leadTime"] = dict(standard_name="forecast_period")

    if "valueOfFirstFixedSurface" not in index.columns:
        index = index.assign(valueOfFirstFixedSurface=index.msg.apply(lambda msg: msg.valueOfFirstFixedSurface))
    if "valueOfsecondFixedSurface" not in index.columns:
        index = index.assign(valueOfSecondFixedSurface=index.msg.apply(lambda msg: msg.valueOfSecondFixedSurface))

    # dim name api change, user could run ds = ds.swap_dims(fixedSurface="valueOfFirstFixedSurface")
    index = index.assign(level=list(zip(index["valueOfFirstFixedSurface"], index["valueOfSecondFixedSurface"])))
    #   index = index.assign(level=index.msg.apply(lambda msg: msg.level))
    # lack of "level" indeicates don't create extra index coordinate "level"
    dim_coords["level"] = ["valueOfFirstFixedSurface", "valueOfSecondFixedSurface"]

    # logic for parsing possible dims from specific product definition section

    if pdtn in {5, 9}:
        # Probability forecasts at a horizontal level or in a horizontal layer
        # in a continuous or non-continuous time interval.  (see Template
        # 4.9)
        #       AVAILABLE_THRESHOLD = {
        #           0: {'has_lower': True, 'has_upper': False},
        #           1: {'has_lower': False, 'has_upper': True},
        #           2: {'has_lower': True, 'has_upper': True},
        #           3: {'has_lower': True, 'has_upper': False},
        #           4: {'has_lower': False, 'has_upper': True},
        #           5: {'has_lower': True, 'has_upper': False},
        #       }

        index, attrs = meta_check(index, attrs, "typeOfProbability")
        if "thresholdLowerLimit" not in index.columns:
            index = index.assign(thresholdLowerLimit=index.msg.apply(lambda msg: msg.thresholdLowerLimit))
        if "thresholdUpperLimit" not in index.columns:
            index = index.assign(thresholdUpperLimit=index.msg.apply(lambda msg: msg.thresholdUpperLimit))
        if "threshold" not in index.columns:
            # using composite of lower and upper, but could use threshold string from grib2io as long as that is unique and based on lower and upper
            index = index.assign(threshold=list(zip(index["thresholdLowerLimit"], index["thresholdUpperLimit"])))
        #           index = index.assign(threshold = index.msg.apply(lambda msg: msg.threshold))

        # ommiting threshold results in no index being assigned for this possible dim
        dim_coords["threshold"] = ["thresholdLowerLimit", "thresholdUpperLimit"]

    if pdtn in {6, 10}:
        # Percentile forecasts at a horizontal level or in a horizontal layer
        # in a continuous or non-continuous time interval.  (see Template
        # 4.10)
        dim_coords["percentileValue"] = ["percentileValue"]
        coord_attrs["percentileValue"] = dict(long_name="percentile", units="percent")

    if pdtn in {
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        42,
        43,
        45,
        46,
        47,
        61,
        62,
        63,
        67,
        68,
        72,
        73,
        78,
        79,
        82,
        83,
        84,
        85,
        87,
        91,
    }:
        dim_coords["duration"] = ["duration"]

    if pdtn in {
        1,
        11,
        33,
        34,
        41,
        43,
        45,
        47,
        49,
        54,
        56,
        58,
        59,
        63,
        68,
        77,
        79,
        81,
        83,
        84,
        85,
        92,
    }:
        dim_coords["perturbationNumber"] = ["perturbationNumber"]

    if pdtn in {2, 3, 4, 12, 13, 14}:
        index, attrs = meta_check(index, attrs, "typeOfDerivedForecast")

    if pdtn in {5, 9}:
        dim_coords["typeOfProbability"] = ["typeOfProbability"]

    if pdtn in {6, 10}:
        dim_coords["percentileValue"] = ["percentileValue"]

    if pdtn in {8, 15, 42, 46, 62, 67, 72, 78, 82, 1001, 1002, 1100, 1101}:
        index, attrs = meta_check(index, attrs, "statisticalProcess")

    # Logic for Trace Gas and Aerosol dimensions
    if pdtn in {40, 41, 42, 43, 76, 77, 78, 79}:
        dim_coords["constituentType"] = ["constituentType"]

    if pdtn in {76, 77, 78, 79}:
        dim_coords["sourceSinkIndicator"] = ["sourceSinkIndicator"]

    if pdtn in {44, 45, 46, 47, 48, 49, 50, 80, 81, 82, 83, 84, 85}:
        dim_coords["typeOfAerosol"] = ["typeOfAerosol"]

    if pdtn in {80, 81, 82, 83, 84}:
        dim_coords["sourceSinkIndicator"] = ["sourceSinkIndicator"]

    if pdtn in {48, 49, 80, 81}:
        dim_coords["firstWavelength"] = ["firstWavelength"]
        dim_coords["secondWavelength"] = ["secondWavelength"]
        dim_coords["firstSizeOfAerosol"] = ["firstSizeOfAerosol"]
        dim_coords["secondSizeOfAerosol"] = ["secondSizeOfAerosol"]

    # Finish logic by pdtn

    for k, v in dim_coords.items():
        for meta in v:
            if meta not in index.columns:
                index = index.assign(**{meta: index.msg.apply(lambda msg: getattr(msg, meta))})

    return index, dim_coords, attrs, coord_attrs


# Custom open_datatree function to open grib files as DataTree
def open_datatree(
    filename: str,
    *,
    drop_variables: typing.Optional[typing.List[str]] = None,
    filters: typing.Optional[typing.Mapping[str, typing.Any]] = None,
    engine: str = "grib2io",
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
    **kwargs,
) -> typing.Any:
    """
    Open a GRIB2 file as an xarray DataTree.

    Parameters
    ----------
    filename : str
        Path to the GRIB2 file.
    drop_variables : list, optional
        List of variables to exclude.
    filters : dict, optional
        Filter criteria for GRIB2 messages.
    engine : str, optional
        Engine to use for opening the file, defaults to "grib2io".
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.
    **kwargs : optional
        Additional keyword arguments passed to the xarray backend.

    Returns
    -------
    xarray.DataTree
        A hierarchical DataTree representation of the GRIB2 data.
    """
    if not _HAS_DATATREE:
        raise ImportError("xarray version does not support DataTree functionality.")

    if filters is None:
        filters = {}

    # Open the file without any filters first to get all messages
    with grib2io.open(filename, _xarray_backend=True) as f:
        file_index = pd.DataFrame(f._index)
        file_index = file_index.assign(msg=msgs_from_index(f._index))

    # Build tree structure from GRIB messages
    root = build_datatree_from_grib(
        filename,
        file_index,
        filters,
        drop_variables=drop_variables,
        chunks=chunks,
    )

    # Update history for provenance
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    existing_history = root.attrs.get("history", "") if hasattr(root, "attrs") else ""
    history = f"{now}: Initialized via grib2io.open_datatree from {filename}\n{existing_history}"
    if hasattr(root, "attrs"):
        root.attrs["history"] = history
    # Also add to all datasets in the tree
    for node in root.subtree:
        if node.ds is not None:
            node.ds.attrs["history"] = history + node.ds.attrs.get("history", "")

    return root

    return root


def build_da_without_coords(index: pd.DataFrame, cube: dict, filename: str, attrs: dict) -> xr.DataArray:
    """
    Build a DataArray without coordinates from a cube of grib2 messages.

    Parameters
    ----------
    index : pd.DataFrame
        Index of cube.
    cube : dict
        Cube of grib2 messages.
    filename : str
        Filename of grib2 file.
    attrs : dict
        Attributes for the DataArray.

    Returns
    -------
    xr.DataArray
        DataArray without coordinates.
    """

    dim_names = [k for k in cube.keys() if cube[k] is not None and len(cube[k]) > 1]
    constant_meta_names = [k for k in cube.keys() if cube[k] is None]
    dims = {k: len(cube[k]) for k in dim_names}

    # guard against bad datarrays being formed
    dims_total = 1
    dims_to_filter = []
    for (
        dim_name,
        dim_len,
    ) in dims.items():
        if dim_name not in {"x", "y", "station"}:
            dims_total *= dim_len
            dims_to_filter.append(dim_name)

    # Check number of GRIB2 message indexed compared to non-X/Y
    # dimensions.
    if dims_total != len(index):
        raise ValueError(
            f"DataArray dimensions are not compatible with number of GRIB2 messages; DataArray has {dims_total} "
            f"and GRIB2 index has {len(index)}. Consider applying a filter for dimensions: {dims_to_filter}"
        )

    data = OnDiskArray(filename, index, cube)
    lock = _LOCK
    data = GribBackendArray(data, lock)
    data = indexing.LazilyIndexedArray(data)
    if len(dim_names) != len(data.shape):
        raise ValueError(
            "different number of dimensions on data "
            f"and dims: {len(data.shape)} vs {len(dim_names)}\n"
            "Grib2 messages could not be formed into a data cube; "
            "It's possible extra messages exist along a non-accounted for dimension based on PDTN\n"
            "It might be possible to get around this by applying a filter on the non-accounted for dimension"
        )
    da = xr.DataArray(data, dims=dim_names)

    da.encoding["original_shape"] = data.shape

    da.encoding["preferred_chunks"] = {"y": -1, "x": -1}
    msg1 = index.msg.iloc[0]

    # plain language metadata is minimized
    # add grib section metadata
    da.attrs["GRIB2IO_section0"] = msg1.section0
    da.attrs["GRIB2IO_section1"] = msg1.section1
    da.attrs["GRIB2IO_section2"] = msg1.section2 if msg1.section2 else []
    da.attrs["GRIB2IO_section3"] = msg1.section3
    da.attrs["GRIB2IO_section4"] = msg1.section4
    da.attrs["GRIB2IO_section5"] = msg1.section5
    da.attrs["fullName"] = str(msg1.fullName)
    da.attrs["shortName"] = str(msg1.shortName)
    da.attrs["units"] = str(msg1.units)
    da.attrs["originatingCenter"] = str(msg1.originatingCenter.definition)
    da.attrs["originatingSubCenter"] = str(msg1.originatingSubCenter.definition)

    # add master table
    da.attrs["masterTableInfo"] = str(msg1.masterTableInfo.definition)

    da.name = index.shortName.iloc[0]
    for meta_name in constant_meta_names:
        if meta_name in index.columns:
            da.attrs[meta_name] = index[meta_name].iloc[0]

    da.attrs.update(attrs)

    return da


def assign_xr_meta(
    ds: xr.Dataset,
    frames: typing.List[pd.DataFrame],
    cube: dict,
    non_geo_dims: typing.Dict[str, typing.List[str]],
    extra_geo: dict,
    coord_attrs: typing.Dict[str, dict],
) -> xr.Dataset:
    """
    Assign coordinates and attributes to the dataset.

    Parameters
    ----------
    ds : xr.Dataset
        The dataset to update.
    frames : list of pd.DataFrame
        The dataframes for each variable.
    cube : dict
        The dimensions cube.
    non_geo_dims : dict
        The non-geographic dimensions.
    extra_geo : dict
        Extra geographic coordinates.
    coord_attrs : dict
        Attributes for coordinates.

    Returns
    -------
    xr.Dataset
        The updated dataset.
    """
    df = frames[0]

    # assign extra geo coords
    ds = ds.assign_coords(extra_geo)
    # add crs data from first grib message to each data variable and the dataset
    geo_attrs = {
        "crs_wkt": CRS.from_dict(df.msg.iloc[0].projParameters).to_wkt(),
        "gridlengthXDirection": df.msg.iloc[0].gridlengthXDirection,
        "gridlengthYDirection": df.msg.iloc[0].gridlengthYDirection,
        "latitudeFirstGridpoint": df.msg.iloc[0].latitudeFirstGridpoint,
        "longitudeFirstGridpoint": df.msg.iloc[0].longitudeFirstGridpoint,
    }
    for data_var in ds.data_vars:
        ds[data_var].attrs.update(geo_attrs)
    ds.attrs.update(geo_attrs)

    # add coordinate specific attributes
    for coord, attrs in coord_attrs.items():
        ds[coord].attrs.update(attrs)

    # assign valid date coords
    try:
        ds = ds.assign_coords(dict(validDate=ds.coords["refDate"] + ds.coords["leadTime"]))
        ds.validDate.attrs["standard_name"] = "time"
        ds.validDate.attrs["long_name"] = "time"
    except Exception as e:
        warnings.warn(f"could not parse validTime: {e}")

    # assign attributes
    ds.attrs["engine"] = "grib2io"

    return ds


def make_variables(
    index: pd.DataFrame,
    f: str,
    non_geo_dims: typing.Dict[str, typing.List[str]],
    allow_uneven_dims: bool = False,
) -> typing.Tuple[
    typing.Optional[typing.List[pd.DataFrame]],
    typing.Optional[typing.List[dict]],
    typing.Optional[dict],
]:
    """
    Create an individual dataframe index and cube for each variable.

    Parameters
    ----------
    index : pd.DataFrame
        Index of messages.
    f : str
        Filename.
    non_geo_dims : dict
        Dimensions not associated with the x,y grid.
    allow_uneven_dims : bool, optional
        If True, allows uneven dimensions (used for DataTree creation).

    Returns
    -------
    ordered_frames : list of pd.DataFrame, optional
        List of dataframes, one for each variable.
    cubes : list of dict, optional
        List of cubes, one for each variable.
    extra_geo : dict, optional
        Extra geographic coordinates.
    """
    # let shortName determine the variables

    # set the index to the name
    index = index.set_index("shortName").sort_index()
    # return nothing if no data
    if index.empty:
        return None, None, None

    # define the DimCube
    dims = copy(non_geo_dims)

    ordered_meta = list(non_geo_dims.keys())
    cubes = list()
    ordered_frames = list()
    for key in index.index.unique():
        frame = index.loc[[key]]
        frame = frame.reset_index()
        # frame is a dataframe with all records for one variable
        c = dict()
        # for colname in frame.columns:
        for colname in ordered_meta:
            uniques = pd.Index(frame[colname]).unique()
            if len(uniques) > 1:
                c[colname] = uniques.sort_values()
            else:
                c[colname] = [uniques[0]]

        dims = [k for k in ordered_meta if len(c[k]) > 1]

        for dim in dims:
            if frame[dim].value_counts().nunique() > 1 and not allow_uneven_dims:
                raise ValueError(f"uneven number of grib msgs associated with dimension: {dim}\n unique values for {dim}: {frame[dim].unique()} ")

        if len(dims) >= 1:  # dims may be empty if no extra dims on top of x,y
            frame = frame.sort_values(dims)
            frame = frame.set_index(dims)

        cubes.append(c)

        # miloc is multi-index integer location of msg in nd DataArray
        miloc = list(zip(*[frame.index.unique(level=dim).get_indexer(frame.index.get_level_values(dim)) for dim in dims]))

        # set frame multi index
        if len(miloc) >= 1:  # miloc will be empty when no extra dims, thus no multiindex
            dim_ix = tuple([n + "_ix" for n in dims])
            frame = frame.set_index(pd.MultiIndex.from_tuples(miloc, names=dim_ix))

        ordered_frames.append(frame)

    # no variables
    if not cubes:
        cubes = [dict()]

    # check geography of data and assign to cube
    if len(index.ny.unique()) > 1 or len(index.nx.unique()) > 1:
        raise ValueError("multiple grids not accommodated")
    for cube in cubes:
        cube["y"] = range(int(index.ny.iloc[0]))
        cube["x"] = range(int(index.nx.iloc[0]))

    extra_geo = None
    msg = index.msg.iloc[0]

    # we want the lat lons; make them via accessing a record; we are assuming
    # all records are the same grid because they have the same shape;
    # may want a unique grid identifier from grib2io to avoid assuming this
    latitude, longitude = msg.latlons()
    latitude = xr.DataArray(latitude, dims=["y", "x"])
    latitude.attrs["standard_name"] = "latitude"
    latitude.attrs["units"] = "degrees_north"
    longitude = xr.DataArray(longitude, dims=["y", "x"])
    longitude.attrs["standard_name"] = "longitude"
    longitude.attrs["units"] = "degrees_east"
    extra_geo = dict(latitude=latitude, longitude=longitude)

    return ordered_frames, cubes, extra_geo


def interp_nd(
    a: np.ndarray,
    *,
    method: typing.Union[str, int],
    grid_def_in: grib2io.Grib2GridDef,
    grid_def_out: grib2io.Grib2GridDef,
    method_options: typing.Optional[typing.List[int]] = None,
    num_threads: int = 1,
) -> np.ndarray:
    """
    Perform multi-dimensional interpolation on a horizontal grid.

    This function reshapes the input array to (N, ny, nx) before performing
    interpolation and then reshapes it back to its original dimensions plus
    the new grid dimensions.

    Parameters
    ----------
    a : np.ndarray
        Input array with horizontal dimensions (..., ny, nx).
    method : str or int
        Interpolation method.
    grid_def_in : grib2io.Grib2GridDef
        Input grid definition.
    grid_def_out : grib2io.Grib2GridDef
        Output grid definition.
    method_options : list of int, optional
        Interpolation options.
    num_threads : int, optional
        Number of threads for parallel interpolation.

    Returns
    -------
    np.ndarray
        Interpolated array with horizontal dimensions of the output grid.
    """
    front_shape = a.shape[:-2]
    a = a.reshape(-1, a.shape[-2], a.shape[-1])
    a = grib2io.interpolate(
        a,
        method,
        grid_def_in,
        grid_def_out,
        method_options=method_options,
        num_threads=num_threads,
    )
    a = a.reshape(front_shape + (a.shape[-2], a.shape[-1]))
    return a


def interp_nd_stations(
    a: np.ndarray,
    *,
    method: typing.Union[str, int],
    grid_def_in: grib2io.Grib2GridDef,
    lats: typing.Sequence[float],
    lons: typing.Sequence[float],
    method_options: typing.Optional[typing.List[int]] = None,
    num_threads: int = 1,
) -> np.ndarray:
    """
    Perform multi-dimensional interpolation to station points.

    This function reshapes the input array to (N, ny, nx) before performing
    interpolation and then reshapes it back to its original dimensions plus
    the station dimension.

    Parameters
    ----------
    a : np.ndarray
        Input array with horizontal dimensions (..., ny, nx).
    method : str or int
        Interpolation method.
    grid_def_in : grib2io.Grib2GridDef
        Input grid definition.
    lats : sequence of float
        Station latitudes.
    lons : sequence of float
        Station longitudes.
    method_options : list of int, optional
        Interpolation options.
    num_threads : int, optional
        Number of threads for parallel interpolation.

    Returns
    -------
    np.ndarray
        Interpolated array with the last dimension representing stations.
    """
    front_shape = a.shape[:-2]
    a = a.reshape(-1, a.shape[-2], a.shape[-1])
    a = grib2io.interpolate_to_stations(
        a,
        method,
        grid_def_in,
        lats,
        lons,
        method_options=method_options,
        num_threads=num_threads,
    )
    a = a.reshape(front_shape + (len(lats),))
    return a


@xr.register_dataset_accessor("grib2io")
class Grib2ioDataSet:
    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    def griddef(self):
        return Grib2GridDef.from_section3(self._obj[list(self._obj.data_vars)[0]].attrs["GRIB2IO_section3"])

    def interp(
        self,
        method: typing.Union[str, int],
        grid_def_out: grib2io.Grib2GridDef,
        method_options: typing.Optional[typing.List[int]] = None,
        num_threads: int = 1,
    ) -> xr.Dataset:
        """
        Perform grid spatial interpolation on all variables in the Dataset.

        Parameters
        ----------
        method : str or int
            Interpolation method.
        grid_def_out : grib2io.Grib2GridDef
            Output grid definition.
        method_options : list of int, optional
            Interpolation options.
        num_threads : int, optional
            Number of threads.

        Returns
        -------
        xarray.Dataset
            Interpolated dataset.
        """
        da = self._obj.to_array()
        da.attrs["GRIB2IO_section3"] = self._obj[list(self._obj.data_vars)[0]].attrs["GRIB2IO_section3"]
        da = da.grib2io.interp(method, grid_def_out, method_options=method_options, num_threads=num_threads)
        ds = da.to_dataset(dim="variable")

        # Update history for provenance
        history = ds.attrs.get("history", "")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ds.attrs["history"] = f"{now}: Interpolated via {method} to {grid_def_out}\n{history}"

        return ds

    def interp_to_stations(
        self,
        method: typing.Union[str, int],
        calls: typing.Sequence[str],
        lats: typing.Sequence[float],
        lons: typing.Sequence[float],
        method_options: typing.Optional[typing.List[int]] = None,
        num_threads: int = 1,
    ) -> xr.Dataset:
        """
        Perform spatial interpolation to station points on all variables.

        Parameters
        ----------
        method : str or int
            Interpolation method.
        calls : sequence of str
            Station call signs.
        lats : sequence of float
            Station latitudes.
        lons : sequence of float
            Station longitudes.
        method_options : list of int, optional
            Interpolation options.
        num_threads : int, optional
            Number of threads.

        Returns
        -------
        xarray.Dataset
            Dataset interpolated to stations.
        """
        da = self._obj.to_array()
        da.attrs["GRIB2IO_section3"] = self._obj[list(self._obj.data_vars)[0]].attrs["GRIB2IO_section3"]
        da = da.grib2io.interp_to_stations(
            method,
            calls,
            lats,
            lons,
            method_options=method_options,
            num_threads=num_threads,
        )
        ds = da.to_dataset(dim="variable")

        # Update history for provenance
        history = ds.attrs.get("history", "")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ds.attrs["history"] = f"{now}: Interpolated to {len(calls)} stations via {method}\n{history}"

        return ds

    def to_grib2(self, filename, mode: typing.Literal["x", "w", "a"] = "x"):
        """
        Write a DataSet to a grib2 file.

        Parameters
        ----------
        filename
            Name of the grib2 file to write to.
        mode: {"x", "w", "a"}, optional, default="x"
            Persistence mode

            | mode | Description                       |
            | :---:| :---:                             |
            | 'x'  | create (fail if exists)           |
            | 'w'  | create (overwrite if exists)      |
            | 'a'  | append (create if does not exist) |

        """
        ds = self._obj

        for shortName in sorted(ds):
            # make a DataArray from the "Data Variables" in the DataSet
            da = ds[shortName]

            da.grib2io.to_grib2(filename, mode=mode)
            mode = "a"

    def update_attrs(self, **kwargs):
        """
        Raises an error because Datasets don't have a .attrs attribute.

        Parameters
        ----------
        attrs
            Attributes to update.
        """
        raise ValueError(f"Datasets do not have a .attrs attribute; use .grib2io.update_attrs({kwargs}) on a DataArray instead.")

    def subset(self, *, lats=None, lons=None) -> xr.Dataset:
        """
        Subset the Dataset to a box defined by latitudes and/or longitudes.

        Parameters
        ----------
        lats
            Two item list or tuple of latitudes.  Default is None which will
            return a subset unbounded by latitude.  The first term defines the
            southern boundary and the second term defines the northern
            boundary.
        lons
            Two item list or tuple of longitudes.  Default is None which will
            return a subset unbounded by longitude.  The first term defines the
            western boundary and the second term defines the eastern
            boundary.  Can follow either: 0 to 360 postive eastward, or 0 to
            -180 westward / 0 to 180 eastward conventions.  The longitude
            boundaries cannot cross 0.

        Returns
        -------
        subset
            Dataset subset to the bounding box created by input 'lats'/'lons'.
            All gridpoints with lat/lon matching contraints are included within
            subset.
        """
        ds = self._obj

        newds = xr.Dataset()
        for shortName in ds:
            newds[shortName] = ds[shortName].grib2io.subset(lats=lats, lons=lons).copy()

        # Update history for provenance
        history = newds.attrs.get("history", "")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        newds.attrs["history"] = f"{now}: Subsetted to lats={lats}, lons={lons}\n{history}"

        return newds

    def compute(self, **kwargs):
        """
        Compute the Dask-backed Dataset with retries for transient errors.

        Wraps :func:`grib2io.utils.compute_with_retries`.

        Parameters
        ----------
        **kwargs
            Arguments passed to :func:`grib2io.utils.compute_with_retries`,
            e.g., `max_attempts` or `base_sleep`.

        Returns
        -------
        xarray.Dataset
            The computed Dataset with NumPy-backed data.
        """
        from .utils import compute_with_retries

        return compute_with_retries(self._obj, **kwargs)


@xr.register_dataarray_accessor("grib2io")
class Grib2ioDataArray:
    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    def griddef(self):
        return Grib2GridDef.from_section3(self._obj.attrs["GRIB2IO_section3"])

    def interp(self, method, grid_def_out, method_options=None, num_threads=1) -> xr.DataArray:
        """
        Perform grid spatial interpolation.

        Uses the [NCEPLIBS-ip library](https://github.com/NOAA-EMC/NCEPLIBS-ip).

        Parameters
        ----------
        method
            Interpolate method to use. This can either be an integer or string
            using the following mapping:

            | Interpolate Scheme | Integer Value |
            | :---:              | :---:         |
            | 'bilinear'         | 0             |
            | 'bicubic'          | 1             |
            | 'neighbor'         | 2             |
            | 'budget'           | 3             |
            | 'spectral'         | 4             |
            | 'neighbor-budget'  | 6             |
        grid_def_out
            Grib2GridDef object of the output grid.
        method_options : list of ints, optional
            Interpolation options. See the NCEPLIBS-ip documentation for
            more information on how these are used.
        num_threads : int, optional
            Number of OpenMP threads to use for interpolation. The default
            value is 1. If grib2io_interp was not built with OpenMP, then
            this keyword argument and value will have no impact.

        Returns
        -------
        interp
            DataSet interpolated to new grid definition.  The attribute
            GRIB2IO_section3 is replaced with the section3 array from the new
            grid definition.
        """
        da = self._obj
        # ensure that y, x are rightmost dims; they should be if opening with
        # grib2io engine

        # gdtn and gdt is not the entirety of the new s3
        npoints = grid_def_out.npoints
        s3_new = np.array([0, npoints, 0, 0, grid_def_out.gdtn] + list(grid_def_out.gdt))

        # make new lat lons
        lats, lons = Grib2Message(section3=s3_new, pdtn=0, drtn=0).grid()
        latitude = xr.DataArray(lats, dims=["y", "x"])
        longitude = xr.DataArray(lons, dims=["y", "x"])

        # create new coords
        new_coords = dict(da.coords)
        del new_coords["latitude"]
        del new_coords["longitude"]
        new_coords["longitude"] = longitude
        new_coords["latitude"] = latitude

        # make grid def in from section3 on da.attrs
        grid_def_in = self.griddef()

        if da.chunks is None:
            data = interp_nd(
                da.data,
                method=method,
                grid_def_in=grid_def_in,
                grid_def_out=grid_def_out,
                method_options=method_options,
                num_threads=num_threads,
            )
        else:
            data = da.data.map_blocks(
                interp_nd,
                method=method,
                grid_def_in=grid_def_in,
                grid_def_out=grid_def_out,
                method_options=method_options,
                chunks=da.chunks[:-2] + latitude.shape,
                dtype=da.dtype,
            )

        new_da = xr.DataArray(data, dims=da.dims, coords=new_coords, attrs=da.attrs)

        new_da.attrs["GRIB2IO_section3"] = s3_new
        new_da.name = da.name

        # Update history for provenance
        history = new_da.attrs.get("history", "")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        new_da.attrs["history"] = f"{now}: Interpolated via {method} to {grid_def_out}\n{history}"

        return new_da

    def interp_to_stations(
        self,
        method: typing.Union[str, int],
        calls: typing.Sequence[str],
        lats: typing.Sequence[float],
        lons: typing.Sequence[float],
        method_options: typing.Optional[typing.List[int]] = None,
        num_threads: int = 1,
    ) -> xr.DataArray:
        """
        Perform spatial interpolation to station points.

        Parameters
        ----------
        method : str or int
            Interpolate method to use. This can either be an integer or string
            using the following mapping:

            | Interpolate Scheme | Integer Value |
            | :---:              | :---:         |
            | 'bilinear'         | 0             |
            | 'bicubic'          | 1             |
            | 'neighbor'         | 2             |
            | 'budget'           | 3             |
            | 'spectral'         | 4             |
            | 'neighbor-budget'  | 6             |

        calls : sequence of str
            Station calls used for labeling new station index coordinate
        lats : sequence of float
            Latitudes of the station points.
        lons : sequence of float
            Longitudes of the station points.
        method_options : list of int, optional
            Interpolation options.
        num_threads : int, optional
            Number of threads.

        Returns
        -------
        xarray.DataArray
            DataArray interpolated to lat and lon locations and labeled with
            dimension and coordinate 'station'. (..., y, x) -> (..., station)
        """
        da = self._obj
        # TODO ensure that y, x are rightmost dims; they should be if opening
        # with grib2io engine

        calls = np.asarray(calls)
        lats = np.asarray(lats)
        lons = np.asarray(lons)
        latitude = xr.DataArray(lats, dims=["station"])
        longitude = xr.DataArray(lons, dims=["station"])

        # create new coords
        new_coords = dict(da.coords)
        del new_coords["latitude"]
        del new_coords["longitude"]
        new_coords["longitude"] = longitude
        new_coords["latitude"] = latitude
        new_coords["station"] = calls

        new_dims = da.dims[:-2] + ("station",)

        # make grid def in from section3 on da attrs
        grid_def_in = self.griddef()

        if da.chunks is None:
            data = interp_nd_stations(
                da.data,
                method=method,
                grid_def_in=grid_def_in,
                lats=lats,
                lons=lons,
                method_options=method_options,
                num_threads=num_threads,
            )
        else:
            data = da.data.map_blocks(
                interp_nd_stations,
                method=method,
                grid_def_in=grid_def_in,
                lats=lats,
                lons=lons,
                method_options=method_options,
                drop_axis=-1,
                chunks=da.chunks[:-2] + latitude.shape,
                dtype=da.dtype,
            )

        new_da = xr.DataArray(data, dims=new_dims, coords=new_coords, attrs=da.attrs)

        new_da.name = da.name

        # Update history for provenance
        history = new_da.attrs.get("history", "")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        new_da.attrs["history"] = f"{now}: Interpolated to {len(calls)} stations via {method}\n{history}"

        return new_da

    def to_grib2(self, filename, mode: typing.Literal["x", "w", "a"] = "x"):
        """
        Write a DataArray to a grib2 file.

        Parameters
        ----------
        filename
            Name of the grib2 file to write to.
        mode: {"x", "w", "a"}, optional, default="x"
            Persistence mode

            +------+-----------------------------------+
            | mode | Description                       |
            +======+===================================+
            | x    | create (fail if exists)           |
            +------+-----------------------------------+
            | w    | create (overwrite if exists)      |
            +------+-----------------------------------+
            | a    | append (create if does not exist) |
            +------+-----------------------------------+

        """
        da = self._obj.copy(deep=True)

        coords_keys = sorted(da.coords.keys())
        coords_keys = [k for k in coords_keys if k in AVAILABLE_NON_GEO_COORDS]

        # If there are dimension coordinates, the DataArray is a hypercube of
        # grib2 messages.

        # Create `indexes` which is a list of lists of dictionaries for all
        # dimension coordinates. Each dictionary key is the dimension
        # coordinate name and the value is a list of the dimension coordinate
        # values.  This allows for easy iteration over all possible grib2
        # messages in the DataArray by using itertools.product.
        #
        # For example:
        # indexes = [
        #     [
        #         {"leadTime": 9},
        #         {"leadTime": 12},
        #     ],
        #     [
        #         {"valueOfFirstFixedSurface": 900},
        #         {"valueOfFirstFixedSurface": 925},
        #         {"valueOfFirstFixedSurface": 950},
        #     ],
        # ]

        # assign loc indexes to dimensions without indexes for uniform selection by name
        loc_indexes = list()
        for dim in da.dims:
            if dim not in da.indexes:
                da = da.assign_coords({dim: range(da[dim].size)})
                loc_indexes.append(dim)

        indexes = []
        for index in [i for i in AVAILABLE_NON_GEO_DIMS if i in da.dims]:
            values = da.coords[index].values
            if len(values) != len(set(values)):
                raise ValueError(
                    f"Dimension coordinate '{index}' has duplicate values, but to_grib2 requires unique values to find each GRIB2 message in the DataArray."
                )
            listeach = [{index: value} for value in sorted(values)]
            indexes.append(listeach)

        # If `dim_coords` is [], then the DataArray is a single grib2 message and
        # itertools.product(*dim_coords) will run once with `selectors = ()`.
        for selectors in itertools.product(*indexes):
            # Need to find the correct data in the DataArray based on the
            # dimension coordinates.
            filters = {k: v for d in selectors for k, v in d.items()}

            # If `filters` is {}, then the DataArray is a single grib2 message
            # and da.sel(indexers={}) returns the DataArray.
            selected = da.sel(indexers=filters)

            newmsg = Grib2Message(
                selected.attrs["GRIB2IO_section0"],
                selected.attrs["GRIB2IO_section1"],
                selected.attrs["GRIB2IO_section2"],
                selected.attrs["GRIB2IO_section3"],
                selected.attrs["GRIB2IO_section4"],
                selected.attrs["GRIB2IO_section5"],
            )
            newmsg.data = np.array(selected.data)

            # For dimension coordinates, set the grib2 message metadata to the
            # dimension coordinate value.
            for index, value in filters.items():
                if index not in loc_indexes:
                    setattr(newmsg, index, value)

            # For non-dimension coordinates, set the grib2 message metadata to
            # the DataArray coordinate value.
            for index in [i for i in coords_keys if i not in da.dims]:
                setattr(newmsg, index, selected.coords[index].values)

            # Set section 5 attributes to the da.encoding dictionary.
            for key, value in selected.encoding.items():
                if key in ["dtype", "chunks", "original_shape"]:
                    continue
                setattr(newmsg, key, value)

            # write the message to file
            with grib2io.open(filename, mode=mode) as f:
                f.write(newmsg)
            mode = "a"

    def update_attrs(self, **kwargs):
        """
        Update many of the attributes of the DataArray.

        Parameters
        ----------
        **kwargs
            Attributes to update.  This can include many of the GRIB2IO message
            attributes that you can find when you print a GRIB2IO message. For
            conflicting updates, the last keyword will be used.

            +-----------------------+------------------------------------------+
            | kwargs                | Description                              |
            +=======================+==========================================+
            | shortName="VTMP"      | Set shortName to "VTMP", along with      |
            |                       | appropriate discipline,                  |
            |                       | parameterCategory, parameterNumber,      |
            |                       | fullName and units.                      |
            +-----------------------+------------------------------------------+
            | discipline=0,         | Set shortName, discipline,               |
            | parameterCategory=0,  | parameterCategory, parameterNumber,      |
            | parameterNumber=1     | fullName and units appropriate for       |
            |                       | "Virtual Temperature".                   |
            +-----------------------+------------------------------------------+
            | discipline=0,         | Conflicting keywords but                 |
            | parameterCategory=0,  | 'shortName="TMP"' wins.  Set shortName,  |
            | parameterNumber=1,    | discipline, parameterCategory,           |
            | shortName="TMP"       | parameterNumber, fullName and units      |
            |                       | appropriate for "Temperature".           |
            +-----------------------+------------------------------------------+

        Returns
        -------
        DataArray
            DataArray with updated attributes.
        """
        da = self._obj.copy(deep=True)

        newmsg = Grib2Message(
            da.attrs["GRIB2IO_section0"],
            da.attrs["GRIB2IO_section1"],
            da.attrs["GRIB2IO_section2"],
            da.attrs["GRIB2IO_section3"],
            da.attrs["GRIB2IO_section4"],
            da.attrs["GRIB2IO_section5"],
        )

        coords_keys = [k for k in da.coords.keys() if k in AVAILABLE_NON_GEO_COORDS]

        for grib2_name, value in kwargs.items():
            if grib2_name == "gridDefinitionTemplateNumber":
                raise ValueError(
                    "The gridDefinitionTemplateNumber attribute cannot be updated.  The best way to change to a different grid is to interpolate the data to a new grid using the grib2io interpolate functions."
                )
            if grib2_name == "productDefinitionTemplateNumber":
                raise ValueError("The productDefinitionTemplateNumber attribute cannot be updated.")
            if grib2_name == "dataRepresentationTemplateNumber":
                raise ValueError("The dataRepresentationTemplateNumber attribute cannot be updated.")
            if grib2_name in coords_keys:
                warnings.warn(f"Skipping attribute '{grib2_name}' because it is a coordinate. Use da.assign_coords() to change coordinate values.")
                continue
            if hasattr(newmsg, grib2_name):
                setattr(newmsg, grib2_name, value)
            else:
                warnings.warn(f"Skipping attribute '{grib2_name}' because it is not a valid GRIB2 attribute for this message and cannot be updated.")
                continue

        da.attrs["GRIB2IO_section0"] = newmsg.section0
        da.attrs["GRIB2IO_section1"] = newmsg.section1
        da.attrs["GRIB2IO_section2"] = newmsg.section2 or []
        da.attrs["GRIB2IO_section3"] = newmsg.section3
        da.attrs["GRIB2IO_section4"] = newmsg.section4
        da.attrs["GRIB2IO_section5"] = newmsg.section5
        da.attrs["fullName"] = newmsg.fullName
        da.attrs["shortName"] = newmsg.shortName
        da.attrs["units"] = newmsg.units

        return da

    def update_section3(self) -> xr.DataArray:
        """
        Update section3 attributes based on the latitude and longitude corners.

        This makes the GRIB2IO_section3 attribute consistent with the grid's
        new corners after a change in the spatial extent.
        """
        da = self._obj
        if "GRIB2IO_section3" not in da.attrs:
            raise ValueError(
                "DataArray has no attr 'GRIB2IO_section3'.  This function only works with Datasets/DataArrrays opened with the 'grib2io' backend."
            )
        if "latitude" not in da.coords:
            raise ValueError("DataArray has no coord 'latitude'")
        if "longitude" not in da.coords:
            raise ValueError("DataArray has no coord 'longitude'")

        grid = Grid(da.attrs["GRIB2IO_section3"])

        if grid.gdtn not in [0, 1, 10, 20, 30, 31, 40, 110]:
            raise ValueError(
                textwrap.dedent("""\
                    update_section3 only works for:

                    Latitude/Longitude, Equidistant Cylindrical, or Plate Carree (gdtn=0)
                    Rotated Latitude/Longitude (gdtn=1)
                    Mercator (gdtn=10)
                    Polar Stereographic (gdtn=20)
                    Lambert Conformal (gdtn=30)
                    Albers Equal-Area (gdtn=31)
                    Gaussian Latitude/Longitude (gdtn=40)
                    Equatorial Azimuthal Equidistant Projection (gdtn=110)
                    """)
            )

        grid.latitudeFirstGridpoint = da.latitude.isel(y=0, x=0)
        grid.longitudeFirstGridpoint = da.longitude.isel(y=0, x=0)
        grid.nx = len(da.x)
        grid.ny = len(da.y)

        # last gridpoint does not affect section3 for some gdt but set anyway
        grid.latitudeLastGridpoint = da.latitude.isel(y=-1, x=-1)
        grid.longitudeLastGridpoint = da.longitude.isel(y=-1, x=-1)

        da.attrs["GRIB2IO_section3"] = grid.section3

        return da

    def subset(self, *, lats=None, lons=None) -> xr.DataArray:
        """
        Subset the DataArray to a box defined by latitudes and/or longitudes.

        Parameters
        ----------
        lats
            Two item list or tuple of latitudes.  Default is None which will
            return a subset unbounded by latitude.  The first term defines the
            southern boundary and the second term defines the northern
            boundary.
        lons
            Two item list or tuple of longitudes.  Default is None which will
            return a subset unbounded by longitude.  The first term defines the
            western boundary and the second term defines the eastern
            boundary.  Can follow either: 0 to 360 postive eastward, or 0 to
            -180 westward / 0 to 180 eastward conventions.  The longitude
            boundaries cannot cross 0.

        Returns
        -------
        subset
            DataArray subset to the bounding box created by input 'lats'/'lons'.
            All gridpoints with lat/lon matching contraints are included within
            subset.
        """

        def slice_from_contiguous_mask(mask):
            indices = np.where(mask)[0]

            if indices.size > 0:
                # slice(start, stop) - stop is exclusive, so we add 1
                my_slice = slice(indices[0], indices[-1] + 1)
            else:
                my_slice = slice(0, 0)
            return my_slice

        da = self._obj.copy()

        if lats is None:
            lats = (np.min(da.latitude), np.max(da.latitude))
        else:
            lats = (min(lats), max(lats))

        if lons is None:
            lons = (np.min(da.longitude), np.max(da.longitude))
        else:
            lons = (min(lons), max(lons))

        # Internally work in common lon data representation (0->360 positive eastward from 0)
        lons = np.mod(np.array(lons) + 360, 360)
        lon_da = np.mod(da.longitude + 360, 360)

        snap_first_point = snap_to_nearest_cell_center(da.latitude, lon_da, lats[0], lons[0])
        snap_last_point = snap_to_nearest_cell_center(da.latitude, lon_da, lats[1], lons[1])
        lats = (snap_first_point[0], snap_last_point[0])
        lons = (snap_first_point[1], snap_last_point[1])

        x = ((lon_da >= lons[0]) & (lon_da <= lons[1])).any("y")
        if x.chunks:
            x = x.compute()

        y = ((da.latitude >= lats[0]) & (da.latitude <= lats[1])).any("x")
        if y.chunks:
            y = y.compute()

        y_slice = slice_from_contiguous_mask(y)
        x_slice = slice_from_contiguous_mask(x)

        da = da.isel(y=y_slice, x=x_slice)
        if da.size < 1:
            raise ValueError("None of grid data is within given lat/lon bounds.")

        da = da.grib2io.update_section3()

        return da

    def compute(self, **kwargs):
        """
        Compute the Dask-backed DataArray with retries for transient errors.

        Wraps :func:`grib2io.utils.compute_with_retries`.

        Parameters
        ----------
        **kwargs
            Arguments passed to :func:`grib2io.utils.compute_with_retries`,
            e.g., `max_attempts` or `base_sleep`.

        Returns
        -------
        xarray.DataArray
            The computed DataArray with NumPy-backed data.
        """
        from .utils import compute_with_retries

        return compute_with_retries(self._obj, **kwargs)


def open_mfdataset(
    filenames: typing.Union[str, typing.Sequence[str]],
    *,
    drop_variables: typing.Optional[typing.List[str]] = None,
    save_index: bool = True,
    filters: typing.Mapping[str, typing.Any] = dict(),
    data_model: typing.Optional[str] = None,
    parallel: bool = False,
    preprocess: typing.Optional[typing.Callable] = None,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
    use_icechunk: bool = False,
    **kwargs,
) -> xr.Dataset:
    """
    Open multiple GRIB2 files as a single xarray Dataset.

    This function is optimized for GRIB2 files by combining their indices
    and creating a single Dataset, which is often much faster than
    using ``xarray.open_mfdataset``. It supports parallel index reading
    and dataset opening when ``parallel=True`` and ``dask`` is installed.

    Parameters
    ----------
    filenames : str or sequence of str
        GRIB2 files to be opened. Can be a glob pattern.
    drop_variables : list of str, optional
        List of variables to exclude from the dataset.
    save_index : bool, optional
        Whether to save the GRIB2 index to a file (default is True).
    filters : dict, optional
        Filter GRIB2 messages to a single hypercube. Dictionary keys can be
        any GRIB2 metadata attribute name.
    data_model : str, optional
        Parse GRIB metadata following a defined data model convention
        (e.g., "nws-viz").
    parallel : bool, optional
        If True, use ``dask`` to read indices and open datasets in parallel.
        Requires the ``dask`` package.
    preprocess : callable, optional
        A function to apply to each file's dataset before combining.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.
    **kwargs : optional
        Additional arguments passed to the combination logic.
        If ``combine='nested'``, passed to ``xarray.combine_nested``.
        If ``combine='by_coords'``, passed to ``xarray.combine_by_coords``.
        If ``combine='merge'``, passed to ``xarray.merge``.
        If no ``combine`` argument is provided, the function attempts
        ``xarray.combine_by_coords`` followed by ``xarray.merge``.

    Returns
    -------
    xarray.Dataset
        Xarray dataset of grib2 messages.

    Notes
    -----
    - This function uses a "fast path" when ``preprocess=None`` and no
      combination ``**kwargs`` are provided, which concatenates all indices
      into a single global index before building the Dataset.
    - All files must share the same horizontal grid (ny, nx).
    """
    if isinstance(filenames, str):
        import glob

        filenames = sorted(glob.glob(filenames))

    if use_icechunk:
        from .icechunk import open_grib2

        # Extract Icechunk-specific kwargs from combination kwargs
        icechunk_kwargs = {
            "storage_options": kwargs.pop("storage_options", None),
            "max_workers": kwargs.pop("max_workers", None),
            "network_timeout": kwargs.pop("network_timeout", 120),
            "max_concurrent_requests": kwargs.pop("max_concurrent_requests", 32),
            "max_scan_attempts": kwargs.pop("max_scan_attempts", 3),
            "store_path": kwargs.pop("store_path", None),
        }

        ds = open_grib2(
            filenames,
            filters=filters,
            data_model=data_model,
            drop_variables=drop_variables,
            chunks=chunks,
            **icechunk_kwargs,
        )

        if preprocess is not None:
            ds = preprocess(ds)

        return ds

    def _get_index(fname_and_index: typing.Tuple[str, int]) -> pd.DataFrame:
        """
        Internal utility to read GRIB2 index from a file.

        Parameters
        ----------
        fname_and_index : tuple of (str, int)
            Tuple containing the filename and its position in the file list.

        Returns
        -------
        pandas.DataFrame
            The GRIB2 index for the specified file.
        """
        fname, i = fname_and_index
        with grib2io.open(fname, save_index=save_index, _xarray_backend=True) as f:
            idx = pd.DataFrame(f._index)
            idx = idx.assign(msg=list(f))
            idx["file_index"] = i
            return idx

    if parallel:
        try:
            import dask
            from dask.bag import from_sequence

            indices = from_sequence(zip(filenames, range(len(filenames)))).map(_get_index).compute()
        except ImportError:
            warnings.warn("dask not installed, falling back to sequential index reading.")
            parallel = False
            indices = [_get_index((fname, i)) for i, fname in enumerate(filenames)]
    else:
        indices = [_get_index((fname, i)) for i, fname in enumerate(filenames)]

    if not indices:
        return xr.Dataset()

    # Validate grid consistency across files using only the first message of each file
    grid_cols = ["ny", "nx"]
    first_msgs = pd.concat([idx.head(1) for idx in indices], ignore_index=True)
    unique_grids = first_msgs[grid_cols].drop_duplicates()
    if len(unique_grids) > 1:
        grid_list = unique_grids.to_dict("records")
        raise ValueError(f"Multiple grids detected in open_mfdataset. All files must have the same grid. Found grids: {grid_list}")

    # Determine if we can use the fast path (single index concatenation)
    # The fast path is only available if no preprocess is provided and no combination kwargs are used
    # that would require individual datasets (like concat_dim for nested combination)
    use_fast_path = preprocess is None and not kwargs

    if not use_fast_path:
        if parallel:
            import dask

            @dask.delayed
            def _open_delayed(idx, fname):
                return _open_dataset_from_index(
                    idx,
                    fname,
                    filters,
                    data_model,
                    drop_variables=drop_variables,
                    chunks=chunks,
                )

            datasets = dask.compute(*[_open_delayed(idx, fname) for idx, fname in zip(indices, filenames)])
        else:
            datasets = [
                _open_dataset_from_index(
                    idx,
                    fname,
                    filters,
                    data_model,
                    drop_variables=drop_variables,
                    chunks=chunks,
                )
                for idx, fname in zip(indices, filenames)
            ]

        if preprocess is not None:
            datasets = [preprocess(ds) for ds in datasets]

        combine_opt = kwargs.pop("combine", None)
        if combine_opt == "nested":
            ds = xr.combine_nested(datasets, **kwargs)
        elif combine_opt == "by_coords":
            ds = xr.combine_by_coords(datasets, **kwargs)
        elif combine_opt == "merge":
            ds = xr.merge(datasets, **kwargs)
        else:
            # Default behavior: try by_coords, then merge
            try:
                ds = xr.combine_by_coords(datasets, **kwargs)
            except Exception:
                ds = xr.merge(datasets, **kwargs)
    else:
        file_index = pd.concat(indices, ignore_index=True)
        ds = _open_dataset_from_index(
            file_index,
            list(filenames),
            filters,
            data_model,
            drop_variables=drop_variables,
            chunks=chunks,
        )

    # Update history for provenance
    history = ds.attrs.get("history", "")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ds.attrs["history"] = f"{now}: Initialized via grib2io.open_mfdataset from {len(filenames)} files\n{history}"

    return ds


def _open_dataset_from_index(
    file_index: pd.DataFrame,
    filenames: typing.Union[str, typing.List[str]],
    filters: typing.Mapping[str, typing.Any] = dict(),
    data_model: typing.Optional[str] = None,
    drop_variables: typing.Optional[typing.List[str]] = None,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
) -> xr.Dataset:
    """
    Create an xarray Dataset from a GRIB2 index DataFrame.

    This is an internal utility used by ``open_dataset`` and ``open_mfdataset``
    to build a Dataset structure from a pre-computed index of GRIB2 messages.

    Parameters
    ----------
    file_index : pandas.DataFrame
        GRIB2 index DataFrame, expected to contain GRIB2 metadata and
        message pointers.
    filenames : str or list of str
        Path(s) to the GRIB2 file(s) referenced by the index.
    filters : dict, optional
        Filter GRIB2 messages to a single hypercube.
    data_model : str, optional
        Target data model for metadata normalization (e.g., "nws-viz").
    drop_variables : list of str, optional
        List of shortnames to exclude from the resulting Dataset.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.

    Returns
    -------
    xarray.Dataset
        Dataset representing the GRIB2 messages.
    """
    # parse grib2io _index to dataframe and acquire non-geo possible dims
    # (scalar coord when not dim due to squeeze) parse_grib_index applies
    # filters to index and expands metadata based on product definition
    # template number
    file_index, dim_coords, attrs, coord_attrs = parse_grib_index(file_index, filters)

    if drop_variables:
        file_index = file_index[~file_index["shortName"].isin(drop_variables)]

    # Divide up records by variable
    frames, cubes, extra_geo = make_variables(file_index, filenames, dim_coords)  # have this return var_attrs

    # return empty dataset if no data
    if frames is None:
        return xr.Dataset()

    # create dataframe and add datarrays without any coords
    ds = xr.Dataset()
    for var_df, var_cube in zip(frames, cubes):
        da = build_da_without_coords(var_df, var_cube, filenames, attrs)

        # Assign variable-specific coords from its cube
        coords = coords_from_cube(var_cube)
        da = da.assign_coords(coords)

        # Assign extra index associated coords for this variable
        for dim_name, coord_names in dim_coords.items():
            retain_index_coord = False
            for name in coord_names:
                if name == dim_name:
                    retain_index_coord = True
                else:
                    if dim_name not in da.dims:
                        # for assigning scalar coords
                        coord_data = var_df[name].unique().item()
                        da = da.assign_coords({name: coord_data})
                    else:
                        # "ValueError: can only convert an array of size 1 to a Python scalar" indicates the coord is not compatible with the index
                        coord_data = [
                            var_df[var_df.index.get_level_values(f"{dim_name}_ix") == val][name].unique().item() for val in range(da[dim_name].size)
                        ]
                        coord = pd.Index(coord_data, name=dim_name)
                        da = da.assign_coords({name: (dim_name, coord)})
            if not retain_index_coord and dim_name in da.coords:
                da = da.drop_vars(dim_name)

        ds[da.name] = da

    # add coords and dataset meta
    # Pass first cube for common geo coords assignment
    ds = assign_xr_meta(ds, frames, cubes[0], dim_coords, extra_geo, coord_attrs)

    if data_model is not None:
        ds = parse_data_model(ds, data_model)

    # assign attributes
    ds.attrs["engine"] = "grib2io"

    if chunks is not None:
        ds = ds.chunk(chunks)

    return ds


def build_datatree_from_grib(
    filename: str,
    file_index: pd.DataFrame,
    filters: typing.Optional[typing.Mapping[str, typing.Any]] = None,
    stack_vertical: bool = False,
    drop_variables: typing.Optional[typing.List[str]] = None,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
) -> typing.Any:
    """
    Build a DataTree from GRIB2 messages.

    This internal function organizes GRIB2 messages into a hierarchical
    tree structure based on level types, PDTNs, and other metadata.

    Parameters
    ----------
    filename : str
        Path to the source GRIB2 file.
    file_index : pandas.DataFrame
        Index of GRIB2 messages.
    filters : dict, optional
        Filter criteria for selecting messages.
    stack_vertical : bool, optional
        If True, vertical levels will be stacked in a single dataset
        within each node, rather than creating separate nodes per level value.
    drop_variables : list of str, optional
        List of variable shortnames to exclude.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.

    Returns
    -------
    xarray.DataTree
        A hierarchical tree representation of the GRIB2 data.
    """
    if filters is None:
        filters = {}

    # Apply any filters from user
    for k, v in filters.items():
        if k not in file_index.columns:
            file_index = file_index.copy()
            file_index[k] = file_index.msg.apply(lambda msg: getattr(msg, k, None))
        file_index = filter_index(file_index, k, v)

    # Make a copy to avoid the SettingWithCopyWarning
    file_index = file_index.copy()

    # Extract metadata needed for tree organization
    # Use a safer approach to handle missing attributes
    def safe_getattr(obj, name):
        try:
            attr = getattr(obj, name)
            # Need to test if the attribute is Grib2Metadata. If so,
            # then get the value attribute.
            if isinstance(attr, grib2io.templates.Grib2Metadata):
                attr = attr.value
            return attr
        except (AttributeError, KeyError):
            return None

    for attr in _TREE_HIERARCHY_LEVELS:
        if (attr not in file_index.columns) and (attr != "valueOfFirstFixedSurface"):
            file_index[attr] = file_index.msg.apply(lambda msg: safe_getattr(msg, attr))

    # Also extract shortName for variable naming
    if "shortName" not in file_index.columns:
        file_index = file_index.assign(shortName=file_index.msg.apply(lambda msg: getattr(msg, "shortName", None)))

    if drop_variables:
        file_index = file_index[~file_index["shortName"].isin(drop_variables)]

    file_index = file_index.assign(nx=file_index.msg.apply(lambda msg: getattr(msg, "nx", None)))
    file_index = file_index.assign(ny=file_index.msg.apply(lambda msg: getattr(msg, "ny", None)))

    # Create root DataTree
    root = xr.DataTree()

    # Adjust hierarchy levels if we're stacking vertical levels
    hierarchy_levels = list(_TREE_HIERARCHY_LEVELS)  # This makes a copy
    if stack_vertical and "valueOfFirstFixedSurface" in hierarchy_levels:
        hierarchy_levels.remove("valueOfFirstFixedSurface")

    # First group by level type
    level_groups = {}

    # Create a dictionary to group data by level type
    for level_type in file_index["typeOfFirstFixedSurface"].unique():
        if pd.notna(level_type):  # Skip None/NaN values
            level_info = _LEVEL_NAME_MAPPING.get(level_type, f"level_{level_type}")
            level_name = level_info[0]
            # Get all rows for this level type
            level_data = file_index[file_index["typeOfFirstFixedSurface"] == level_type]
            level_groups[level_type] = {"name": level_name, "data": level_data}

    # Process each level group
    for level_type, group_info in level_groups.items():
        level_name = group_info["name"]
        level_df = group_info["data"]

        # Create a branch for this level type
        level_tree = xr.DataTree()

        # Process this branch based on PDTN, perturbation number, etc.
        process_level_branch(level_tree, level_df, filename, chunks=chunks)

        # Add this branch to the main tree
        root[level_name] = level_tree

    return root


def process_level_branch(
    level_tree: typing.Any,
    df: pd.DataFrame,
    filename: str,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
):
    """
    Process a level type branch of the data tree.

    Organizes the tree by PDTN and other attributes.

    Parameters
    ----------
    level_tree : xarray.DataTree
        The DataTree node for this level type.
    df : pandas.DataFrame
        DataFrame of messages for this level type.
    filename : str
        Path to the GRIB2 file.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.
    """
    # Group by PDTN
    pdtn_groups = {}

    # Group data by PDTN first
    for pdtn_value in df["productDefinitionTemplateNumber"].unique():
        if pd.notna(pdtn_value):
            pdtn_df = df[df["productDefinitionTemplateNumber"] == pdtn_value]
            pdtn_groups[pdtn_value] = pdtn_df

    # If there's only one PDTN value, skip creating PDTN branch level
    if len(pdtn_groups) == 1:
        pdtn, pdtn_df = next(iter(pdtn_groups.items()))

        pdtn_name = f"pdtn_{int(pdtn)}"

        # Check if we need to further subdivide by perturbation number
        has_perturbations = "perturbationNumber" in pdtn_df.columns and len(pdtn_df["perturbationNumber"].dropna().unique()) > 1

        # Check if we need to further subdivide by probabilities unique for each variable.
        has_probabilities = "typeOfProbability" in pdtn_df.columns and len(pdtn_df["typeOfProbability"].dropna().unique()) > 1

        if has_perturbations:
            # Process perturbations directly on the level tree
            process_perturbation_groups(level_tree, pdtn_df, filename, chunks=chunks)
        elif has_probabilities:
            # Process probability groups
            process_probability_groups(level_tree, pdtn_df, filename, chunks=chunks)
        else:
            # Try to create dataset directly on level
            try:
                dss = create_datasets_from_df(pdtn_df, filename, chunks=chunks)
                if dss is not None:
                    dt = xr.DataTree()
                    if len(dss) == 1:
                        dt.ds = dss[0]
                    else:
                        for ds in dss:
                            varname = list(ds.data_vars)[0]
                            dt[f"var_{varname}"] = ds
                    level_tree[pdtn_name] = dt
                else:
                    # Try to separate by variable name as a fallback
                    try_process_by_variables(level_tree, pdtn_df, filename, chunks=chunks)
            except Exception as e:
                print(f"Error creating dataset for level with pdtn {int(pdtn)}: {e}")

                # Try to separate by variable name as a fallback
                try_process_by_variables(level_tree, pdtn_df, filename, chunks=chunks)
    else:
        # Multiple PDTN values, process each group with PDTN branch nodes
        for pdtn, pdtn_df in pdtn_groups.items():
            # Use a simple node name that's easy to use in code
            pdtn_name = f"pdtn_{int(pdtn)}"

            # Check if we need to further subdivide by perturbation number
            has_perturbations = "perturbationNumber" in pdtn_df.columns and len(pdtn_df["perturbationNumber"].dropna().unique()) > 1

            # Check if we need to further subdivide by probabilities unique for each variable.
            has_probabilities = "typeOfProbability" in pdtn_df.columns and len(pdtn_df["typeOfProbability"].dropna().unique()) > 1

            if has_perturbations:
                # Create a branch for this PDTN
                pdtn_tree = xr.DataTree()

                # Process perturbation groups
                process_perturbation_groups(pdtn_tree, pdtn_df, filename, chunks=chunks)

                # Only add the PDTN branch if it has children
                if len(pdtn_tree.children) > 0 or pdtn_tree.ds is not None:
                    level_tree[pdtn_name] = pdtn_tree
            elif has_probabilities:
                # Create a branch for this PDTN
                pdtn_tree = xr.DataTree()

                # Process probability groups
                process_probability_groups(pdtn_tree, pdtn_df, filename, chunks=chunks)

                # Only add the PDTN branch if it has children
                if len(pdtn_tree.children) > 0 or pdtn_tree.ds is not None:
                    level_tree[pdtn_name] = pdtn_tree
            else:
                # Create a subtree for this PDTN
                pdtn_tree = xr.DataTree()

                # Try to create dataset directly on level
                try:
                    dss = create_datasets_from_df(pdtn_df, filename, chunks=chunks)
                    if dss is not None:
                        if len(dss) == 1:
                            pdtn_tree.ds = dss[0]
                        else:
                            for ds in dss:
                                varname = list(ds.data_vars)[0]
                                pdtn_tree[f"var_{varname}"] = ds
                        level_tree[pdtn_name] = pdtn_tree
                    else:
                        # Try to separate by variable name as a fallback
                        try_process_by_variables(pdtn_tree, pdtn_df, filename, chunks=chunks)
                        level_tree[pdtn_name] = pdtn_tree
                except Exception as e:
                    print(f"Error creating dataset for level with pdtn {int(pdtn)}: {e}")

                    # Try to separate by variable name as a fallback
                    try_process_by_variables(pdtn_tree, pdtn_df, filename, chunks=chunks)
                    level_tree[pdtn_name] = pdtn_tree


def process_probability_groups(
    target_tree: typing.Any,
    pdtn_df: pd.DataFrame,
    filename: str,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
) -> bool:
    """
    Process probability groups and add them to the target tree.

    Parameters
    ----------
    target_tree : xarray.DataTree
        The tree node to add probability groups to.
    pdtn_df : pandas.DataFrame
        DataFrame of messages for a specific PDTN.
    filename : str
        Path to the GRIB2 file.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.

    Returns
    -------
    bool
        True if successful.
    """
    success = False
    # Group by type of probability
    prob_groups = {}
    for prob_value in pdtn_df["typeOfProbability"].unique():
        if pd.notna(prob_value):
            prob_df = pdtn_df[pdtn_df["typeOfProbability"] == prob_value]
            prob_groups[prob_value] = prob_df

    # Process each probability group
    for prob_num, prob_df in prob_groups.items():
        prob_name = f"prob_{int(prob_num)}"

        # Try to create dataset for this probability group
        try:
            dss = create_datasets_from_df(prob_df, filename, chunks=chunks)
            dt = xr.DataTree()
            if len(dss) == 1:
                dt.ds = dss[0]
                target_tree[prob_name] = dt
            elif len(dss) > 1:
                for ds in dss:
                    dt[f"var_{ds.data_vars[0]}"] = ds
            target_tree[prob_name] = dt
        except Exception as e:
            # Log error but continue processing other groups
            print(f"Error creating dataset for type of probability {prob_name}: {e}")

    return success


def process_perturbation_groups(
    target_tree: typing.Any,
    pdtn_df: pd.DataFrame,
    filename: str,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
) -> bool:
    """
    Process perturbation groups and add them to the target tree.

    Parameters
    ----------
    target_tree : xarray.DataTree
        The tree node to add perturbation groups to.
    pdtn_df : pandas.DataFrame
        DataFrame of messages for a specific PDTN.
    filename : str
        Path to the GRIB2 file.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.

    Returns
    -------
    bool
        True if at least one perturbation was successfully processed.
    """
    success = False
    # Group by perturbation number
    pert_groups = {}
    for pert_value in pdtn_df["perturbationNumber"].unique():
        if pd.notna(pert_value):
            pert_df = pdtn_df[pdtn_df["perturbationNumber"] == pert_value]
            pert_groups[pert_value] = pert_df

    # Process each perturbation group
    for pert_num, pert_df in pert_groups.items():
        pert_name = f"pert_{int(pert_num)}"

        ## Try to create dataset for this perturbation group
        # try:
        #    dss = create_datasets_from_df(pert_df, filename)
        #    if dss is not None:
        #        if len(dss) == 1:
        #            target_tree.ds = dss[0]
        #        else:
        #            dss_dict = {f"ds_{i}": ds for i, ds in enumerate(dss)}
        #            atree = xr.DataTree(dss_dict)
        #            target_tree[prob_name] = atree
        #        success = True
        # except Exception as e:
        #    # Log error but continue processing other groups
        #    print(f"Error creating dataset for perturbation {pert_name}: {e}")

        # Try to create dataset for this perturbation group
        try:
            dss = create_datasets_from_df(pert_df, filename, chunks=chunks)
            dt = xr.DataTree()
            if len(dss) == 1:
                dt.ds = dss[0]
                target_tree[pert_name] = dt
            elif len(dss) > 1:
                for ds in dss:
                    dt[f"pert{ds.data_vars[0]}"] = ds
            target_tree[pert_name] = dt
        except Exception as e:
            # Log error but continue processing other groups
            print(f"Error creating dataset for perturbation {pert_name}: {e}")

    return success


def try_process_by_variables(
    target_tree: typing.Any,
    df: pd.DataFrame,
    filename: str,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
) -> bool:
    """
    Try to separate data by variable names and create datasets.

    Parameters
    ----------
    target_tree : xarray.DataTree
        The tree node to add variable datasets to.
    df : pandas.DataFrame
        DataFrame of messages.
    filename : str
        Path to the GRIB2 file.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.

    Returns
    -------
    bool
        True if at least one variable was successfully processed.
    """
    success = False

    try:
        for var_name in df["shortName"].unique():
            if pd.notna(var_name):
                var_df = df[df["shortName"] == var_name]
                try:
                    var_ds = create_datasets_from_df(var_df, filename, chunks=chunks)
                    if var_ds is not None:
                        target_tree[f"var_{var_name}"] = var_ds[0]
                        success = True
                except Exception as var_e:
                    print(f"Error creating dataset for variable {var_name}: {var_e}")
    except Exception as nested_e:
        print(f"Failed to process variables: {nested_e}")

    return success


def create_datasets_from_df(
    df: pd.DataFrame,
    filename: str,
    verbose: bool = False,
    chunks: typing.Optional[typing.Union[int, typing.Dict[typing.Any, typing.Any], typing.Literal["auto"]]] = None,
) -> typing.Optional[typing.List[xr.Dataset]]:
    """
    Create a list of xarray Datasets from a DataFrame of messages.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame of GRIB messages.
    filename : str
        Path to the GRIB2 file.
    verbose : bool, optional
        If True, prints detailed debugging information.
    chunks : int, dict or 'auto', optional
        If chunks is provided, it is used to load the dataset into a
        dask-backed dataset.

    Returns
    -------
    list of xarray.Dataset, optional
        List of Datasets, or None if creation failed.
    """
    try:
        # Use parse_grib_index to get dimensions and attributes
        file_index, dim_coords, attrs, coord_attrs = parse_grib_index(df, {})

        # Divide up records by variable
        frames, cubes, extra_geo = make_variables(file_index, filename, dim_coords, allow_uneven_dims=True)

        if frames is None:
            return None

        ds_list = []
        for var_df, var_cube in zip(frames, cubes):
            da = build_da_without_coords(var_df, var_cube, filename, attrs)

            # Assign variable-specific coords from its cube
            coords = coords_from_cube(var_cube)
            da = da.assign_coords(coords)

            # Assign extra index associated coords for this variable
            for dim_name, coord_names in dim_coords.items():
                retain_index_coord = False
                for name in coord_names:
                    if name == dim_name:
                        retain_index_coord = True
                    else:
                        if dim_name not in da.dims:
                            # for assigning scalar coords
                            coord_data = var_df[name].unique().item()
                            da = da.assign_coords({name: coord_data})
                        else:
                            # Handle non-scalar coords
                            coord_data = [
                                var_df[var_df.index.get_level_values(f"{dim_name}_ix") == val][name].unique().item()
                                for val in range(da[dim_name].size)
                            ]
                            coord = pd.Index(coord_data, name=dim_name)
                            da = da.assign_coords({name: (dim_name, coord)})
                if not retain_index_coord and dim_name in da.coords:
                    da = da.drop_vars(dim_name)

            # Create a dataset for this variable
            var_ds = xr.Dataset({da.name: da})

            # Assign metadata and common coords
            var_ds = assign_xr_meta(var_ds, [var_df], var_cube, dim_coords, extra_geo, coord_attrs)

            if chunks is not None:
                var_ds = var_ds.chunk(chunks)

            ds_list.append(var_ds)

        return ds_list
    except Exception as e:
        if verbose:
            print(f"Error in create_datasets_from_df: {e}")
        return None


if _HAS_DATATREE:

    @xr.register_datatree_accessor("grib2io")
    class Grib2ioDataTree:
        """
        DataTree accessor for GRIB2 files.

        This accessor provides methods for working with GRIB2 data organized
        in a hierarchical tree structure.
        """

        def __init__(self, datatree_obj):
            self._obj = datatree_obj

        def to_grib2(self, filename, mode: typing.Literal["x", "w", "a"] = "x"):
            """
            Write all datasets in the DataTree to a GRIB2 file.

            Parameters
            ----------
            filename : str
                Name of the GRIB2 file to write to.
            mode : {"x", "w", "a"}, optional
                Persistence mode, default is "x" (create, fail if exists)
            """
            # Start with the specified mode
            current_mode = mode

            # Function to recursively process the tree
            def process_tree(node):
                nonlocal current_mode

                # If this is a Dataset node with data variables
                if node.ds is not None and node.ds.data_vars:
                    # Write dataset to GRIB2 file
                    node.ds.grib2io.to_grib2(filename, mode=current_mode)
                    # Switch to append mode after first write
                    current_mode = "a"

                # Process children
                for child_name, child_node in node.children.items():
                    process_tree(child_node)

            # Start processing from the root
            process_tree(self._obj)

        def griddef(self):
            """
            Get the grid definition from the first dataset in the tree that has one.

            Returns
            -------
            grib2io.Grib2GridDef
                Grid definition object
            """

            # Function to find first dataset with GRIB2IO_section3
            def find_griddef(node):
                if node.ds is not None and node.ds.data_vars:
                    for var_name in node.ds.data_vars:
                        if "GRIB2IO_section3" in node.ds[var_name].attrs:
                            return Grib2GridDef.from_section3(node.ds[var_name].attrs["GRIB2IO_section3"])

                # Check children
                for child_name, child_node in node.children.items():
                    griddef = find_griddef(child_node)
                    if griddef is not None:
                        return griddef

                return None

            return find_griddef(self._obj)

        def interp(
            self,
            method: typing.Union[str, int],
            grid_def_out: grib2io.Grib2GridDef,
            method_options: typing.Optional[typing.List[int]] = None,
            num_threads: int = 1,
        ) -> typing.Any:
            """
            Interpolate all datasets in the tree to a new grid.

            Parameters
            ----------
            method : str or int
                Interpolation method to use.
            grid_def_out : grib2io.Grib2GridDef
                Target grid definition.
            method_options : list of int, optional
                Options for interpolation method.
            num_threads : int, optional
                Number of threads to use for interpolation.

            Returns
            -------
            xarray.DataTree
                New DataTree with interpolated data.
            """
            new_tree = xr.DataTree()

            # Function to recursively process the tree
            def process_tree(node, new_parent):
                # If this is a Dataset node with data variables
                if node.ds is not None and node.ds.data_vars:
                    # Interpolate dataset
                    interp_ds = node.ds.grib2io.interp(
                        method,
                        grid_def_out,
                        method_options=method_options,
                        num_threads=num_threads,
                    )

                    # Add to new tree at the same path
                    if node == self._obj:  # Root node
                        new_parent.ds = interp_ds
                    else:
                        new_parent.ds = interp_ds

                # Process children
                for child_name, child_node in node.children.items():
                    # Create same child in new tree
                    new_child = xr.DataTree()
                    new_parent[child_name] = new_child
                    process_tree(child_node, new_child)

            # Start processing from the root
            process_tree(self._obj, new_tree)

            return new_tree

        def subset(self, lats: typing.Sequence[float], lons: typing.Sequence[float]) -> typing.Any:
            """
            Subset all datasets in the tree to a region.

            Parameters
            ----------
            lats : sequence of float
                Latitude bounds [min_lat, max_lat].
            lons : sequence of float
                Longitude bounds [min_lon, max_lon].

            Returns
            -------
            xarray.DataTree
                New DataTree with subset data.
            """
            new_tree = xr.DataTree()

            # Function to recursively process the tree
            def process_tree(node, new_parent):
                # If this is a Dataset node with data variables
                if node.ds is not None and node.ds.data_vars:
                    # Subset dataset
                    subset_ds = node.ds.grib2io.subset(lats, lons)

                    # Add to new tree at the same path
                    if node == self._obj:  # Root node
                        new_parent.ds = subset_ds
                    else:
                        new_parent.ds = subset_ds

                # Process children
                for child_name, child_node in node.children.items():
                    # Create same child in new tree
                    new_child = xr.DataTree()
                    new_parent[child_name] = new_child
                    process_tree(child_node, new_child)

            # Start processing from the root
            process_tree(self._obj, new_tree)

            return new_tree
