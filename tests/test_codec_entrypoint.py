"""
Tests for GRIB2 codec auto-discovery via package entry points.

The grib2io Zarr v2 / numcodecs codec is advertised through the
``numcodecs.codecs`` entry-point group so that ``numcodecs`` can lazily load
it the first time it encounters a ``grib2io`` codec id in a Zarr ``.zarray``
manifest -- *without* any prior ``import grib2io.codecs``.

This decoupling is what allows a generic (GRIB2-agnostic) reader, or a plain
``xarray.open_zarr`` call, to decode a grib2io Kerchunk reference.  These tests
guard that contract.
"""

import os
import subprocess
import sys
import tempfile

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="kerchunk support requires Python >= 3.11",
)

pytest.importorskip("numcodecs", reason="numcodecs is not installed")
pytest.importorskip("fsspec", reason="fsspec is not installed")

INPUT_DATA = os.path.join(os.path.dirname(__file__), "input_data")
GRIB2_FILE = os.path.join(INPUT_DATA, "gfs.complex.grib2")


def test_grib2io_codec_advertised_in_numcodecs_entry_points():
    """grib2io must register its codec in the ``numcodecs.codecs`` group."""
    from importlib.metadata import entry_points

    eps = entry_points().select(group="numcodecs.codecs")
    mapping = {e.name: e.value for e in eps}

    assert "grib2io" in mapping, f"grib2io codec is not advertised in the 'numcodecs.codecs' entry-point group; found: {sorted(mapping)}"
    assert mapping["grib2io"] == "grib2io.codecs:Grib2Codec"


def test_codec_auto_loads_from_entry_point_without_import():
    """numcodecs should auto-load the codec on first ``get_codec`` use.

    We clear any already-registered ``grib2io`` codec from the live registry,
    then ask numcodecs for it by id.  If the entry point is wired correctly,
    numcodecs loads ``grib2io.codecs:Grib2Codec`` on demand.
    """
    import numcodecs
    from numcodecs import registry

    # Make sure discovery does not see a previously-registered class.
    registry.codec_registry.pop("grib2io", None)
    # Refresh the entry-point cache (in case the registry was imported before
    # grib2io was installed in this interpreter).
    registry.run_entrypoints()

    config = {
        "id": "grib2io",
        "drtn": 0,
        "drt": [],
        "gdtn": 0,
        "gdt": [],
        "gds": [],
        "nx": 1,
        "ny": 1,
        "bitmap_flag": 255,
    }
    codec = numcodecs.get_codec(config)
    assert type(codec).__name__ == "Grib2Codec"
    assert type(codec).codec_id == "grib2io"


@pytest.mark.skipif(not os.path.isfile(GRIB2_FILE), reason="sample GRIB2 file missing")
def test_reference_decodes_in_fresh_process_without_grib2io_import():
    """A grib2io Kerchunk reference decodes via plain ``xr.open_zarr``.

    The reference is built in this process (which uses grib2io), then opened in
    a *fresh* subprocess that never imports grib2io.  Decoding succeeds only if
    numcodecs auto-loaded the ``grib2io`` codec from its entry point.
    """
    pytest.importorskip("xarray")
    from grib2io.kerchunk import ReferenceGenerator

    with tempfile.TemporaryDirectory(prefix="grib2io_ep_test_") as tmpdir:
        ref_path = os.path.join(tmpdir, "reference.json")
        gen = ReferenceGenerator([GRIB2_FILE])
        gen.generate()
        gen.to_json(ref_path)

        child = (
            "import sys, numpy as np, fsspec, xarray as xr\n"
            "import numcodecs\n"
            # Must NOT be registered before the open in a fresh interpreter.
            "assert 'grib2io' not in numcodecs.registry.codec_registry, "
            "'grib2io codec unexpectedly pre-registered'\n"
            "fs = fsspec.filesystem('reference', fo=sys.argv[1])\n"
            "ds = xr.open_zarr(fs.get_mapper(''), consolidated=False)\n"
            "v = next(iter(ds.data_vars))\n"
            "arr = ds[v].load().values\n"
            "assert np.isfinite(arr).any(), 'no finite values decoded'\n"
            "assert 'grib2io' in numcodecs.registry.codec_registry, "
            "'codec was not auto-loaded from entry point'\n"
            "print('OK', v, arr.shape)\n"
        )

        proc = subprocess.run(
            [sys.executable, "-c", child, ref_path],
            capture_output=True,
            text=True,
        )

    assert proc.returncode == 0, f"fresh-process decode failed.\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "OK" in proc.stdout
