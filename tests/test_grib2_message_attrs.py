import pytest
import numpy as np
import datetime
import grib2io

def test_section0_attrs(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        msg = f[8]
    expected_section0 = np.array([1196575042, 0, 0, 2, 69146])
    np.testing.assert_array_equal(expected_section0, msg.section0)
    np.testing.assert_array_equal(msg.indicatorSection, expected_section0)
    assert msg.discipline.value == 0
    assert msg.discipline.definition == 'Meteorological Products'

def test_section1_attrs(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        msg = f[8]
    expected_section1 = np.array([   7,    0,    2,    1,    1, 2022,   11,    7,    0,    0,    0,
               0,    1])
    np.testing.assert_array_equal(expected_section1, msg.section1)
    assert msg.identificationSection is msg.section1
    assert msg.originatingCenter.value == 7
    assert msg.originatingCenter.definition == 'US National Weather Service - NCEP (WMC)'
    assert msg.originatingSubCenter.value == 0
    assert msg.originatingSubCenter.definition is None
    assert msg.localTableInfo.value == 1
    assert msg.localTableInfo.definition == 'Number of local table version used.'
    assert msg.significanceOfReferenceTime.value == 1
    assert msg.significanceOfReferenceTime.definition == 'Start of Forecast'
    assert msg.year == 2022
    assert msg.month == 11
    assert msg.day == 7
    assert msg.hour == 0
    assert msg.minute == 0
    assert msg.second == 0
    assert msg.refDate == datetime.datetime(2022,11,7)
    assert msg.productionStatus.value == 0
    assert msg.productionStatus.definition == 'Operational Products'
    assert msg.typeOfData.value == 1
    assert msg.typeOfData.definition == 'Forecast Products'

def test_section3(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        msg = f[8]
    expected_section3 = np.array([        0,     65160,         0,         0,         0,         6,
               0,         0,         0,         0,         0,         0,
             360,       181,         0,        -1,  90000000,         0,
              48, -90000000, 359000000,   1000000,   1000000,         0])
    np.testing.assert_array_equal(expected_section3, msg.section3)
    np.testing.assert_array_equal(expected_section3[:5], msg.gridDefinitionSection)
    assert msg.sourceOfGridDefinition.value == 0
    assert msg.sourceOfGridDefinition.definition == 'Specified in Code Table 3.1'


