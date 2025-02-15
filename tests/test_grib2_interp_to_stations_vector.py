import pytest
import numpy as np
import datetime
import grib2io

np.set_printoptions(formatter={'float': '{: 0.5f}'.format})

# Test stations
#            KPHL,     KPIT,     KMFL,     KORD,     KDEN,     KSFO
lats = [  39.8605,  40.4846,  25.7542,  41.9602,  39.8466,  37.6196]
lons = [ -75.2708, -80.2145, -80.3839, -87.9316,-104.6562,-122.3656]

def test_bicubic_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'input_data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        umsg = f.select(shortName='UGRD',level='10 m above ground')[0]
        vmsg = f.select(shortName='VGRD',level='10 m above ground')[0]
        rtol = 1./10**umsg.decScaleFactor
        grid_def_in = grib2io.Grib2GridDef(umsg.gdtn,umsg.gridDefinitionTemplate)
        sdata = grib2io.interpolate_to_stations((umsg.data,vmsg.data),'bicubic',grid_def_in,lats,lons)
        np.testing.assert_allclose(sdata[0],np.array([2.77504, 1.13036, -5.58242, -2.72262, 1.35933, 4.20723]),rtol=rtol)
        np.testing.assert_allclose(sdata[1],np.array([-2.8205, -2.5066, -8.25053, -2.28479, 1.5556, 3.09094]),rtol=rtol)

def test_bilinear_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'input_data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        umsg = f.select(shortName='UGRD',level='10 m above ground')[0]
        vmsg = f.select(shortName='VGRD',level='10 m above ground')[0]
        rtol = 1./10**umsg.decScaleFactor
        grid_def_in = grib2io.Grib2GridDef(umsg.gdtn,umsg.gridDefinitionTemplate)
        sdata = grib2io.interpolate_to_stations((umsg.data,vmsg.data),'bilinear',grid_def_in,lats,lons)
        np.testing.assert_allclose(sdata[0],np.array([2.67897, 1.09885, -5.73067, -2.66697, 0.93868, 3.85792]),rtol=rtol)
        np.testing.assert_allclose(sdata[1],np.array([-3.00674, -2.67472, -8.32837, -2.31592, 2.11204, 2.90466]),rtol=rtol)

def test_budget_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'input_data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        umsg = f.select(shortName='UGRD',level='10 m above ground')[0]
        vmsg = f.select(shortName='VGRD',level='10 m above ground')[0]
        rtol = 1./10**umsg.decScaleFactor
        grid_def_in = grib2io.Grib2GridDef(umsg.gdtn,umsg.gridDefinitionTemplate)
        sdata = grib2io.interpolate_to_stations((umsg.data,vmsg.data),'budget',grid_def_in,lats,lons)
        np.testing.assert_allclose(sdata[0],np.array([2.60448, 1.11867, -5.74128, -2.65074, 0.61570, 3.84874]),rtol=rtol)
        np.testing.assert_allclose(sdata[1],np.array([-3.19010, -2.74230, -8.34333, -2.86165, 2.39821, 2.87611]),rtol=rtol)

def test_neighbor_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'input_data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        umsg = f.select(shortName='UGRD',level='10 m above ground')[0]
        vmsg = f.select(shortName='VGRD',level='10 m above ground')[0]
        rtol = 1./10**umsg.decScaleFactor
        grid_def_in = grib2io.Grib2GridDef(umsg.gdtn,umsg.gridDefinitionTemplate)
        sdata = grib2io.interpolate_to_stations((umsg.data,vmsg.data),'neighbor',grid_def_in,lats,lons)
        np.testing.assert_allclose(sdata[0],np.array([2.88667, 1.40519, -7.25290, -2.59283, 2.89911, 3.11281]),rtol=rtol)
        np.testing.assert_allclose(sdata[1],np.array([-2.60096, -2.65632, -9.70096, -1.98764, -2.51089, 4.08250]),rtol=rtol)

def test_neighbor_budget_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'input_data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f024') as f:
        umsg = f.select(shortName='UGRD',level='10 m above ground')[0]
        vmsg = f.select(shortName='VGRD',level='10 m above ground')[0]
        rtol = 1./10**umsg.decScaleFactor
        grid_def_in = grib2io.Grib2GridDef(umsg.gdtn,umsg.gridDefinitionTemplate)
        sdata = grib2io.interpolate_to_stations((umsg.data,vmsg.data),'neighbor-budget',grid_def_in,lats,lons)
        np.testing.assert_allclose(sdata[0],np.array([2.73996, 1.11899, -5.61142, -2.59283, 0.61475, 3.95788]),rtol=rtol)
        np.testing.assert_allclose(sdata[1],np.array([-3.11859, -2.70217, -8.24905, -1.98764, 2.78802, 2.81118]),rtol=rtol)
