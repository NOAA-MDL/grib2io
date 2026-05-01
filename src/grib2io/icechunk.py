"""
Icechunk Virtual Store Writer
=============================

Provides :class:`IcechunkWriter`, which writes grib2io reference manifests
(Kerchunk v1 format) into an `Icechunk <https://icechunk.io/>`_ virtual
store, creating versioned Zarr v3 datasets backed by the original GRIB2 file
bytes.

The writer translates each entry in the manifest's ``"refs"`` dict into
either a virtual chunk reference (for data chunks pointing at byte ranges
in GRIB2 files) or native Zarr metadata (for ``.zarray``, ``.zattrs``,
``.zgroup`` entries and inline base64-encoded coordinate arrays).

Icechunk uses Zarr v3 format internally, so the writer converts Kerchunk v1
(Zarr v2) metadata and chunk keys to Zarr v3 equivalents:

- ``.zgroup`` → ``zarr.json`` with ``node_type: "group"``
- ``.zarray`` + ``.zattrs`` → ``<var>/zarr.json`` with ``node_type: "array"``
- Chunk keys ``VAR/0.0.0`` → ``VAR/c/0/0/0``

Example
-------
>>> from grib2io.kerchunk import ReferenceGenerator
>>> from grib2io.icechunk import IcechunkWriter
>>> gen = ReferenceGenerator("gfs.grib2")
>>> manifest = gen.generate()
>>> writer = IcechunkWriter("/tmp/gfs_icechunk")
>>> writer.write(manifest)
>>> snapshot_id = writer.commit("Initial ingest of GFS data")
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Optional, Set

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import guard
# ---------------------------------------------------------------------------


def _ensure_icechunk():
    """Raise ``ImportError`` if *icechunk* is not available."""
    try:
        import icechunk  # noqa: F401
    except ImportError:
        raise ImportError("icechunk is required for virtual store support. Install with: pip install grib2io[icechunk]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_metadata_key(key: str) -> bool:
    """Return ``True`` if *key* is a Zarr metadata key."""
    basename = key.rsplit("/", 1)[-1] if "/" in key else key
    return basename.startswith(".z")


def _is_inline_data(value) -> bool:
    """Return ``True`` if *value* is inline data (a JSON string or
    base64-encoded bytes), as opposed to a ``[uri, offset, length]``
    reference list."""
    return isinstance(value, str)


def _is_virtual_ref(value) -> bool:
    """Return ``True`` if *value* is a virtual chunk reference
    ``[uri, offset, length]``."""
    return isinstance(value, list) and len(value) == 3


def _decode_inline_value(value: str) -> bytes:
    """Decode an inline manifest value to raw bytes.

    Inline values are either:
    - ``"base64:<data>"`` — base64-encoded binary data (coordinate arrays)
    - A plain JSON string (metadata like ``.zarray``, ``.zattrs``)

    Parameters
    ----------
    value : str
        The inline value from the manifest.

    Returns
    -------
    bytes
        The decoded bytes.
    """
    if value.startswith("base64:"):
        return base64.b64decode(value[7:])
    # Plain JSON string — encode to UTF-8 bytes for storage
    return value.encode("utf-8")


def _collect_virtual_chunk_prefixes(refs: Dict[str, Any]) -> Set[str]:
    """Scan all virtual refs and collect the unique URI prefixes needed
    for Icechunk virtual chunk containers.

    For ``file://`` URIs, the prefix is the directory portion.
    For ``s3://``, ``gcs://``, ``https://`` URIs, the prefix is the
    bucket/host + path up to the last ``/``.

    Parameters
    ----------
    refs : dict
        The ``"refs"`` dict from a Kerchunk v1 manifest.

    Returns
    -------
    set of str
        Unique URI prefixes (each ending with ``/``).
    """
    prefixes: Set[str] = set()
    for key, value in refs.items():
        if _is_virtual_ref(value):
            uri = value[0]
            # Extract the directory prefix from the URI
            last_slash = uri.rfind("/")
            if last_slash > 0:
                prefix = uri[: last_slash + 1]
                prefixes.add(prefix)
    return prefixes


def _chunk_key_v2_to_v3(key: str) -> str:
    """Convert a Kerchunk v1 (Zarr v2) chunk key to Zarr v3 format.

    Zarr v2 chunk keys use dot-separated indices under the variable name:
    ``"TMP/0.0.0.0"`` or ``"level/0"``.

    Zarr v3 chunk keys use ``c/`` prefix with slash-separated indices:
    ``"TMP/c/0/0/0/0"`` or ``"level/c/0"``.

    Parameters
    ----------
    key : str
        A Zarr v2 chunk key like ``"TMP/0.0.0"`` or ``"level/0"``.

    Returns
    -------
    str
        The Zarr v3 equivalent like ``"TMP/c/0/0/0"`` or ``"level/c/0"``.
    """
    if "/" not in key:
        # Root-level key, no conversion needed
        return key

    parts = key.split("/")
    var_name = parts[0]
    index_str = parts[1]

    # Split dot-separated indices and rejoin with slashes under c/
    indices = index_str.split(".")
    return var_name + "/c/" + "/".join(indices)


def _make_zarr_v3_group_metadata(v2_zgroup_str: str) -> str:
    """Convert a Zarr v2 ``.zgroup`` JSON string to Zarr v3 ``zarr.json``
    group metadata.

    Parameters
    ----------
    v2_zgroup_str : str
        JSON string like ``'{"zarr_format": 2}'``.

    Returns
    -------
    str
        Zarr v3 group metadata JSON string.
    """
    return json.dumps(
        {
            "zarr_format": 3,
            "node_type": "group",
            "attributes": {},
        }
    )


def _make_zarr_v3_array_metadata(
    v2_zarray_str: str,
    v2_zattrs_str: Optional[str] = None,
) -> str:
    """Convert Zarr v2 ``.zarray`` and ``.zattrs`` JSON strings to a
    single Zarr v3 ``zarr.json`` array metadata string.

    Parameters
    ----------
    v2_zarray_str : str
        JSON string with Zarr v2 array metadata (shape, chunks, dtype, etc.).
    v2_zattrs_str : str, optional
        JSON string with Zarr v2 attributes (_ARRAY_DIMENSIONS, etc.).

    Returns
    -------
    str
        Zarr v3 array metadata JSON string.
    """
    v2_zarray = json.loads(v2_zarray_str)
    v2_zattrs = json.loads(v2_zattrs_str) if v2_zattrs_str else {}

    shape = v2_zarray.get("shape", [])
    chunks = v2_zarray.get("chunks", shape)
    dtype = v2_zarray.get("dtype", "<f4")
    fill_value = v2_zarray.get("fill_value", None)

    # Convert numpy dtype string to Zarr v3 data_type
    dtype_map = {
        "<f4": "float32",
        "<f8": "float64",
        "<i4": "int32",
        "<i8": "int64",
        "<i2": "int16",
        "<u1": "uint8",
        "<u2": "uint16",
        "<u4": "uint32",
        ">f4": "float32",
        ">f8": "float64",
        ">i4": "int32",
        ">i8": "int64",
    }
    data_type = dtype_map.get(dtype, "float32")

    # Determine endianness for the bytes codec
    endian = "big" if dtype.startswith(">") else "little"

    # Extract dimension names from attributes
    dim_names = v2_zattrs.get("_ARRAY_DIMENSIONS", [])

    # Build codecs — for Zarr v3 / Icechunk, we use a simple bytes codec.
    # The grib2io compressor is a Zarr v2 concept used by the Kerchunk
    # reference filesystem; Icechunk accesses data via virtual refs so
    # the codec pipeline just needs to handle raw bytes.
    codecs = [{"name": "bytes", "configuration": {"endian": endian}}]

    # Preserve the grib2io compressor config in attributes so it can be
    # recovered if needed, but don't put it in the codecs list where
    # Zarr v3 would try to instantiate it.
    compressor = v2_zarray.get("compressor", None)
    if compressor and compressor.get("id") == "grib2io":
        v2_zattrs["_grib2io_compressor"] = compressor

    # Handle fill_value — "NaN" string is valid in Zarr v3
    if fill_value == "NaN" or fill_value is None:
        fill_value_v3 = "NaN"
    else:
        fill_value_v3 = fill_value

    v3_meta = {
        "zarr_format": 3,
        "node_type": "array",
        "shape": shape,
        "data_type": data_type,
        "chunk_grid": {
            "name": "regular",
            "configuration": {"chunk_shape": chunks},
        },
        "chunk_key_encoding": {
            "name": "default",
            "configuration": {"separator": "/"},
        },
        "fill_value": fill_value_v3,
        "codecs": codecs,
        "dimension_names": dim_names if dim_names else None,
        "attributes": v2_zattrs,
    }

    return json.dumps(v3_meta)


def _store_set_sync(store, key: str, data: bytes) -> None:
    """Synchronously write bytes to an Icechunk store.

    Icechunk v2's ``store.set()`` is an async coroutine. This helper
    wraps it using the store's ``_sync`` method and converts raw bytes
    to a Zarr ``Buffer`` object.

    Parameters
    ----------
    store : IcechunkStore
        The Icechunk store.
    key : str
        The Zarr key to write.
    data : bytes
        The raw bytes to write.
    """
    from zarr.core.buffer import default_buffer_prototype

    buf = default_buffer_prototype().buffer.from_bytes(data)
    store._sync(store.set(key, buf))


def _store_get_sync(store, key: str):
    """Synchronously read bytes from an Icechunk store.

    Parameters
    ----------
    store : IcechunkStore
        The Icechunk store.
    key : str
        The Zarr key to read.

    Returns
    -------
    bytes or None
        The raw bytes, or ``None`` if the key does not exist.
    """
    from zarr.core.buffer import default_buffer_prototype

    buf = store._sync(store.get(key, default_buffer_prototype()))
    if buf is not None:
        return buf.to_bytes()
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class IcechunkWriter:
    """Write grib2io reference manifests into an Icechunk virtual store.

    Parameters
    ----------
    store_path : str
        Path or URI for the Icechunk store.  For local filesystem stores
        this is a directory path.  For cloud stores, provide the
        appropriate URI (e.g. ``s3://bucket/prefix``).
    storage_config : optional
        An Icechunk ``Storage`` object.  If ``None`` (the default), a
        local filesystem storage is created at *store_path*.
    """

    def __init__(
        self,
        store_path: str,
        storage_config: Optional[Any] = None,
    ):
        _ensure_icechunk()

        self._store_path = store_path
        self._storage_config = storage_config
        self._repo = None
        self._session = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_storage(self):
        """Return an Icechunk ``Storage`` object."""
        if self._storage_config is not None:
            return self._storage_config

        import icechunk

        return icechunk.local_filesystem_storage(path=self._store_path)

    def _create_or_open_repo(self, mode: str, virtual_prefixes: Set[str]):
        """Create or open an Icechunk repository.

        Parameters
        ----------
        mode : str
            ``'w'`` to create a new repo (or overwrite), ``'a'`` to open
            an existing repo for appending.
        virtual_prefixes : set of str
            URI prefixes that need to be registered as virtual chunk
            containers.
        """
        import icechunk

        storage = self._get_storage()

        # Build repository config with virtual chunk containers
        config = icechunk.config.RepositoryConfig.default()
        for prefix in virtual_prefixes:
            container_store = self._make_container_store(prefix)
            config.set_virtual_chunk_container(icechunk.virtual.VirtualChunkContainer(prefix, container_store))

        # Build authorize_virtual_chunk_access mapping
        # Use None for credentials (will use environment or anonymous)
        authorize = {prefix: None for prefix in virtual_prefixes}

        if mode == "w":
            self._repo = icechunk.Repository.open_or_create(
                storage,
                config=config,
                authorize_virtual_chunk_access=authorize if authorize else None,
            )
        else:
            # Append mode — open existing
            self._repo = icechunk.Repository.open(
                storage,
                config=config,
                authorize_virtual_chunk_access=authorize if authorize else None,
            )

        self._session = self._repo.writable_session("main")

    def _make_container_store(self, prefix: str):
        """Create an appropriate Icechunk storage backend for a virtual
        chunk container based on the URI prefix scheme.

        Parameters
        ----------
        prefix : str
            URI prefix like ``file:///path/to/dir/`` or
            ``s3://bucket/prefix/``.

        Returns
        -------
        An Icechunk storage store object.
        """
        import icechunk

        if prefix.startswith("file://"):
            # Extract local path from file:// URI
            local_path = prefix[7:]  # Remove "file://"
            # Remove trailing slash for the store path
            if local_path.endswith("/"):
                local_path = local_path[:-1]
            return icechunk.storage.local_filesystem_store(local_path)
        elif prefix.startswith("s3://"):
            return icechunk.storage.s3_store(region="us-east-1")
        elif prefix.startswith("gcs://"):
            return icechunk.storage.gcs_store(opts={})
        elif prefix.startswith("http://") or prefix.startswith("https://"):
            return icechunk.storage.http_store(opts={})
        else:
            # Default to local filesystem
            return icechunk.storage.local_filesystem_store(prefix)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def write(
        self,
        manifest: dict,
        mode: str = "w",
        append_dim: Optional[str] = None,
    ) -> None:
        """Write a reference manifest into the Icechunk store.

        Parameters
        ----------
        manifest : dict
            Kerchunk v1 reference manifest dict with ``"version"`` and
            ``"refs"`` keys.
        mode : str
            ``'w'`` for create/overwrite, ``'a'`` for append.
        append_dim : str, optional
            Dimension along which to append when ``mode='a'``.  Required
            when appending multi-file data along a specific dimension
            (e.g. ``"refDate"`` or ``"leadTime"``).
        """
        refs = manifest.get("refs", {})

        # Collect virtual chunk URI prefixes for container registration
        virtual_prefixes = _collect_virtual_chunk_prefixes(refs)

        # Create or open the repository
        self._create_or_open_repo(mode, virtual_prefixes)

        store = self._session.store

        if mode == "a" and append_dim is not None:
            self._write_append(refs, store, append_dim)
        else:
            self._write_create(refs, store)

    def _write_create(self, refs: Dict[str, Any], store) -> None:
        """Write all refs to a fresh store.

        Converts Kerchunk v1 (Zarr v2) metadata and chunk keys to
        Zarr v3 format as required by Icechunk.

        Parameters
        ----------
        refs : dict
            The ``"refs"`` dict from the manifest.
        store : IcechunkStore
            The Icechunk store to write to.
        """
        # First pass: collect all metadata by variable so we can merge
        # .zarray and .zattrs into a single zarr.json per variable.
        zarray_refs: Dict[str, str] = {}  # var_name -> .zarray JSON str
        zattrs_refs: Dict[str, str] = {}  # var_name -> .zattrs JSON str
        root_zgroup: Optional[str] = None
        data_refs: Dict[str, Any] = {}  # chunk keys -> values
        inline_data_refs: Dict[str, str] = {}  # inline data keys -> values

        for key, value in refs.items():
            if key == ".zgroup":
                root_zgroup = value
            elif key.endswith("/.zarray"):
                var_name = key.rsplit("/.zarray", 1)[0]
                zarray_refs[var_name] = value
            elif key.endswith("/.zattrs"):
                var_name = key.rsplit("/.zattrs", 1)[0]
                zattrs_refs[var_name] = value
            elif _is_virtual_ref(value):
                data_refs[key] = value
            elif _is_inline_data(value) and not _is_metadata_key(key):
                inline_data_refs[key] = value
            elif _is_metadata_key(key):
                # Other metadata keys (e.g., root .zattrs) — skip for now
                pass
            else:
                _logger.warning(
                    "Skipping unrecognized manifest entry: %s = %r",
                    key,
                    value,
                )

        # Write root group metadata as zarr.json
        if root_zgroup is not None:
            v3_group = _make_zarr_v3_group_metadata(root_zgroup)
            _store_set_sync(store, "zarr.json", v3_group.encode("utf-8"))

        # Write array metadata: merge .zarray + .zattrs into zarr.json
        for var_name, zarray_str in zarray_refs.items():
            zattrs_str = zattrs_refs.get(var_name)
            v3_array = _make_zarr_v3_array_metadata(zarray_str, zattrs_str)
            _store_set_sync(
                store,
                f"{var_name}/zarr.json",
                v3_array.encode("utf-8"),
            )

        # Write inline data (coordinate arrays) with v3 chunk keys
        for key, value in inline_data_refs.items():
            raw_bytes = _decode_inline_value(value)
            v3_key = _chunk_key_v2_to_v3(key)
            _store_set_sync(store, v3_key, raw_bytes)

        # Write virtual chunk references with v3 chunk keys
        for key, value in data_refs.items():
            uri, offset, length = value
            v3_key = _chunk_key_v2_to_v3(key)
            store.set_virtual_ref(
                v3_key,
                uri,
                offset=int(offset),
                length=int(length),
                validate_container=True,
            )

    def _write_append(
        self,
        refs: Dict[str, Any],
        store,
        append_dim: str,
    ) -> None:
        """Append new data to an existing store along *append_dim*.

        This handles extending existing arrays by:
        1. Reading existing array metadata to determine current shape
        2. Computing the offset along the append dimension
        3. Updating array shape to reflect the concatenated size
        4. Writing new data chunks with adjusted indices
        5. Extending coordinate arrays

        Parameters
        ----------
        refs : dict
            The ``"refs"`` dict from the new manifest.
        store : IcechunkStore
            The Icechunk store to append to.
        append_dim : str
            Dimension name along which to append.
        """
        # Separate refs by type
        zarray_refs: Dict[str, str] = {}
        zattrs_refs: Dict[str, str] = {}
        data_refs: Dict[str, Any] = {}
        inline_refs: Dict[str, str] = {}
        root_zgroup: Optional[str] = None

        for key, value in refs.items():
            if key == ".zgroup":
                root_zgroup = value
            elif key.endswith("/.zarray"):
                var_name = key.rsplit("/.zarray", 1)[0]
                zarray_refs[var_name] = value
            elif key.endswith("/.zattrs"):
                var_name = key.rsplit("/.zattrs", 1)[0]
                zattrs_refs[var_name] = value
            elif _is_virtual_ref(value):
                data_refs[key] = value
            elif _is_inline_data(value) and not _is_metadata_key(key):
                inline_refs[key] = value

        # Group data refs by variable (top-level array name)
        var_data_refs: Dict[str, Dict[str, list]] = {}
        for key, value in data_refs.items():
            parts = key.split("/")
            var_name = parts[0]
            var_data_refs.setdefault(var_name, {})[key] = value

        # For each variable, determine the append offset and write
        for var_name, chunk_refs in var_data_refs.items():
            new_zarray_str = zarray_refs.get(var_name)
            if new_zarray_str is None:
                continue

            new_zarray = json.loads(new_zarray_str)
            new_shape = new_zarray["shape"]

            # Try to read existing zarr.json from the store
            existing_shape = None
            existing_v3_meta = None
            try:
                existing_bytes = _store_get_sync(store, f"{var_name}/zarr.json")
                if existing_bytes is not None:
                    existing_v3_meta = json.loads(existing_bytes.decode("utf-8"))
                    existing_shape = existing_v3_meta.get("shape")
            except Exception:
                pass

            # Determine the append dimension index from .zattrs
            new_zattrs_str = zattrs_refs.get(var_name)
            if new_zattrs_str:
                new_zattrs = json.loads(new_zattrs_str)
                dim_labels = new_zattrs.get("_ARRAY_DIMENSIONS", [])
            else:
                dim_labels = []

            if append_dim in dim_labels:
                append_axis = dim_labels.index(append_dim)
            else:
                append_axis = None

            if existing_shape is not None and append_axis is not None:
                # Compute offset: existing size along append axis
                offset = existing_shape[append_axis]

                # Update shape: extend along append axis
                updated_shape = list(existing_shape)
                updated_shape[append_axis] += new_shape[append_axis]
                new_zarray["shape"] = updated_shape

                # Write updated zarr.json (merged .zarray + .zattrs)
                v3_array = _make_zarr_v3_array_metadata(json.dumps(new_zarray), new_zattrs_str)
                _store_set_sync(
                    store,
                    f"{var_name}/zarr.json",
                    v3_array.encode("utf-8"),
                )

                # Write data chunks with adjusted indices
                for key, value in chunk_refs.items():
                    uri, chunk_offset, length = value
                    adjusted_key = self._adjust_chunk_key(key, var_name, append_axis, offset)
                    v3_key = _chunk_key_v2_to_v3(adjusted_key)
                    store.set_virtual_ref(
                        v3_key,
                        uri,
                        offset=int(chunk_offset),
                        length=int(length),
                        validate_container=True,
                    )
            else:
                # No existing data or append_dim not relevant — write as-is
                v3_array = _make_zarr_v3_array_metadata(json.dumps(new_zarray), new_zattrs_str)
                _store_set_sync(
                    store,
                    f"{var_name}/zarr.json",
                    v3_array.encode("utf-8"),
                )
                for key, value in chunk_refs.items():
                    uri, chunk_offset, length = value
                    v3_key = _chunk_key_v2_to_v3(key)
                    store.set_virtual_ref(
                        v3_key,
                        uri,
                        offset=int(chunk_offset),
                        length=int(length),
                        validate_container=True,
                    )

        # Write root group if present
        if root_zgroup is not None:
            v3_group = _make_zarr_v3_group_metadata(root_zgroup)
            _store_set_sync(store, "zarr.json", v3_group.encode("utf-8"))

        # Handle coordinate arrays for the append dimension
        for key, value in inline_refs.items():
            parts = key.split("/")
            coord_name = parts[0] if len(parts) >= 2 else None

            if coord_name == append_dim:
                self._extend_coord(store, coord_name, key, value, zarray_refs, zattrs_refs)
            else:
                raw_bytes = _decode_inline_value(value)
                v3_key = _chunk_key_v2_to_v3(key)
                _store_set_sync(store, v3_key, raw_bytes)

        # Write remaining metadata (coordinate .zarray/.zattrs) that
        # aren't for data variables
        for var_name in zarray_refs:
            if var_name not in var_data_refs and var_name != append_dim:
                zarray_str = zarray_refs[var_name]
                zattrs_str = zattrs_refs.get(var_name)
                v3_array = _make_zarr_v3_array_metadata(zarray_str, zattrs_str)
                _store_set_sync(
                    store,
                    f"{var_name}/zarr.json",
                    v3_array.encode("utf-8"),
                )

    def _adjust_chunk_key(
        self,
        key: str,
        var_name: str,
        append_axis: int,
        offset: int,
    ) -> str:
        """Adjust a chunk key's index along the append axis.

        Parameters
        ----------
        key : str
            Original chunk key like ``"TMP/0.0.0.0"``.
        var_name : str
            Variable name prefix.
        append_axis : int
            Axis index along which to offset.
        offset : int
            Number of existing chunks along the append axis.

        Returns
        -------
        str
            Adjusted chunk key (still in Zarr v2 format — caller
            converts to v3).
        """
        # Extract the index portion after the variable name
        prefix = var_name + "/"
        if not key.startswith(prefix):
            return key

        index_str = key[len(prefix) :]
        indices = index_str.split(".")
        if append_axis < len(indices):
            indices[append_axis] = str(int(indices[append_axis]) + offset)
        return prefix + ".".join(indices)

    def _extend_coord(
        self,
        store,
        coord_name: str,
        data_key: str,
        new_value: str,
        zarray_refs: Dict[str, str],
        zattrs_refs: Dict[str, str],
    ) -> None:
        """Extend a coordinate array with new values for append mode.

        Parameters
        ----------
        store : IcechunkStore
            The Icechunk store.
        coord_name : str
            Coordinate name (e.g. ``"refDate"``).
        data_key : str
            The data chunk key in v2 format (e.g. ``"refDate/0"``).
        new_value : str
            The new inline value (base64-encoded).
        zarray_refs : dict
            Variable name -> .zarray JSON string from the new manifest.
        zattrs_refs : dict
            Variable name -> .zattrs JSON string from the new manifest.
        """
        import numpy as np

        new_bytes = _decode_inline_value(new_value)
        v3_data_key = _chunk_key_v2_to_v3(data_key)

        # Try to read existing coordinate data
        existing_bytes = None
        try:
            existing_bytes = _store_get_sync(store, v3_data_key)
        except Exception:
            pass

        if existing_bytes is not None:
            # Read existing zarr.json to get dtype
            existing_v3_bytes = None
            try:
                existing_v3_bytes = _store_get_sync(store, f"{coord_name}/zarr.json")
            except Exception:
                pass

            dtype = np.float64
            if existing_v3_bytes is not None:
                existing_v3_meta = json.loads(existing_v3_bytes.decode("utf-8"))
                dt_str = existing_v3_meta.get("data_type", "float64")
                dtype_map = {
                    "float32": np.float32,
                    "float64": np.float64,
                    "int32": np.int32,
                    "int64": np.int64,
                }
                dtype = dtype_map.get(dt_str, np.float64)

            # Concatenate existing and new coordinate values
            existing_arr = np.frombuffer(existing_bytes, dtype=dtype)
            new_arr = np.frombuffer(new_bytes, dtype=dtype)
            combined = np.concatenate([existing_arr, new_arr])

            # Write combined data
            _store_set_sync(store, v3_data_key, combined.tobytes())

            # Update zarr.json with new shape
            new_zarray_str = zarray_refs.get(coord_name)
            if new_zarray_str:
                coord_zarray = json.loads(new_zarray_str)
            else:
                # Reconstruct from existing v3 metadata
                coord_zarray = {
                    "shape": [len(combined)],
                    "chunks": [len(combined)],
                    "dtype": "<f8",
                    "fill_value": "NaN",
                    "order": "C",
                    "zarr_format": 2,
                    "compressor": None,
                }

            coord_zarray["shape"] = [len(combined)]
            coord_zarray["chunks"] = [len(combined)]

            zattrs_str = zattrs_refs.get(coord_name)
            v3_array = _make_zarr_v3_array_metadata(json.dumps(coord_zarray), zattrs_str)
            _store_set_sync(
                store,
                f"{coord_name}/zarr.json",
                v3_array.encode("utf-8"),
            )
        else:
            # No existing data — write as-is
            _store_set_sync(store, v3_data_key, new_bytes)
            zarray_str = zarray_refs.get(coord_name)
            zattrs_str = zattrs_refs.get(coord_name)
            if zarray_str:
                v3_array = _make_zarr_v3_array_metadata(zarray_str, zattrs_str)
                _store_set_sync(
                    store,
                    f"{coord_name}/zarr.json",
                    v3_array.encode("utf-8"),
                )

    def commit(self, message: str = "") -> str:
        """Commit the current transaction.

        Parameters
        ----------
        message : str
            Commit message describing the changes.

        Returns
        -------
        str
            The snapshot ID of the committed transaction.

        Raises
        ------
        RuntimeError
            If no session is active (i.e. :meth:`write` has not been
            called).
        """
        if self._session is None:
            raise RuntimeError("No active session. Call write() before commit().")
        snapshot_id = self._session.commit(message)
        return str(snapshot_id)
