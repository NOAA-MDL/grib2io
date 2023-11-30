import pytest
import grib2io

def test_read_unpack_data(request):
    grib2file = request.config.rootdir / 'tests' / 'data' / 'gfs.t00z.pgrb2.1p00.f024'
    g = grib2io.open(grib2file)
    for msg in g:
        msg.__str__()
        msg.data
    g.close()
