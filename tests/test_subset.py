import pytest
import xarray as xr
from numpy.testing import assert_array_equal

import grib2io


@pytest.fixture()
def inp_ds(request):
    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

    filters = {
        "typeOfFirstFixedSurface": 103,
        "valueOfFirstFixedSurface": 2,
        "productDefinitionTemplateNumber": 0,
        "shortName": "TMP",
    }

    ids = xr.open_mfdataset(
        [
            datadir / "gfs.t00z.pgrb2.1p00.f009_subset",
            datadir / "gfs.t00z.pgrb2.1p00.f012_subset",
        ],
        combine="nested",
        concat_dim="leadTime",
        engine="grib2io",
        filters=filters,
    )

    yield ids


@pytest.fixture()
def inp_msgs(request):
    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

    with grib2io.open(datadir / "gfs.t00z.pgrb2.1p00.f012_subset") as imsgs:
        yield imsgs


@pytest.mark.parametrize(
    "lats, lons, expected_section3",
    [
        pytest.param(
            (43, 32.7),
            (117, 79),
            [
                0,
                380,
                0,
                0,
                0,
                6,
                0,
                0,
                0,
                0,
                0,
                0,
                38,
                10,
                0,
                -1,
                43000000,
                79000000,
                48,
                33000000,
                117000000,
                1000000,
                1000000,
                0,
            ],
            id="subset_1",
        ),
    ],
)
def test_message_subset(inp_msgs, inp_ds, lats, lons, expected_section3):
    """Test subsetting a single DataArray to a single grib2 message."""
    newmsg = inp_msgs[0].subset(lats=lats, lons=lons)
    assert_array_equal(newmsg.section3, expected_section3)

    newds = inp_ds["TMP"].grib2io.subset(lats=lats, lons=lons)
    assert_array_equal(newds.attrs["GRIB2IO_section3"], expected_section3)

    newds = inp_ds.grib2io.subset(lats=lats, lons=lons)
    assert_array_equal(newds["TMP"].attrs["GRIB2IO_section3"], expected_section3)
