import itertools
from pathlib import Path

import grib2io
import pytest
import xarray as xr
from numpy.testing import assert_allclose, assert_array_equal


def _del_list_inplace(input_list, indices):
    for index in sorted(indices, reverse=True):
        del input_list[index]
    return input_list


def _test_any_differences(da1, da2, atol=0.005, rtol=0):
    """Test if two DataArrays are equal, including most attributes."""
    assert_array_equal(
        da1.attrs["GRIB2IO_section0"][:-1], da2.attrs["GRIB2IO_section0"][:-1]
    )
    assert_array_equal(da1.attrs["GRIB2IO_section1"], da2.attrs["GRIB2IO_section1"])
    assert_array_equal(da1.attrs["GRIB2IO_section2"], da2.attrs["GRIB2IO_section2"])
    assert_array_equal(da1.attrs["GRIB2IO_section3"], da2.attrs["GRIB2IO_section3"])
    assert_array_equal(da1.attrs["GRIB2IO_section4"], da2.attrs["GRIB2IO_section4"])
    skip = [2, 9, 10, 11, 16, 17]
    assert_array_equal(
        _del_list_inplace(list(da1.attrs["GRIB2IO_section5"]), skip),
        _del_list_inplace(list(da2.attrs["GRIB2IO_section5"]), skip),
    )
    assert_allclose(da1.data, da2.data, atol=atol, rtol=rtol)


def test_da_write(tmp_path, request):
    """Test writing a single DataArray to a single grib2 message."""
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_da.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

    with grib2io.open(datadir / "gfs.t00z.pgrb2.1p00.f012_subset") as inp:
        print(inp[0].section3)
        newmsg = inp[0].subset(lats=(43, 32.7), lons=(117, 79))

        print(inp[0])
        print(newmsg)
        print(newmsg.section0)
        print(inp[0].section0)
        print(newmsg.section1)
        print(inp[0].section1)
        print(newmsg.section2)
        print(inp[0].section2)
        print(newmsg.section3)
        print(inp[0].section3)
        print(newmsg.section4)
        print(inp[0].section4)
        print(newmsg.section5)
        print(inp[0].section5)

        print(inp[0].data.shape)
        print(newmsg.data.shape)

    with grib2io.open(target_file, mode="w") as out:
        out.write(newmsg)
    assert False
