# PR #243 — Kerchunk / Icechunk / numcodecs Support

## Overview

This PR adds cloud-native virtual dataset access to grib2io.  GRIB2 files can
now be exposed as Zarr stores — without copying or converting the data — so that
tools like xarray, Dask, and any Zarr-compatible client can read them with
standard array semantics.  Three new optional modules (`kerchunk`, `icechunk`,
`codecs`) implement the full pipeline from reference-manifest generation to
versioned virtual-store persistence.

---

## New Modules

### `grib2io.kerchunk` — Reference Manifest Generator

Scans one or more GRIB2 files and produces a **Kerchunk v1** (Zarr v2) reference
manifest: a JSON/Parquet document that maps Zarr chunk keys to exact byte ranges
(`[uri, offset, length]`) inside the original files.

- Supports all major Data Representation Templates (DRT 0, 2/3, 40/JPEG2000,
  41/PNG).
- Handles bitmap sections (missing-value masking) by storing the section 6 byte
  range alongside section 7 in the manifest.
- Multi-file ingestion: messages from multiple GRIB2 files are merged into a
  single logical dataset, with shared dimensions (refDate, leadTime, level, …)
  resolved across files.
- Per-chunk codec config (`Grib2Codec`) is embedded in `.zarray` metadata so
  readers can decode without knowing GRIB2 internals.
- Manifests serialize to **JSON** (fsspec ReferenceFileSystem) or **Parquet**
  (kerchunk MultiZarrToZarr format).

### `grib2io.icechunk` — Versioned Virtual Store Writer

Takes a Kerchunk v1 manifest and writes it into an **Icechunk** virtual store:
a versioned, cloud-optimised Zarr v3 repository backed by the original GRIB2
bytes.

- Uses zarr's Python API (`group.create_array`) for all metadata so Zarr v3
  `zarr.json` files are written correctly.
- Data variables are created with `Grib2SerializerCodec` as the zarr v3
  serializer, enabling transparent on-the-fly decoding.
- Coordinate arrays (leadTime, refDate, level, …) are written as native Zarr
  arrays.
- **Append mode** (`mode="a"`) extends existing stores along any named
  dimension, enabling incremental NWP archive construction.
- Commit/snapshot model via `IcechunkWriter.commit()` — every write is a
  point-in-time snapshot that can be replayed or rolled back.

### `grib2io.codecs` — Dual-Interface GRIB2 Codec

Provides two codec implementations that share the same underlying C decode path
(`g2clib.unpack7`):

| Class | Interface | Use case |
|---|---|---|
| `Grib2Codec` | `numcodecs.abc.Codec` (Zarr v2) | fsspec / kerchunk reference filesystem |
| `Grib2SerializerCodec` | `zarr.abc.ArrayBytesCodec` (Zarr v3) | Icechunk virtual store |

Both are registered automatically at import time so xarray/zarr discover them
without any manual configuration.  The shared `_decode_grib2_bytes()` helper
keeps the decode logic in one place.

---

## Performance Characteristics

| Property | Impact |
|---|---|
| **Zero data copy** | Virtual chunk refs point at byte ranges in the original GRIB2 files.  No re-encoding or intermediate files. |
| **Minimal reads** | Only the section 7 bytes (and section 6 bitmap when present) for each requested chunk are read.  The rest of the GRIB2 message is never touched. |
| **C decode kernel** | `g2clib.unpack7()` is the same compiled C routine used by `grib2io.open()`. No Python overhead in the inner loop. |
| **Parallel async reads** | Zarr v3's codec pipeline dispatches chunk reads concurrently via `asyncio.gather`.  Scales naturally with Dask or multi-threaded access. |
| **Cloud-native** | Icechunk stores work with S3, GCS, and HTTP object stores.  Byte-range requests mean only needed data is fetched. |
| **Incremental appends** | Appending a new forecast cycle to an existing Icechunk store is O(new chunks) — existing data is never rewritten. |

---

## Optional Dependency Design

All three modules are **opt-in** — the base `grib2io` package continues to work
without `numcodecs`, `kerchunk`, or `icechunk` installed.

- `grib2io.codecs` imports numcodecs lazily; `Grib2Codec` raises `ImportError`
  at instantiation (not at module import) when numcodecs is absent.
- `grib2io.kerchunk` and `grib2io.icechunk` guard their dependencies with
  `_ensure_numcodecs()` / `_ensure_kerchunk()` / `_ensure_icechunk()` that
  raise clear `pip install grib2io[kerchunk]` / `pip install grib2io[icechunk]`
  messages.
- `grib2io.__init__` uses `__getattr__` lazy loading so `import grib2io` never
  touches these modules unless explicitly accessed.

### Install extras

```bash
pip install grib2io[kerchunk]   # numcodecs + kerchunk + fsspec
pip install grib2io[icechunk]   # all of the above + icechunk + zarr
```

---

## CLI Extensions

A new `grib2io kerchunk` sub-command exposes manifest generation from the
command line:

```bash
# Generate a JSON reference manifest
grib2io kerchunk --output refs.json gfs.t00z.pgrb2.1p00.f024

# Write directly to an Icechunk store
grib2io kerchunk --icechunk /path/to/store gfs.t00z.pgrb2.1p00.f024
```

---

## CI / Workflow Changes

- **`build_linux.yml` / `build_macos.yml`**: optional deps installed per Python
  version gate — `numcodecs`+`kerchunk` on Python ≥ 3.11, `icechunk` on
  Python ≥ 3.12.
- **`lint.yml`**: new workflow runs `ruff check` on every push/PR.

---

## Test Coverage

Nine new test modules (≈ 3,000 lines) were added:

| Module | What it tests |
|---|---|
| `test_codec.py` | `Grib2Codec` interface, config round-trip, per-DRT decoding |
| `test_codec_properties.py` | Property-based: codec output == `grib2io._data()` for all DRTs |
| `test_kerchunk.py` | JSON/Parquet serialization, manifest structure |
| `test_kerchunk_properties.py` | Property-based: manifest validity, chunk key uniqueness, multi-file concat |
| `test_icechunk.py` | Write/read-back with xarray, append mode, commit snapshots |
| `test_integration.py` | End-to-end: generate → write → `xr.open_zarr` → compare to direct read |
| `test_imports.py` | ImportError messages when optional deps are absent |
| `test_aero_improvements.py` | Aerosol message improvements |
| `test_cli.py` | CLI sub-commands including `kerchunk` |

All 196 tests pass; 8 skipped (Python-version or missing optional dep).

---

## Python Version Matrix

| Feature | Min Python |
|---|---|
| `grib2io.codecs` (`Grib2Codec`) | 3.9 |
| `grib2io.kerchunk` | **3.11** |
| `grib2io.icechunk` | **3.12** |
