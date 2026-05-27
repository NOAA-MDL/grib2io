import pytest
import xarray as xr
from numpy.testing import assert_array_equal

import grib2io

# List of all GRIB2 files in test data
GRIB2_FILES = [
    "2024101012_Milton_Adv22_e70_cum_dat.grb",
    "blend.t00z.core.f001.co_4x_reduce.grib2",
    "ds.temp.bin",
    "gefs.chem.t00z.a2d_0p25.f000.grib2_subset",
    "gfs.complex.grib2",
    "gfs.jpeg.grib2",
    "gfs.png.grib2",
    "gfs.t00z.pgrb2.1p00.f024",
    "gfs_20221107/gfs.t00z.pgrb2.1p00.f009_subset",
]

# create subset test data below by first generating a subset with wgrib2:
# wgrib2 file.grb2 -small_grib min_lon:max_lon min_lat:max_lat out.grb2
# then read section3 of out.grb with grib2io:
# import grib2io
# msgs = grib2io.open("out.grb2")
# print(msgs[0].section3)
# the print reflects wgrib2's use of South to North grid point ordering and
# scanning mode value 64 (i.e S->N, last entry); grib2io uses N->S, so for
# test data, change scanning mode to zero (i.e. N->S), and swap the wgrib2
# values for latitudeFirstGridpoint and latitudeLastGridpoint (17th and
# 20th entries)

parametrize_data = [
    pytest.param(
        "rap.tsoil.gdt32769.grib2",
        (43, 32.7),
        (-281, -243),
        ValueError,
        id="RAP grid not supported.",
    ),
    pytest.param(
        "gfs_20221107/gfs.t00z.pgrb2.1p00.f012_subset",
        None,
        (-281, -243),
        [
            0,
            7059,
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
            39,
            181,
            0,
            -1,
            90000000,
            79000000,
            48,
            -90000000,
            117000000,
            1000000,
            1000000,
            0,
        ],
        id="Valid subset with lats=None.",
    ),
    pytest.param(
        "gfs_20221107/gfs.t00z.pgrb2.1p00.f009_subset",
        (32.7, 43),
        None,
        [
            0,
            3960,
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
            360,
            11,
            0,
            -1,
            43000000,
            0,
            48,
            33000000,
            359000000,
            1000000,
            1000000,
            0,
        ],
        id="Valid subset with lons=None.",
    ),
    pytest.param(
        "gfs_20221107/gfs.t00z.pgrb2.1p00.f012_subset",
        None,
        None,
        [
            0,
            65160,
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
            360,
            181,
            0,
            -1,
            90000000,
            0,
            48,
            -90000000,
            359000000,
            1000000,
            1000000,
            0,
        ],
        id="Valid subset with lats=None and lons=None",
    ),
    pytest.param(
        "gfs_20221107/gfs.t00z.pgrb2.1p00.f012_subset",
        (32.7, 43),
        (-281, -243),
        [
            0,
            429,
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
            39,
            11,
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
        id="Valid ",
    ),
]


@pytest.mark.parametrize(
    "filename, lats, lons, expected",
    parametrize_data,
)
def test_message_subset(request, filename, lats, lons, expected):
    """Test subsetting messages from various GRIB2 files."""
    datadir = request.config.rootdir / "tests" / "input_data"
    filepath = datadir / filename

    with grib2io.open(filepath) as msgs:
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                msgs[0].subset(lats=lats, lons=lons)
        else:
            newmsg = msgs[0].subset(lats=lats, lons=lons)
            assert_array_equal(newmsg.section3, expected)


@pytest.mark.parametrize("filename", GRIB2_FILES)
def test_file_open_and_basic_subset(request, filename):
    """Test that all GRIB2 files can be opened and basic subset operations work."""
    datadir = request.config.rootdir / "tests" / "input_data"
    filepath = datadir / filename

    with grib2io.open(filepath) as msgs:
        # Try a basic subset operation that should work for most files
        msg = msgs[0]
        # Get grid info to determine reasonable subset bounds
        lats, lons = msg.latlons()
        lat_min, lat_max = float(lats.min()), float(lats.max())
        lon_min, lon_max = float(lons.min()), float(lons.max())

        # Create a small subset in the middle of the grid
        lat_center = (lat_min + lat_max) / 2
        lon_center = (lon_min + lon_max) / 2
        lat_range = (lat_max - lat_min) * 0.1  # 10% of range
        lon_range = (lon_max - lon_min) * 0.1

        subset_lats = (lat_center - lat_range / 2, lat_center + lat_range / 2)
        subset_lons = (lon_center - lon_range / 2, lon_center + lon_range / 2)

        # Attempt subset - should not raise exception
        subset_msg = msg.subset(lats=subset_lats, lons=subset_lons)
        assert subset_msg is not None


def test_xarray_subset_original_case(request):
    """Test the original xarray subset functionality."""
    datadir = request.config.rootdir / "tests" / "input_data"

    filters = {
        "typeOfFirstFixedSurface": 103,
        "valueOfFirstFixedSurface": 2,
        "productDefinitionTemplateNumber": 0,
        "shortName": "TMP",
    }

    ds = xr.open_mfdataset(
        [
            datadir / "gfs_20221107" / "gfs.t00z.pgrb2.1p00.f009_subset",
            datadir / "gfs_20221107" / "gfs.t00z.pgrb2.1p00.f012_subset",
        ],
        combine="nested",
        concat_dim="leadTime",
        engine="grib2io",
        filters=filters,
        coords="different",
        compat="no_conflicts",
    )

    lats, lons = (32.7, 43), (79 - 360, 117 - 360)
    expected = [
        # lats and lons test
        [
            0,
            429,
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
            39,
            11,
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
        # lats=None test
        [
            0,
            7059,
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
            39,
            181,
            0,
            -1,
            90000000,
            79000000,
            48,
            -90000000,
            117000000,
            1000000,
            1000000,
            0,
        ],
        # lons=None test
        [
            0,
            3960,
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
            360,
            11,
            0,
            -1,
            43000000,
            0,
            48,
            33000000,
            359000000,
            1000000,
            1000000,
            0,
        ],
        # lats=None and lons=None test
        [
            0,
            65160,
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
            360,
            181,
            0,
            -1,
            90000000,
            0,
            48,
            -90000000,
            359000000,
            1000000,
            1000000,
            0,
        ],
    ]

    # lats and lons test
    newds_xr = ds["TMP"].grib2io.subset(lats=lats, lons=lons)
    newds_gr = ds.grib2io.subset(lats=lats, lons=lons)
    assert_array_equal(newds_xr.attrs["GRIB2IO_section3"], expected[0])
    assert_array_equal(newds_gr["TMP"].attrs["GRIB2IO_section3"], expected[0])

    # lats=None test
    newds_xr = ds["TMP"].grib2io.subset(lats=None, lons=lons)
    newds_gr = ds.grib2io.subset(lats=None, lons=lons)
    assert_array_equal(newds_xr.attrs["GRIB2IO_section3"], expected[1])
    assert_array_equal(newds_gr["TMP"].attrs["GRIB2IO_section3"], expected[1])

    # lons=None test
    newds_xr = ds["TMP"].grib2io.subset(lats=lats, lons=None)
    newds_gr = ds.grib2io.subset(lats=lats, lons=None)
    assert_array_equal(newds_xr.attrs["GRIB2IO_section3"], expected[2])
    assert_array_equal(newds_gr["TMP"].attrs["GRIB2IO_section3"], expected[2])

    # lats=None and lons=None test
    newds_xr = ds["TMP"].grib2io.subset(lats=None, lons=None)
    newds_gr = ds.grib2io.subset(lats=None, lons=None)
    assert_array_equal(newds_xr.attrs["GRIB2IO_section3"], expected[3])
    assert_array_equal(newds_gr["TMP"].attrs["GRIB2IO_section3"], expected[3])


@pytest.fixture()
def inp_ds(request):
    datadir = request.config.rootdir / "tests" / "input_data" / "gfs_20221107"

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
    datadir = request.config.rootdir / "tests" / "input_data" / "gfs_20221107"

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
                429,
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
                39,
                11,
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
