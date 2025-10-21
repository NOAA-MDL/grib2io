from numpy.testing import assert_array_equal

import pytest
import numpy as np
import datetime
import grib2io

def test_grib2_shallow_copy(request):
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'
    g = grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset')
    msg = g['TMAX'][0]

    # Create shallow copy
    newmsg = msg.copy(deep=False)

    # Test Grib2Message object's memory reference id different
    assert id(newmsg) != id(msg)

    # Test memory reference ids are same for the
    # GRIB2 sections, except section 5.
    assert id(newmsg.section0) == id(msg.section0)
    assert id(newmsg.section1) == id(msg.section1)
    assert id(newmsg.section2) == id(msg.section2)
    assert id(newmsg.section3) == id(msg.section3)
    assert id(newmsg.section4) == id(msg.section4)

    # Test section5 ids 
    assert id(newmsg.section5) != id(msg.section5)

    # Test dtrn is the same
    assert newmsg.drtn == msg.drtn

    # Test data are not equal
    assert id(newmsg.data) != id(msg.data)

    # Test newmsg data shape is zero.
    assert len(newmsg.data.shape) == 0

    # Test newmsg data size is 1 (a None object in the Numpy Array)
    assert newmsg.data.size == 1

    g.close()


def test_grib2_deep_copy(request):
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'
    g = grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset')
    msg = g['TMAX'][0]

    # Create shallow copy
    newmsg = msg.copy(deep=True) # True is default, just being explicit here.

    # Test Grib2Message object's memory reference id different
    assert id(newmsg) != id(msg)

    # Test memory reference ids are different for the
    # GRIB2 sections, except section 5.
    assert id(newmsg.section0) != id(msg.section0)
    assert id(newmsg.section1) != id(msg.section1)
    # Since section2 is an empty byte string, a deep copy of it
    # yields the same id value.
    assert id(newmsg.section2) == id(msg.section2)
    assert id(newmsg.section3) != id(msg.section3)
    assert id(newmsg.section4) != id(msg.section4)
    assert id(newmsg.section5) != id(msg.section5)

    # Test data are equal
    assert_array_equal(newmsg.data, msg.data)

    g.close()
