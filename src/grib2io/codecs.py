"""
GRIB2 Codec for Zarr / numcodecs
=================================

Provides :class:`Grib2Codec`, a ``numcodecs.abc.Codec`` implementation that
decodes raw GRIB2 section 7 bytes into NumPy arrays.  This codec is registered
with the numcodecs registry so that Zarr can transparently decode GRIB2 data
chunks when reading through a Kerchunk reference manifest or an Icechunk
virtual store.

The codec is **decode-only**; encoding (writing GRIB2 data) is handled by
:func:`grib2io.open`.
"""

from typing import List, Optional

import numpy as np

from . import g2clib


# ---------------------------------------------------------------------------
# Lazy import guard
# ---------------------------------------------------------------------------


def _ensure_numcodecs():
    """Raise ``ImportError`` if *numcodecs* is not available."""
    try:
        import numcodecs  # noqa: F401
    except ImportError:
        raise ImportError("numcodecs is required for the GRIB2 codec. Install with: pip install grib2io[kerchunk]")


# ---------------------------------------------------------------------------
# Codec implementation
# ---------------------------------------------------------------------------

_ensure_numcodecs()

from numcodecs.abc import Codec  # noqa: E402
from numcodecs.registry import register_codec  # noqa: E402


class Grib2Codec(Codec):
    """Zarr codec for decoding raw GRIB2 section 7 bytes.

    All constructor parameters are JSON-serializable integers or lists
    extracted from the GRIB2 message's section metadata at
    reference-generation time.  Together they carry everything needed to
    call ``g2clib.unpack7()`` — the same low-level routine used by
    ``grib2io._data()``.
    """

    codec_id = "grib2io"

    def __init__(
        self,
        drtn: int,
        drt: List[int],
        gdtn: int,
        gdt: List[int],
        gds: List[int],
        nx: int,
        ny: int,
        bitmap_flag: int,
        bitmap_offset: Optional[int] = None,
        bitmap_length: Optional[int] = None,
        scan_mode_flags: Optional[List[int]] = None,
        type_of_values: int = 0,
        number_of_data_points: int = 0,
        number_of_packed_values: int = 0,
    ):
        self.drtn = drtn
        self.drt = list(drt)
        self.gdtn = gdtn
        self.gdt = list(gdt)
        self.gds = list(gds)
        self.nx = nx
        self.ny = ny
        self.bitmap_flag = bitmap_flag
        self.bitmap_offset = bitmap_offset
        self.bitmap_length = bitmap_length
        self.scan_mode_flags = list(scan_mode_flags) if scan_mode_flags is not None else None
        self.type_of_values = type_of_values
        self.number_of_data_points = number_of_data_points
        self.number_of_packed_values = number_of_packed_values

    # ---- encode (not supported) ------------------------------------------

    def encode(self, buf):
        """Not supported — GRIB2 encoding is handled by ``grib2io.open()``."""
        raise NotImplementedError("Grib2Codec is decode-only; GRIB2 encoding is handled by grib2io.open()")

    # ---- decode ----------------------------------------------------------

    def decode(self, buf, out=None):
        """Decode raw GRIB2 section 7 bytes into a NumPy array.

        Parameters
        ----------
        buf : bytes-like
            Raw bytes of GRIB2 section 7 (including the 5-byte section
            header with size and section number).  When a bitmap is
            present and ``bitmap_length`` is set, the bitmap section
            bytes are expected to be prepended to the section 7 bytes
            so that ``buf[:bitmap_length]`` contains the bitmap and
            ``buf[bitmap_length:]`` contains section 7.
        out : numpy.ndarray, optional
            Pre-allocated output array.  If provided the decoded values
            are written into *out* and it is returned.

        Returns
        -------
        numpy.ndarray
            Decoded data with shape ``(ny, nx)``.
        """
        if not isinstance(buf, bytes):
            buf = bytes(buf)

        gdt = np.array(self.gdt, dtype=np.int64)
        drt = np.array(self.drt, dtype=np.int64)

        # Determine storage order from scan mode flags
        storageorder = "C"
        if self.scan_mode_flags is not None and len(self.scan_mode_flags) > 2:
            storageorder = "F" if self.scan_mode_flags[2] else "C"

        # When bitmap bytes are prepended, split the buffer into bitmap
        # and section 7 portions *before* calling unpack7.
        bmap = None
        sec7_buf = buf
        if self.bitmap_flag in {0, 254} and self.bitmap_length is not None and self.bitmap_length > 0:
            bmap_bytes = buf[: self.bitmap_length]
            sec7_buf = buf[self.bitmap_length :]
            _bmapflag, bmap, _bpos = g2clib.unpack6(bmap_bytes, self.number_of_data_points)

        # Unpack section 7 data
        fld1, _ipos = g2clib.unpack7(
            sec7_buf,
            self.gdtn,
            gdt,
            self.drtn,
            drt,
            self.number_of_packed_values,
            storageorder=storageorder,
        )

        # Apply bitmap masking when bitmap is present
        if self.bitmap_flag in {0, 254}:
            ngrdpts = self.number_of_data_points
            if bmap is not None:
                fld = np.full(ngrdpts, np.nan, dtype=np.float32)
                np.put(fld, np.nonzero(bmap), fld1)
            else:
                # No bitmap bytes available — return the unpacked data as-is.
                fld = fld1
        else:
            fld = fld1

        # Reshape to 2-D grid
        fld = np.reshape(fld, (self.ny, self.nx))

        # Handle alternating row scan mode
        if self.scan_mode_flags is not None and len(self.scan_mode_flags) > 3:
            if self.scan_mode_flags[3]:
                fldsave = fld.astype(np.float32)
                fld[1::2, :] = fldsave[1::2, ::-1]

        # Convert to int32 if typeOfValues indicates integer data
        if self.type_of_values == 1:
            fld = fld.astype(np.int32)

        if out is not None:
            np.copyto(out, fld)
            return out

        return fld

    # ---- config serialization --------------------------------------------

    def get_config(self):
        """Return a JSON-serializable dict of all codec parameters."""
        return {
            "id": self.codec_id,
            "drtn": self.drtn,
            "drt": self.drt,
            "gdtn": self.gdtn,
            "gdt": self.gdt,
            "gds": self.gds,
            "nx": self.nx,
            "ny": self.ny,
            "bitmap_flag": self.bitmap_flag,
            "bitmap_offset": self.bitmap_offset,
            "bitmap_length": self.bitmap_length,
            "scan_mode_flags": self.scan_mode_flags,
            "type_of_values": self.type_of_values,
            "number_of_data_points": self.number_of_data_points,
            "number_of_packed_values": self.number_of_packed_values,
        }

    @classmethod
    def from_config(cls, config):
        """Reconstruct the codec from a configuration dict.

        Parameters
        ----------
        config : dict
            Dictionary as returned by :meth:`get_config`.

        Returns
        -------
        Grib2Codec
        """
        # Remove the 'id' key which is not a constructor parameter
        cfg = {k: v for k, v in config.items() if k != "id"}
        return cls(**cfg)


register_codec(Grib2Codec)
