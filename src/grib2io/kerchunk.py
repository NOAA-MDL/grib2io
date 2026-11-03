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
import warnings
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
    validate : bool, default True
        Check the finished manifest for internal consistency before returning
        it, and raise :class:`ValueError` if any variable's dimension lengths
        disagree with the coordinate arrays it references.  Pass ``False`` to
        emit the manifest regardless.
    """

    def __init__(
        self,
        file_paths: Union[str, List[str]],
        filters: Optional[Dict[str, Any]] = None,
        storage_options: Optional[Dict[str, Any]] = None,
        max_workers: Optional[int] = None,
        validate: bool = True,
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
        self.validate = validate
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
        # Emitted dimension name -> coordinate values written under it.  Shared
        # across every variable so that two variables needing different values
        # for the same dimension get distinct names instead of one silently
        # overwriting the other's coordinate array.
        dim_coord_registry: Dict[str, list] = {}
        for group_key, msg_entries in all_var_messages.items():
            var_name = group_key[0]  # shortName is the first element
            if var_name in used_var_names:
                used_var_names[var_name] += 1
                zarr_var_name = f"{var_name}_{used_var_names[var_name]}"
            else:
                used_var_names[var_name] = 0
                zarr_var_name = var_name
            self._build_variable_refs(zarr_var_name, msg_entries, refs, dim_coord_registry)

        # Build latitude/longitude coordinate arrays from the grid definition.
        # All messages are assumed to share the same grid (required by the
        # xarray backend too), so we use the first available message.
        if all_var_messages:
            first_entries = next(iter(all_var_messages.values()))
            rep_msg = first_entries[0].msg
            _build_latlon_coord_refs(rep_msg, refs)

            # Root-level dataset metadata (CF global attributes + GRIB2
            # provenance from Sections 0/1/4).  Without this, a manifest
            # separated from its filename carries no record of which model,
            # center, or cycle it describes.
            refs[".zattrs"] = json.dumps(_build_root_zattrs(rep_msg))

        if self.validate:
            problems = _validate_refs(refs)
            if problems:
                raise ValueError(_format_validation_errors(problems))

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
            scan_storage_options = _remote_scan_storage_options(file_path, self.storage_options)
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
            index, msgs = self._build_remote_index_filtered(file_path, shortname_filter, scan_storage_options)

        n_msgs = len(msgs)

        # GRIB2 submessages may omit Section 3 and inherit the grid definition
        # of the message before them, so index["section3"] is not necessarily
        # parallel to the message list and must not be indexed by the message
        # counter.  Resolve each message to its own Section 3 entry first.
        sec3_map = _build_section3_map(index, n_msgs)

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
                index_section3=index["section3"][sec3_map[i]],
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
        dim_coord_registry: Optional[Dict[str, list]] = None,
    ) -> None:
        """Build all Zarr refs for a single variable."""
        # Derive surface-type-specific level dim name (mirrors xarray_backend).
        level_base = _level_dim_name(msg_entries[0].msg)
        dim_mapping = _map_messages_to_dimensions(msg_entries, level_dim_name=level_base)

        dim_names = dim_mapping["dim_names"]      # ordered, using base names
        dim_values = dim_mapping["dim_values"]    # base name -> sorted unique values
        msg_index_map = dim_mapping["msg_index_map"]
        duplicate_entry_indices = dim_mapping["duplicate_entry_indices"]

        # Resolve every non-spatial dimension against the shared registry, not
        # just the level one.  Two variables can disagree on the extent of any
        # of them -- NBM, for example, emits CWASP over 7 percentiles and CAPE
        # over 3 -- and whichever is written second would otherwise overwrite
        # the first's coordinate array, leaving the manifest unopenable.
        rename = _resolve_dim_names(dim_names, dim_values, dim_coord_registry)
        emitted = [rename[d] for d in dim_names]

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
        dim_labels = emitted + ["y", "x"]
        zattrs = _build_zattrs(rep_msg, dim_labels)

        # ``level`` and ``valueOfFirstFixedSurface`` describe the representative
        # message only.  When several messages are folded into one array along a
        # level dimension they are correct for the first level and wrong for
        # every other one, so a consumer reading attributes instead of the
        # coordinate array is misled (e.g. a 41-level pressure array labelled
        # "0.01 mb").  Drop them here and let the level coordinate carry the
        # information instead -- see _build_coord_refs / _level_coord_attrs.
        n_levels = len(dim_values.get(level_base, ()))
        if n_levels > 1:
            for _key in ("level", "valueOfFirstFixedSurface"):
                zattrs.pop(_key, None)

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

        # Build coordinate arrays as inline base64-encoded refs.  The emitted
        # name may be suffixed, so pass the base name too: the value encoding
        # and CF attributes are chosen from what the dimension *is*, not from
        # what it ended up being called.
        for d in dim_names:
            _build_coord_refs(
                rename[d],
                dim_values[d],
                refs,
                msg=rep_msg,
                is_level=(d == level_base),
                base_name=d,
            )

        # Re-emit any messages whose identifying metadata exactly collided
        # with an earlier message as a sibling variable, so no message's
        # bytes are silently dropped from the manifest.  smartinit, for
        # example, encodes a 1-bit binary field whose PDT is byte-identical
        # to the real surface TMP message; only the packing (Section 5)
        # differs.  Which message is "the" variable and which is the
        # duplicate is file-order and cannot be determined from metadata,
        # hence the warning telling consumers to inspect both.
        if duplicate_entry_indices:
            dup_entries = [msg_entries[i] for i in duplicate_entry_indices]
            m = re.match(r"^(.*)_dup(\d*)$", var_name)
            if m:
                dup_name = f"{m.group(1)}_dup{int(m.group(2) or 1) + 1}"
            else:
                dup_name = f"{var_name}_dup"
            warnings.warn(
                f"{len(dup_entries)} message(s) share identical identifying "
                f"metadata with an earlier '{var_name}' message; emitting "
                f"them as '{dup_name}'.  The GRIB2 encoding of these "
                f"products is ambiguous; inspect both variables to "
                f"determine which is the intended field."
            )
            self._build_variable_refs(dup_name, dup_entries, refs, dim_coord_registry)

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


def _build_section3_map(index: dict, n_msgs: int) -> List[int]:
    """Map each message index onto its entry in ``index["section3"]``.

    ``build_index`` appends to ``index["section3"]`` only when it actually
    reads a Section 3.  After a message ends, the trailer check reads the next
    section number, which may be 2, 3, or 4:

    * ``nextsec == 4`` — Sections 2 and 3 are not repeated and the submessage
      inherits the preceding grid definition, so ``section3`` does not grow.
    * ``nextsec == 3`` — Section 3 is re-read and appended, so it does grow.
    * ``nextsec == 2`` — Section 2 repeats and Section 3 follows, so it grows.

    ``_isSubmessage`` is set for all three, which is why a counter keyed on it
    is only correct for the first case.  ``sectionOffset[i][3]`` is deep-copied
    per message and retains the previous Section 3 offset when a submessage
    omits it, so distinct offsets in order of first appearance correspond
    one-to-one with the appended Section 3 entries.  Mapping through the offset
    is therefore correct in all three cases.

    Parameters
    ----------
    index : dict
        The grib2io file index.
    n_msgs : int
        Number of messages in the file.

    Returns
    -------
    list of int
        ``sec3_map[i]`` is the index into ``index["section3"]`` for message
        ``i``.  Reduces to the identity mapping when no submessages are present.
    """
    n_sec3 = len(index.get("section3", ()))
    if n_sec3 == 0:
        return [0] * n_msgs

    # Fast path: no submessages, so the lists are already parallel.
    if n_sec3 == n_msgs:
        return list(range(n_msgs))

    offsets = index.get("sectionOffset")
    if offsets is None:
        # Nothing to map through; clamp so a malformed index degrades to the
        # last known grid definition rather than raising IndexError.
        return [min(i, n_sec3 - 1) for i in range(n_msgs)]

    seen: Dict[int, int] = {}
    sec3_map: List[int] = []
    for i in range(n_msgs):
        try:
            off = int(offsets[i][3])
        except (IndexError, KeyError, TypeError, ValueError):
            sec3_map.append(sec3_map[-1] if sec3_map else 0)
            continue
        if off not in seen:
            seen[off] = min(len(seen), n_sec3 - 1)
        sec3_map.append(seen[off])
    return sec3_map


def _remote_scan_storage_options(file_path: str, storage_options: Dict[str, Any]) -> Dict[str, Any]:
    """Build tuned fsspec options for remote metadata scans.

    These defaults reduce accidental large-block downloads while scanning
    message headers/indices across large remote GRIB2 objects.
    """
    tuned = {
        "default_fill_cache": False,
        "default_cache_type": "none",
        "default_block_size": 131072,
    }

    # Public S3 GRIB2 archives are common; default to anonymous access
    # unless the caller explicitly requests credentialed access.
    if urlparse(file_path).scheme in {"s3", "s3a"} and "anon" not in storage_options:
        tuned["anon"] = True

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


def _decode(md: Any) -> Optional[str]:
    """Return the plain-language definition of a ``Grib2Metadata`` value.

    grib2io stores coded metadata as :class:`grib2io.templates.Grib2Metadata`
    objects whose ``definition`` attribute is the decoded string.  Some code
    tables (e.g. Table 4.5) return a ``[definition, units]`` list; in that case
    only the description is taken.  Returns ``None`` when no definition exists.
    """
    if md is None:
        return None
    d = getattr(md, "definition", md)
    if isinstance(d, (list, tuple)):
        d = d[0] if d else None
    if d is None:
        return None
    return str(d)


def _cf_standard_name(msg) -> str:
    """Return the CF standard name for a message, or ``"unknown"``.

    Mirrors the lookup used by grib2io's xarray backend so that manifests and
    the native backend agree on the CF vocabulary.
    """
    record = grib2io.tables.get_table("shortname_to_cf").get(str(msg.shortName))
    if record is None:
        return "unknown"
    return record.get("cf_standard_name") or "unknown"


def _cf_cell_methods(msg) -> Optional[str]:
    """Return the CF ``cell_methods`` string for a message, if any."""
    record = grib2io.tables.get_table("shortname_to_cf").get(str(msg.shortName))
    if record is None:
        return None
    return record.get("cf_cell_methods")


def _level_string(msg) -> str:
    """Return the human-readable wgrib2-style level/layer description.

    Uses grib2io's ``Level`` descriptor (e.g. ``"500 mb"``,
    ``"2 m above ground"``), which is far more usable than the raw
    ``typeOfFirstFixedSurface`` code and ``valueOfFirstFixedSurface``.
    """
    try:
        return str(msg.level)
    except Exception:
        return ""


def _timedelta_hours(td: Any) -> Optional[float]:
    """Convert a ``timedelta``-like value to hours, or ``None``.

    Returns a plain ``float`` (whole hours collapse to e.g. ``24.0``) suitable
    for JSON serialization; returns ``None`` when the value is missing or not a
    duration.
    """
    if td is None:
        return None
    total = getattr(td, "total_seconds", None)
    if total is None:
        return None
    return total() / 3600.0


def _build_root_zattrs(msg) -> dict:
    """Build root-level (dataset) Zarr attributes from a representative message.

    Combines CF global attributes with GRIB2 identification metadata decoded
    from Sections 0/1/4.  This makes a manifest self-describing: which center
    produced it, from what model, for which reference cycle, and under what
    table versions — none of which the per-variable attributes capture.

    Parameters
    ----------
    msg : Grib2Message
        Representative message (all messages in a manifest are assumed to share
        the same originating center, model, and reference time).

    Returns
    -------
    dict
        Root ``.zattrs`` metadata.
    """
    # Institution: originating center, with sub-center appended when defined.
    institution = _decode(getattr(msg, "originatingCenter", None))
    subcenter = _decode(getattr(msg, "originatingSubCenter", None))
    if institution and subcenter:
        institution = f"{institution} / {subcenter}"

    # Reference time (model cycle) as ISO 8601.
    ref = getattr(msg, "refDate", None)
    if hasattr(ref, "isoformat"):
        reference_time = ref.isoformat()
    elif ref is not None:
        reference_time = str(ref)
    else:
        reference_time = None

    zattrs: Dict[str, Any] = {"Conventions": "CF-1.8"}

    # Only emit keys we could actually decode, so consumers never see
    # placeholder/None values in the manifest.
    for key, value in [
        ("institution", institution),
        ("source", _decode(getattr(msg, "generatingProcess", None))),
        ("reference_time", reference_time),
        ("reference_time_significance", _decode(getattr(msg, "significanceOfReferenceTime", None))),
        ("production_status", _decode(getattr(msg, "productionStatus", None))),
        ("type_of_data", _decode(getattr(msg, "typeOfData", None))),
    ]:
        if value is not None:
            zattrs[key] = value

    # GRIB2 table versions (numeric codes) for full reproducibility.
    master = getattr(msg, "masterTableInfo", None)
    if master is not None:
        zattrs["GRIB2_master_table_version"] = int(getattr(master, "value", master))
    local = getattr(msg, "localTableInfo", None)
    if local is not None:
        zattrs["GRIB2_local_table_version"] = int(getattr(local, "value", local))

    version = getattr(grib2io, "__version__", None)
    if version:
        zattrs["grib2io_version"] = str(version)

    return zattrs


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

    Notes
    -----
    ``level`` and ``valueOfFirstFixedSurface`` describe the representative
    message.  They are meaningful only when the variable holds a single level;
    :meth:`ReferenceGenerator._build_variable_refs` removes them for variables
    that span a level dimension, where the level coordinate carries the values
    instead.
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

    zattrs = {
        "_ARRAY_DIMENSIONS": dim_labels,
        "coordinates": "latitude longitude",
        # CF vocabulary (Interoperable) -----------------------------------
        "standard_name": _cf_standard_name(msg),
        "long_name": str(msg.fullName),
        "fullName": str(msg.fullName),
        "units": str(msg.units),
        # GRIB2-native provenance (kept alongside CF for Reusability) -----
        "discipline": int(msg.section0[2]),
        "parameterCategory": int(msg.parameterCategory),
        "parameterNumber": int(msg.parameterNumber),
        "typeOfFirstFixedSurface": int(type_of_first_fixed_surface),
        "valueOfFirstFixedSurface": float(value_of_first_fixed_surface),
        "level": _level_string(msg),
        "shortName": str(msg.shortName),
        "valid_time": valid_time_str,
    }

    # Representative forecast lead time.  Distinguishes an f000 manifest from
    # an f384 one, which is otherwise only recoverable from the filename.
    lead_hours = _timedelta_hours(getattr(msg, "leadTime", None))
    if lead_hours is not None:
        zattrs["lead_time_hours"] = lead_hours

    # Statistical processing period (e.g. accumulation/max/min window); only
    # meaningful for messages that carry one.
    dur_hours = _timedelta_hours(getattr(msg, "duration", None))
    if dur_hours:
        zattrs["duration_hours"] = dur_hours

    # CF cell_methods only when the parameter defines one (e.g. time: maximum).
    cell_methods = _cf_cell_methods(msg)
    if cell_methods:
        zattrs["cell_methods"] = cell_methods

    return zattrs


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
        - ``"duplicate_entry_indices"``: indices of entries whose dim-value
          tuple exactly collided with an earlier entry's
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

    # Build the mapping from dimension-value tuples to entry indices.
    # Two messages can carry fully identical identifying metadata (same
    # parameter, level, lead time, PDT) yet contain different data --
    # smartinit encodes a 1-bit binary field with the same IDs as the real
    # surface TMP.  Overwriting would silently drop the earlier message's
    # bytes from the manifest, so collisions are collected for the caller
    # to emit as a separate variable instead.
    msg_index_map: Dict[tuple, int] = {}
    duplicate_entry_indices: List[int] = []
    for idx, entry in enumerate(msg_entries):
        msg = entry.msg
        dim_tuple = tuple(_get_dim_value(msg, "level" if d == level_dim_name else d) for d in active_dims)
        if dim_tuple in msg_index_map:
            duplicate_entry_indices.append(idx)
        else:
            msg_index_map[dim_tuple] = idx

    return {
        "dim_names": active_dims,
        "dim_values": dim_values,
        "msg_index_map": msg_index_map,
        "duplicate_entry_indices": duplicate_entry_indices,
    }


# CF attributes for vertical coordinates, keyed by GRIB2 Table 4.5
# typeOfFirstFixedSurface.  Values are ``(standard_name, positive)``; either
# element may be ``None`` when CF does not define it.  Units are read from
# Table 4.5 itself rather than duplicated here.
#
# Single-valued surfaces (mean sea level, tropopause, planetary boundary layer,
# entire atmosphere) are deliberately absent: they are labels rather than
# measurable vertical coordinates, and the CF standard names that sound
# applicable — air_pressure_at_mean_sea_level, for instance — belong to the data
# variable, not to the coordinate it sits on.  Those surfaces still receive
# units and a long_name from Table 4.5.
_CF_LEVEL_ATTRS: Dict[int, tuple] = {
    100: ("air_pressure", "down"),          # isobaric surface
    102: ("altitude", "up"),                # specific altitude above mean sea level
    103: ("height", "up"),                  # specified height above ground
    # CF's atmosphere_sigma_coordinate and
    # atmosphere_hybrid_sigma_pressure_coordinate are parametric and require
    # formula_terms referencing the surface-pressure and coefficient variables.
    # Those are not present in a kerchunk manifest, so claiming the
    # standard_name without them would be non-conformant.  Direction alone is
    # both safe and useful.
    104: (None, "down"),                    # sigma level
    105: (None, "down"),                    # hybrid level
    106: ("depth", "down"),                 # depth below land surface
    107: ("air_potential_temperature", "up"),   # isentropic (theta) level
    108: ("air_pressure", "down"),          # pressure difference from ground
    109: ("ertel_potential_vorticity", "up"),   # potential vorticity surface
    160: ("depth", "down"),                 # depth below sea level
}


def _level_coord_attrs(msg, dim_name: str) -> dict:
    """Build CF attributes for a vertical coordinate variable.

    A vertical coordinate carrying only ``_ARRAY_DIMENSIONS`` is not
    CF-conformant and leaves a consumer unable to distinguish Pa from hPa
    except by inspecting the magnitude of the values.  Units and a description
    come from Table 4.5, which grib2io already loads; ``standard_name`` and
    ``positive`` come from :data:`_CF_LEVEL_ATTRS` where CF defines them.

    Parameters
    ----------
    msg : Grib2Message
        Representative message for the variable using this coordinate.
    dim_name : str
        Coordinate name, used only as a ``long_name`` fallback.

    Returns
    -------
    dict
        Attributes to merge into the coordinate's ``.zattrs``.  Empty when the
        surface type cannot be determined.
    """
    toffs = getattr(msg, "typeOfFirstFixedSurface", None)
    if toffs is None:
        return {}
    val = getattr(toffs, "value", toffs)
    try:
        val = int(val)
    except (TypeError, ValueError):
        return {}

    attrs: Dict[str, Any] = {}

    # Units and a human-readable description from Table 4.5, whose entries are
    # ``[definition, units]``.  "unknown" units are omitted rather than emitted
    # literally, since an explicit "unknown" is worse than a missing attribute.
    try:
        entry = grib2io.tables.get_table("4.5").get(str(val))
    except Exception:
        entry = None
    if entry:
        description = str(entry[0]) if len(entry) > 0 else ""
        units = str(entry[1]) if len(entry) > 1 else ""
        if units and units.lower() != "unknown":
            attrs["units"] = units
        if description:
            attrs["long_name"] = description

    if "long_name" not in attrs:
        attrs["long_name"] = dim_name.replace("_", " ")

    cf = _CF_LEVEL_ATTRS.get(val)
    if cf:
        standard_name, positive = cf
        if standard_name:
            attrs["standard_name"] = standard_name
        if positive:
            attrs["positive"] = positive

    # Retain the GRIB2-native surface code alongside the CF vocabulary, for the
    # same reason the data variables keep theirs.
    attrs["typeOfFirstFixedSurface"] = val
    return attrs


def _resolve_dim_names(
    dim_names: List[str],
    dim_values: Dict[str, list],
    registry: Optional[Dict[str, list]],
) -> Dict[str, str]:
    """Map each dimension to the name it should be emitted under.

    A kerchunk manifest is a single flat Zarr group, so a dimension name means
    one thing across the whole file.  Variables within a GRIB2 file frequently
    disagree about a dimension's extent -- different pressure-level sets, some
    fields at 7 percentiles and others at 3, accumulations over different
    windows -- and whichever variable is written last would otherwise overwrite
    the coordinate array, leaving earlier variables pointing at a coordinate of
    the wrong length.  xarray then refuses to open the dataset.

    Any dimension whose values differ from what the registry already holds is
    given a numeric suffix ('percentileValue_2'), matching how the xarray
    backend keeps each surface type in its own Dataset.  Dimensions whose
    values match an existing entry share it, so unrelated variables at the same
    levels continue to use one coordinate.

    Parameters
    ----------
    dim_names : list of str
        Base dimension names for this variable, in order.
    dim_values : dict
        Base dimension name -> sorted unique coordinate values.
    registry : dict or None
        Emitted name -> values already written to the manifest.  Updated in
        place.  When ``None``, names pass through unchanged.

    Returns
    -------
    dict
        Base dimension name -> emitted dimension name.
    """
    out: Dict[str, str] = {}
    for d in dim_names:
        if registry is None:
            out[d] = d
            continue
        vals = dim_values.get(d, [])
        name = d
        if name in registry and registry[name] != vals:
            suffix = 2
            candidate = f"{d}_{suffix}"
            while candidate in registry and registry[candidate] != vals:
                suffix += 1
                candidate = f"{d}_{suffix}"
            name = candidate
        if name not in registry:
            registry[name] = vals
        out[d] = name
    return out


def _build_coord_refs(
    dim_name: str,
    values: list,
    refs: Dict[str, Any],
    msg=None,
    is_level: bool = False,
    base_name: Optional[str] = None,
) -> None:
    """Build inline base64-encoded coordinate array refs.

    Parameters
    ----------
    dim_name : str
        Name the coordinate is emitted under.  May carry a numeric suffix
        assigned by :func:`_resolve_dim_names`.
    values : list
        Sorted unique coordinate values.
    refs : dict
        The refs dict to populate.
    msg : Grib2Message, optional
        Representative message, used to derive CF attributes for the vertical
        coordinate.  When omitted the coordinate is written without them.
    is_level : bool, default False
        Whether this is the variable's vertical dimension.  Only that
        coordinate receives vertical-coordinate attributes.
    base_name : str, optional
        Unsuffixed dimension name.  Value encoding and the time/duration
        attributes are chosen from this, so that a renamed dimension such as
        ``valid_time_2`` is still encoded as datetime64 rather than falling
        through to the float64 default.  Defaults to *dim_name*.
    """
    base = base_name or dim_name
    if values and isinstance(values[0], tuple):
        # Level-type coordinate: values are (v1, v2) tuples; use v1
        coord_values = np.array(
            [v[0] if isinstance(v, tuple) else float(v) for v in values],
            dtype=np.float64,
        )
    elif base == "valid_time":
        # Store as int64 nanoseconds since epoch so xarray decodes as datetime64
        ns_vals = [int(np.datetime64(v, "ns").astype(np.int64)) for v in values]
        coord_values = np.array(ns_vals, dtype=np.int64)
    elif base == "duration":
        # Store as float seconds
        coord_values = np.array(values, dtype=np.float64)
    elif base == "perturbationNumber":
        coord_values = np.array(values, dtype=np.int32)
    elif base == "percentileValue":
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
    coord_zattrs: Dict[str, Any] = {"_ARRAY_DIMENSIONS": [dim_name]}
    if base == "valid_time":
        # CF-compliant time metadata so xarray decodes int64 ns as datetime64
        coord_zattrs["units"] = "nanoseconds since 1970-01-01T00:00:00"
        coord_zattrs["calendar"] = "proleptic_gregorian"
    elif base == "duration":
        coord_zattrs["units"] = "seconds"
        coord_zattrs["long_name"] = "time period over which the field applies"
    elif base == "percentileValue":
        coord_zattrs["units"] = "%"
        coord_zattrs["long_name"] = "percentile"
    elif base == "perturbationNumber":
        coord_zattrs["long_name"] = "ensemble member number"
    elif msg is not None and is_level:
        # Vertical coordinate: CF requires units here, and the level
        # description belongs on the coordinate rather than repeated (and
        # wrong) on every data variable that uses it.
        coord_zattrs.update(_level_coord_attrs(msg, dim_name))

    # Several variables can share a level dimension, and this function is
    # called once per variable.  Keep whichever attribute set is richer so a
    # later, barer write does not strip metadata an earlier one supplied.
    existing = refs.get(f"{dim_name}/.zattrs")
    if existing is not None:
        try:
            prev = json.loads(existing)
        except (TypeError, ValueError):
            prev = {}
        if len(prev) > len(coord_zattrs):
            coord_zattrs = prev

    refs[f"{dim_name}/.zattrs"] = json.dumps(coord_zattrs)

    # Inline data chunk
    refs[f"{dim_name}/0"] = "base64:" + b64_data


def _validate_refs(refs: Dict[str, Any]) -> List[tuple]:
    """Check a finished manifest for internal consistency.

    A kerchunk manifest is only useful if it can be opened.  The failure mode
    worth catching here is a variable whose array shape disagrees with the
    length of a coordinate it names: the manifest serializes cleanly, uploads
    cleanly, and then fails at ``xr.open_dataset`` with a conflicting-sizes
    error that names the variables but not the cause.  Catching it at
    generation time turns a downstream mystery into an immediate, local error.

    Parameters
    ----------
    refs : dict
        The finished ``refs`` mapping.

    Returns
    -------
    list of tuple
        ``(variable, dimension, variable_length, coordinate_length)`` for each
        mismatch found.  Empty when the manifest is self-consistent.
    """
    # Lengths of the 1-D coordinate arrays.  latitude/longitude are 2-D and are
    # not dimensions, so they are skipped.
    coord_len: Dict[str, int] = {}
    for key, val in refs.items():
        if not key.endswith("/.zarray") or key.count("/") != 1:
            continue
        try:
            shape = json.loads(val)["shape"]
        except (TypeError, ValueError, KeyError):
            continue
        if len(shape) == 1:
            coord_len[key.split("/")[0]] = int(shape[0])

    problems: List[tuple] = []
    for key, val in refs.items():
        if not key.endswith("/.zattrs") or key.count("/") != 1:
            continue
        name = key.split("/")[0]
        try:
            attrs = json.loads(val)
        except (TypeError, ValueError):
            continue
        if "shortName" not in attrs:
            continue  # coordinate, not a data variable
        zarray_key = f"{name}/.zarray"
        if zarray_key not in refs:
            continue
        try:
            shape = json.loads(refs[zarray_key])["shape"]
        except (TypeError, ValueError, KeyError):
            continue
        for dim, length in zip(attrs.get("_ARRAY_DIMENSIONS", []), shape):
            if dim in coord_len and coord_len[dim] != int(length):
                problems.append((name, dim, int(length), coord_len[dim]))

    return problems


def _format_validation_errors(problems: List[tuple], limit: int = 10) -> str:
    """Render :func:`_validate_refs` output as an actionable error message."""
    dims = sorted({p[1] for p in problems})
    lines = [
        f"Manifest is internally inconsistent: {len(problems)} variable/dimension "
        f"pairs disagree with their coordinate arrays.",
        f"Affected dimensions: {', '.join(dims)}",
        "",
    ]
    for var, dim, got, expected in problems[:limit]:
        lines.append(f"  {var}: dimension '{dim}' has length {got}, "
                     f"but the coordinate array has length {expected}")
    if len(problems) > limit:
        lines.append(f"  ... and {len(problems) - limit} more")
    lines += [
        "",
        "This manifest would fail to open with xarray.  It usually means two "
        "variables need different values for the same dimension and one "
        "overwrote the other's coordinate array; _resolve_dim_names should "
        "have given them distinct names.",
        "Pass validate=False to ReferenceGenerator to emit it anyway.",
    ]
    return "\n".join(lines)


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
        