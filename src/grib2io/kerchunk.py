"""
Kerchunk Reference Manifest Generator
======================================

Provides :class:`ReferenceGenerator`, which scans one or more GRIB2 files
using grib2io's :func:`build_index` infrastructure and produces a
`Kerchunk v1 reference manifest <https://fsspec.github.io/kerchunk/spec>`_
mapping Zarr chunk keys to ``[url, offset, length]`` tuples within the
original files.

The manifest can be serialized to JSON or Parquet and later opened with
``fsspec.filesystem("reference")`` to create a virtual Zarr store that
reads data lazily from the original GRIB2 bytes, decoded on-the-fly by
:class:`grib2io.codecs.Grib2Codec`.

Example
-------
>>> from grib2io.kerchunk import ReferenceGenerator
>>> gen = ReferenceGenerator("gfs.grib2")
>>> manifest = gen.generate()
>>> gen.to_json("gfs_refs.json")
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

import numpy as np

import grib2io

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import guards
# ---------------------------------------------------------------------------


def _ensure_kerchunk():
    """Raise ``ImportError`` if *kerchunk* is not available."""
    try:
        import kerchunk  # noqa: F401
    except ImportError:
        raise ImportError("kerchunk is required for reference generation. Install with: pip install grib2io[kerchunk]")


def _ensure_numcodecs():
    """Raise ``ImportError`` if *numcodecs* is not available."""
    try:
        import numcodecs  # noqa: F401
    except ImportError:
        raise ImportError("numcodecs is required for the GRIB2 codec. Install with: pip install grib2io[kerchunk]")


# ---------------------------------------------------------------------------
# Dimension names used for grouping (mirrors xarray_backend logic)
# ---------------------------------------------------------------------------

# These are the non-geographic dimensions that can appear in GRIB2 data.
# The order here determines the dimension order in the Zarr array
# (before the trailing y, x spatial dims).
_ORDERED_DIM_NAMES = [
    "refDate",
    "leadTime",
    "level",
    "perturbationNumber",
    "duration",
    "percentileValue",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ReferenceGenerator:
    """Generate Kerchunk v1 reference manifests from GRIB2 files.

    Parameters
    ----------
    file_paths : str or list of str
        One or more GRIB2 file paths (local paths or URIs).
    filters : dict, optional
        Filter GRIB2 messages by metadata attributes.  Keys can be any
        ``Grib2Message`` attribute name (e.g. ``shortName``, ``leadTime``).
    """

    def __init__(
        self,
        file_paths: Union[str, List[str]],
        filters: Optional[Dict[str, Any]] = None,
    ):
        _ensure_numcodecs()

        if isinstance(file_paths, (str, os.PathLike)):
            file_paths = [str(file_paths)]
        else:
            file_paths = [str(p) for p in file_paths]

        # Validate file accessibility
        for fp in file_paths:
            if not os.path.isfile(fp):
                raise FileNotFoundError(f"GRIB2 file not found: {fp}")

        self.file_paths = file_paths
        self.filters = filters or {}
        self._manifest: Optional[dict] = None

    def generate(self) -> dict:
        """Scan files and produce a Kerchunk v1 reference manifest.

        Returns
        -------
        dict
            Kerchunk reference spec v1 dict with keys ``"version"`` and
            ``"refs"``.
        """
        refs: Dict[str, Any] = {}

        # .zgroup at root
        refs[".zgroup"] = json.dumps({"zarr_format": 2})

        # Collect all messages across files, keyed by variable group
        # group_key = (shortName, typeOfFirstFixedSurface, pdtn, typeOfSecondFixedSurface)
        # This ensures messages with different surface types are not mixed.
        all_var_messages: Dict[tuple, list] = {}

        for file_path in self.file_paths:
            file_uri = _file_uri(file_path)
            try:
                self._scan_file(file_path, file_uri, all_var_messages)
            except Exception as e:
                raise ValueError(f"Failed to parse GRIB2 file '{file_path}': {e}") from e

        # For each variable group, map messages to dimensions and build refs.
        # Track used variable names to handle collisions (same shortName
        # but different surface types).
        used_var_names: Dict[str, int] = {}
        for group_key, msg_entries in all_var_messages.items():
            var_name = group_key[0]  # shortName is the first element
            if var_name in used_var_names:
                used_var_names[var_name] += 1
                zarr_var_name = f"{var_name}_{used_var_names[var_name]}"
            else:
                used_var_names[var_name] = 0
                zarr_var_name = var_name
            self._build_variable_refs(zarr_var_name, msg_entries, refs)

        self._manifest = {"version": 1, "refs": refs}
        return self._manifest

    def to_json(self, output_path: str) -> None:
        """Serialize the manifest to a JSON file.

        Parameters
        ----------
        output_path : str
            Path to the output JSON file.
        """
        if self._manifest is None:
            self.generate()
        with open(output_path, "w") as f:
            json.dump(self._manifest, f)

    def to_parquet(self, output_path: str) -> None:
        """Serialize the manifest to a Parquet reference store.

        Parameters
        ----------
        output_path : str
            Path to the output Parquet directory.
        """
        _ensure_kerchunk()
        if self._manifest is None:
            self.generate()
        from kerchunk.df import refs_to_dataframe

        refs_to_dataframe(self._manifest, output_path)

    # ------------------------------------------------------------------
    # Internal scanning
    # ------------------------------------------------------------------

    def _scan_file(
        self,
        file_path: str,
        file_uri: str,
        all_var_messages: Dict[str, list],
    ) -> None:
        """Scan a single GRIB2 file and collect message entries."""
        with grib2io.open(file_path, save_index=False, use_index=False) as f:
            index = f._index
            msgs = list(f)

        n_msgs = len(msgs)
        for i in range(n_msgs):
            msg = msgs[i]

            # Apply filters
            if not self._matches_filters(msg):
                continue

            sec_offsets = index["sectionOffset"][i]
            sec_sizes = index["sectionSize"][i]
            bmapflag = index["bmapflag"][i]

            # Section 7 offset and length
            sec7_offset = sec_offsets[7]
            sec7_length = sec_sizes[7]

            # Section 6 (bitmap) offset and length
            sec6_offset = sec_offsets[6] if bmapflag in {0, 254} else None
            sec6_length = sec_sizes[6] if bmapflag in {0, 254} else None

            # Build a composite variable key that includes the surface type
            # to avoid grouping messages with different surface types together.
            # This mirrors how the xarray backend requires filtering to a
            # single typeOfFirstFixedSurface.
            var_name = str(msg.shortName)
            type_of_first_fixed_surface = msg.typeOfFirstFixedSurface
            if hasattr(type_of_first_fixed_surface, "value"):
                toffs_val = type_of_first_fixed_surface.value
            else:
                toffs_val = type_of_first_fixed_surface

            # Also include typeOfGeneratingProcess and
            # productDefinitionTemplateNumber to disambiguate further
            # (same approach as xarray backend's required_uniques)
            pdtn = msg.productDefinitionTemplateNumber
            if hasattr(pdtn, "value"):
                pdtn_val = pdtn.value
            else:
                pdtn_val = pdtn

            type_of_second_fixed_surface = msg.typeOfSecondFixedSurface
            if hasattr(type_of_second_fixed_surface, "value"):
                tosfs_val = type_of_second_fixed_surface.value
            else:
                tosfs_val = type_of_second_fixed_surface

            # Group key: shortName + surface type + pdtn + second surface type
            group_key = (var_name, int(toffs_val), int(pdtn_val), int(tosfs_val))

            entry = _MsgEntry(
                msg=msg,
                file_uri=file_uri,
                sec7_offset=sec7_offset,
                sec7_length=sec7_length,
                sec6_offset=sec6_offset,
                sec6_length=sec6_length,
                bmapflag=bmapflag,
                index_section3=index["section3"][i],
                index_section5=index["section5"][i],
            )

            all_var_messages.setdefault(group_key, []).append(entry)

    def _matches_filters(self, msg) -> bool:
        """Check if a message matches all user-supplied filters."""
        for key, value in self.filters.items():
            msg_val = getattr(msg, key, None)
            if msg_val is None:
                return False
            # Handle Grib2Metadata objects
            if hasattr(msg_val, "value"):
                msg_val = msg_val.value
            if msg_val != value:
                return False
        return True

    # ------------------------------------------------------------------
    # Variable reference building
    # ------------------------------------------------------------------

    def _build_variable_refs(
        self,
        var_name: str,
        msg_entries: list,
        refs: Dict[str, Any],
    ) -> None:
        """Build all Zarr refs for a single variable."""
        # Map messages to dimensions
        dim_mapping = _map_messages_to_dimensions(msg_entries)

        dim_names = dim_mapping["dim_names"]  # ordered list of dim names
        dim_values = dim_mapping["dim_values"]  # dict: dim_name -> sorted unique values
        msg_index_map = dim_mapping["msg_index_map"]  # dict: dim_tuple -> msg_entry index

        # Representative message for metadata
        rep_msg = msg_entries[0].msg

        # Compute shape (ensure plain Python ints for JSON serialization)
        shape = [len(dim_values[d]) for d in dim_names] + [int(rep_msg.ny), int(rep_msg.nx)]
        chunks = [1] * len(dim_names) + [int(rep_msg.ny), int(rep_msg.nx)]

        # Build .zarray
        codec_config = _build_codec_config(msg_entries[0])
        zarray = _build_zarray_metadata(rep_msg, shape, chunks, codec_config)
        refs[f"{var_name}/.zarray"] = json.dumps(zarray)

        # Build .zattrs
        dim_labels = dim_names + ["y", "x"]
        zattrs = _build_zattrs(rep_msg, dim_labels)
        refs[f"{var_name}/.zattrs"] = json.dumps(zattrs)

        # Build data chunk refs
        for dim_tuple, entry_idx in msg_index_map.items():
            entry = msg_entries[entry_idx]
            dim_indices = []
            for i, d in enumerate(dim_names):
                val = dim_tuple[i]
                idx = list(dim_values[d]).index(val)
                dim_indices.append(idx)

            chunk_key = _build_chunk_key(var_name, dim_indices)

            # The reference points to section 7 bytes in the original file.
            # If bitmap is present, we include bitmap bytes as a companion ref
            # and adjust the codec config per-chunk if needed.
            if entry.bmapflag in {0, 254} and entry.sec6_offset is not None:
                # For bitmap messages, we create a combined reference:
                # The codec expects bitmap bytes prepended to section 7 bytes.
                # We store them as separate companion refs and the main ref
                # points to section 7 only. The codec config carries bitmap info.
                refs[chunk_key] = [
                    entry.file_uri,
                    entry.sec7_offset,
                    entry.sec7_length,
                ]
                # Store bitmap as companion reference
                bitmap_key = f"{var_name}/.bitmap/{'.'.join(str(i) for i in dim_indices)}"
                refs[bitmap_key] = [
                    entry.file_uri,
                    entry.sec6_offset,
                    entry.sec6_length,
                ]
            else:
                refs[chunk_key] = [
                    entry.file_uri,
                    entry.sec7_offset,
                    entry.sec7_length,
                ]

        # Build coordinate arrays as inline base64-encoded refs
        for dim_name in dim_names:
            values = dim_values[dim_name]
            _build_coord_refs(dim_name, values, refs)

    # ------------------------------------------------------------------
    # Manifest access
    # ------------------------------------------------------------------

    @property
    def manifest(self) -> Optional[dict]:
        """The generated manifest, or ``None`` if :meth:`generate` has not
        been called yet."""
        return self._manifest


# ---------------------------------------------------------------------------
# Internal data class for message entries
# ---------------------------------------------------------------------------


class _MsgEntry:
    """Lightweight container for a scanned GRIB2 message."""

    __slots__ = (
        "msg",
        "file_uri",
        "sec7_offset",
        "sec7_length",
        "sec6_offset",
        "sec6_length",
        "bmapflag",
        "index_section3",
        "index_section5",
    )

    def __init__(
        self,
        msg,
        file_uri: str,
        sec7_offset: int,
        sec7_length: int,
        sec6_offset: Optional[int],
        sec6_length: Optional[int],
        bmapflag: int,
        index_section3: np.ndarray,
        index_section5: np.ndarray,
    ):
        self.msg = msg
        self.file_uri = file_uri
        self.sec7_offset = sec7_offset
        self.sec7_length = sec7_length
        self.sec6_offset = sec6_offset
        self.sec6_length = sec6_length
        self.bmapflag = bmapflag
        self.index_section3 = index_section3
        self.index_section5 = index_section5


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _file_uri(file_path: str) -> str:
    """Convert a local file path to a ``file://`` URI."""
    abs_path = os.path.abspath(file_path)
    return f"file://{abs_path}"


def _build_chunk_key(var_name: str, dim_indices: List[int]) -> str:
    """Construct a Zarr chunk key like ``"TMP/0.0.0"``.

    Parameters
    ----------
    var_name : str
        Variable name (top-level Zarr array name).
    dim_indices : list of int
        Integer indices along each non-spatial dimension.

    Returns
    -------
    str
        Zarr chunk key, e.g. ``"TMP/0.1.0.0"`` where the trailing
        two zeros are for the y and x spatial dimensions (always 0
        since each message is one full grid).
    """
    parts = [str(i) for i in dim_indices] + ["0", "0"]
    return f"{var_name}/{'.'.join(parts)}"


def _build_zarray_metadata(
    msg,
    shape: List[int],
    chunks: List[int],
    codec_config: dict,
) -> dict:
    """Build ``.zarray`` JSON metadata for a variable.

    Parameters
    ----------
    msg : Grib2Message
        Representative message for dtype info.
    shape : list of int
        Full array shape including spatial dims.
    chunks : list of int
        Chunk shape (one message per chunk).
    codec_config : dict
        ``Grib2Codec`` configuration dict.

    Returns
    -------
    dict
        Zarr ``.zarray`` metadata.
    """
    dtype = "<f4" if msg.typeOfValues == 0 else "<i4"

    return {
        "zarr_format": 2,
        "shape": shape,
        "chunks": chunks,
        "dtype": dtype,
        "fill_value": "NaN" if dtype == "<f4" else 0,
        "order": "C",
        "compressor": codec_config,
        "filters": None,
    }


def _build_zattrs(msg, dim_labels: List[str]) -> dict:
    """Extract GRIB2 section metadata as Zarr attributes.

    Parameters
    ----------
    msg : Grib2Message
        Representative message.
    dim_labels : list of str
        Ordered dimension names including ``"y"`` and ``"x"``.

    Returns
    -------
    dict
        Zarr ``.zattrs`` metadata.
    """
    # Extract typeOfFirstFixedSurface - handle Grib2Metadata objects
    type_of_first_fixed_surface = msg.typeOfFirstFixedSurface
    if hasattr(type_of_first_fixed_surface, "value"):
        type_of_first_fixed_surface = type_of_first_fixed_surface.value

    # Extract valueOfFirstFixedSurface
    value_of_first_fixed_surface = msg.valueOfFirstFixedSurface
    if hasattr(value_of_first_fixed_surface, "value"):
        value_of_first_fixed_surface = value_of_first_fixed_surface.value

    # Extract refDate and leadTime
    ref_date = msg.refDate
    if isinstance(ref_date, np.datetime64):
        ref_date = str(ref_date)
    elif hasattr(ref_date, "isoformat"):
        ref_date = ref_date.isoformat()
    else:
        ref_date = str(ref_date)

    lead_time = msg.leadTime
    if hasattr(lead_time, "total_seconds"):
        lead_time = lead_time.total_seconds()
    else:
        lead_time = str(lead_time)

    return {
        "_ARRAY_DIMENSIONS": dim_labels,
        "discipline": int(msg.section0[2]),
        "parameterCategory": int(msg.parameterCategory),
        "parameterNumber": int(msg.parameterNumber),
        "typeOfFirstFixedSurface": int(type_of_first_fixed_surface),
        "valueOfFirstFixedSurface": float(value_of_first_fixed_surface),
        "refDate": ref_date,
        "leadTime": lead_time,
        "shortName": str(msg.shortName),
        "fullName": str(msg.fullName),
        "units": str(msg.units),
    }


def _build_codec_config(entry: _MsgEntry) -> dict:
    """Build ``Grib2Codec`` configuration from a message entry.

    Parameters
    ----------
    entry : _MsgEntry
        Scanned message entry with index metadata.

    Returns
    -------
    dict
        Codec configuration suitable for ``Grib2Codec.from_config()``.
    """
    msg = entry.msg
    sec3 = entry.index_section3
    sec5 = entry.index_section5

    # GDS: first 5 elements of section 3
    gds = [int(x) for x in sec3[:5]]
    # GDT: remaining elements of section 3
    gdt = [int(x) for x in sec3[5:]]
    # DRT number and template
    drtn = int(sec5[1])
    drt = [int(x) for x in sec5[2:]]

    # Grid dimensions
    nx = int(msg.nx)
    ny = int(msg.ny)

    # Scan mode flags
    scan_mode_flags = None
    if hasattr(msg, "scanModeFlags"):
        scan_mode_flags = [int(x) for x in msg.scanModeFlags]

    # Bitmap info
    bitmap_flag = int(entry.bmapflag)
    bitmap_offset = None
    bitmap_length = None
    if bitmap_flag in {0, 254} and entry.sec6_offset is not None:
        bitmap_offset = int(entry.sec6_offset)
        bitmap_length = int(entry.sec6_length)

    # Number of data points and packed values
    number_of_data_points = int(msg.numberOfDataPoints)
    number_of_packed_values = int(msg.numberOfPackedValues)

    # Type of values
    type_of_values = int(msg.typeOfValues) if hasattr(msg, "typeOfValues") else 0

    return {
        "id": "grib2io",
        "drtn": drtn,
        "drt": drt,
        "gdtn": int(msg.gdtn),
        "gdt": gdt,
        "gds": gds,
        "nx": nx,
        "ny": ny,
        "bitmap_flag": bitmap_flag,
        "bitmap_offset": bitmap_offset,
        "bitmap_length": bitmap_length,
        "scan_mode_flags": scan_mode_flags,
        "type_of_values": type_of_values,
        "number_of_data_points": number_of_data_points,
        "number_of_packed_values": number_of_packed_values,
    }


def _get_dim_value(msg, dim_name: str) -> Any:
    """Extract a dimension coordinate value from a message.

    Parameters
    ----------
    msg : Grib2Message
        The GRIB2 message.
    dim_name : str
        Dimension name.

    Returns
    -------
    Any
        The coordinate value, converted to a hashable/sortable type.
    """
    if dim_name == "level":
        # Use the tuple (valueOfFirstFixedSurface, valueOfSecondFixedSurface)
        # as the level identifier, matching xarray_backend logic
        v1 = msg.valueOfFirstFixedSurface
        v2 = msg.valueOfSecondFixedSurface
        return (float(v1), float(v2))
    elif dim_name == "refDate":
        rd = msg.refDate
        if hasattr(rd, "isoformat"):
            return rd.isoformat()
        return str(rd)
    elif dim_name == "leadTime":
        lt = msg.leadTime
        if hasattr(lt, "total_seconds"):
            return lt.total_seconds()
        return str(lt)
    elif dim_name == "duration":
        d = msg.duration
        if hasattr(d, "total_seconds"):
            return d.total_seconds()
        return str(d)
    else:
        val = getattr(msg, dim_name, None)
        if hasattr(val, "value"):
            val = val.value
        return val


def _map_messages_to_dimensions(
    msg_entries: List[_MsgEntry],
) -> dict:
    """Group messages by variable and map to dimension indices.

    This mirrors the logic in ``parse_grib_index()`` from the xarray
    backend: for each message, extract the values of potential dimension
    coordinates (level, leadTime, refDate, perturbationNumber, etc.),
    determine which dimensions have more than one unique value, and
    build a mapping from dimension-value tuples to message indices.

    Parameters
    ----------
    msg_entries : list of _MsgEntry
        All message entries for a single variable.

    Returns
    -------
    dict
        Dictionary with keys:
        - ``"dim_names"``: ordered list of active dimension names
        - ``"dim_values"``: dict mapping dim name to sorted unique values
        - ``"msg_index_map"``: dict mapping dim-value tuple to entry index
    """
    # Collect dimension values for each message
    all_dim_vals: Dict[str, list] = {d: [] for d in _ORDERED_DIM_NAMES}

    for entry in msg_entries:
        msg = entry.msg
        for dim_name in _ORDERED_DIM_NAMES:
            try:
                val = _get_dim_value(msg, dim_name)
                all_dim_vals[dim_name].append(val)
            except (AttributeError, TypeError):
                all_dim_vals[dim_name].append(None)

    # Determine which dimensions are active (have >1 unique value)
    active_dims = []
    dim_values: Dict[str, list] = {}

    for dim_name in _ORDERED_DIM_NAMES:
        vals = all_dim_vals[dim_name]
        # Filter out None values
        non_none = [v for v in vals if v is not None]
        if not non_none:
            continue
        unique_vals = sorted(set(non_none))
        if len(unique_vals) > 1:
            active_dims.append(dim_name)
            dim_values[dim_name] = unique_vals
        elif len(unique_vals) == 1:
            # Single value - still include as a dimension of size 1
            # to ensure every message gets a chunk key
            active_dims.append(dim_name)
            dim_values[dim_name] = unique_vals

    # If no dimensions are active (single message), create a trivial mapping
    if not active_dims:
        # Use refDate as a single dimension of size 1
        msg = msg_entries[0].msg
        rd = _get_dim_value(msg, "refDate")
        active_dims = ["refDate"]
        dim_values = {"refDate": [rd]}

    # Build the mapping from dimension-value tuples to entry indices
    msg_index_map: Dict[tuple, int] = {}
    for idx, entry in enumerate(msg_entries):
        msg = entry.msg
        dim_tuple = tuple(_get_dim_value(msg, d) for d in active_dims)
        msg_index_map[dim_tuple] = idx

    return {
        "dim_names": active_dims,
        "dim_values": dim_values,
        "msg_index_map": msg_index_map,
    }


def _build_coord_refs(
    dim_name: str,
    values: list,
    refs: Dict[str, Any],
) -> None:
    """Build inline base64-encoded coordinate array refs.

    Parameters
    ----------
    dim_name : str
        Coordinate/dimension name.
    values : list
        Sorted unique coordinate values.
    refs : dict
        The refs dict to populate.
    """
    if dim_name == "level":
        # Level is a tuple (v1, v2) - use v1 as the coordinate value
        coord_values = np.array(
            [v[0] if isinstance(v, tuple) else float(v) for v in values],
            dtype=np.float64,
        )
    elif dim_name == "refDate":
        # Store refDate as strings
        coord_values = np.array(values, dtype="U30")
    elif dim_name in {"leadTime", "duration"}:
        # Store as float seconds
        coord_values = np.array(values, dtype=np.float64)
    elif dim_name == "perturbationNumber":
        coord_values = np.array(values, dtype=np.int32)
    elif dim_name == "percentileValue":
        coord_values = np.array(values, dtype=np.float64)
    else:
        coord_values = np.array(values, dtype=np.float64)

    # Encode as base64
    raw_bytes = coord_values.tobytes()
    b64_data = base64.b64encode(raw_bytes).decode("ascii")

    # .zarray for the coordinate
    coord_zarray = {
        "zarr_format": 2,
        "shape": [len(values)],
        "chunks": [len(values)],
        "dtype": coord_values.dtype.str,
        "fill_value": None if coord_values.dtype.kind in {"U", "S"} else 0,
        "order": "C",
        "compressor": None,
        "filters": None,
    }
    refs[f"{dim_name}/.zarray"] = json.dumps(coord_zarray)

    # .zattrs for the coordinate
    coord_zattrs = {"_ARRAY_DIMENSIONS": [dim_name]}
    refs[f"{dim_name}/.zattrs"] = json.dumps(coord_zattrs)

    # Inline data chunk
    refs[f"{dim_name}/0"] = "base64:" + b64_data
