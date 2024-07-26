import datetime

import pytest
import xarray as xr

TESTGRIB = xr.open_mfdataset(
    [
        "tests/data/gfs_20221107/gfs.t00z.pgrb2.1p00.f009_subset",
        "tests/data/gfs_20221107/gfs.t00z.pgrb2.1p00.f012_subset",
    ],
    combine="nested",
    concat_dim="leadTime",
    engine="grib2io",
    filters={
        "productDefinitionTemplateNumber": 0,
        "typeOfFirstFixedSurface": 103,
        "valueOfFirstFixedSurface": 2,
        "shortName": "TMP",
    },
)

ORIGINAL_ATTRS = TESTGRIB["TMP"].attrs


@pytest.mark.parametrize(
    "kwargs, expected_type, expected, error_message",
    [
        pytest.param(
            {"parameterNumber": 1},
            set,
            {
                ("shortName", "TMP"),
                ("shortName", "VTMP"),
                ("fullName", "Temperature"),
                ("fullName", "Virtual Temperature"),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   0   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   1   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
            },
            None,
            id="parameterNumber=1",
        ),
        pytest.param(
            {"parameterNumber": 2},
            set,
            {
                ("shortName", "TMP"),
                ("shortName", "POT"),
                ("fullName", "Temperature"),
                ("fullName", "Potential Temperature"),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   0   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   2   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
            },
            None,
            id="parameterNumber=2",
        ),
        pytest.param(
            {"shortName": "POT"},
            set,
            {
                ("shortName", "TMP"),
                ("shortName", "POT"),
                ("fullName", "Temperature"),
                ("fullName", "Potential Temperature"),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   0   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   2   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
            },
            None,
            id="shortName=POT",
        ),
        pytest.param(
            {
                "discipline": 0,
                "parameterCategory": 0,
                "parameterNumber": 0,
                "shortName": "POT",
            },
            set,
            {
                ("shortName", "TMP"),
                ("shortName", "POT"),
                ("fullName", "Temperature"),
                ("fullName", "Potential Temperature"),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   0   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
                (
                    "GRIB2IO_section4",
                    "[  0   0   0   2   2   0  96   0   0   1   9 103   0   2 255   0   0]",
                ),
            },
            None,
            id="last_wins",
        ),
        pytest.param(
            {
                "discipline": 0,
                "parameterCategory": 0,
                "parameterNumber": 3,
                "shortName": "TMP",
            },
            set,
            set(),
            None,
            id="tempest_in_a_teapot",
        ),
        pytest.param(
            {
                "leadTime": 4,
            },  # kwargs
            Warning,  # expected_type
            UserWarning,  # expected
            "",  # error_message
            id="warning_dims",
        ),
        pytest.param(
            {
                "leadTime": 4,
            },  # kwargs
            set,  # expected_type
            set(),  # expected
            None,
            id="warning_dims",
        ),
        pytest.param(
            {
                "zebra": 4,
            },  # kwargs
            Warning,  # expected_type
            UserWarning,  # expected
            "",  # error_message
            id="warning_not_found",
        ),
        pytest.param(
            {
                "zebra": 4,
            },  # kwargs
            set,  # expected_type
            set(),  # expected
            None,  # error_message
            id="warning_not_found",
        ),
        pytest.param(
            {
                "refDate": datetime.datetime(2022, 11, 7, 0, 0),
            },  # kwargs
            set,  # expected_type
            set(),  # expected
            None,
            id="refDate",
        ),
        pytest.param(
            {
                "refDate": datetime.datetime(2021, 11, 7, 0, 0),
            },  # kwargs
            set,  # expected_type
            {
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2022   11    7    0    0    0    0    1]",
                ),
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2021   11    7    0    0    0    0    1]",
                ),
            },  # expected
            None,
            id="refDate_year",
        ),
        pytest.param(
            {
                "year": 2021,
            },  # kwargs
            set,  # expected_type
            {
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2022   11    7    0    0    0    0    1]",
                ),
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2021   11    7    0    0    0    0    1]",
                ),
            },  # expected
            None,
            id="year",
        ),
        pytest.param(
            {
                "refDate": datetime.datetime(2022, 10, 7, 0, 0),
            },  # kwargs
            set,  # expected_type
            {
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2022   11    7    0    0    0    0    1]",
                ),
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2022   10    7    0    0    0    0    1]",
                ),
            },  # expected
            None,
            id="refDate_month",
        ),
        pytest.param(
            {
                "month": 10,
            },  # kwargs
            set,  # expected_type
            {
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2022   11    7    0    0    0    0    1]",
                ),
                (
                    "GRIB2IO_section1",
                    "[   7    0    2    1    1 2022   10    7    0    0    0    0    1]",
                ),
            },  # expected
            None,
            id="month",
        ),
    ],
)
def test_update_attrs(kwargs, expected_type, expected, error_message):
    if issubclass(expected_type, Warning):
        with pytest.warns(expected) as record:
            result = TESTGRIB["TMP"].grib2io.update_attrs(**kwargs).attrs
        if not record:
            pytest.fail("No warning raised")

    elif issubclass(expected_type, Exception):
        with pytest.raises(expected) as exc_info:
            result = TESTGRIB["TMP"].grib2io.update_attrs(**kwargs).attrs
        assert error_message == str(exc_info.value)

    elif isinstance(expected_type, type):
        tst = TESTGRIB["TMP"].grib2io.update_attrs(**kwargs).attrs

        # Convert all dictionary values to string for set comparison because
        # strings are hashable.
        result1 = {k: str(v) for k, v in tst.items()}
        result2 = {k: str(v) for k, v in ORIGINAL_ATTRS.items()}

        # Compare the two dictionaries as sets taking the symmetric difference.
        result = result1.items() ^ result2.items()

        assert isinstance(
            result, expected_type
        ), f"Expected result type {expected_type}, got {type(result)}"

        if expected is not None:
            assert result == expected, f"Expected {expected}, got {result}"
