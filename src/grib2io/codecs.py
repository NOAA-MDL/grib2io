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

try:
    from numcodecs.abc import Codec
    from numcodecs.registry import register_codec

    _HAS_NUMCODECS = True
except ImportError:
    _HAS_NUMCODECS = False
    Codec = object  # type: ignore[assignment,misc]

    def register_codec(cls):  # type: ignore[misc]
        pass


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
        if not _HAS_NUMCODECS:
            raise ImportError("numcodecs is required for Grib2Codec. Install with: pip install grib2io[kerchunk]")
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
        """Decode raw GRIB2 section 7 bytes into a NumPy array."""
        if not isinstance(buf, bytes):
            buf = bytes(buf)

        fld = _decode_grib2_bytes(
            buf,
            drtn=self.drtn,
            drt=list(self.drt) if not isinstance(self.drt, list) else self.drt,
            gdtn=self.gdtn,
            gdt=list(self.gdt) if not isinstance(self.gdt, list) else self.gdt,
            nx=self.nx,
            ny=self.ny,
            bitmap_flag=self.bitmap_flag,
            bitmap_length=self.bitmap_length,
            scan_mode_flags=list(self.scan_mode_flags) if self.scan_mode_flags is not None else None,
            type_of_values=self.type_of_values,
            number_of_data_points=self.number_of_data_points,
            number_of_packed_values=self.number_of_packed_values,
        )

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


# ---------------------------------------------------------------------------
# Zarr v3 ArrayBytesCodec implementation
# ---------------------------------------------------------------------------

try:
    from dataclasses import dataclass
    from zarr.abc.codec import ArrayBytesCodec
    from zarr.core.array_spec import ArraySpec
    from zarr.core.buffer import Buffer, NDBuffer
    import zarr.registry as _zarr_registry

    _HAS_ZARR_V3 = True
except ImportError:
    _HAS_ZARR_V3 = False


if _HAS_ZARR_V3:

    @dataclass(frozen=True)
    class Grib2SerializerCodec(ArrayBytesCodec):
        """Zarr v3 ``ArrayBytesCodec`` (serializer) for GRIB2 virtual chunks.

        Receives the raw GRIB2 section 7 bytes fetched from a virtual chunk
        reference and decodes them into a NumPy array using
        ``g2clib.unpack7()``.  This is the zarr v3 counterpart of
        :class:`Grib2Codec` (which targets numcodecs / zarr v2).

        All constructor parameters mirror those of :class:`Grib2Codec` and
        are stored in ``zarr.json`` so they travel with the array metadata.
        """

        is_fixed_size: bool = False  # GRIB2 compressed size varies

        # ---- GRIB2 decode parameters (mirror Grib2Codec) ----
        drtn: int = 0
        drt: tuple = ()
        gdtn: int = 0
        gdt: tuple = ()
        gds: tuple = ()
        nx: int = 0
        ny: int = 0
        bitmap_flag: int = 255
        bitmap_offset: Optional[int] = None
        bitmap_length: Optional[int] = None
        scan_mode_flags: Optional[tuple] = None
        type_of_values: int = 0
        number_of_data_points: int = 0
        number_of_packed_values: int = 0

        # dataclass frozen=True uses __init__ auto-generated; we need a
        # custom __init__ to accept list args and coerce to tuples.
        def __new__(cls, **kwargs):
            # coerce list args to tuples so the frozen dataclass is hashable
            for f in ("drt", "gdt", "gds", "scan_mode_flags"):
                if f in kwargs and isinstance(kwargs[f], list):
                    kwargs[f] = tuple(kwargs[f])
            obj = object.__new__(cls)
            return obj

        def __init__(
            self,
            *,
            drtn: int = 0,
            drt=(),
            gdtn: int = 0,
            gdt=(),
            gds=(),
            nx: int = 0,
            ny: int = 0,
            bitmap_flag: int = 255,
            bitmap_offset: Optional[int] = None,
            bitmap_length: Optional[int] = None,
            scan_mode_flags=None,
            type_of_values: int = 0,
            number_of_data_points: int = 0,
            number_of_packed_values: int = 0,
        ):
            object.__setattr__(self, "drtn", int(drtn))
            object.__setattr__(self, "drt", tuple(drt) if drt is not None else ())
            object.__setattr__(self, "gdtn", int(gdtn))
            object.__setattr__(self, "gdt", tuple(gdt) if gdt is not None else ())
            object.__setattr__(self, "gds", tuple(gds) if gds is not None else ())
            object.__setattr__(self, "nx", int(nx))
            object.__setattr__(self, "ny", int(ny))
            object.__setattr__(self, "bitmap_flag", int(bitmap_flag))
            object.__setattr__(self, "bitmap_offset", bitmap_offset)
            object.__setattr__(self, "bitmap_length", bitmap_length)
            object.__setattr__(self, "scan_mode_flags", tuple(scan_mode_flags) if scan_mode_flags is not None else None)
            object.__setattr__(self, "type_of_values", int(type_of_values))
            object.__setattr__(self, "number_of_data_points", int(number_of_data_points))
            object.__setattr__(self, "number_of_packed_values", int(number_of_packed_values))

        # ---- zarr v3 codec interface --------------------------------

        @classmethod
        def from_dict(cls, data: dict) -> "Grib2SerializerCodec":
            cfg = data.get("configuration", {})
            return cls(**cfg)

        def to_dict(self) -> dict:
            return {
                "name": "grib2io",
                "configuration": {
                    "drtn": self.drtn,
                    "drt": list(self.drt),
                    "gdtn": self.gdtn,
                    "gdt": list(self.gdt),
                    "gds": list(self.gds),
                    "nx": self.nx,
                    "ny": self.ny,
                    "bitmap_flag": self.bitmap_flag,
                    "bitmap_offset": self.bitmap_offset,
                    "bitmap_length": self.bitmap_length,
                    "scan_mode_flags": list(self.scan_mode_flags) if self.scan_mode_flags else None,
                    "type_of_values": self.type_of_values,
                    "number_of_data_points": self.number_of_data_points,
                    "number_of_packed_values": self.number_of_packed_values,
                },
            }

        def compute_encoded_size(self, input_byte_length: int, chunk_spec: "ArraySpec") -> int:
            raise NotImplementedError("Grib2SerializerCodec has variable encoded size")

        async def _decode_single(
            self,
            chunk_bytes: "Buffer",
            chunk_spec: "ArraySpec",
        ) -> "NDBuffer":
            raw = bytes(chunk_bytes.as_array_like())
            fld = _decode_grib2_bytes(
                raw,
                drtn=self.drtn,
                drt=list(self.drt),
                gdtn=self.gdtn,
                gdt=list(self.gdt),
                nx=self.nx,
                ny=self.ny,
                bitmap_flag=self.bitmap_flag,
                bitmap_length=self.bitmap_length,
                scan_mode_flags=list(self.scan_mode_flags) if self.scan_mode_flags else None,
                type_of_values=self.type_of_values,
                number_of_data_points=self.number_of_data_points,
                number_of_packed_values=self.number_of_packed_values,
            )
            # Reshape to the full chunk shape zarr expects (e.g. [1,1,1,1,ny,nx])
            if fld.shape != chunk_spec.shape:
                fld = fld.reshape(chunk_spec.shape)
            return chunk_spec.prototype.nd_buffer.from_ndarray_like(fld)

        async def _encode_single(
            self,
            chunk_array: "NDBuffer",
            chunk_spec: "ArraySpec",
        ) -> Optional["Buffer"]:
            raise NotImplementedError("Grib2SerializerCodec is decode-only")

    _zarr_registry.register_codec("grib2io", Grib2SerializerCodec)


def _decode_grib2_bytes(
    raw: bytes,
    *,
    drtn: int,
    drt: List[int],
    gdtn: int,
    gdt: List[int],
    nx: int,
    ny: int,
    bitmap_flag: int,
    bitmap_length: Optional[int],
    scan_mode_flags: Optional[List[int]],
    type_of_values: int,
    number_of_data_points: int,
    number_of_packed_values: int,
) -> np.ndarray:
    """Shared GRIB2 decode logic used by both :class:`Grib2Codec` (numcodecs)
    and :class:`Grib2SerializerCodec` (zarr v3).
    """
    gdt_arr = np.array(gdt, dtype=np.int64)
    drt_arr = np.array(drt, dtype=np.int64)

    storageorder = "C"
    if scan_mode_flags is not None and len(scan_mode_flags) > 2:
        storageorder = "F" if scan_mode_flags[2] else "C"

    bmap = None
    sec7_buf = raw
    if bitmap_flag in {0, 254} and bitmap_length is not None and bitmap_length > 0:
        bmap_bytes = raw[:bitmap_length]
        sec7_buf = raw[bitmap_length:]
        _bmapflag, bmap, _bpos = g2clib.unpack6(bmap_bytes, number_of_data_points)

    fld1, _ipos = g2clib.unpack7(
        sec7_buf,
        gdtn,
        gdt_arr,
        drtn,
        drt_arr,
        number_of_packed_values,
        storageorder=storageorder,
    )

    if bitmap_flag in {0, 254}:
        if bmap is not None:
            fld = np.full(number_of_data_points, np.nan, dtype=np.float32)
            np.put(fld, np.nonzero(bmap), fld1)
        else:
            fld = fld1
    else:
        fld = fld1

    fld = np.reshape(fld, (ny, nx))

    if scan_mode_flags is not None and len(scan_mode_flags) > 3:
        if scan_mode_flags[3]:
            fldsave = fld.astype(np.float32)
            fld[1::2, :] = fldsave[1::2, ::-1]

    if type_of_values == 1:
        fld = fld.astype(np.int32)

    return fld
