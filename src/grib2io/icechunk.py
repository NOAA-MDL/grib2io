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

        # Build authorize_virtual_chunk_access mapping with appropriate credentials.
        # icechunk.containers_credentials() validates and returns the {prefix: cred} dict
        # in the format expected by Repository.open_or_create/open.
        # None values (local file:// prefixes) are valid — they authorize local access
        # without credentials. Do NOT filter them out.
        raw_authorize = {prefix: self._make_credentials_for_prefix(prefix) for prefix in virtual_prefixes}
        authorize = icechunk.containers_credentials(raw_authorize) if raw_authorize else None

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

    def _make_credentials_for_prefix(self, prefix: str):
        """Return appropriate Icechunk credentials for a virtual chunk URI prefix.

        Parameters
        ----------
        prefix : str
            URI prefix like ``s3://bucket/prefix/``, ``file:///path/``, etc.

        Returns
        -------
        Credentials or ``None``
            Anonymous credentials for public S3/GCS; ``None`` for local files.
        """
        import icechunk  # local import — only used inside the class

        if prefix.startswith("s3://"):
            return icechunk.s3_anonymous_credentials()
        elif prefix.startswith("gs://") or prefix.startswith("gcs://"):
            return icechunk.gcs_credentials(anon=True)
        else:
            # Local filesystem or other — no credentials needed
            return None

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
        """Write all refs to a fresh store using zarr's Python API.

        Creates the root group and all arrays via ``zarr.open_group`` /
        ``group.create_array`` so that Zarr v3 metadata is stored through
        the proper path that icechunk and zarr recognise.  Coordinate
        (inline) data is written via the zarr Array write API, and virtual
        chunk refs for data variables are registered with
        ``store.set_virtual_ref``.

        Parameters
        ----------
        refs : dict
            The ``"refs"`` dict from the manifest.
        store : IcechunkStore
            The Icechunk store to write to.
        """
        import numpy as np
        import zarr

        # Collect all metadata by variable
        zarray_refs: Dict[str, str] = {}  # var_name -> .zarray JSON str
        zattrs_refs: Dict[str, str] = {}  # var_name -> .zattrs JSON str
        data_refs: Dict[str, Any] = {}  # chunk key -> [uri, offset, len]
        inline_data_refs: Dict[str, str] = {}  # chunk key -> inline value

        for key, value in refs.items():
            if key == ".zgroup":
                pass  # zarr.open_group handles the root group metadata
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
                pass  # skip other metadata keys
            else:
                _logger.warning(
                    "Skipping unrecognized manifest entry: %s = %r",
                    key,
                    value,
                )

        # Create root group and all arrays via zarr's Python API so that
        # metadata is stored in the location that zarr/icechunk actually
        # reads, rather than as raw chunk bytes at the zarr.json key.
        root = zarr.open_group(store, mode="w", zarr_format=3)

        # Identify which variables have virtual (data) refs — those need
        # Grib2SerializerCodec as their zarr v3 serializer.
        data_var_names: set = {key.split("/")[0] for key in data_refs}

        # Import the zarr v3 serializer codec (registered at import time)
        from grib2io.codecs import Grib2SerializerCodec as _Grib2Ser

        for var_name, zarray_str in zarray_refs.items():
            v2_zarray = json.loads(zarray_str)
            zattrs_str = zattrs_refs.get(var_name)
            v2_zattrs = json.loads(zattrs_str) if zattrs_str else {}

            shape = v2_zarray["shape"]
            chunks = [max(1, c) for c in v2_zarray.get("chunks", shape)]
            dtype_str = v2_zarray.get("dtype", "<f4")
            fill_value = v2_zarray.get("fill_value", None)
            dim_names = v2_zattrs.get("_ARRAY_DIMENSIONS", [])

            dtype = np.dtype(dtype_str)
            if fill_value == "NaN" or fill_value is None:
                fv: Any = float("nan") if np.issubdtype(dtype, np.floating) else 0
            else:
                fv = fill_value

            if var_name in data_var_names:
                # Data variable — use Grib2SerializerCodec so zarr v3 can
                # decode the raw GRIB2 section 7 bytes from virtual chunks.
                # The manifest stores the codec config in filters[0]
                # (compressor is null); fall back to compressor for older manifests.
                filters_list = v2_zarray.get("filters", []) or []
                codec_src = filters_list[0] if filters_list else (v2_zarray.get("compressor") or {})
                codec_cfg = {k: v for k, v in codec_src.items() if k != "id"}
                serializer = _Grib2Ser(**codec_cfg)
                root.create_array(
                    var_name,
                    shape=shape,
                    chunks=chunks,
                    dtype=dtype,
                    fill_value=fv,
                    serializer=serializer,
                    compressors=[],
                    filters=[],
                    dimension_names=dim_names if dim_names else None,
                    attributes=v2_zattrs if v2_zattrs else None,
                )
            else:
                # Coordinate array — plain bytes serializer (default)
                root.create_array(
                    var_name,
                    shape=shape,
                    chunks=chunks,
                    dtype=dtype,
                    fill_value=fv,
                    dimension_names=dim_names if dim_names else None,
                    attributes=v2_zattrs if v2_zattrs else None,
                )

        # Write coordinate (inline) data via zarr's Array write API so
        # that encoding goes through the proper codec pipeline.
        for key, value in inline_data_refs.items():
            parts = key.split("/")
            var_name = parts[0]
            if var_name not in zarray_refs:
                _logger.warning("Inline data for unknown variable %s, skipping", var_name)
                continue

            raw_bytes = _decode_inline_value(value)
            v2_zarray = json.loads(zarray_refs[var_name])
            dtype = np.dtype(v2_zarray["dtype"])
            shape = v2_zarray["shape"]
            coord_values = np.frombuffer(raw_bytes, dtype=dtype).reshape(shape)
            root[var_name][...] = coord_values

        # Write virtual chunk references for data arrays (unchanged path)
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

        Opens the existing zarr group and uses zarr's Python API to resize
        arrays and write new coordinate data, ensuring metadata is stored
        correctly.

        Parameters
        ----------
        refs : dict
            The ``"refs"`` dict from the new manifest.
        store : IcechunkStore
            The Icechunk store to append to.
        append_dim : str
            Dimension name along which to append.
        """
        import numpy as np
        import zarr

        # Separate refs by type
        zarray_refs: Dict[str, str] = {}
        zattrs_refs: Dict[str, str] = {}
        data_refs: Dict[str, Any] = {}
        inline_refs: Dict[str, str] = {}

        for key, value in refs.items():
            if key in {".zgroup"}:
                pass
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

        # Open the existing group via zarr API
        root = zarr.open_group(store, mode="r+", zarr_format=3)

        # Group data refs by variable
        var_data_refs: Dict[str, Dict[str, list]] = {}
        for key, value in data_refs.items():
            var_name = key.split("/")[0]
            var_data_refs.setdefault(var_name, {})[key] = value

        # Extend each data variable and register new virtual refs
        for var_name, chunk_refs in var_data_refs.items():
            new_zarray_str = zarray_refs.get(var_name)
            if new_zarray_str is None:
                continue

            new_zarray = json.loads(new_zarray_str)
            new_shape_per_append = new_zarray["shape"]

            # Determine append axis from dimension labels
            new_zattrs_str = zattrs_refs.get(var_name)
            dim_labels: list = []
            if new_zattrs_str:
                dim_labels = json.loads(new_zattrs_str).get("_ARRAY_DIMENSIONS", [])

            append_axis = dim_labels.index(append_dim) if append_dim in dim_labels else None

            if var_name in root and append_axis is not None:
                zarr_arr = root[var_name]
                existing_shape = list(zarr_arr.shape)
                offset = existing_shape[append_axis]

                # Resize array along append axis
                new_size = existing_shape[append_axis] + new_shape_per_append[append_axis]
                new_shape_full = list(existing_shape)
                new_shape_full[append_axis] = new_size
                zarr_arr.resize(new_shape_full)
            else:
                offset = 0

            # Write virtual refs with adjusted chunk indices
            for key, value in chunk_refs.items():
                uri, chunk_offset, length = value
                if append_axis is not None and offset > 0:
                    adjusted_key = self._adjust_chunk_key(key, var_name, append_axis, offset)
                else:
                    adjusted_key = key
                v3_key = _chunk_key_v2_to_v3(adjusted_key)
                store.set_virtual_ref(
                    v3_key,
                    uri,
                    offset=int(chunk_offset),
                    length=int(length),
                    validate_container=True,
                )

        # Handle coordinate arrays
        for key, inline_value in inline_refs.items():
            coord_name = key.split("/")[0] if "/" in key else None
            if coord_name is None:
                continue

            raw_bytes = _decode_inline_value(inline_value)
            new_zarray_str = zarray_refs.get(coord_name)
            if new_zarray_str is None:
                continue
            dtype = np.dtype(json.loads(new_zarray_str)["dtype"])
            new_values = np.frombuffer(raw_bytes, dtype=dtype)

            if coord_name == append_dim and coord_name in root:
                # Concatenate with existing coordinate values
                existing_arr = root[coord_name][...]
                combined = np.concatenate([existing_arr, new_values])
                root[coord_name].resize(len(combined))
                root[coord_name][...] = combined
            elif coord_name not in root:
                # Create new coordinate array via zarr API
                v2_zattrs = json.loads(zattrs_refs[coord_name]) if coord_name in zattrs_refs else {}
                dim_names = v2_zattrs.get("_ARRAY_DIMENSIONS", [])
                shape = [len(new_values)]
                root.create_array(
                    coord_name,
                    shape=shape,
                    chunks=shape,
                    dtype=dtype,
                    fill_value=0,
                    dimension_names=dim_names if dim_names else None,
                    attributes=v2_zattrs if v2_zattrs else None,
                )
                root[coord_name][...] = new_values
            # else: coordinate already exists and isn't the append dim — leave as-is

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

    def get_readonly_session(self):
        """Return a read-only Icechunk session for data access after committing.

        Uses the same repository object (and therefore the same virtual chunk
        credentials) that were set up during :meth:`write`.  Call this after
        :meth:`commit` to open the store with ``xarray.open_zarr``.

        Returns
        -------
        icechunk.Session
            A read-only session on the ``"main"`` branch.

        Raises
        ------
        RuntimeError
            If :meth:`write` has not been called yet.

        Example
        -------
        >>> session = writer.get_readonly_session()
        >>> ds = xr.open_zarr(session.store, consolidated=False)
        """
        if self._repo is None:
            raise RuntimeError("No repository open. Call write() before get_readonly_session().")
        return self._repo.readonly_session("main")


def open_dataset(manifest: dict, store_path: str | None = None, **xr_kwargs):
    """Open a grib2io kerchunk manifest as an :class:`xarray.Dataset`.

    Writes the manifest into a temporary (or caller-supplied) Icechunk virtual
    store and immediately opens it with :func:`xarray.open_zarr`.  Works for
    manifests whose chunk data lives locally **or** on remote object stores
    (S3, GCS, …) — credentials are resolved automatically from the virtual
    chunk URI prefixes embedded in the manifest.

    Parameters
    ----------
    manifest:
        A kerchunk v1 reference manifest dict, as produced by
        :meth:`grib2io.kerchunk.ReferenceGenerator.generate`.
    store_path:
        Filesystem path for the Icechunk repository.  A temporary directory is
        created and used when omitted (suitable for ephemeral/notebook use).
    **xr_kwargs:
        Additional keyword arguments forwarded to :func:`xarray.open_zarr`
        (e.g. ``chunks={}`` to enable Dask lazy loading).

    Returns
    -------
    xarray.Dataset

    Examples
    --------
    Remote S3 data (anonymous access resolved automatically):

    >>> from grib2io.icechunk import open_dataset
    >>> ds = open_dataset(manifest)
    >>> ds.TMP.isel(valid_time=0, isobaric_surface=0).compute()

    Local data with a persistent store:

    >>> ds = open_dataset(manifest, store_path="/tmp/my_grib2_store")
    """
    import tempfile
    import xarray as xr

    if store_path is None:
        store_path = tempfile.mkdtemp(prefix="grib2io_icechunk_")

    writer = IcechunkWriter(store_path)
    writer.write(manifest)
    writer.commit("grib2io kerchunk manifest")
    session = writer.get_readonly_session()
    xr_kwargs.setdefault("consolidated", False)
    return xr.open_zarr(session.store, **xr_kwargs)


def open_grib2(
    url: str,
    storage_options: dict | None = None,
    filters: dict | None = None,
    store_path: str | None = None,
    **xr_kwargs,
):
    """Open a GRIB2 file as an :class:`xarray.Dataset` via a virtual Icechunk store.

    One-call interface that combines manifest generation and dataset opening:

    1. Builds a kerchunk reference manifest from *url* (local path or remote
       object-store URI) using :class:`~grib2io.kerchunk.ReferenceGenerator`.
    2. Passes the manifest to :func:`open_dataset`, which writes it into a
       temporary Icechunk virtual store and opens it with
       :func:`xarray.open_zarr`.

    Cloud credentials are resolved automatically from the URI prefix.  For
    anonymous public S3 buckets, pass ``storage_options={"anon": True}``.

    For remote files, grib2io automatically uses a ``.idx`` sidecar file
    (e.g. ``url + ".idx"``) when available to skip streaming the large data
    payloads and read only message header bytes.  Combining this with
    ``filters`` to restrict which GRIB2 messages are indexed makes manifest
    generation near-instant even for multi-gigabyte files.

    Parameters
    ----------
    url:
        Path or URI to a GRIB2 file, e.g.
        ``"s3://noaa-gfs-bdp-pds/gfs.20240501/00/atmos/gfs.t00z.pgrb2.0p25.f000"``
        or a local path like ``"/data/gfs.t00z.pgrb2.1p00.f024"``.
    storage_options:
        fsspec storage options forwarded to
        :class:`~grib2io.kerchunk.ReferenceGenerator`, e.g.
        ``{"anon": True}`` for public S3 buckets.
    filters:
        Optional dict of ``Grib2Message`` attribute filters passed to
        :class:`~grib2io.kerchunk.ReferenceGenerator`.  Only messages
        matching all key/value pairs are included in the manifest.  Use this
        to restrict the dataset to specific variables and dramatically reduce
        manifest-generation time for large files.  For example, to extract
        only 2-metre temperature::

            filters={"shortName": "TMP", "typeOfFirstFixedSurface": 103, "level": 2}
    store_path:
        Filesystem path for the Icechunk repository.  A temporary directory is
        created and used when omitted.
    **xr_kwargs:
        Additional keyword arguments forwarded to :func:`xarray.open_zarr`.

    Returns
    -------
    xarray.Dataset

    Examples
    --------
    Public S3 bucket (anonymous access):

    >>> from grib2io.icechunk import open_grib2
    >>> ds = open_grib2(
    ...     "s3://noaa-gfs-bdp-pds/gfs.20240501/00/atmos/gfs.t00z.pgrb2.0p25.f000",
    ...     storage_options={"anon": True},
    ... )
    >>> ds.TMP.isel(valid_time=0, isobaric_surface=0).compute()

    Filter to a single variable (much faster for large files):

    >>> ds = open_grib2(
    ...     "s3://noaa-gfs-bdp-pds/gfs.20240501/00/atmos/gfs.t00z.pgrb2.0p25.f000",
    ...     storage_options={"anon": True},
    ...     filters={"shortName": "TMP", "typeOfFirstFixedSurface": 103, "level": 2},
    ... )

    Local file:

    >>> ds = open_grib2("/data/gfs.t00z.pgrb2.1p00.f024")
    """
    from grib2io.kerchunk import ReferenceGenerator

    gen = ReferenceGenerator(url, filters=filters, storage_options=storage_options or {})
    manifest = gen.generate()
    return open_dataset(manifest, store_path=store_path, **xr_kwargs)
