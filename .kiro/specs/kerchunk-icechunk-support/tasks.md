# Implementation Plan: Kerchunk & Icechunk Support for grib2io

## Overview

This plan implements Kerchunk reference manifest generation, a GRIB2 Zarr codec, Icechunk virtual store writing, CLI tooling, and xarray backend extensions for grib2io. Each task builds incrementally — starting with the codec (the foundational decoding layer), then reference generation, serialization, Icechunk writing, xarray integration, CLI, and finally packaging. All new modules use lazy imports so core grib2io remains unaffected when optional dependencies are absent.

## Tasks

- [x] 1. Implement the Grib2Codec (`src/grib2io/codecs.py`)
  - [x] 1.1 Create `src/grib2io/codecs.py` with the `Grib2Codec` class implementing `numcodecs.abc.Codec`
    - Implement `__init__` accepting all DRT/GDT/grid/bitmap parameters as JSON-serializable values
    - Set `codec_id = "grib2io"`
    - Implement `encode()` raising `NotImplementedError` with message `"Grib2Codec is decode-only; GRIB2 encoding is handled by grib2io.open()"`
    - Implement `decode(buf, out=None)` that unpacks raw section 7 bytes using `g2clib.unpack7()` with stored DRT/GDT parameters, applies bitmap masking (NaN fill) when `bitmap_flag` is 0 or 254, and returns a NumPy array
    - Implement `get_config()` returning a JSON-serializable dict of all codec parameters
    - Implement `from_config(cls, config)` classmethod to reconstruct the codec from a config dict
    - Call `register_codec(Grib2Codec)` at module level
    - Add `_ensure_numcodecs()` lazy import guard that raises `ImportError` with install instructions
    - _Requirements: 3.1, 3.2, 3.7, 3.8, 8.4_

  - [x] 1.2 Write property test for codec decode equivalence (Property 5)
    - **Property 5: Codec Decode Equivalence**
    - Use real GRIB2 test files from `tests/input_data/` covering DRT types 0, 2, 3, 40, 41
    - For each message, extract raw section 7 bytes and build codec config from index metadata
    - Decode via `Grib2Codec.decode()` and compare to `grib2io._data()` output within floating-point tolerance
    - Verify NaN placement matches at bitmap-masked grid points
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9**

  - [x] 1.3 Write unit tests for codec interface compliance and per-DRT decoding
    - Verify `Grib2Codec` is a `numcodecs.abc.Codec` subclass with `codec_id` attribute
    - Test `get_config()` / `from_config()` round-trip produces equivalent codec
    - Test `encode()` raises `NotImplementedError`
    - Test one example per DRT type (0, 2/3, 40, 41) using real test files
    - Test bitmap handling with `blend.t00z.core.f001.co_4x_reduce.grib2`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 3.9_

- [x] 2. Checkpoint — Ensure codec tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement the ReferenceGenerator (`src/grib2io/kerchunk.py`)
  - [x] 3.1 Create `src/grib2io/kerchunk.py` with the `ReferenceGenerator` class and internal helpers
    - Implement `__init__(file_paths, filters=None)` that accepts single or multiple GRIB2 file paths and optional message filters; call `_ensure_kerchunk()` lazy import guard
    - Implement `generate()` that scans each file via `build_index()` and `msgs_from_index()`, groups messages by variable using dimension mapping logic (same approach as `parse_grib_index()` in xarray_backend), and produces a Kerchunk v1 reference manifest dict
    - Implement helper `_build_chunk_key(var_name, dim_indices)` to construct Zarr chunk keys like `"TMP/0.0.0"`
    - Implement helper `_build_zarray_metadata(msg, shape, chunks, codec_config)` to build `.zarray` JSON including `Grib2Codec` as the compressor
    - Implement helper `_build_zattrs(msg)` to extract GRIB2 section metadata (discipline, parameterCategory, parameterNumber, typeOfFirstFixedSurface, valueOfFirstFixedSurface, refDate, leadTime) as Zarr attributes with `_ARRAY_DIMENSIONS`
    - Implement helper `_map_messages_to_dimensions(msgs, index)` to group messages by variable and map to dimension indices (level, leadTime, refDate, perturbationNumber, etc.)
    - For messages with bitmap (flag 0 or 254), include bitmap offset/length in codec config and optionally as companion reference keys
    - Populate `.zgroup` with `{"zarr_format": 2}`
    - Populate coordinate arrays (level, leadTime, etc.) as inline base64-encoded refs
    - Handle multi-file inputs by tracking source file URIs per chunk reference
    - Raise `FileNotFoundError` for inaccessible files, `ValueError` for malformed files
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3, 5.4_

  - [x] 3.2 Write property test for manifest structural validity (Property 1)
    - **Property 1: Manifest Structural Validity**
    - Generate mock index dicts with varying numbers of messages, variables, DRT types, and bitmap flags
    - Verify manifest has `"version": 1` and `"refs"` key
    - Verify each variable has `.zarray` with required fields (chunks, dtype, fill_value, shape, compressor, order)
    - Verify each variable has `.zattrs` with required fields (_ARRAY_DIMENSIONS, discipline, parameterCategory, parameterNumber, typeOfFirstFixedSurface, valueOfFirstFixedSurface, refDate, leadTime)
    - Verify bitmap messages have non-null bitmap_offset and bitmap_length in codec config
    - **Validates: Requirements 1.1, 1.4, 1.5, 1.6**

  - [x] 3.3 Write property test for chunk key uniqueness and determinism (Property 2)
    - **Property 2: Chunk Key Uniqueness and Determinism**
    - Generate sets of messages with random but distinct (shortName, valueOfFirstFixedSurface, leadTime, refDate, perturbationNumber) tuples
    - Verify all chunk keys are unique
    - Verify same input always produces same chunk keys (run twice, compare)
    - **Validates: Requirements 1.2**

  - [x] 3.4 Write property test for multi-dimensional hierarchy correctness (Property 3)
    - **Property 3: Multi-Dimensional Hierarchy Correctness**
    - Generate indexes with varying dimension cardinalities
    - Verify `.zarray` shape reflects actual number of unique values along each dimension
    - Verify total number of data chunk keys equals product of dimension sizes
    - **Validates: Requirements 1.3**

  - [x] 3.5 Write property test for multi-file source correctness (Property 6)
    - **Property 6: Multi-File Reference Source Correctness**
    - Generate multi-file scenarios with mock indexes
    - Verify each chunk ref `[uri, offset, length]` points to the correct source file URI
    - **Validates: Requirements 5.1, 5.4**

  - [x] 3.6 Write property test for multi-file dimension concatenation (Property 7)
    - **Property 7: Multi-File Dimension Concatenation**
    - Generate multi-file scenarios with same variable at different times
    - Verify concatenated dimension size equals total unique values across all files
    - Verify `.zarray` shape reflects concatenated dimension
    - **Validates: Requirements 5.2**

- [x] 4. Implement serialization methods (JSON and Parquet)
  - [x] 4.1 Add `to_json(output_path)` method to `ReferenceGenerator`
    - Serialize the manifest dict to a JSON file using `json.dumps`
    - Ensure output is compatible with `fsspec.filesystem("reference")`
    - _Requirements: 2.1, 2.4_

  - [x] 4.2 Add `to_parquet(output_path)` method to `ReferenceGenerator`
    - Serialize the manifest to Parquet using `kerchunk.df.refs_to_dataframe`
    - Ensure output is compatible with `fsspec` reference filesystem
    - _Requirements: 2.2, 2.4_

  - [x] 4.3 Write property test for JSON serialization round-trip (Property 4)
    - **Property 4: JSON Serialization Round-Trip**
    - Generate manifest dicts, serialize to JSON, load back via `fsspec.filesystem("reference")`
    - Verify loaded manifest produces identical Zarr store keys and structurally equivalent metadata
    - **Validates: Requirements 2.3**

  - [x] 4.4 Write unit tests for JSON and Parquet serialization
    - Test JSON output with a known manifest, verify file contents parse correctly
    - Test Parquet output, verify structure is valid
    - Test error handling for inaccessible output paths
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 5. Checkpoint — Ensure reference generation and serialization tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement the IcechunkWriter (`src/grib2io/icechunk.py`)
  - [x] 6.1 Create `src/grib2io/icechunk.py` with the `IcechunkWriter` class
    - Implement `__init__(store_path, storage_config=None)` with `_ensure_icechunk()` lazy import guard
    - Implement `write(manifest, mode='w', append_dim=None)` that iterates the manifest, calls `store.set_virtual_ref()` for each data chunk, writes Zarr metadata as native Icechunk metadata, and handles append mode for multi-file concatenation along `append_dim`
    - Implement `commit(message='')` that commits the transaction and returns the snapshot ID
    - Raise `ImportError` with install instructions when icechunk is not installed
    - _Requirements: 4.1, 4.2, 4.4, 4.5_

  - [x] 6.2 Write unit tests for IcechunkWriter
    - Test write manifest to local Icechunk store, read back with xarray and verify dataset structure
    - Test multi-file append: write two manifests, verify concatenated dataset
    - Test commit returns a snapshot ID string
    - Test `ImportError` when icechunk is not installed (mock import)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 7. Extend the xarray backend for reference and Icechunk format detection
  - [x] 7.1 Add format detection and dispatch to `GribBackendEntrypoint.open_dataset()`
    - Implement `_is_kerchunk_reference(filename_or_obj)` — detect JSON (file ends with `.json`, contains `"version"` key) and Parquet (directory with `.zmetadata` and `refs.*.parq` files)
    - Implement `_is_icechunk_store(filename_or_obj)` — detect Icechunk URI schemes or `IcechunkStore` instances
    - Implement `_open_from_reference(filename_or_obj, ...)` — open via `fsspec.filesystem("reference")` and return xarray Dataset with same coordinate/dimension conventions
    - Implement `_open_from_icechunk(filename_or_obj, ...)` — open via Icechunk Zarr interface
    - Apply `data_model` support (e.g., `"nws-viz"`) to reference-backed datasets
    - Call `_ensure_kerchunk()` / `_ensure_icechunk()` guards as appropriate
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 7.2 Write unit tests for xarray backend format detection and dispatch
    - Test detection of JSON reference files, Parquet reference directories, Icechunk stores, and plain GRIB2 files
    - Test `ImportError` raised when kerchunk not installed and reference file provided
    - Test that reference-backed datasets have same variables, dimensions, and attributes as direct GRIB2 reads
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 8. Checkpoint — Ensure Icechunk and xarray backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement the CLI entry point (`src/grib2io/cli.py`)
  - [x] 9.1 Create `src/grib2io/cli.py` with `main()` and `kerchunk_cli()` functions
    - Implement `main()` as the top-level CLI dispatcher using `argparse`
    - Implement `kerchunk` subcommand accepting: one or more GRIB2 file paths, `--output-format` (json or parquet, default json), `--output` (output path), `--filters` (key=value pairs)
    - Call `ReferenceGenerator` with provided files and filters, then serialize to the requested format
    - Print usage message and exit with code 2 when no files provided
    - Print error message and exit with code 2 for invalid `--output-format` or `--filters` syntax
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 9.2 Write unit tests for CLI
    - Test `grib2io kerchunk` with a real GRIB2 test file, verify JSON output is created
    - Test `--output-format parquet` option
    - Test `--filters` option with key=value pairs
    - Test error cases: no files, invalid format, invalid filter syntax
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 10. Update `pyproject.toml` and package configuration
  - [x] 10.1 Add optional dependency groups and entry points to `pyproject.toml`
    - Add `[project.optional-dependencies]` groups: `kerchunk = ["kerchunk", "numcodecs"]` and `icechunk = ["icechunk"]`
    - Add `[project.scripts]` entry: `grib2io = "grib2io.cli:main"`
    - Add `grib2io.codecs` and `grib2io.kerchunk` and `grib2io.icechunk` and `grib2io.cli` to `[tool.setuptools] packages`
    - _Requirements: 8.1, 8.2_

  - [x] 10.2 Update `src/grib2io/__init__.py` to expose new public API
    - Add lazy imports for `kerchunk`, `codecs`, `icechunk` modules (only imported when accessed, not at package import time)
    - Ensure core grib2io functionality is unaffected when optional deps are absent
    - _Requirements: 8.3, 8.4_

  - [x] 10.3 Write unit tests for optional dependency isolation
    - Mock missing `kerchunk`, `numcodecs`, and `icechunk` packages
    - Verify core `grib2io.open()`, `Grib2Message`, and xarray backend for direct GRIB2 files work without errors
    - Verify `ImportError` with correct install instructions raised when accessing kerchunk/icechunk features
    - _Requirements: 8.3, 8.4_

- [x] 11. Integration wiring and end-to-end tests
  - [x] 11.1 Write end-to-end integration tests
    - Test Kerchunk pipeline: generate refs from real GRIB2 file → serialize to JSON → open with `fsspec` → read data → compare to direct `grib2io.open()` read
    - Test Icechunk pipeline: generate refs → write to Icechunk → open with `xarray.open_zarr()` → compare to direct grib2io read
    - Test multi-file pipeline: generate refs from multiple test files → combine → verify unified dataset dimensions and data
    - Test CLI pipeline: run CLI on test files → verify output files → open and validate
    - _Requirements: 1.1, 2.3, 3.9, 4.3, 5.1, 5.2, 6.1, 6.3_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All new modules (`codecs.py`, `kerchunk.py`, `icechunk.py`, `cli.py`) use lazy imports for optional dependencies so core grib2io is never affected
- The implementation language is Python, matching the existing codebase and design document
