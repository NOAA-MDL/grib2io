import pytest
import numpy as np
import datetime
import grib2io

def test_datetime_attrs(request):
    data = request.config.rootdir / 'tests' / 'data'

    f = grib2io.open(data / 'ds.temp.bin')
    msg = f[0]

    expected_refDate = datetime.datetime(2025, 2, 6, 0, 30)
    expected_leadTime = datetime.timedelta(seconds=1800) # 30 minutes
    expected_duration = datetime.timedelta(seconds=0)
    expected_validDate = datetime.datetime(2025, 2, 6, 1, 0)

    assert msg.refDate == expected_refDate
    assert msg.leadTime == expected_leadTime
    assert msg.duration == expected_duration
    assert msg.validDate == expected_validDate

    msg = f[1]

    expected_refDate = datetime.datetime(2025, 2, 6, 0, 30)
    expected_leadTime = datetime.timedelta(seconds=5400) # 90 minutes
    expected_duration = datetime.timedelta(seconds=0)
    expected_validDate = datetime.datetime(2025, 2, 6, 2, 0)

    assert msg.refDate == expected_refDate
    assert msg.leadTime == expected_leadTime
    assert msg.duration == expected_duration
    assert msg.validDate == expected_validDate

    f.close()
