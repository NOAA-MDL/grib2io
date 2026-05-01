"""
Unit tests for Grib2Codec interface compliance and per-DRT decoding.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 3.9**

Tests cover:
- Codec is a ``numcodecs.abc.Codec`` subclass with ``codec_id`` attribute
- ``get_config()`` / ``from_config()`` round-trip produces equivalent codec
- ``encode()`` raises ``NotImplementedError``
- One example per DRT type (0, 2/3, 40, 41) using real test files
- Bitmap handling with ``blend.t00z.core.f001.co_4x_reduce.grib2``
"""

import os

import numpy as np
import pytest
from numcodecs.abc import Codec

import grib2io._grib2io as _g2io_module
from grib2io._grib2io import build_index, msgs_from_index, _data
from grib2io.codecs import Grib2Codec

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------
INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")


# ---------------------------------------------------------------------------
# Helper: decode a single message via both Grib2Codec and _data()
# ---------------------------------------------------------------------------

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
        has_mvm = (
            hasattr(msg, "typeOfMissingValueManagement")
            and int(msg.typeOfMissingValueManagement) in {1, 2}
        )

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
        bitmap_offset = index["sectionOffset"][msg_idx][6] if has_bitmap else None
        data_offset = index["sectionOffset"][msg_idx][7]

        if has_mvm and not has_bitmap:
            old_auto_nans = _g2io_module._AUTO_NANS
            _g2io_module._AUTO_NANS = False
            try:
                ref_data = _data(fh, msg, bitmap_offset, data_offset)
            finally:
                _g2io_module._AUTO_NANS = old_auto_nans
        else:
            ref_data = _data(fh, msg, bitmap_offset, data_offset)

    return codec_data, ref_data, has_bitmap, has_mvm


def _find_first_message_with_drt(filepath, target_drtn):
    """Find the index of the first message with the given DRT number."""
    with open(filepath, "rb") as fh:
        index = build_index(fh)
    n_msgs = len(index["section0"])
    for i in range(n_msgs):
        drtn = int(index["section5"][i][1])
        if drtn == target_drtn:
            return i
    return None


# ===========================================================================
# 1. Interface compliance tests
# ===========================================================================

class TestGrib2CodecInterface:
    """Verify Grib2Codec is a proper numcodecs.abc.Codec subclass."""

    def test_is_codec_subclass(self):
        """Grib2Codec must be a subclass of numcodecs.abc.Codec.

        **Validates: Requirement 3.1**
        """
        assert issubclass(Grib2Codec, Codec)

    def test_codec_id_attribute(self):
        """Grib2Codec must have a codec_id attribute set to 'grib2io'.

        **Validates: Requirement 3.1**
        """
        assert hasattr(Grib2Codec, "codec_id")
        assert Grib2Codec.codec_id == "grib2io"

    def test_instance_is_codec(self):
        """An instance of Grib2Codec must be an instance of Codec.

        **Validates: Requirement 3.1**
        """
        codec = Grib2Codec(
            drtn=0, drt=[0] * 5, gdtn=0, gdt=[0] * 19,
            gds=[0] * 5, nx=10, ny=10, bitmap_flag=255,
        )
        assert isinstance(codec, Codec)

    def test_encode_raises_not_implemented(self):
        """encode() must raise NotImplementedError with the expected message.

        **Validates: Requirement 3.1**
        """
        codec = Grib2Codec(
            drtn=0, drt=[0] * 5, gdtn=0, gdt=[0] * 19,
            gds=[0] * 5, nx=10, ny=10, bitmap_flag=255,
        )
        with pytest.raises(NotImplementedError, match="decode-only"):
            codec.encode(b"dummy")


class TestGrib2CodecConfig:
    """Verify get_config() / from_config() round-trip."""

    def test_get_config_returns_dict(self):
        """get_config() must return a JSON-serializable dict.

        **Validates: Requirement 3.1**
        """
        codec = Grib2Codec(
            drtn=40, drt=[1, 2, 3], gdtn=0, gdt=[4, 5, 6],
            gds=[7, 8, 9, 10, 11], nx=1440, ny=721,
            bitmap_flag=255, scan_mode_flags=[0, 1, 0, 0],
            type_of_values=0, number_of_data_points=1038240,
            number_of_packed_values=1038240,
        )
        config = codec.get_config()
        assert isinstance(config, dict)
        assert config["id"] == "grib2io"
        assert config["drtn"] == 40
        assert config["nx"] == 1440
        assert config["ny"] == 721

    def test_config_round_trip(self):
        """from_config(get_config()) must produce an equivalent codec.

        **Validates: Requirement 3.1**
        """
        original = Grib2Codec(
            drtn=3, drt=[10, 20, 30, 40, 50], gdtn=0,
            gdt=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            gds=[0, 1038240, 0, 0, 0], nx=1440, ny=721,
            bitmap_flag=0, bitmap_offset=12345, bitmap_length=6789,
            scan_mode_flags=[0, 1, 0, 0, 0, 0, 0, 0],
            type_of_values=0, number_of_data_points=1038240,
            number_of_packed_values=1038240,
        )
        config = original.get_config()
        restored = Grib2Codec.from_config(config)

        # All attributes must match
        assert restored.drtn == original.drtn
        assert restored.drt == original.drt
        assert restored.gdtn == original.gdtn
        assert restored.gdt == original.gdt
        assert restored.gds == original.gds
        assert restored.nx == original.nx
        assert restored.ny == original.ny
        assert restored.bitmap_flag == original.bitmap_flag
        assert restored.bitmap_offset == original.bitmap_offset
        assert restored.bitmap_length == original.bitmap_length
        assert restored.scan_mode_flags == original.scan_mode_flags
        assert restored.type_of_values == original.type_of_values
        assert restored.number_of_data_points == original.number_of_data_points
        assert restored.number_of_packed_values == original.number_of_packed_values

    def test_config_round_trip_with_none_optionals(self):
        """Round-trip works when optional fields are None.

        **Validates: Requirement 3.1**
        """
        original = Grib2Codec(
            drtn=0, drt=[0, 0, 0, 0, 0], gdtn=0,
            gdt=[0] * 19, gds=[0] * 5, nx=100, ny=50,
            bitmap_flag=255,
        )
        config = original.get_config()
        restored = Grib2Codec.from_config(config)

        assert restored.bitmap_offset is None
        assert restored.bitmap_length is None
        assert restored.scan_mode_flags is None

    def test_from_config_ignores_id_key(self):
        """from_config() must handle the 'id' key without error.

        **Validates: Requirement 3.1**
        """
        config = {
            "id": "grib2io",
            "drtn": 0, "drt": [0] * 5, "gdtn": 0, "gdt": [0] * 19,
            "gds": [0] * 5, "nx": 10, "ny": 10, "bitmap_flag": 255,
            "type_of_values": 0, "number_of_data_points": 100,
            "number_of_packed_values": 100,
        }
        codec = Grib2Codec.from_config(config)
        assert codec.drtn == 0


# ===========================================================================
# 2. Per-DRT type decoding tests
# ===========================================================================

class TestGrib2CodecDRT0:
    """Test simple packing (DRT 0) decoding.

    **Validates: Requirement 3.7**
    """

    def test_drt0_decode(self):
        """Decode a DRT 0 (simple packing) message and compare to _data()."""
        filepath = os.path.join(INPUT_DATA, "gfs.t00z.pgrb2.1p00.f024")
        msg_idx = _find_first_message_with_drt(filepath, 0)
        assert msg_idx is not None, "No DRT 0 message found in test file"

        codec_data, ref_data, _, _ = _decode_message(filepath, msg_idx)

        assert codec_data.shape == ref_data.shape
        assert np.array_equal(np.isnan(codec_data), np.isnan(ref_data))
        assert np.allclose(codec_data, ref_data, equal_nan=True, rtol=1e-6, atol=1e-6)


class TestGrib2CodecDRT2_3:
    """Test complex packing (DRT 2/3) decoding.

    **Validates: Requirement 3.6**
    """

    def test_drt3_decode(self):
        """Decode a DRT 3 (complex packing) message and compare to _data()."""
        filepath = os.path.join(INPUT_DATA, "gfs.complex.grib2")
        msg_idx = _find_first_message_with_drt(filepath, 3)
        assert msg_idx is not None, "No DRT 3 message found in test file"

        codec_data, ref_data, _, _ = _decode_message(filepath, msg_idx)

        assert codec_data.shape == ref_data.shape
        assert np.array_equal(np.isnan(codec_data), np.isnan(ref_data))
        assert np.allclose(codec_data, ref_data, equal_nan=True, rtol=1e-6, atol=1e-6)

    def test_drt2_decode(self):
        """Decode a DRT 2 (complex packing variant) message if available."""
        # blend file has DRT 2 messages
        filepath = os.path.join(INPUT_DATA, "blend.t00z.core.f001.co_4x_reduce.grib2")
        msg_idx = _find_first_message_with_drt(filepath, 2)
        if msg_idx is None:
            pytest.skip("No DRT 2 message found in test files")

        codec_data, ref_data, _, _ = _decode_message(filepath, msg_idx)

        assert codec_data.shape == ref_data.shape
        assert np.array_equal(np.isnan(codec_data), np.isnan(ref_data))
        assert np.allclose(codec_data, ref_data, equal_nan=True, rtol=1e-6, atol=1e-6)


class TestGrib2CodecDRT40:
    """Test JPEG2000 compression (DRT 40) decoding.

    **Validates: Requirement 3.3**
    """

    def test_drt40_decode(self):
        """Decode a DRT 40 (JPEG2000) message and compare to _data()."""
        filepath = os.path.join(INPUT_DATA, "gfs.jpeg.grib2")
        msg_idx = _find_first_message_with_drt(filepath, 40)
        assert msg_idx is not None, "No DRT 40 message found in test file"

        codec_data, ref_data, _, _ = _decode_message(filepath, msg_idx)

        assert codec_data.shape == ref_data.shape
        assert np.array_equal(np.isnan(codec_data), np.isnan(ref_data))
        assert np.allclose(codec_data, ref_data, equal_nan=True, rtol=1e-6, atol=1e-6)


class TestGrib2CodecDRT41:
    """Test PNG compression (DRT 41) decoding.

    **Validates: Requirement 3.4**
    """

    def test_drt41_decode(self):
        """Decode a DRT 41 (PNG) message and compare to _data()."""
        filepath = os.path.join(INPUT_DATA, "gfs.png.grib2")
        msg_idx = _find_first_message_with_drt(filepath, 41)
        assert msg_idx is not None, "No DRT 41 message found in test file"

        codec_data, ref_data, _, _ = _decode_message(filepath, msg_idx)

        assert codec_data.shape == ref_data.shape
        assert np.array_equal(np.isnan(codec_data), np.isnan(ref_data))
        assert np.allclose(codec_data, ref_data, equal_nan=True, rtol=1e-6, atol=1e-6)


# ===========================================================================
# 3. Bitmap handling tests
# ===========================================================================

class TestGrib2CodecBitmap:
    """Test bitmap handling using gfs.t00z.pgrb2.1p00.f024 (which contains bitmap messages).

    The task originally referenced blend.t00z.core.f001.co_4x_reduce.grib2 for
    bitmap testing, but that file has bmapflag=255 on all messages (no bitmaps).
    gfs.t00z.pgrb2.1p00.f024 contains 34 messages with bmapflag=0.

    **Validates: Requirements 3.8, 3.9**
    """

    @pytest.fixture
    def bitmap_file(self):
        return os.path.join(INPUT_DATA, "gfs.t00z.pgrb2.1p00.f024")

    def _find_bitmap_message(self, filepath):
        """Find the first message with a bitmap in the file."""
        with open(filepath, "rb") as fh:
            index = build_index(fh)
        n_msgs = len(index["section0"])
        for i in range(n_msgs):
            if index["bmapflag"][i] in {0, 254}:
                return i
        return None

    def test_bitmap_message_exists(self, bitmap_file):
        """The test file must contain at least one bitmap message."""
        msg_idx = self._find_bitmap_message(bitmap_file)
        assert msg_idx is not None, "No bitmap message found in test file"

    def test_bitmap_nan_placement(self, bitmap_file):
        """Bitmap-masked grid points must be NaN in codec output.

        **Validates: Requirement 3.8**
        """
        msg_idx = self._find_bitmap_message(bitmap_file)
        assert msg_idx is not None

        codec_data, ref_data, has_bitmap, _ = _decode_message(bitmap_file, msg_idx)
        assert has_bitmap, "Expected a bitmap message"

        # Both must have NaN values at the same positions
        codec_nans = np.isnan(codec_data)
        ref_nans = np.isnan(ref_data)

        assert codec_nans.sum() > 0, "Expected NaN values in bitmap message"
        assert np.array_equal(codec_nans, ref_nans), (
            f"NaN placement mismatch: codec NaN count={codec_nans.sum()}, "
            f"ref NaN count={ref_nans.sum()}"
        )

    def test_bitmap_non_nan_values_match(self, bitmap_file):
        """Non-NaN values must match between codec and reference for bitmap messages.

        **Validates: Requirement 3.9**
        """
        msg_idx = self._find_bitmap_message(bitmap_file)
        assert msg_idx is not None

        codec_data, ref_data, has_bitmap, _ = _decode_message(bitmap_file, msg_idx)
        assert has_bitmap

        mask = ~np.isnan(ref_data)
        assert mask.any(), "Expected some non-NaN values"
        assert np.allclose(
            codec_data[mask], ref_data[mask], rtol=1e-6, atol=1e-6
        )

    def test_bitmap_decode_shape(self, bitmap_file):
        """Codec output shape must match reference for bitmap messages.

        **Validates: Requirement 3.2**
        """
        msg_idx = self._find_bitmap_message(bitmap_file)
        assert msg_idx is not None

        codec_data, ref_data, _, _ = _decode_message(bitmap_file, msg_idx)
        assert codec_data.shape == ref_data.shape
