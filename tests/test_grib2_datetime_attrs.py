import pytest
import numpy as np
import datetime
import grib2io

def test_datetime_attrs(request):
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['TMAX'][0]

    expected_refDate = datetime.datetime(2022, 11, 7, 0, 0)
    expected_leadTime = datetime.timedelta(seconds=43200) # 12-hours (ending lead time)
    expected_duration = datetime.timedelta(seconds=21600) # 6-hour duration
    expected_validDate = datetime.datetime(2022, 11, 7, 12, 0)

    assert msg.refDate == expected_refDate
    assert msg.leadTime == expected_leadTime
    assert msg.duration == expected_duration
    assert msg.validDate == expected_validDate

    # Change lead time from 12 hours to 24 hours.
    msg.leadTime = datetime.timedelta(hours=24)

    assert msg.refDate == datetime.datetime(2022, 11, 7, 0, 0)
    assert msg.leadTime == datetime.timedelta(days=1)
    assert msg.duration == datetime.timedelta(seconds=21600)
    assert msg.validDate == datetime.datetime(2022, 11, 8, 0, 0)

    # Change duration from 6 hours to 18 hours.
    msg.duration = datetime.timedelta(hours=18)

    assert msg.refDate == datetime.datetime(2022, 11, 7, 0, 0)
    assert msg.leadTime == datetime.timedelta(days=1)
    assert msg.duration == datetime.timedelta(seconds=64800)
    assert msg.validDate == datetime.datetime(2022, 11, 8, 0, 0)

    # Change lead time to 6 hours
    msg.leadTime = datetime.timedelta(seconds=21600)
    # Change duration to 6 hours
    msg.duration = datetime.timedelta(seconds=21600)

    assert msg.refDate == datetime.datetime(2022, 11, 7, 0, 0)
    assert msg.leadTime == datetime.timedelta(seconds=21600)
    assert msg.duration == datetime.timedelta(seconds=21600)
    assert msg.validDate == datetime.datetime(2022, 11, 7, 6, 0)
