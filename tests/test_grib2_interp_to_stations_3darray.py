import numpy as np
import grib2io

try:
    import grib2io.iplib as iplib
except ImportError:
    import pytest

    pytest.skip("NCEPLIBS-ip not found", allow_module_level=True)

# Output grid (NBM 2.5km CONUS Grid)
gdtn_out = 30
gdt_out = np.array(
    [
        1,
        0,
        6371200,
        255,
        255,
        255,
        255,
        2345,
        1597,
        19229000,
        233723400,
        48,
        25000000,
        265000000,
        2539703,
        2539703,
        0,
        80,
        25000000,
        25000000,
        -90000000,
        0,
    ],
    dtype=np.int32,
)
grid_def_out = grib2io.Grib2GridDef(gdtn_out, gdt_out)

# Test stations
#                    KPHL,     KPIT,     KMFL,     KORD,     KDEN,     KSFO
station_lats = [39.8605, 40.4846, 25.7542, 41.9602, 39.8466, 37.6196]
station_lons = [-75.2708, -80.2145, -80.3839, -87.9316, -104.6562, -122.3656]


def test_interp_to_stations_3darray(request):
    data = request.config.rootdir / "tests" / "input_data"
    with grib2io.open(data / "gfs.t00z.pgrb2.1p00.f024") as f:
        msg = f.select(shortName="TMP", level="2 m above ground")[0]

        # Interpolate
        newmsg = msg.interpolate("bilinear", grid_def_out, num_threads=1)

        # Build 3D arrays of lats and lons
        n = 5
        ny, nx = newmsg.ny, newmsg.nx
        glats = np.zeros((n, ny, nx), dtype=np.float32)
        glons = np.zeros((n, ny, nx), dtype=np.float32)
        for i in range(n):
            glats[i] = newmsg.lats
            glons[i] = newmsg.lons

        # Interpolate lats and lons to stations using neighbor
        slats = grib2io.interpolate_to_stations(glats, "neighbor", newmsg.griddef, station_lats, station_lons)
        slons = grib2io.interpolate_to_stations(glons, "neighbor", newmsg.griddef, station_lats, station_lons)

        # ...
        latdiff = []
        londiff = []
        for s in range(len(station_lats)):
            latdiff.append(np.unique(np.abs(slats[:, s] - station_lats[s])))
            londiff.append(np.unique(np.abs(slons[:, s] - station_lons[s])))
        latdiff = np.array(latdiff).flatten()
        londiff = np.array(londiff).flatten()

        rtol = 1e-3
        np.testing.assert_allclose(
            latdiff,
            np.array(
                [
                    3.15060425e-03,
                    9.87618408e-03,
                    2.30978088e-03,
                    5.65974731e-03,
                    1.03450378e-02,
                    4.41650391e-05,
                ],
                dtype=np.float32,
            ),
            rtol=rtol,
        )
        np.testing.assert_allclose(
            londiff,
            np.array(
                [0.00893629, 0.00386768, 0.00795333, 0.00233707, 0.00023229, 0.00444852],
                dtype=np.float32,
            ),
            rtol=rtol,
        )
