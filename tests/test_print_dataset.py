import xarray as xr


def test_da_repr(tmp_path, request):
    """Test writing a single DataArray to a single grib2 message."""
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

    filters = {
        "productDefinitionTemplateNumber": 0,
        "typeOfFirstFixedSurface": 1,
        "shortName": "TMP",
    }
    ds1 = xr.open_dataset(
        datadir / "gfs.t00z.pgrb2.1p00.f012_subset",
        engine="grib2io",
        filters=filters,
    )
    assert (
        repr(ds1)
        == """<xarray.Dataset> Size: 1MB
Dimensions:                   (y: 181, x: 360)
Coordinates:
    refDate                   datetime64[ns] 8B ...
    leadTime                  timedelta64[ns] 8B ...
    valueOfFirstFixedSurface  float64 8B ...
    latitude                  (y, x) float64 521kB ...
    longitude                 (y, x) float64 521kB ...
    validDate                 datetime64[ns] 8B ...
Dimensions without coordinates: y, x
Data variables:
    TMP                       (y, x) float32 261kB ...
Attributes:
    engine:   grib2io"""
    )
