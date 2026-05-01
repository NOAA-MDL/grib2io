# Feature: kerchunk-icechunk-support, Property 5: Codec Decode Equivalence
"""
Property-based test for Grib2Codec decode equivalence.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9**

Property 5: Codec Decode Equivalence
-------------------------------------
For any GRIB2 message from a valid GRIB2 file (across all supported Data
Representation Template numbers: simple packing DRT 0, complex packing DRT 2/3,
JPEG2000 DRT 40, PNG DRT 41), decoding the raw section 7 bytes through
Grib2Codec.decode() with the message's section metadata SHALL produce a NumPy
array equal (within floating-point tolerance) to the array produced by
grib2io._data() for the same message, including correct NaN placement at
bitmap-masked grid points.

Note: The _data() function performs additional post-processing for messages with
typeOfMissingValueManagement (replacing sentinel values with NaN). The codec
operates at the section 7 level and does not perform this replacement. For such
messages, we verify that the raw decoded values match by comparing against
_data() with auto_nans disabled, and separately verify that bitmap-based NaN
placement is correct.
"""

import os

import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

import grib2io._grib2io as _g2io_module
from grib2io._grib2io import build_index, msgs_from_index, _data
from grib2io.codecs import Grib2Codec

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------
INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")

# Map of test files to the DRT types they contain
TEST_FILES = {
    "gfs.t00z.pgrb2.1p00.f024": {0, 3},  # simple + complex packing, some with bitmaps
    "gfs.complex.grib2": {3},  # complex packing (DRT 3)
    "gfs.jpeg.grib2": {40},  # JPEG2000 (DRT 40)
    "gfs.png.grib2": {41},  # PNG (DRT 41)
    "blend.t00z.core.f001.co_4x_reduce.grib2": {0, 2, 3},  # mixed DRTs
}

# Target DRT types to cover
TARGET_DRTS = {0, 2, 3, 40, 41}


# ---------------------------------------------------------------------------
# Helpers: build a catalog of (file, message_index) pairs grouped by DRT
# ---------------------------------------------------------------------------


def _build_message_catalog():
    """Scan test files and build a catalog of messages grouped by DRT type.

    Returns a list of tuples:
        (filepath, msg_index, drtn, has_bitmap, has_missing_value_mgmt)
    for all messages across all test files whose DRT is in TARGET_DRTS.
    """
    catalog = []
    for filename, expected_drts in TEST_FILES.items():
        filepath = os.path.join(INPUT_DATA, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath, "rb") as fh:
            index = build_index(fh)
            msgs = msgs_from_index(index, filehandle=fh)
        n_msgs = len(index["section0"])
        for i in range(n_msgs):
            drtn = int(index["section5"][i][1])
            if drtn in TARGET_DRTS:
                has_bitmap = index["bmapflag"][i] in {0, 254}
                msg = msgs[i]
                has_mvm = hasattr(msg, "typeOfMissingValueManagement") and int(msg.typeOfMissingValueManagement) in {1, 2}
                catalog.append((filepath, i, drtn, has_bitmap, has_mvm))
    return catalog


# Build the catalog once at module load time
_CATALOG = _build_message_catalog()

# Group by DRT for targeted sampling
_CATALOG_BY_DRT = {}
for entry in _CATALOG:
    _CATALOG_BY_DRT.setdefault(entry[2], []).append(entry)

# Collect bitmap entries
_BITMAP_ENTRIES = [e for e in _CATALOG if e[3]]


def _decode_message(filepath, msg_idx):
    """Decode a single message via both Grib2Codec and _data(), return both arrays.

    Returns (codec_data, ref_data, has_bitmap, has_mvm).
    """
    with open(filepath, "rb") as fh:
        index = build_index(fh)
        msgs = msgs_from_index(index, filehandle=fh)
        msg = msgs[msg_idx]

        # Build codec config from message metadata
        gds = msg.section3[0:5].tolist()
        gdt = msg.section3[5:].tolist()
        drt = msg._orig_section5[2:].tolist()
        drtn = int(msg.drtn)
        gdtn = int(msg.gdtn)
        bitmap_flag = int(msg.bitMapFlag)
        has_bitmap = bitmap_flag in {0, 254}
        has_mvm = hasattr(msg, "typeOfMissingValueManagement") and int(msg.typeOfMissingValueManagement) in {1, 2}

        # Read section 7 bytes
        sec7_offset = index["sectionOffset"][msg_idx][7]
        sec7_size = index["sectionSize"][msg_idx][7]
        fh.seek(sec7_offset)
        sec7_bytes = fh.read(sec7_size)

        # If bitmap present, read bitmap section and prepend
        bitmap_length = None
        if has_bitmap:
            sec6_offset = index["sectionOffset"][msg_idx][6]
            sec6_size = index["sectionSize"][msg_idx][6]
            fh.seek(sec6_offset)
            bmap_bytes = fh.read(sec6_size)
            bitmap_length = sec6_size
            buf = bmap_bytes + sec7_bytes
        else:
            buf = sec7_bytes

        codec = Grib2Codec(
            drtn=drtn,
            drt=drt,
            gdtn=gdtn,
            gdt=gdt,
            gds=gds,
            nx=int(msg.nx),
            ny=int(msg.ny),
            bitmap_flag=bitmap_flag,
            bitmap_offset=index["sectionOffset"][msg_idx][6] if has_bitmap else None,
            bitmap_length=bitmap_length,
            scan_mode_flags=[int(x) for x in msg.scanModeFlags],
            type_of_values=int(msg.typeOfValues),
            number_of_data_points=int(msg.numberOfDataPoints),
            number_of_packed_values=int(msg.numberOfPackedValues),
        )

        # Decode via codec
        codec_data = codec.decode(buf)

        # Decode via _data() (reference implementation)
        # For messages with missing value management but no bitmap, _data()
        # replaces sentinel values with NaN. The codec does not do this.
        # We compare against _data() with auto_nans disabled for such messages
        # to verify the raw section 7 decode is equivalent.
        bitmap_offset = index["sectionOffset"][msg_idx][6] if has_bitmap else None
        data_offset = index["sectionOffset"][msg_idx][7]

        if has_mvm and not has_bitmap:
            # Temporarily disable auto_nans to get raw values from _data()
            old_auto_nans = _g2io_module._AUTO_NANS
            _g2io_module._AUTO_NANS = False
            try:
                ref_data = _data(fh, msg, bitmap_offset, data_offset)
            finally:
                _g2io_module._AUTO_NANS = old_auto_nans
        else:
            ref_data = _data(fh, msg, bitmap_offset, data_offset)

    return codec_data, ref_data, has_bitmap, has_mvm


# ---------------------------------------------------------------------------
# Hypothesis strategy: draw a random message from the catalog
# ---------------------------------------------------------------------------

catalog_index_strategy = st.sampled_from(range(len(_CATALOG)))


# ---------------------------------------------------------------------------
# Property test: Codec Decode Equivalence
# ---------------------------------------------------------------------------


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(idx=catalog_index_strategy)
def test_codec_decode_equivalence(idx):
    """Property 5: Codec Decode Equivalence

    For any GRIB2 message from a valid GRIB2 file, decoding the raw section 7
    bytes through Grib2Codec.decode() with the message's section metadata SHALL
    produce a NumPy array equal (within floating-point tolerance) to the array
    produced by grib2io._data() for the same message, including correct NaN
    placement at bitmap-masked grid points.

    For messages with typeOfMissingValueManagement (sentinel-based missing
    values), the comparison is against the raw _data() output (auto_nans=False)
    since the codec decodes at the section 7 level without post-processing
    sentinel replacement.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9**
    """
    filepath, msg_idx, drtn, has_bitmap, has_mvm = _CATALOG[idx]

    codec_data, ref_data, _, _ = _decode_message(filepath, msg_idx)

    # Shape must match
    assert codec_data.shape == ref_data.shape, (
        f"Shape mismatch: codec={codec_data.shape}, ref={ref_data.shape} (file={os.path.basename(filepath)}, msg={msg_idx}, DRT={drtn})"
    )

    # NaN placement must match exactly
    codec_nans = np.isnan(codec_data)
    ref_nans = np.isnan(ref_data)
    assert np.array_equal(codec_nans, ref_nans), (
        f"NaN placement mismatch: codec NaN count={codec_nans.sum()}, "
        f"ref NaN count={ref_nans.sum()} "
        f"(file={os.path.basename(filepath)}, msg={msg_idx}, DRT={drtn})"
    )

    # Non-NaN values must be equal within floating-point tolerance
    assert np.allclose(codec_data, ref_data, equal_nan=True, rtol=1e-6, atol=1e-6), (
        f"Value mismatch: max diff={np.nanmax(np.abs(codec_data - ref_data))} (file={os.path.basename(filepath)}, msg={msg_idx}, DRT={drtn})"
    )


# ---------------------------------------------------------------------------
# Per-DRT targeted tests to ensure each DRT type is covered
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("drtn", sorted(TARGET_DRTS))
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_codec_decode_per_drt(data, drtn):
    """Property 5 (per-DRT): Codec decode equivalence for a specific DRT type.

    Ensures each DRT type (0, 2, 3, 40, 41) is tested with at least 100
    iterations by sampling only from messages of that DRT type.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9**
    """
    entries = _CATALOG_BY_DRT.get(drtn, [])
    assume(len(entries) > 0)

    entry = data.draw(st.sampled_from(entries))
    filepath, msg_idx, _, has_bitmap, has_mvm = entry

    codec_data, ref_data, _, _ = _decode_message(filepath, msg_idx)

    # Shape must match
    assert codec_data.shape == ref_data.shape

    # NaN placement must match exactly
    assert np.array_equal(np.isnan(codec_data), np.isnan(ref_data))

    # Values must be equal within tolerance
    assert np.allclose(codec_data, ref_data, equal_nan=True, rtol=1e-6, atol=1e-6)


# ---------------------------------------------------------------------------
# Bitmap-specific property test
# ---------------------------------------------------------------------------


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(data=st.data())
def test_codec_bitmap_nan_placement(data):
    """Property 5 (bitmap): NaN placement at bitmap-masked grid points.

    For messages with a bitmap (bitmap_flag 0 or 254), verify that NaN values
    appear at exactly the same grid points in both codec and reference output.

    **Validates: Requirements 3.8, 3.9**
    """
    assume(len(_BITMAP_ENTRIES) > 0)

    entry = data.draw(st.sampled_from(_BITMAP_ENTRIES))
    filepath, msg_idx, drtn, _, _ = entry

    codec_data, ref_data, has_bitmap, _ = _decode_message(filepath, msg_idx)
    assert has_bitmap, "Expected a bitmap message"

    # Both must have NaN values
    codec_nans = np.isnan(codec_data)
    ref_nans = np.isnan(ref_data)

    # NaN count must match
    assert codec_nans.sum() == ref_nans.sum(), f"NaN count mismatch: codec={codec_nans.sum()}, ref={ref_nans.sum()}"

    # NaN positions must match exactly
    assert np.array_equal(codec_nans, ref_nans), "NaN positions differ between codec and reference output"

    # Non-NaN values must match
    mask = ~ref_nans
    if mask.any():
        assert np.allclose(codec_data[mask], ref_data[mask], rtol=1e-6, atol=1e-6), (
            f"Non-NaN value mismatch: max diff={np.max(np.abs(codec_data[mask] - ref_data[mask]))}"
        )
