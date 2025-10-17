import pytest
import numpy as np
import datetime
import grib2io

def test_new_message_data_shape(request):
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['TMAX'][0]

    # Create new message
    newmsg = grib2io.Grib2Message(
        msg.section0,
        msg.section1,
        None,
        msg.section3,
        msg.section4,
        drtn=3)

    
    # Make some data
    stuff = np.ones((100, 300), dtype=np.float32)

    print(f"{newmsg.shape = }")
    print(f"{stuff.shape = }")

    # Test adding stuff to newmsg.
    with pytest.raises(ValueError, match=r"^Data shape mismatch.*"):
        newmsg.data = stuff    


def test_new_message_data_shape_no_griddef(request):
    data = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f012_subset') as f:
        msg = f['TMAX'][0]

    # Create new message. Here we have an "empty" grid definition, so
    # nx and ny are not defined, but will be set according to the data
    # shape.
    newmsg = grib2io.Grib2Message(
        msg.section0,
        msg.section1,
        None,
        gdtn=msg.gdtn,
        pdtn=msg.pdtn,
        drtn=msg.drtn,
    )

    # Make some data
    stuff = np.ones((100, 300), dtype=np.float32)

    newmsg.data = stuff

    assert newmsg.ny == stuff.shape[0]
    assert newmsg.nx == stuff.shape[1]

    stuff = np.ones((101, 301), dtype=np.float32)

    # Test adding stuff to newmsg.
    with pytest.raises(ValueError, match=r"^Data shape mismatch.*"):
        newmsg.data = stuff    
