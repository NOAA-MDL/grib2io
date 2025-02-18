import grib2io
import numpy as np
import pytest

def test_grib2_write_local_use(tmp_path, request):
    target_dir = tmp_path / "test_grib2_write_local_use"
    target_dir.mkdir()
    target_file = target_dir / "testwrite_localuse.grib2"

    grib2file = request.config.rootdir / 'tests' / 'input_data' / 'gfs_20221107' / 'gfs.t00z.pgrb2.1p00.f012_subset'
    grib2out = grib2io.open(target_file, mode='w')
    with grib2io.open(grib2file) as g:
        msg = g[0]
        print(type(msg))
        newmsg = grib2io.Grib2Message(msg.section0, msg.section1, b"HELLO WORLD!",
                                      msg.section3, msg.section4,
                                      msg.section5)
        newmsg.data = np.copy(msg.data)
        newmsg.pack()
        grib2out.write(newmsg)

    grib2out.close

    g = grib2io.open(target_file)
    msg = g[0]
    assert msg.section2 == b"HELLO WORLD!" 
    g.close()
