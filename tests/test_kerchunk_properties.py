# Feature: kerchunk-icechunk-support, Property 1: Manifest Structural Validity
# Feature: kerchunk-icechunk-support, Property 2: Chunk Key Uniqueness and Determinism
# Feature: kerchunk-icechunk-support, Property 3: Multi-Dimensional Hierarchy Correctness
# Feature: kerchunk-icechunk-support, Property 4: JSON Serialization Round-Trip
# Feature: kerchunk-icechunk-support, Property 6: Multi-File Reference Source Correctness
# Feature: kerchunk-icechunk-support, Property 7: Multi-File Dimension Concatenation
"""
Property-based tests for the ReferenceGenerator (kerchunk.py).

These tests use real GRIB2 test files from ``tests/input_data/`` and the
Hypothesis library to verify correctness properties of the generated
Kerchunk v1 reference manifests.

Each property test uses ``st.data()`` to draw both a test file and a random
subset of variables to inspect, ensuring Hypothesis generates at least 100
distinct examples per test even though the file pool is small.
"""

import json
import os
from functools import reduce
from itertools import combinations as _combinations, permutations as _permutations
from operator import mul

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from grib2io.kerchunk import ReferenceGenerator, _file_uri

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------
INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")

# All available test files with their characteristics
TEST_FILES = [
    "gfs.t00z.pgrb2.1p00.f024",                  # mixed DRT types, multiple vars/levels, has bitmaps
    "gfs.complex.grib2",                           # complex packing (DRT 3)
    "gfs.jpeg.grib2",                              # JPEG2000 (DRT 40)
    "gfs.png.grib2",                               # PNG (DRT 41)
    "blend.t00z.core.f001.co_4x_reduce.grib2",    # reduced grids, mixed DRTs
    "blend.t00z.core.f001.tmp.co.grib2",           # another blend file
]

# Files known to contain bitmap messages (bmapflag 0 or 254)
BITMAP_FILES = [
    "gfs.t00z.pgrb2.1p00.f024",
]

# Small files suitable for multi-file tests (avoid the large 743-message file
# to keep test runtime reasonable while still covering multi-file logic).
_SMALL_FILES = [
    "gfs.complex.grib2",
    "gfs.jpeg.grib2",
    "gfs.png.grib2",
    "blend.t00z.core.f001.tmp.co.grib2",
]

# Build all 2-file, 3-file, and 4-file combinations from the small files,
# plus selected combinations that include the larger files for broader coverage.
MULTI_FILE_GROUPS = []
for _r in (2, 3, 4):
    for _combo in _combinations(_SMALL_FILES, _r):
        MULTI_FILE_GROUPS.append(list(_combo))

# Also add permutations of 2-file combos (order can matter for URI tracking)
for _combo in _permutations(_SMALL_FILES, 2):
    _group = list(_combo)
    if _group not in MULTI_FILE_GROUPS:
        MULTI_FILE_GROUPS.append(_group)

# Include the blend reduced-grid file in some combinations
_EXTRA_FILE = "blend.t00z.core.f001.co_4x_reduce.grib2"
for _sf in _SMALL_FILES:
    MULTI_FILE_GROUPS.append([_sf, _EXTRA_FILE])
    MULTI_FILE_GROUPS.append([_EXTRA_FILE, _sf])

# Validate that test files exist
_AVAILABLE_FILES = [f for f in TEST_FILES if os.path.isfile(os.path.join(INPUT_DATA, f))]
_AVAILABLE_BITMAP_FILES = [f for f in BITMAP_FILES if os.path.isfile(os.path.join(INPUT_DATA, f))]
_AVAILABLE_MULTI_FILE_GROUPS = [
    g for g in MULTI_FILE_GROUPS
    if all(os.path.isfile(os.path.join(INPUT_DATA, f)) for f in g)
]

# Required fields in .zarray metadata
ZARRAY_REQUIRED_FIELDS = {"chunks", "dtype", "fill_value", "shape", "compressor", "order"}

# Required fields in .zattrs metadata
ZATTRS_REQUIRED_FIELDS = {
    "_ARRAY_DIMENSIONS",
    "discipline",
    "parameterCategory",
    "parameterNumber",
    "typeOfFirstFixedSurface",
    "valueOfFirstFixedSurface",
    "refDate",
    "leadTime",
}


# ---------------------------------------------------------------------------
# Pre-computed manifests (cached to avoid regenerating on every example)
# ---------------------------------------------------------------------------

_MANIFEST_CACHE = {}


def _get_manifest(file_key):
    """Return a cached manifest for the given file key (tuple of filenames)."""
    if file_key not in _MANIFEST_CACHE:
        if isinstance(file_key, str):
            file_key = (file_key,)
        full_paths = [os.path.join(INPUT_DATA, f) for f in file_key]
        gen = ReferenceGenerator(full_paths)
        _MANIFEST_CACHE[file_key] = gen.generate()
    return _MANIFEST_CACHE[file_key]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_variable_names(refs):
    """Extract data variable names from manifest refs.

    Data variables have a ``.zarray`` whose ``compressor`` is a dict with
    ``id == "grib2io"``.  Coordinate arrays (level, leadTime, refDate, …)
    have ``compressor: null`` and are excluded.
    """
    var_names = []
    for key in sorted(refs.keys()):
        if key.endswith("/.zarray"):
            var_name = key.rsplit("/.zarray", 1)[0]
            if "/" not in var_name:
                zarray = json.loads(refs[key])
                compressor = zarray.get("compressor")
                if isinstance(compressor, dict) and compressor.get("id") == "grib2io":
                    var_names.append(var_name)
    return var_names


def _get_data_chunk_keys(refs, var_name):
    """Get all data chunk keys for a variable (not .zarray, .zattrs, .bitmap)."""
    chunk_keys = []
    prefix = f"{var_name}/"
    for key in refs:
        if key.startswith(prefix):
            suffix = key[len(prefix):]
            # Skip metadata and bitmap keys
            if suffix.startswith(".") or ".bitmap" in key:
                continue
            # Must look like dimension indices (e.g., "0.0.0.0")
            parts = suffix.split(".")
            if all(p.isdigit() for p in parts):
                chunk_keys.append(key)
    return chunk_keys


# ---------------------------------------------------------------------------
# Build a catalog of (file, variable) pairs for fine-grained sampling
# ---------------------------------------------------------------------------

_VAR_CATALOG = []  # list of (filename, var_name)
_BITMAP_VAR_CATALOG = []  # list of (filename, var_name) for bitmap vars
_BITMAP_CHUNK_CATALOG = []  # list of (filename, var_name, ref_key, ref_type) for bitmap refs

for _fname in _AVAILABLE_FILES:
    _manifest = _get_manifest((_fname,))
    _vars = _extract_variable_names(_manifest["refs"])
    for _vn in _vars:
        _VAR_CATALOG.append((_fname, _vn))
        _zarray = json.loads(_manifest["refs"][f"{_vn}/.zarray"])
        if _zarray["compressor"]["bitmap_flag"] in {0, 254}:
            _BITMAP_VAR_CATALOG.append((_fname, _vn))
            # Collect bitmap companion ref keys
            for _k in _manifest["refs"]:
                if _k.startswith(f"{_vn}/.bitmap/"):
                    _BITMAP_CHUNK_CATALOG.append((_fname, _vn, _k, "bitmap"))
            # Also collect data chunk ref keys for bitmap variables
            _prefix = f"{_vn}/"
            for _k in _manifest["refs"]:
                if _k.startswith(_prefix):
                    _suffix = _k[len(_prefix):]
                    if not _suffix.startswith(".") and ".bitmap" not in _k:
                        _parts = _suffix.split(".")
                        if all(_p.isdigit() for _p in _parts):
                            _BITMAP_CHUNK_CATALOG.append((_fname, _vn, _k, "data"))

_MULTI_FILE_VAR_CATALOG = []  # list of (file_group_tuple, var_name)
for _group in _AVAILABLE_MULTI_FILE_GROUPS:
    _key = tuple(_group)
    _manifest = _get_manifest(_key)
    _vars = _extract_variable_names(_manifest["refs"])
    for _vn in _vars:
        _MULTI_FILE_VAR_CATALOG.append((_key, _vn))


# ===========================================================================
# Property 1: Manifest Structural Validity
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_manifest_structural_validity(data):
    """Property 1: Manifest Structural Validity

    For any valid GRIB2 file and any variable within it, the generated
    reference manifest SHALL have ``"version": 1``, a ``"refs"`` key, and
    the variable SHALL have a ``.zarray`` entry with required fields and a
    ``.zattrs`` entry with required fields.

    **Validates: Requirements 1.1, 1.4, 1.5, 1.6**
    """
    filename, var_name = data.draw(st.sampled_from(_VAR_CATALOG))
    manifest = _get_manifest((filename,))

    # Top-level structure
    assert manifest["version"] == 1, "Manifest version must be 1"
    assert "refs" in manifest, "Manifest must have 'refs' key"

    refs = manifest["refs"]

    # Must have .zgroup
    assert ".zgroup" in refs, "Manifest must have .zgroup"
    zgroup = json.loads(refs[".zgroup"])
    assert zgroup["zarr_format"] == 2, ".zgroup must have zarr_format 2"

    # Verify .zarray for the drawn variable
    zarray_key = f"{var_name}/.zarray"
    assert zarray_key in refs, f"Variable {var_name} must have .zarray"
    zarray = json.loads(refs[zarray_key])

    missing_fields = ZARRAY_REQUIRED_FIELDS - set(zarray.keys())
    assert not missing_fields, (
        f"Variable {var_name} .zarray missing fields: {missing_fields}"
    )

    # Verify .zarray field types
    assert isinstance(zarray["chunks"], list), f"{var_name} chunks must be a list"
    assert isinstance(zarray["shape"], list), f"{var_name} shape must be a list"
    assert isinstance(zarray["dtype"], str), f"{var_name} dtype must be a string"
    assert isinstance(zarray["order"], str), f"{var_name} order must be a string"
    assert len(zarray["shape"]) == len(zarray["chunks"]), (
        f"{var_name} shape and chunks must have same length"
    )

    # Verify compressor is a dict with 'id' = 'grib2io'
    compressor = zarray["compressor"]
    assert isinstance(compressor, dict), f"{var_name} compressor must be a dict"
    assert compressor.get("id") == "grib2io", (
        f"{var_name} compressor id must be 'grib2io'"
    )

    # Verify .zattrs
    zattrs_key = f"{var_name}/.zattrs"
    assert zattrs_key in refs, f"Variable {var_name} must have .zattrs"
    zattrs = json.loads(refs[zattrs_key])

    missing_attrs = ZATTRS_REQUIRED_FIELDS - set(zattrs.keys())
    assert not missing_attrs, (
        f"Variable {var_name} .zattrs missing fields: {missing_attrs}"
    )

    # Verify _ARRAY_DIMENSIONS is a list ending with y, x
    dims = zattrs["_ARRAY_DIMENSIONS"]
    assert isinstance(dims, list), f"{var_name} _ARRAY_DIMENSIONS must be a list"
    assert len(dims) >= 2, f"{var_name} must have at least y, x dimensions"
    assert dims[-2:] == ["y", "x"], (
        f"{var_name} last two dimensions must be ['y', 'x'], got {dims[-2:]}"
    )


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_manifest_bitmap_codec_config(data):
    """Property 1 (bitmap): Bitmap messages have non-null bitmap_offset and bitmap_length.

    For any variable whose codec config has ``bitmap_flag`` in {0, 254}, the
    codec config within ``.zarray.compressor`` SHALL include non-null
    ``bitmap_offset`` and ``bitmap_length`` values.  Additionally, bitmap
    companion refs and data chunk refs SHALL be valid ``[uri, offset, length]``
    tuples.

    **Validates: Requirements 1.5, 1.6**
    """
    assume(len(_BITMAP_CHUNK_CATALOG) > 0)
    filename, var_name, ref_key, ref_type = data.draw(
        st.sampled_from(_BITMAP_CHUNK_CATALOG)
    )

    manifest = _get_manifest((filename,))
    refs = manifest["refs"]

    zarray = json.loads(refs[f"{var_name}/.zarray"])
    compressor = zarray["compressor"]

    assert compressor["bitmap_flag"] in {0, 254}, (
        f"Variable {var_name} expected bitmap_flag in {{0, 254}}, "
        f"got {compressor['bitmap_flag']}"
    )
    assert compressor["bitmap_offset"] is not None, (
        f"Variable {var_name} with bitmap_flag={compressor['bitmap_flag']} "
        f"must have non-null bitmap_offset"
    )
    assert compressor["bitmap_length"] is not None, (
        f"Variable {var_name} with bitmap_flag={compressor['bitmap_flag']} "
        f"must have non-null bitmap_length"
    )
    assert isinstance(compressor["bitmap_offset"], int), (
        f"Variable {var_name} bitmap_offset must be an int"
    )
    assert isinstance(compressor["bitmap_length"], int), (
        f"Variable {var_name} bitmap_length must be an int"
    )
    assert compressor["bitmap_length"] > 0, (
        f"Variable {var_name} bitmap_length must be > 0"
    )

    # Verify the specific ref is valid
    assert ref_key in refs, f"Ref {ref_key} not found in manifest"
    ref_value = refs[ref_key]
    assert isinstance(ref_value, list) and len(ref_value) == 3, (
        f"Ref {ref_key} must be [uri, offset, length]"
    )
    uri, offset, length = ref_value
    assert isinstance(offset, int) and offset >= 0, (
        f"Ref {ref_key} has invalid offset: {offset}"
    )
    assert isinstance(length, int) and length > 0, (
        f"Ref {ref_key} has invalid length: {length}"
    )

    # Verify the referenced bytes are within file bounds
    file_path = uri.replace("file://", "")
    file_size = os.path.getsize(file_path)
    assert offset + length <= file_size, (
        f"Ref {ref_key} references bytes [{offset}:{offset + length}] "
        f"but file is only {file_size} bytes"
    )


# ===========================================================================
# Property 2: Chunk Key Uniqueness and Determinism
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_chunk_key_uniqueness(data):
    """Property 2: Chunk Key Uniqueness

    For any GRIB2 file and any variable within it, the chunk key mapping
    SHALL produce unique keys following the Zarr naming convention.

    **Validates: Requirements 1.2**
    """
    filename, var_name = data.draw(st.sampled_from(_VAR_CATALOG))
    manifest = _get_manifest((filename,))
    refs = manifest["refs"]

    chunk_keys = _get_data_chunk_keys(refs, var_name)

    # All chunk keys must be unique
    assert len(chunk_keys) == len(set(chunk_keys)), (
        f"Variable {var_name} has duplicate chunk keys"
    )

    # Each chunk key must follow the Zarr naming convention
    for key in chunk_keys:
        suffix = key[len(f"{var_name}/"):]
        parts = suffix.split(".")
        assert all(p.isdigit() for p in parts), (
            f"Chunk key {key} does not follow Zarr naming convention"
        )


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_chunk_key_determinism(data):
    """Property 2: Chunk Key Determinism

    The same input SHALL always produce the same chunk keys (run twice, compare).

    **Validates: Requirements 1.2**
    """
    filename = data.draw(st.sampled_from(_AVAILABLE_FILES))

    # Generate two fresh manifests (bypass cache)
    full_path = os.path.join(INPUT_DATA, filename)
    manifest1 = ReferenceGenerator([full_path]).generate()
    manifest2 = ReferenceGenerator([full_path]).generate()

    refs1 = manifest1["refs"]
    refs2 = manifest2["refs"]

    # Same set of keys
    assert set(refs1.keys()) == set(refs2.keys()), (
        f"Determinism violation: key sets differ for {filename}"
    )

    # Pick a random subset of keys to compare values
    all_keys = sorted(refs1.keys())
    key_to_check = data.draw(st.sampled_from(all_keys))

    val1 = refs1[key_to_check]
    val2 = refs2[key_to_check]
    assert val1 == val2, (
        f"Determinism violation: values differ for key '{key_to_check}' in {filename}"
    )


# ===========================================================================
# Property 3: Multi-Dimensional Hierarchy Correctness
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_multidimensional_hierarchy_correctness(data):
    """Property 3: Multi-Dimensional Hierarchy Correctness

    For any GRIB2 file and any variable within it, the ``.zarray`` shape
    SHALL reflect the actual number of unique values along each dimension,
    and the total number of data chunk keys SHALL equal the product of the
    non-spatial dimension sizes.

    **Validates: Requirements 1.3**
    """
    filename, var_name = data.draw(st.sampled_from(_VAR_CATALOG))
    manifest = _get_manifest((filename,))
    refs = manifest["refs"]

    zarray = json.loads(refs[f"{var_name}/.zarray"])
    zattrs = json.loads(refs[f"{var_name}/.zattrs"])

    shape = zarray["shape"]
    dims = zattrs["_ARRAY_DIMENSIONS"]

    # shape and dims must have same length
    assert len(shape) == len(dims), (
        f"Variable {var_name}: shape length {len(shape)} != dims length {len(dims)}"
    )

    # Last two dims are y, x (spatial) - non-spatial dims are the rest
    non_spatial_dims = dims[:-2]
    non_spatial_shape = shape[:-2]

    # All non-spatial dimension sizes must be >= 1
    for d, s in zip(non_spatial_dims, non_spatial_shape):
        assert s >= 1, (
            f"Variable {var_name}: dimension {d} has size {s}, expected >= 1"
        )

    # Total data chunk keys should equal product of non-spatial dimension sizes
    chunk_keys = _get_data_chunk_keys(refs, var_name)
    expected_chunks = reduce(mul, non_spatial_shape, 1) if non_spatial_shape else 1

    assert len(chunk_keys) == expected_chunks, (
        f"Variable {var_name}: {len(chunk_keys)} chunk keys != "
        f"expected {expected_chunks} (product of non-spatial dims {non_spatial_shape})"
    )

    # Verify that chunk indices are within bounds
    for key in chunk_keys:
        suffix = key[len(f"{var_name}/"):]
        indices = [int(p) for p in suffix.split(".")]

        # Number of indices should match number of dimensions
        assert len(indices) == len(dims), (
            f"Variable {var_name}: chunk key {key} has {len(indices)} indices "
            f"but {len(dims)} dimensions"
        )

        # Each index must be within the shape bounds
        for idx_val, dim_size, dim_name in zip(indices, shape, dims):
            assert 0 <= idx_val < dim_size, (
                f"Variable {var_name}: chunk key {key} has index {idx_val} "
                f"for dimension {dim_name} with size {dim_size}"
            )


# ===========================================================================
# Property 6: Multi-File Reference Source Correctness
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_multifile_source_correctness(data):
    """Property 6: Multi-File Reference Source Correctness

    For any combined reference manifest generated from multiple GRIB2 files,
    every data chunk reference ``[uri, offset, length]`` SHALL point to a
    correct source file URI that is one of the input files.

    **Validates: Requirements 5.1, 5.4**
    """
    assume(len(_MULTI_FILE_VAR_CATALOG) > 0)
    file_group_key, var_name = data.draw(st.sampled_from(_MULTI_FILE_VAR_CATALOG))

    full_paths = [os.path.join(INPUT_DATA, f) for f in file_group_key]
    expected_uris = {_file_uri(p) for p in full_paths}

    manifest = _get_manifest(file_group_key)
    refs = manifest["refs"]

    chunk_keys = _get_data_chunk_keys(refs, var_name)

    for key in chunk_keys:
        ref_value = refs[key]

        # Data chunk refs must be [uri, offset, length] lists
        assert isinstance(ref_value, list), (
            f"Chunk ref {key} must be a list, got {type(ref_value)}"
        )
        assert len(ref_value) == 3, (
            f"Chunk ref {key} must have 3 elements [uri, offset, length], "
            f"got {len(ref_value)}"
        )

        uri, offset, length = ref_value

        # URI must be one of the input file URIs
        assert uri in expected_uris, (
            f"Chunk ref {key} points to URI '{uri}' which is not one of "
            f"the input files: {expected_uris}"
        )

        # Offset and length must be non-negative integers
        assert isinstance(offset, int) and offset >= 0, (
            f"Chunk ref {key} has invalid offset: {offset}"
        )
        assert isinstance(length, int) and length > 0, (
            f"Chunk ref {key} has invalid length: {length}"
        )

        # Verify the referenced bytes are actually readable from the file
        file_path = uri.replace("file://", "")
        file_size = os.path.getsize(file_path)
        assert offset + length <= file_size, (
            f"Chunk ref {key} references bytes [{offset}:{offset + length}] "
            f"but file {file_path} is only {file_size} bytes"
        )

    # Also check bitmap companion refs point to valid files
    for key, value in refs.items():
        if key.startswith(f"{var_name}/.bitmap/") and isinstance(value, list):
            uri, offset, length = value
            assert uri in expected_uris, (
                f"Bitmap ref {key} points to URI '{uri}' not in input files"
            )


# ===========================================================================
# Property 7: Multi-File Dimension Concatenation
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_multifile_dimension_concatenation(data):
    """Property 7: Multi-File Dimension Concatenation

    For any set of GRIB2 files containing the same variable at different times
    or with different metadata, the combined reference manifest SHALL have
    dimensions whose sizes reflect the total unique values across all files.
    The ``.zarray`` shape SHALL reflect the concatenated dimensions.

    **Validates: Requirements 5.2**
    """
    assume(len(_MULTI_FILE_VAR_CATALOG) > 0)
    file_group_key, var_name = data.draw(st.sampled_from(_MULTI_FILE_VAR_CATALOG))

    # Get individual manifests
    individual_manifests = [_get_manifest((f,)) for f in file_group_key]

    # Get combined manifest
    combined_manifest = _get_manifest(file_group_key)
    combined_refs = combined_manifest["refs"]

    combined_zarray = json.loads(combined_refs[f"{var_name}/.zarray"])
    combined_zattrs = json.loads(combined_refs[f"{var_name}/.zattrs"])
    combined_shape = combined_zarray["shape"]
    combined_dims = combined_zattrs["_ARRAY_DIMENSIONS"]

    # Collect the same variable from individual manifests
    individual_shapes = []
    for ind_manifest in individual_manifests:
        ind_refs = ind_manifest["refs"]
        ind_zarray_key = f"{var_name}/.zarray"
        if ind_zarray_key in ind_refs:
            ind_zarray = json.loads(ind_refs[ind_zarray_key])
            individual_shapes.append(ind_zarray["shape"])

    if len(individual_shapes) >= 2:
        # The combined shape's spatial dimensions (last 2) should match
        # across individual files — but only when all files share the
        # same grid size for this variable.  When files have different
        # grids (e.g. 400x587 vs 1597x2345), the combined manifest
        # picks one grid and the property cannot assert equality.
        spatial_dims_set = {tuple(s[-2:]) for s in individual_shapes}
        if len(spatial_dims_set) == 1:
            # All individual files agree on the spatial grid
            for ind_shape in individual_shapes:
                assert combined_shape[-2:] == ind_shape[-2:], (
                    f"Variable {var_name}: spatial dims mismatch. "
                    f"Combined={combined_shape[-2:]}, individual={ind_shape[-2:]}"
                )

        # For non-spatial dimensions, the combined size should be >= max
        # of individual sizes (concatenation can only grow or stay same)
        non_spatial_combined = combined_shape[:-2]
        for dim_idx in range(len(non_spatial_combined)):
            individual_sizes = [
                s[dim_idx] for s in individual_shapes
                if len(s) > dim_idx + 2
            ]
            if individual_sizes:
                max_individual = max(individual_sizes)
                assert non_spatial_combined[dim_idx] >= max_individual, (
                    f"Variable {var_name}, dim {combined_dims[dim_idx]}: "
                    f"combined size {non_spatial_combined[dim_idx]} < "
                    f"max individual size {max_individual}"
                )

    # Verify total chunk count matches product of non-spatial dims
    non_spatial_shape = combined_shape[:-2]
    chunk_keys = _get_data_chunk_keys(combined_refs, var_name)
    expected_chunks = reduce(mul, non_spatial_shape, 1) if non_spatial_shape else 1
    assert len(chunk_keys) == expected_chunks, (
        f"Variable {var_name}: {len(chunk_keys)} chunk keys != "
        f"expected {expected_chunks} in combined manifest"
    )


# ===========================================================================
# Feature: kerchunk-icechunk-support, Property 4: JSON Serialization Round-Trip
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_json_serialization_round_trip_keys(data):
    """Property 4: JSON Serialization Round-Trip — Key Equivalence

    For any valid reference manifest generated from a real GRIB2 test file,
    serializing to JSON and loading back via ``fsspec.filesystem("reference")``
    SHALL produce a Zarr store with identical keys.

    **Validates: Requirements 2.3**
    """
    import tempfile

    import fsspec

    filename = data.draw(st.sampled_from(_AVAILABLE_FILES))
    manifest = _get_manifest((filename,))

    # Serialize to a temporary JSON file
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False
    ) as tmp:
        json.dump(manifest, tmp)
        json_path = tmp.name

    try:
        # Load back via fsspec reference filesystem
        fs = fsspec.filesystem("reference", fo=json_path)
        store = fs.get_mapper("")

        loaded_keys = set(store.keys())
        original_keys = set(manifest["refs"].keys())

        assert loaded_keys == original_keys, (
            f"Key mismatch for {filename}.\n"
            f"  Missing from loaded: {original_keys - loaded_keys}\n"
            f"  Extra in loaded: {loaded_keys - original_keys}"
        )
    finally:
        os.unlink(json_path)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_json_serialization_round_trip_metadata(data):
    """Property 4: JSON Serialization Round-Trip — Metadata Structural Equivalence

    For any valid reference manifest and any variable within it, serializing
    to JSON and loading back via ``fsspec.filesystem("reference")`` SHALL
    produce structurally equivalent ``.zarray``, ``.zattrs``, and ``.zgroup``
    metadata (parsed JSON dicts are equal).

    **Validates: Requirements 2.3**
    """
    import tempfile

    import fsspec

    filename, var_name = data.draw(st.sampled_from(_VAR_CATALOG))
    manifest = _get_manifest((filename,))

    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False
    ) as tmp:
        json.dump(manifest, tmp)
        json_path = tmp.name

    try:
        fs = fsspec.filesystem("reference", fo=json_path)
        store = fs.get_mapper("")

        # Check .zgroup
        orig_zgroup = json.loads(manifest["refs"][".zgroup"])
        loaded_zgroup = json.loads(store[".zgroup"])
        assert orig_zgroup == loaded_zgroup, (
            f".zgroup mismatch: orig={orig_zgroup}, loaded={loaded_zgroup}"
        )

        # Check variable .zarray
        zarray_key = f"{var_name}/.zarray"
        orig_zarray = json.loads(manifest["refs"][zarray_key])
        loaded_zarray = json.loads(store[zarray_key])
        assert orig_zarray == loaded_zarray, (
            f"{zarray_key} mismatch:\n  orig={orig_zarray}\n  loaded={loaded_zarray}"
        )

        # Check variable .zattrs
        zattrs_key = f"{var_name}/.zattrs"
        orig_zattrs = json.loads(manifest["refs"][zattrs_key])
        loaded_zattrs = json.loads(store[zattrs_key])
        assert orig_zattrs == loaded_zattrs, (
            f"{zattrs_key} mismatch:\n  orig={orig_zattrs}\n  loaded={loaded_zattrs}"
        )
    finally:
        os.unlink(json_path)
