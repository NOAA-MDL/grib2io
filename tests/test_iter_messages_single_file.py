import grib2io
import numpy as np
import pytest

def test_iter_messages_read(request):
    grib2file = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107' / 'gfs.t00z.pgrb2.1p00.f012_subset'
    with grib2io.open(grib2file) as g:
        for msg in g:
            print(msg)
            print(f'\tmin: {np.nanmin(msg.data)} max: {np.nanmax(msg.data)} mean: {np.nanmean(msg.data)}')
            msg.flush_data()

def test_iter_messages_write(tmp_path, request):
    target_dir = tmp_path / "test_iter_messages_write"
    target_dir.mkdir()
    target_file = target_dir / "testwrite.grib2"

    grib2file = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107' / 'gfs.t00z.pgrb2.1p00.f012_subset'
    grib2out = grib2io.open(target_file, mode='w')
    with grib2io.open(grib2file) as g:
        for msg in g[:10]:
            print(type(msg))
            newmsg = grib2io.Grib2Message(msg.section0, msg.section1, None,
                                          msg.section3, msg.section4,
                                          msg.section5)
            newmsg.data = np.copy(msg.data)
            newmsg.pack()
            grib2out.write(newmsg)
    grib2out.close
