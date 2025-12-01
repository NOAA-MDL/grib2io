import pytest
import numpy as np
import datetime
import grib2io

# Test stations
#            KPHL,     KPIT,     KMFL,     KORD,     KDEN,     KSFO      PMDY
lats = [  39.8605,  40.4846,  25.7542,  41.9602,  39.8466,  37.6196,  28.2015]
lons = [ -75.2708, -80.2145, -80.3839, -87.9316,-104.6562,-122.3656,-177.3813]

XLOC_EXPECTED = np.array([
    1973.6736,
    1799.815,
    1864.3274,
    1530.0651,
    952.95715,
    322.15088,
    np.nan],
    dtype=np.float32
)

YLOC_EXPECTED = np.array([
    813.0962,
    819.43164,
    168.9331,
    865.2627,
    774.5322,
    759.9668,
    np.nan],
    dtype=np.float32
)

def test_station_grid_coords(request):
    data = request.config.rootdir / 'tests' / 'input_data'
    with grib2io.open(data / 'blend.t00z.core.f001.tmp.co.grib2') as f:
        msg = f[0]
        xloc, yloc = grib2io.utils.latlon_to_ij(
            msg.gdtn,
            msg.gdt,
            np.array(lats, dtype=np.float32),
            np.array(lons, dtype=np.float32),
        )

    np.testing.assert_allclose(xloc, XLOC_EXPECTED, rtol=10e-4) 
    np.testing.assert_allclose(yloc, YLOC_EXPECTED, rtol=10e-4) 
