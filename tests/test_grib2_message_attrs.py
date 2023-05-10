import pytest
import grib2io
import numpy as np
import datetime

def test_section0_attrs(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg9 = f[8]
    expected_section0 = np.array([1196575042, 0, 0, 2, 69489])
    np.testing.assert_array_equal(expected_section0, msg9.section0)
    assert msg9.indicatorSection is msg9.section0
    assert msg9.discipline.value == 0
    assert msg9.discipline.definition == 'Meteorological Products'

def test_section1_attrs(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg9 = f[8]
    expected_section1 = np.array([   7,    0,    2,    1,    1, 2022,   11,    7,    0,    0,    0,
               0,    1])
    np.testing.assert_array_equal(expected_section1, msg9.section1)
    assert msg9.identificationSection is msg9.section1
    assert msg9.originatingCenter.value == 7
    assert msg9.originatingCenter.definition == 'US National Weather Service - NCEP (WMC)'
    assert msg9.originatingSubCenter.value == 0
    assert msg9.originatingSubCenter.definition is None
    assert msg9.localTableInfo.value == 1
    assert msg9.localTableInfo.definition == 'Number of local table version used.'
    assert msg9.significanceOfReferenceTime.value == 1
    assert msg9.significanceOfReferenceTime.definition == 'Start of Forecast'
    assert msg9.year == 2022
    assert msg9.month == 11
    assert msg9.day == 7
    assert msg9.hour == 0
    assert msg9.minute == 0
    assert msg9.second == 0
    assert msg9.refDate == datetime.datetime(2022,11,7)
    assert msg9.productionStatus.value == 0
    assert msg9.productionStatus.definition == 'Operational Products'
    assert msg9.typeOfData.value == 1
    assert msg9.typeOfData.definition == 'Forecast Products'

def test_section3(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg9 = f[8]
    expected_section3 = np.array([        0,     65160,         0,         0,         0,         6,
               0,         0,         0,         0,         0,         0,
             360,       181,         0,        -1,  90000000,         0,
              48, -90000000, 359000000,   1000000,   1000000,         0])
    np.testing.assert_array_equal(expected_section3, msg9.section3)
    np.testing.assert_array_equal(expected_section3[:5], msg9.gridDefinitionSection)
    assert msg9.sourceOfGridDefinition.value == 0
    assert msg9.sourceOfGridDefinition.definition == 'Specified in Code Table 3.1'


