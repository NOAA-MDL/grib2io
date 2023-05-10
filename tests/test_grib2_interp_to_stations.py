import pytest
import grib2io
import numpy as np
import datetime

# Test stations
#            KPHL,     KPIT,     KMFL,     KORD,     KDEN,     KSFO
lats = [  39.8605,  40.4846,  25.7542,  41.9602,  39.8466,  37.6196]
lons = [ -75.2708, -80.2145, -80.3839, -87.9316,-104.6562,-122.3656]

def test_bicubic_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg = f.select(shortName='TMP',level='2 m above ground')[0]
    grid_def_in = grib2io.Grib2GridDef(msg.gdtn,msg.gridDefinitionTemplate)
    sdata = grib2io.interpolate_to_stations(msg.data,'bicubic',grid_def_in,lats=lats,lons=lons)
    assert sdata == np.array([290.51328 280.273   299.15262 281.8346  283.5935  285.205  ])

def test_bilinear_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg = f.select(shortName='TMP',level='2 m above ground')[0]
    grid_def_in = grib2io.Grib2GridDef(msg.gdtn,msg.gridDefinitionTemplate)
    sdata = grib2io.interpolate_to_stations(msg.data,'bilinear',grid_def_in,lats=lats,lons=lons)
    assert sdata == np.array([290.19937 280.47717 299.17844 281.69833 283.07642 285.1446 ])

def test_budget_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg = f.select(shortName='TMP',level='2 m above ground')[0]
    grid_def_in = grib2io.Grib2GridDef(msg.gdtn,msg.gridDefinitionTemplate)
    sdata = grib2io.interpolate_to_stations(msg.data,'budget',grid_def_in,lats=lats,lons=lons)
    assert sdata == np.array([289.66833 280.4579  299.18106 280.9805  282.58932 285.13675])

def test_neighbor_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg = f.select(shortName='TMP',level='2 m above ground')[0]
    grid_def_in = grib2io.Grib2GridDef(msg.gdtn,msg.gridDefinitionTemplate)
    sdata = grib2io.interpolate_to_stations(msg.data,'neighbor',grid_def_in,lats=lats,lons=lons)
    assert sdata == np.array([291.9625 282.1125 299.7225 281.8125 282.1825 285.3825])

def test_neighbor_budget_interp_to_stations(request):
    data = request.config.rootdir / 'tests' / 'data'
    with grib2io.open(data / 'gfs.t00z.pgrb2.1p00.f048') as f:
        msg = f.select(shortName='TMP',level='2 m above ground')[0]
    grid_def_in = grib2io.Grib2GridDef(msg.gdtn,msg.gridDefinitionTemplate)
    sdata = grib2io.interpolate_to_stations(msg.data,'neighbor-budget',grid_def_in,lats=lats,lons=lons)
    assert sdata == np.array([290.60046 280.74164 299.11053 281.8125  283.12054 285.14172])
