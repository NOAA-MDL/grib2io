import pytest
import xarray as xr

def test_named_filter(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
    ds1 = xr.open_dataset(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io', filters=filters)
    filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface='Ground or Water Surface')
    ds2 = xr.open_dataset(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io', filters=filters)
    xr.testing.assert_equal(ds1, ds2)

def test_multi_lead(request):
    data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
    filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
    da = xr.open_mfdataset([data / 'gfs.t00z.pgrb2.1p00.f009_subset', data / 'gfs.t00z.pgrb2.1p00.f012_subset'], engine='grib2io', filters=filters, combine='nested', concat_dim='leadTime').to_array()
    assert da.shape == (1, 2, 181, 360)

def test_interp(request):
    try:
        from grib2io._grib2io import Grib2GridDef
        gdtn_nbm = 30
        gdt_nbm = [1, 0, 6371200, 255, 255, 255, 255, 2345, 1597, 19229000, 233723400,
                                                 48, 25000000, 265000000, 2539703, 2539703, 0, 64, 25000000,
                                                 25000000, -90000000, 0]
        nbm_grid_def = Grib2GridDef(gdtn_nbm, gdt_nbm)
        data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
        filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
        ds = xr.open_dataset(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io', filters=filters)
        da = ds.grib2io.interp('neighbor', nbm_grid_def).to_array()
        assert da.shape == (1, 1597, 2345)
    except(ModuleNotFoundError):
        pytest.skip()

def test_interp_with_openmp_threads(request):
    try:
        from grib2io._grib2io import Grib2GridDef
        gdtn_nbm = 30
        gdt_nbm = [1, 0, 6371200, 255, 255, 255, 255, 2345, 1597, 19229000, 233723400,
                                                 48, 25000000, 265000000, 2539703, 2539703, 0, 64, 25000000,
                                                 25000000, -90000000, 0]
        nbm_grid_def = Grib2GridDef(gdtn_nbm, gdt_nbm)
        data = request.config.rootdir / 'tests' / 'data' / 'gfs_20221107'
        filters = dict(productDefinitionTemplateNumber=0, typeOfFirstFixedSurface=1)
        ds = xr.open_dataset(data / 'gfs.t00z.pgrb2.1p00.f012_subset', engine='grib2io', filters=filters)
        da = ds.grib2io.interp('neighbor', nbm_grid_def, num_threads=2).to_array()
        assert da.shape == (1, 1597, 2345)
    except(ModuleNotFoundError):
        pytest.skip()
