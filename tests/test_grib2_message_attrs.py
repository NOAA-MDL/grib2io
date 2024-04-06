import pytest
import numpy as np
import datetime
import grib2io
import hashlib

def test_section0_attrs(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['REFC'][0]
    expected_section0 = np.array([1196575042, 0, 0, 2, 69683])
    np.testing.assert_array_equal(expected_section0, msg.section0)
    np.testing.assert_array_equal(msg.indicatorSection, expected_section0)
    assert msg.discipline.value == 0
    assert msg.discipline.definition == 'Meteorological Products'

def test_section1_attrs(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['REFC'][0]
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
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['REFC'][0]
    expected_section3 = np.array([        0,     65160,         0,         0,         0,         6,
               0,         0,         0,         0,         0,         0,
             360,       181,         0,        -1,  90000000,         0,
              48, -90000000, 359000000,   1000000,   1000000,         0])
    np.testing.assert_array_equal(expected_section3, msg.section3)
    np.testing.assert_array_equal(expected_section3[:5], msg.gridDefinitionSection)
    assert msg.sourceOfGridDefinition.value == 0
    assert msg.sourceOfGridDefinition.definition == 'Specified in Code Table 3.1'

def test_section4(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['REFC'][0]
    expected_section4 = np.array([  0,   0,  16, 196,   2,   0,  96,   0,   0,   1,  12,  10,   0,
                                    0, 255,   0,   0])
    assert msg.typeOfFirstFixedSurface.value == 10
    assert msg.typeOfFirstFixedSurface.definition == ['Entire Atmosphere', 'unknown']
    assert msg.scaleFactorOfFirstFixedSurface == 0
    assert msg.scaledValueOfFirstFixedSurface == 0
    assert msg.typeOfSecondFixedSurface.value == 255
    assert msg.typeOfSecondFixedSurface.definition == ['Missing', 'unknown']
    assert msg.scaleFactorOfSecondFixedSurface == 0
    assert msg.scaledValueOfSecondFixedSurface == 0
    assert msg.unitOfFirstFixedSurface == 'unknown'
    assert msg.valueOfFirstFixedSurface == 0.0
    assert msg.unitOfSecondFixedSurface == None
    assert msg.valueOfSecondFixedSurface == 0.0
    assert msg.fullName == 'Composite reflectivity'
    assert msg.units == 'dB'
    assert msg.shortName == 'REFC'
    assert msg.leadTime == datetime.timedelta(hours=12)
    assert msg.duration == datetime.timedelta(hours=0)
    assert msg.validDate == datetime.datetime(2022,11,7,12)
    assert msg.level == 'entire atmosphere'
    assert msg.parameterCategory == 16
    assert msg.parameterNumber == 196
    assert msg.typeOfGeneratingProcess.value == 2
    assert msg.typeOfGeneratingProcess.definition == 'Forecast'
    assert msg.generatingProcess.value == 96
    assert msg.generatingProcess.definition == 'Global Forecast System Model T1534 - Forecast hours 00-384 T574 - Forecast hours 00-192 T190 - Forecast hours 204-384'
    assert msg.backgroundGeneratingProcessIdentifier == 0
    assert msg.hoursAfterDataCutoff == 0
    assert msg.minutesAfterDataCutoff == 0
    assert msg.unitOfForecastTime.value == 1
    assert msg.unitOfForecastTime.definition == 'Hour'
    assert msg.valueOfForecastTime == 12
    np.testing.assert_array_equal(expected_section4, msg.section4)

def test_section5(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['REFC'][0]
    expected_section5 = np.array([     65160,          3, 3304718338,          0,          2,
                                          15,          0,          1,          0, 1649987994,
                                          -1,       3127,          0,          4,          1,
                                           1,         49,          8,          2,          2])
    assert msg.dataRepresentationTemplateNumber.value == 3
    assert msg.dataRepresentationTemplateNumber.definition == 'Grid Point Data - Complex Packing and Spatial Differencing (see Template 5.3)'
    assert msg.numberOfPackedValues == 65160
    assert msg.typeOfValues.value == 0
    assert msg.typeOfValues.definition == 'Floating Point'
    assert msg.refValue == -2000.000244140625
    assert msg.binScaleFactor == 0
    assert msg.decScaleFactor == 2
    assert msg.nBitsPacking == 15
    assert msg.groupSplittingMethod.value == 1
    assert msg.groupSplittingMethod.definition == 'General Group Splitting'
    assert msg.typeOfMissingValueManagement.value == 0
    assert msg.typeOfMissingValueManagement.definition == 'No explicit missing values included within the data values'
    assert msg.priMissingValue == None
    assert msg.secMissingValue == None
    assert msg.nGroups == 3127
    assert msg.refGroupWidth == 0
    assert msg.nBitsGroupWidth == 4
    assert msg.refGroupLength == 1
    assert msg.groupLengthIncrement == 1
    assert msg.lengthOfLastGroup == 49
    assert msg.nBitsScaledGroupLength == 8
    assert msg.spatialDifferenceOrder.value == 2
    assert msg.spatialDifferenceOrder.definition == 'Second-Order Spatial Differencing'
    assert msg.nBytesSpatialDifference == 2
    np.testing.assert_array_equal(expected_section5, msg.section5)

def test_data(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['REFC'][0]
        assert hashlib.sha1(msg.data).hexdigest() == '47a930feaf4c7389529cfb8de94578c06e3c9ce3'
    assert msg.min == np.float32(-20.000002)
    assert msg.max == np.float32(45.85)
    assert msg.mean == np.float32(-11.05756)
    assert msg.median == np.float32(-20.000002)

def test_latlons(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['REFC'][0]
    assert hashlib.sha1(msg.lats).hexdigest() == 'b750c3a2dd582cf6ab62b7caec1e6c228eefd289'
    assert hashlib.sha1(msg.lons).hexdigest() == '7eff5b0b19a5036396031315e956b8c40a567bd3'
