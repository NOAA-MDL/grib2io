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
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Set, Union

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
    "valid_time",
    "perturbationNumber",
    "duration",
    "percentileValue",
    "level",
]

# These dims are always emitted (even at size 1) so that manifests from
# different files can be concatenated along them without shape errors.
_ALWAYS_INCLUDE_DIMS = frozenset({"valid_time"})

# Lazy-loaded level name mapping (typeOfFirstFixedSurface int -> (name, source))
_LEVEL_NAME_MAPPING: Optional[dict] = None


def _get_level_name_mapping() -> dict:
    global _LEVEL_NAME_MAPPING
    if _LEVEL_NAME_MAPPING is None:
        _LEVEL_NAME_MAPPING = grib2io.tables.get_table("4.5.grib2io.level.name")
    return _LEVEL_NAME_MAPPING


def _level_dim_name(msg) -> str:
    """Return a surface-type-specific level dimension name.

    Mirrors the xarray backend's ``swap_dims({"level": key})`` logic so
    variables at different surface types get distinct dimension names
    (e.g. ``isobaric_surface``, ``height_above_ground``) and can
    coexist in a single flat xarray Dataset without conflicting sizes.
    """
    toffs = getattr(msg, "typeOfFirstFixedSurface", None)
    if toffs is None:
        return "level"
    val = toffs.value if hasattr(toffs, "value") else int(toffs)
    entry = _get_level_name_mapping().get(int(val))
    if entry:
        return entry[0]  # e.g. 'isobaric_surface', 'height_above_ground'
    return "level"


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
    storage_options : dict, optional
        Extra options passed to ``fsspec.open`` for remote URIs
        (e.g. ``{"anon": True}`` for public S3 buckets).
    """

    def __init__(
        self,
        file_paths: Union[str, List[str]],
        filters: Optional[Dict[str, Any]] = None,
        storage_options: Optional[Dict[str, Any]] = None,
        max_workers: Optional[int] = None,
    ):
        _ensure_numcodecs()

        if isinstance(file_paths, (str, os.PathLike)):
            file_paths = [str(file_paths)]
        else:
            file_paths = [str(p) for p in file_paths]

        # Validate file accessibility.
        # Local filesystem paths must exist. URI inputs are handled by
        # grib2io.open/fsspec at scan time and should not be rejected here.
        for fp in file_paths:
            if _is_local_path(fp) and not os.path.isfile(fp):
                raise FileNotFoundError(f"GRIB2 file not found: {fp}")

        self.file_paths = file_paths
        self.filters = filters or {}
        self.storage_options = storage_options or {}
        self.max_workers = max_workers
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

        n_files = len(self.file_paths)
        use_parallel = self.max_workers != 1 and n_files > 1 and not _is_local_path(self.file_paths[0])

        if use_parallel:
            import concurrent.futures

            workers = self.max_workers or min(n_files, 8)

            def _scan_one(file_path):
                file_uri = _file_uri(file_path)
                local_msgs: Dict[tuple, list] = {}
                self._scan_file(file_path, file_uri, local_msgs)
                return local_msgs

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_scan_one, fp): fp for fp in self.file_paths}
                for future in concurrent.futures.as_completed(futures):
                    fp = futures[future]
                    try:
                        local_msgs = future.result()
                        for key, entries in local_msgs.items():
                            all_var_messages.setdefault(key, []).extend(entries)
                    except Exception as e:
                        raise ValueError(f"Failed to parse GRIB2 file '{fp}': {e}") from e
        else:
            for file_path in self.file_paths:
                file_uri = _file_uri(file_path)
                try:
                    self._scan_file(file_path, file_uri, all_var_messages)
                except Exception as e:
                    raise ValueError(f"Failed to parse GRIB2 file '{file_path}': {e}") from e

        # For each variable group, map messages to dimensions and build refs.
        # Track used variable names to handle collisions (same shortName
        # but different surface types).
        # Also track level coord name -> level values so that the same surface
        # type but different level extents get disambiguated names (mirrors
        # how the xarray backend keeps each surface type in its own Dataset).
        used_var_names: Dict[str, int] = {}
        level_coord_registry: Dict[str, list] = {}  # name -> sorted level values
        for group_key, msg_entries in all_var_messages.items():
            var_name = group_key[0]  # shortName is the first element
            if var_name in used_var_names:
                used_var_names[var_name] += 1
                zarr_var_name = f"{var_name}_{used_var_names[var_name]}"
            else:
                used_var_names[var_name] = 0
                zarr_var_name = var_name
            self._build_variable_refs(zarr_var_name, msg_entries, refs, level_coord_registry)

        # Build latitude/longitude coordinate arrays from the grid definition.
        # All messages are assumed to share the same grid (required by the
        # xarray backend too), so we use the first available message.
        if all_var_messages:
            first_entries = next(iter(all_var_messages.values()))
            rep_msg = first_entries[0].msg
            _build_latlon_coord_refs(rep_msg, refs)

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

        import fsspec
        from fsspec.implementations.reference import LazyReferenceMapper

        fs, _ = fsspec.core.url_to_fs(output_path)
        out = LazyReferenceMapper.create(output_path, fs=fs, record_size=100_000, engine="pyarrow")
        refs = self._manifest.get("refs", self._manifest)
        for k in sorted(refs):
            out[k] = refs[k]
        out.flush()

    # ------------------------------------------------------------------
    # Internal scanning
    # ------------------------------------------------------------------

    def _build_remote_index_filtered(
        self,
        file_path: str,
        shortname_filter: Optional[Union[str, Set[str]]] = None,
        scan_storage_options: Optional[dict] = None,
    ):
        """Build a GRIB2 index for a remote file using sidecar pre-filtering.

        Works with any combination of filters: a ``shortName`` alone,
        ``shortName`` plus additional filters (e.g. ``typeOfFirstFixedSurface``
        / ``level``), or filters without a ``shortName`` at all.

        Instead of fetching headers for every message (~700 HTTP requests for a
        full GFS 0.25° file), this method:

        1. Checks grib2io's local cache – if the full or filtered index was
           saved from a previous run, it loads it instantly.
        2. Checks for a remote grib2io ``.grib2ioidx`` sidecar (binary index)
           alongside the GRIB2 file — the most efficient format, containing
           pre-parsed section offsets and avoiding header reads entirely.
        3. Fetches the wgrib2 ``.idx`` text sidecar and keeps only the byte
           offsets whose shortName matches the filter, reducing HTTP range
           requests from ~700 to ~1–50.
        4. Saves the partial index to a filter-specific cache key so the next
           call for the same file+filter is also instant.
        5. Falls back to ``grib2io.open`` (full index, slow on first call) if
           no sidecar is available.

        Returns
        -------
        tuple(dict, list)
            ``(index, msgs)`` where *index* is a grib2io index dict and *msgs*
            is a list of :class:`~grib2io.Grib2Message` objects.
        """
        import builtins
        import hashlib
        import pickle

        import fsspec

        from grib2io._grib2io import build_index
        from grib2io import msgs_from_index

        scan_storage_options = scan_storage_options or {}
        cache_root = os.path.join(os.path.expanduser("~"), ".cache", "grib2io")

        # Open the remote file to obtain its size (one lightweight HEAD/info call).
        # For the filtered fast-path we override cache settings: "readahead" with
        # a small block size means consecutive section-header reads within the same
        # message share one HTTP range request instead of each triggering a new one.
        fh_options = dict(scan_storage_options)
        fh_options["default_cache_type"] = "readahead"
        fh_options["default_block_size"] = 4096
        fh = fsspec.open(file_path, "rb", **fh_options).open()
        try:
            size = int(fh.info().get("size", 0) or 0)
        except Exception:
            size = 0

        # ------------------------------------------------------------------ #
        # 1. Full-index cache (populated by unfiltered grib2io.open calls)    #
        # ------------------------------------------------------------------ #
        full_cache_key = hashlib.sha1((file_path + str(size)).encode("ASCII")).hexdigest()
        full_cache_path = os.path.join(cache_root, f"{full_cache_key}.grib2ioidx")
        if os.path.exists(full_cache_path):
            with builtins.open(full_cache_path, "rb") as cf:
                index = pickle.load(cf)
            msgs = msgs_from_index(index, filehandle=fh)
            fh.close()
            return index, msgs

        # ------------------------------------------------------------------ #
        # 2. Filter-specific partial-index cache                              #
        # ------------------------------------------------------------------ #
        filter_repr = ":".join(f"{k}={v}" for k, v in sorted(self.filters.items()))
        filtered_cache_key = hashlib.sha1((file_path + str(size) + ":" + filter_repr).encode("ASCII")).hexdigest()
        filtered_cache_path = os.path.join(cache_root, f"{filtered_cache_key}.grib2ioidx")
        if os.path.exists(filtered_cache_path):
            with builtins.open(filtered_cache_path, "rb") as cf:
                index = pickle.load(cf)
            msgs = msgs_from_index(index, filehandle=fh)
            fh.close()
            return index, msgs

        # ------------------------------------------------------------------ #
        # 3. Remote grib2io index sidecar (.grib2ioidx)                       #
        # ------------------------------------------------------------------ #
        # grib2io publishes its own binary index alongside the GRIB2 file.
        # This is the most efficient index format — it contains the full
        # parsed section offsets/sizes and avoids any header reads.  Check
        # for it before falling back to the wgrib2 text .idx sidecar.
        grib2io_idx_url = file_path + ".grib2ioidx"
        try:
            with fsspec.open(grib2io_idx_url, "rb", **scan_storage_options) as gf:
                index = pickle.load(gf)
            msgs = msgs_from_index(index, filehandle=fh)
            fh.close()
            # Cache locally so subsequent calls are instant.
            try:
                os.makedirs(cache_root, exist_ok=True)
                with builtins.open(full_cache_path, "wb") as cf:
                    pickle.dump(index, cf)
            except Exception:
                pass
            return index, msgs
        except Exception:
            pass

        # ------------------------------------------------------------------ #
        # 4. wgrib2 .idx sidecar pre-filtering                                #
        # ------------------------------------------------------------------ #
        idx_url = file_path + ".idx"
        idx_fetch_ok = False
        filtered_offsets: List[int] = []
        try:
            with fsspec.open(idx_url, "r", **scan_storage_options) as idxf:
                filtered_offsets = _prefilter_idx_offsets(idxf, shortname_filter, self.filters)
            idx_fetch_ok = True
        except Exception:
            pass

        if idx_fetch_ok:
            if not filtered_offsets:
                # shortName simply does not appear in this file.
                fh.close()
                return {}, []
            index = build_index(fh, offsets=filtered_offsets)
            msgs = msgs_from_index(index, filehandle=fh)
            fh.close()
            # Persist the partial index so the next call is instant.
            try:
                os.makedirs(cache_root, exist_ok=True)
                with builtins.open(filtered_cache_path, "wb") as cf:
                    pickle.dump(index, cf)
            except Exception:
                pass
            return index, msgs

        # ------------------------------------------------------------------ #
        # 5. Fall back: let grib2io.open build the full index (slow on first  #
        #    call, but saves to grib2io's own cache for future calls).         #
        # ------------------------------------------------------------------ #
        fh.close()
        with grib2io.open(file_path, save_index=True, use_index=True, **scan_storage_options) as f:
            return f._index, list(f)

    def _scan_file(
        self,
        file_path: str,
        file_uri: str,
        all_var_messages: Dict[str, list],
    ) -> None:
        """Scan a single GRIB2 file and collect message entries."""
        if _is_local_path(file_path):
            with grib2io.open(file_path, save_index=False, use_index=True) as f:
                index = f._index
                msgs = list(f)
        else:
            scan_storage_options = _remote_scan_storage_options(self.storage_options)
            shortname_filter = self.filters.get("shortName") if self.filters else None
            # Normalise list/tuple to a set so _prefilter_idx_offsets can do a
            # fast membership test; leave scalar strings as-is.
            if isinstance(shortname_filter, (list, tuple)):
                shortname_filter = set(shortname_filter)
            # Fast path: resolve the index from a sidecar (.grib2ioidx or the
            # wgrib2 .idx) instead of fetching headers for every message.  This
            # works whether or not a shortName filter is given: when shortName
            # is present it is combined with any other filters; when it is
            # absent, other filters (e.g. typeOfFirstFixedSurface/level) are
            # still applied to the .idx, and the .grib2ioidx sidecar yields the
            # full parsed index with no header reads at all.
            index, msgs = self._build_remote_index_filtered(
                file_path, shortname_filter, scan_storage_options
            )

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

            # Section 5 (data representation) — always present
            sec5_offset = sec_offsets[5]
            sec5_length = sec_sizes[5]

            # Section 6 (bitmap) — always present (6 bytes when no bitmap)
            sec6_length = sec_sizes[6]
            # Offset only needed for the old bitmap-conditional path (kept for reference)
            sec6_offset = sec_offsets[6] if bmapflag in {0, 254} else None

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
                sec5_offset=sec5_offset,
                sec5_length=sec5_length,
                sec6_length=sec6_length,
                sec7_offset=sec7_offset,
                sec7_length=sec7_length,
                sec6_offset=sec6_offset,
                bmapflag=bmapflag,
                index_section3=index["section3"][i],
                index_section5=index["section5"][i],
            )

            all_var_messages.setdefault(group_key, []).append(entry)

    def _matches_filters(self, msg) -> bool:
        """Check if a message matches all user-supplied filters.

        Filter values may be:

        * **scalar** – exact equality (``{"shortName": "TMP"}``)
        * **list / tuple / set** – membership test
          (``{"level": [500, 850, 250]}``)
        * **slice** – inclusive range test
          (``{"level": slice(500, 850)}``)
        """
        for key, value in self.filters.items():
            msg_val = getattr(msg, key, None)
            if msg_val is None:
                return False
            # Unwrap Grib2Metadata wrapper objects
            if hasattr(msg_val, "value"):
                msg_val = msg_val.value
            if isinstance(value, slice):
                lo = value.start if value.start is not None else float("-inf")
                hi = value.stop if value.stop is not None else float("inf")
                try:
                    if not (lo <= msg_val <= hi):
                        return False
                except TypeError:
                    return False
            elif isinstance(value, (list, tuple, set)):
                if msg_val not in value:
                    return False
            else:
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
        level_coord_registry: Optional[Dict[str, list]] = None,
    ) -> None:
        """Build all Zarr refs for a single variable."""
        # Derive surface-type-specific level dim name (mirrors xarray_backend)
        level_name = _level_dim_name(msg_entries[0].msg)
        # Map messages to dimensions
        dim_mapping = _map_messages_to_dimensions(msg_entries, level_dim_name=level_name)

        # Disambiguate the level dim name if this surface type already appears
        # in the manifest with different level values.  This prevents xarray
        # from seeing conflicting dimension sizes when variables at the same
        # surface type have different level counts.
        if level_coord_registry is not None and level_name in dim_mapping["dim_values"]:
            level_vals = dim_mapping["dim_values"][level_name]
            if level_name in level_coord_registry:
                if level_coord_registry[level_name] != level_vals:
                    # Same surface type, different level values — append suffix
                    suffix = 2
                    candidate = f"{level_name}_{suffix}"
                    while candidate in level_coord_registry and level_coord_registry[candidate] != level_vals:
                        suffix += 1
                        candidate = f"{level_name}_{suffix}"
                    level_name = candidate
                    dim_mapping = _map_messages_to_dimensions(msg_entries, level_dim_name=level_name)
            if level_name not in level_coord_registry:
                level_coord_registry[level_name] = dim_mapping["dim_values"].get(level_name, [])

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

            # Store a combined reference covering sections 5+6+7 so that the
            # codec can parse the per-chunk data representation template (sec5)
            # and bitmap (sec6) dynamically.  Sections 5, 6, and 7 are always
            # contiguous in the GRIB2 byte stream.
            refs[chunk_key] = [
                entry.file_uri,
                entry.sec5_offset,
                entry.sec5_length + entry.sec6_length + entry.sec7_length,
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
        "sec5_offset",
        "sec5_length",
        "sec6_length",
        "sec7_offset",
        "sec7_length",
        "sec6_offset",
        "bmapflag",
        "index_section3",
        "index_section5",
    )

    def __init__(
        self,
        msg,
        file_uri: str,
        sec5_offset: int,
        sec5_length: int,
        sec6_length: int,
        sec7_offset: int,
        sec7_length: int,
        sec6_offset: Optional[int],
        bmapflag: int,
        index_section3: np.ndarray,
        index_section5: np.ndarray,
    ):
        self.msg = msg
        self.file_uri = file_uri
        self.sec5_offset = sec5_offset
        self.sec5_length = sec5_length
        self.sec6_length = sec6_length
        self.sec7_offset = sec7_offset
        self.sec7_length = sec7_length
        self.sec6_offset = sec6_offset
        self.bmapflag = bmapflag
        self.index_section3 = index_section3
        self.index_section5 = index_section5


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _file_uri(file_path: str) -> str:
    """Convert a local file path to ``file://`` URI, preserving URI inputs."""
    if not _is_local_path(file_path):
        return file_path
    abs_path = os.path.abspath(file_path)
    return f"file://{abs_path}"


def _is_local_path(path: str) -> bool:
    """Return ``True`` if *path* looks like a local filesystem path."""
    parsed = urlparse(path)
    return parsed.scheme == ""


def _remote_scan_storage_options(storage_options: Dict[str, Any]) -> Dict[str, Any]:
    """Build tuned fsspec options for remote metadata scans.

    These defaults reduce accidental large-block downloads while scanning
    message headers/indices across large remote GRIB2 objects.
    """
    tuned = {
        "default_fill_cache": False,
        "default_cache_type": "none",
        "default_block_size": 131072,
    }
    tuned.update(storage_options)
    return tuned


def _value_matches(val: float, filter_val: Any) -> bool:
    """Return True if *val* satisfies the scalar / list / slice *filter_val*."""
    if isinstance(filter_val, (list, tuple, set)):
        return val in filter_val or val in {float(v) for v in filter_val}
    if isinstance(filter_val, slice):
        lo = float(filter_val.start) if filter_val.start is not None else float("-inf")
        hi = float(filter_val.stop) if filter_val.stop is not None else float("inf")
        return lo <= val <= hi
    return val == filter_val or val == float(filter_val)


# Mapping from GRIB2 Table 4.5 typeOfFirstFixedSurface to wgrib2 .idx level
# string prefixes for single-valued surfaces (no numeric level component).
_TOFS_FIXED_STRINGS: Dict[int, tuple] = {
    1: ("surface", "ground or water surface"),
    6: ("max wind",),
    7: ("tropopause",),
    8: ("top of atmosphere", "nominal top of atmosphere"),
    10: ("entire atmosphere",),
    101: ("mean sea level",),
}


def _idx_level_matches(level_str: str, tofs: Any, level_filter: Any) -> bool:
    """Return True if the wgrib2 ``.idx`` level string is consistent with filters.

    Conservative: returns True when the level type is unrecognised so that
    false negatives (silently skipping a matching message) are avoided.

    Recognised mappings:

    * ``typeOfFirstFixedSurface=103`` (height above ground, m):
      ``"2 m above ground"``
    * ``typeOfFirstFixedSurface=100`` (isobaric surface, Pa):
      ``"500 mb"`` — grib2io returns Pa so ``500 mb`` → ``level=50000``.
      Both hPa and Pa values are tried to handle version differences.
    * Fixed-label surfaces (1, 6, 7, 10, 11, 101): matched by keyword.
    """
    if tofs is None and level_filter is None:
        return True

    # Height above ground in metres (tofs = 103)
    if tofs == 103:
        m = re.match(r"^(\d+(?:\.\d+)?)\s+m\s+above\s+ground", level_str)
        if not m:
            return False
        return level_filter is None or _value_matches(float(m.group(1)), level_filter)

    # Isobaric surface in Pa (tofs = 100); wgrib2 uses hPa ("mb")
    if tofs == 100:
        m = re.match(r"^(\d+(?:\.\d+)?)\s+mb", level_str)
        if not m:
            return False
        if level_filter is None:
            return True
        idx_mb = float(m.group(1))
        # grib2io returns Pa (500 mb → 50000); accept both Pa and hPa
        return _value_matches(idx_mb * 100, level_filter) or _value_matches(idx_mb, level_filter)

    # Fixed-label surfaces with no numeric level component
    if tofs in _TOFS_FIXED_STRINGS:
        ls = level_str.lower()
        return any(ls.startswith(s) for s in _TOFS_FIXED_STRINGS[tofs])

    # Unknown surface type — keep conservatively
    return True


def _prefilter_idx_offsets(
    filehandle,
    shortname: Optional[Union[str, Set[str]]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[int]:
    """Parse a wgrib2 ``.idx`` sidecar and return byte offsets matching filters.

    The wgrib2 ``.idx`` line format is::

        MSG_NUM:BYTE_OFFSET:d=YYYYMMDDCC:SHORTNAME:LEVEL:FORECAST:

    *shortname* may be a single string, a set/list of strings, or ``None``.
    When ``None`` the shortName is not constrained and every message is kept
    unless another filter rules it out.  When *filters* is provided, the level
    string (``parts[4]``) is also checked against ``typeOfFirstFixedSurface``
    and ``level`` entries in *filters*, which can drastically reduce the number
    of messages passed to :func:`build_index` (e.g. from ~50 TMP pressure
    levels to 1 for T2M).

    Returns an empty list if the sidecar cannot be parsed or contains no
    matching messages.
    """
    names: Optional[Set[str]] = None
    if shortname is not None:
        names = {shortname} if isinstance(shortname, str) else set(shortname)
    tofs = filters.get("typeOfFirstFixedSurface") if filters else None
    level_filter = filters.get("level") if filters else None
    offsets: List[int] = []
    for line in filehandle:
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        parts = line.split(":")
        if len(parts) >= 5 and (names is None or parts[3] in names):
            # Level-string pre-filter: skip if we can definitively rule out a
            # match from the .idx level description (e.g. "500 mb" vs "2 m
            # above ground").  Conservative: unknown formats are kept.
            if not _idx_level_matches(parts[4], tofs, level_filter):
                continue
            try:
                offsets.append(int(parts[1]))
            except ValueError:
                continue
    return offsets


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

    # Place the codec config in `filters` (a list) rather than `compressor`
    # (a single dict). VirtualiZarr v2's translator iterates the `compressor`
    # field directly, which unpacks a dict's keys instead of the dict itself.
    # Using `filters: [codec_config]` with `compressor: null` is handled
    # correctly by both VirtualiZarr and zarr v2/numcodecs via fsspec.
    return {
        "zarr_format": 2,
        "shape": shape,
        "chunks": chunks,
        "dtype": dtype,
        "fill_value": "NaN" if dtype == "<f4" else 0,
        "order": "C",
        "compressor": None,
        "filters": [codec_config],
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

    # Extract valid_time (= refDate + leadTime = msg.validDate)
    vt = getattr(msg, "validDate", None)
    if vt is None:
        try:
            vt = msg.refDate + msg.leadTime
        except Exception:
            vt = msg.refDate
    if hasattr(vt, "isoformat"):
        valid_time_str = vt.isoformat()
    elif isinstance(vt, np.datetime64):
        valid_time_str = str(vt)
    else:
        valid_time_str = str(vt)

    return {
        "_ARRAY_DIMENSIONS": dim_labels,
        "coordinates": "latitude longitude",
        "discipline": int(msg.section0[2]),
        "parameterCategory": int(msg.parameterCategory),
        "parameterNumber": int(msg.parameterNumber),
        "typeOfFirstFixedSurface": int(type_of_first_fixed_surface),
        "valueOfFirstFixedSurface": float(value_of_first_fixed_surface),
        "valid_time": valid_time_str,
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

    # Emit a Zarr v2/v3-compatible codec config dict for VirtualiZarr compatibility.
    config = {
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
    # For VirtualiZarr, the 'compressor' field must be a dict, not a string or id.
    return config


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
    elif dim_name == "valid_time":
        # valid_time = refDate + leadTime (i.e. msg.validDate)
        vt = getattr(msg, "validDate", None)
        if vt is None:
            rd = msg.refDate
            lt = msg.leadTime
            try:
                vt = rd + lt
            except Exception:
                vt = rd
        if hasattr(vt, "isoformat"):
            return vt.isoformat()
        if isinstance(vt, np.datetime64):
            return str(vt)
        return str(vt)
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
    level_dim_name: str = "level",
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
    # Build ordered dim names, substituting the surface-type-specific level name
    ordered_dims = [level_dim_name if d == "level" else d for d in _ORDERED_DIM_NAMES]

    # Collect dimension values for each message
    all_dim_vals: Dict[str, list] = {d: [] for d in ordered_dims}

    for entry in msg_entries:
        msg = entry.msg
        for dim_name in ordered_dims:
            # Map the (possibly renamed) level dim back to "level" for _get_dim_value
            orig_name = "level" if dim_name == level_dim_name else dim_name
            try:
                val = _get_dim_value(msg, orig_name)
                all_dim_vals[dim_name].append(val)
            except (AttributeError, TypeError):
                all_dim_vals[dim_name].append(None)

    # Determine which dimensions are active (have >1 unique value)
    active_dims = []
    dim_values: Dict[str, list] = {}

    for dim_name in ordered_dims:
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
            # Always emit valid_time and the level dim (so multi-file concat
            # can grow those axes).  All other dims are optional: only emit
            # them when they actually vary within this variable group.
            if dim_name in _ALWAYS_INCLUDE_DIMS or dim_name == level_dim_name:
                active_dims.append(dim_name)
                dim_values[dim_name] = unique_vals

    # If no dimensions are active at all, fall back to a single valid_time
    if not active_dims:
        msg = msg_entries[0].msg
        vt = _get_dim_value(msg, "valid_time")
        active_dims = ["valid_time"]
        dim_values = {"valid_time": [vt]}

    # Remap back so callers can use dim_names as coordinate keys directly
    # (level_dim_name is already baked in via ordered_dims)

    # Build the mapping from dimension-value tuples to entry indices
    msg_index_map: Dict[tuple, int] = {}
    for idx, entry in enumerate(msg_entries):
        msg = entry.msg
        dim_tuple = tuple(_get_dim_value(msg, "level" if d == level_dim_name else d) for d in active_dims)
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
    if values and isinstance(values[0], tuple):
        # Level-type coordinate: values are (v1, v2) tuples; use v1
        coord_values = np.array(
            [v[0] if isinstance(v, tuple) else float(v) for v in values],
            dtype=np.float64,
        )
    elif dim_name == "valid_time":
        # Store as int64 nanoseconds since epoch so xarray decodes as datetime64
        ns_vals = [int(np.datetime64(v, "ns").astype(np.int64)) for v in values]
        coord_values = np.array(ns_vals, dtype=np.int64)
    elif dim_name == "duration":
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
    coord_zattrs: dict = {"_ARRAY_DIMENSIONS": [dim_name]}
    if dim_name == "valid_time":
        # CF-compliant time metadata so xarray decodes int64 ns as datetime64
        coord_zattrs["units"] = "nanoseconds since 1970-01-01T00:00:00"
        coord_zattrs["calendar"] = "proleptic_gregorian"
    refs[f"{dim_name}/.zattrs"] = json.dumps(coord_zattrs)

    # Inline data chunk
    refs[f"{dim_name}/0"] = "base64:" + b64_data


def _build_latlon_coord_refs(msg, refs: Dict[str, Any]) -> None:
    """Build inline latitude/longitude 2-D coordinate arrays from the grid.

    Calls ``msg.latlons()`` to compute the full (ny, nx) grids and encodes
    them as base64 inline Zarr refs, matching the xarray backend's behaviour.
    """
    try:
        lats, lons = msg.latlons()
    except Exception:
        return

    ny, nx = int(msg.ny), int(msg.nx)

    for name, data, attrs in [
        (
            "latitude",
            lats.astype(np.float64),
            {
                "_ARRAY_DIMENSIONS": ["y", "x"],
                "standard_name": "latitude",
                "units": "degrees_north",
            },
        ),
        (
            "longitude",
            lons.astype(np.float64),
            {
                "_ARRAY_DIMENSIONS": ["y", "x"],
                "standard_name": "longitude",
                "units": "degrees_east",
            },
        ),
    ]:
        # Skip if already present (e.g. from a prior variable group)
        if f"{name}/.zarray" in refs:
            continue

        zarray = {
            "zarr_format": 2,
            "shape": [ny, nx],
            "chunks": [ny, nx],
            "dtype": "<f8",
            "fill_value": None,
            "order": "C",
            "compressor": None,
            "filters": None,
        }
        refs[f"{name}/.zarray"] = json.dumps(zarray)
        refs[f"{name}/.zattrs"] = json.dumps(attrs)
        refs[f"{name}/0.0"] = "base64:" + base64.b64encode(data.tobytes()).decode("ascii")
