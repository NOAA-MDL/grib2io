# Requirements Document

## Introduction

This feature enables grib2io to produce Kerchunk-compatible reference manifests and Icechunk-compatible stores from GRIB2 files. Kerchunk creates lightweight JSON or Parquet reference files that describe byte ranges within existing GRIB2 files, allowing them to be read as virtual Zarr stores without data duplication. Icechunk is a transactional storage engine for Zarr v3 that can ingest these references into a versioned, cloud-native store. Together, they allow grib2io users to access GRIB2 data through the Zarr protocol with lazy, chunk-level reads — bridging the gap between legacy GRIB2 archives and modern cloud-native analysis workflows.

## Glossary

- **Reference_Generator**: The grib2io component that scans a GRIB2 file's index and produces a Kerchunk-compatible reference manifest describing byte ranges for each GRIB2 message's data section.
- **Reference_Manifest**: A dictionary (or serialized JSON/Parquet file) conforming to the Kerchunk reference specification (version 1), mapping Zarr chunk keys to `[url, offset, length]` tuples within the original GRIB2 file.
- **Icechunk_Writer**: The grib2io component that writes a Reference_Manifest into an Icechunk virtual store, creating a transactional, versioned Zarr v3 dataset backed by the original GRIB2 file bytes.
- **Virtual_Store**: A Zarr-compatible store that does not copy data but instead references byte ranges in one or more existing GRIB2 files.
- **Chunk_Key**: A Zarr-style key string (e.g., `"TMP/0.0.0"`) that identifies a single chunk within a Zarr store hierarchy.
- **grib2io_Index**: The dictionary returned by `build_index()` containing section arrays, byte offsets, section offsets, section sizes, and message metadata for all GRIB2 messages in a file.
- **Codec_Pipeline**: The sequence of decompression and decoding steps (e.g., JPEG2000, PNG, AEC, complex packing) required to transform raw GRIB2 section 7 bytes into a NumPy array.
- **GRIB2_Message**: A single GRIB2 record consisting of sections 0 through 8, representing one field on one grid at one time.
- **Zarr_Metadata**: The `.zarray`, `.zattrs`, and `.zgroup` JSON metadata files that describe the structure, data types, dimensions, and attributes of a Zarr store.

## Requirements

### Requirement 1: Generate Kerchunk Reference Manifest from a GRIB2 File

**User Story:** As a data engineer, I want to generate a Kerchunk reference manifest from a GRIB2 file using grib2io, so that I can access the GRIB2 data as a virtual Zarr store without duplicating the data.

#### Acceptance Criteria

1. WHEN a GRIB2 file path is provided, THE Reference_Generator SHALL scan the file using `build_index()` and produce a Reference_Manifest dictionary conforming to Kerchunk reference spec version 1.
2. THE Reference_Generator SHALL map each GRIB2_Message data section to a Chunk_Key using the message's variable short name, dimension indices, and grid shape derived from the grib2io_Index.
3. WHEN a GRIB2 file contains multiple variables, lead times, levels, or ensemble members, THE Reference_Generator SHALL organize Chunk_Keys into a multi-dimensional Zarr hierarchy reflecting those dimensions.
4. THE Reference_Generator SHALL populate Zarr_Metadata (`.zarray`, `.zattrs`, `.zgroup`) for each variable, including data type, chunk shape, fill value, dimension names, and coordinate arrays.
5. WHEN a GRIB2_Message uses a bitmap (bitmap flag 0 or 254), THE Reference_Generator SHALL record the bitmap section offset and length alongside the data section reference so that the Codec_Pipeline can apply the bitmap during decoding.
6. THE Reference_Generator SHALL include GRIB2 section metadata (discipline, parameter category, parameter number, level type, level value, reference time, lead time) as Zarr_Metadata attributes on each variable.

### Requirement 2: Serialize Reference Manifest to JSON and Parquet

**User Story:** As a data engineer, I want to save the reference manifest to JSON or Parquet format, so that I can store and share lightweight reference files alongside the original GRIB2 data.

#### Acceptance Criteria

1. WHEN the user requests JSON output, THE Reference_Generator SHALL serialize the Reference_Manifest to a JSON file compatible with `fsspec.filesystem("reference")`.
2. WHEN the user requests Parquet output, THE Reference_Generator SHALL serialize the Reference_Manifest to a Parquet file compatible with `kerchunk.utils.refs_to_dataframe` and `fsspec` reference filesystem.
3. WHEN a Reference_Manifest is serialized and then loaded back via `fsspec`, THE loaded manifest SHALL produce an identical Zarr store structure (round-trip property).
4. IF the GRIB2 file path is not accessible or the file is malformed, THEN THE Reference_Generator SHALL raise a descriptive error indicating the file path and the nature of the failure.

### Requirement 3: Register a GRIB2 Codec for Zarr

**User Story:** As a developer, I want a Zarr-compatible codec that can decode raw GRIB2 section bytes into NumPy arrays, so that Zarr reads through the reference manifest produce correct data values.

#### Acceptance Criteria

1. THE Codec_Pipeline SHALL implement the `numcodecs.abc.Codec` interface so that Zarr can use the codec to decode GRIB2 data chunks on read.
2. WHEN a raw GRIB2 section 7 byte buffer and associated section metadata are provided, THE Codec_Pipeline SHALL decode the buffer into a NumPy array matching the output of `grib2io._data()` for the same message.
3. WHEN a GRIB2_Message uses JPEG2000 compression (DRT 40), THE Codec_Pipeline SHALL decode the data correctly.
4. WHEN a GRIB2_Message uses PNG compression (DRT 41), THE Codec_Pipeline SHALL decode the data correctly.
5. WHEN a GRIB2_Message uses AEC/CCSDS compression (DRT 42), THE Codec_Pipeline SHALL decode the data correctly.
6. WHEN a GRIB2_Message uses complex packing (DRT 2 or 3), THE Codec_Pipeline SHALL decode the data correctly.
7. WHEN a GRIB2_Message uses simple packing (DRT 0), THE Codec_Pipeline SHALL decode the data correctly.
8. WHEN a bitmap is present, THE Codec_Pipeline SHALL apply the bitmap and fill masked grid points with NaN.
9. FOR ALL supported Data Representation Template numbers, decoding a GRIB2 chunk through the Codec_Pipeline SHALL produce an array equal to the array produced by reading the same message via `grib2io.open()` and accessing its data (round-trip equivalence property).

### Requirement 4: Write References to an Icechunk Virtual Store

**User Story:** As a cloud data engineer, I want to write grib2io reference manifests into an Icechunk store, so that I can create versioned, transactional Zarr v3 datasets backed by existing GRIB2 files.

#### Acceptance Criteria

1. WHEN a Reference_Manifest and an Icechunk store path are provided, THE Icechunk_Writer SHALL create a Zarr v3 virtual store with virtual chunk references pointing to byte ranges in the original GRIB2 file.
2. THE Icechunk_Writer SHALL write all Zarr_Metadata (array metadata, group attributes, dimension coordinates) into the Icechunk store.
3. WHEN the Icechunk store is opened with `xarray.open_zarr()`, THE resulting Dataset SHALL contain the same variables, dimensions, coordinates, and attributes as a Dataset produced by `xarray.open_dataset(engine="grib2io")` for the same GRIB2 file.
4. WHEN multiple GRIB2 files are provided, THE Icechunk_Writer SHALL append or concatenate references into a single Icechunk store along the appropriate dimension (e.g., time or lead time).
5. IF the Icechunk library is not installed, THEN THE Icechunk_Writer SHALL raise an ImportError with a message indicating the required package and installation instructions.

### Requirement 5: Support Multi-File Reference Generation

**User Story:** As a data engineer, I want to generate a single reference manifest from multiple GRIB2 files, so that I can create a unified virtual dataset spanning multiple forecast cycles or time steps.

#### Acceptance Criteria

1. WHEN a list of GRIB2 file paths is provided, THE Reference_Generator SHALL scan each file and produce a single combined Reference_Manifest with Chunk_Keys referencing the correct source file for each chunk.
2. WHEN multiple files contain the same variable on the same grid but at different times or lead times, THE Reference_Generator SHALL concatenate them along the appropriate dimension in the combined Reference_Manifest.
3. IF any file in the list is not accessible or malformed, THEN THE Reference_Generator SHALL raise a descriptive error identifying the problematic file.
4. THE combined Reference_Manifest SHALL produce a valid Zarr store where each chunk reference includes the correct source file URI, byte offset, and byte length.

### Requirement 6: Integrate with the Existing Xarray Backend

**User Story:** As a scientist, I want to open a Kerchunk reference file or Icechunk store using the grib2io xarray backend, so that I can use familiar xarray workflows on virtualized GRIB2 data.

#### Acceptance Criteria

1. WHEN a Kerchunk JSON or Parquet reference file path is provided to `xarray.open_dataset()` with `engine="grib2io"`, THE GribBackendEntrypoint SHALL detect the reference format and open the data through the `fsspec` reference filesystem.
2. WHEN an Icechunk store URI is provided to `xarray.open_dataset()` with `engine="grib2io"`, THE GribBackendEntrypoint SHALL detect the Icechunk store and open the data through the Icechunk Zarr interface.
3. THE GribBackendEntrypoint SHALL apply the same coordinate, dimension, and attribute conventions (including `data_model` support) when reading from reference files as when reading directly from GRIB2 files.
4. IF the `kerchunk` package is not installed and a reference file is provided, THEN THE GribBackendEntrypoint SHALL raise an ImportError with a message indicating the required package and installation instructions.

### Requirement 7: Provide a Command-Line Interface for Reference Generation

**User Story:** As an operations engineer, I want a CLI command to generate Kerchunk references from GRIB2 files, so that I can integrate reference generation into automated data pipelines.

#### Acceptance Criteria

1. THE Reference_Generator SHALL provide a CLI entry point (e.g., `grib2io kerchunk`) that accepts one or more GRIB2 file paths and an output path.
2. WHEN the `--output-format` option is set to `json`, THE CLI SHALL write the Reference_Manifest as a JSON file.
3. WHEN the `--output-format` option is set to `parquet`, THE CLI SHALL write the Reference_Manifest as a Parquet file.
4. WHEN the `--filters` option is provided with key-value pairs, THE CLI SHALL apply those filters to select a subset of GRIB2 messages before generating the Reference_Manifest.
5. IF no GRIB2 files are provided, THEN THE CLI SHALL display a usage message and exit with a non-zero status code.

### Requirement 8: Declare Optional Dependencies

**User Story:** As a package maintainer, I want kerchunk and icechunk to be optional dependencies, so that users who do not need cloud-native access are not burdened with additional installations.

#### Acceptance Criteria

1. THE grib2io package SHALL declare `kerchunk` and `icechunk` as optional dependencies under a `[project.optional-dependencies]` group (e.g., `kerchunk` and `icechunk` extras).
2. THE grib2io package SHALL declare `numcodecs` as a dependency of the `kerchunk` optional group.
3. WHEN the optional dependencies are not installed, THE grib2io core functionality (file reading, writing, xarray backend for direct GRIB2 files) SHALL continue to operate without errors.
4. WHEN a user attempts to use kerchunk or icechunk features without the required packages installed, THE grib2io module SHALL raise an ImportError with a clear message naming the missing package and the install extra (e.g., `pip install grib2io[kerchunk]`).
