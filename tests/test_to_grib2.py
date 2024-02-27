import xarray as xr
from numpy.testing import assert_allclose, assert_array_equal


def test_da_write(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_da.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107" / "00"

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

    ds1["TMP"].grib2io.to_grib2(target_file)

    ds2 = xr.open_dataset(target_file, engine="grib2io")

    assert_array_equal(
        ds1["TMP"].attrs["GRIB2IO_section0"][:-1],
        ds2["TMP"].attrs["GRIB2IO_section0"][:-1],
    )
    assert_array_equal(
        ds1["TMP"].attrs["GRIB2IO_section1"], ds2["TMP"].attrs["GRIB2IO_section1"]
    )
    assert_array_equal(
        ds1["TMP"].attrs["GRIB2IO_section3"], ds2["TMP"].attrs["GRIB2IO_section3"]
    )
    assert_array_equal(
        ds1["TMP"].attrs["GRIB2IO_section4"], ds2["TMP"].attrs["GRIB2IO_section4"]
    )
    # Too many differences in section 5 to easily compare and should be added
    # when/if there is an understanding of the differences.

    assert_allclose(ds1["TMP"].data, ds2["TMP"].data, atol=0.02, rtol=0)


def test_ds_write(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107" / "00"

    filters = {
        "productDefinitionTemplateNumber": 0,
        "typeOfFirstFixedSurface": 103,
        "valueOfFirstFixedSurface": 2,
    }

    ds1 = xr.open_dataset(
        datadir / "gfs.t00z.pgrb2.1p00.f012_subset",
        engine="grib2io",
        filters=filters,
    )

    ds1.grib2io.to_grib2(target_file)

    ds2 = xr.open_dataset(target_file, engine="grib2io")

    for var in ["APTMP", "DPT", "RH", "SPFH", "TMP"]:
        assert_array_equal(
            ds1[var].attrs["GRIB2IO_section0"][:-1],
            ds2[var].attrs["GRIB2IO_section0"][:-1],
        )
        assert_array_equal(
            ds1[var].attrs["GRIB2IO_section1"], ds2[var].attrs["GRIB2IO_section1"]
        )
        assert_array_equal(
            ds1[var].attrs["GRIB2IO_section3"], ds2[var].attrs["GRIB2IO_section3"]
        )
        assert_array_equal(
            ds1[var].attrs["GRIB2IO_section4"], ds2[var].attrs["GRIB2IO_section4"]
        )
        # Too many differences in section 5 to easily compare and should be
        # added when/if there is an understanding of the differences.

        assert_allclose(ds1[var].data, ds2[var].data, atol=0.02, rtol=0)


def test_ds_write_levels(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds_levels.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107" / "00"

    filters = {
        "productDefinitionTemplateNumber": 0,
        "shortName": "TMP",
        "typeOfFirstFixedSurface": 100,
    }

    ds1 = xr.open_dataset(
        datadir / "gfs.t00z.pgrb2.1p00.f012_subset",
        engine="grib2io",
        filters=filters,
    )

    ds1.grib2io.to_grib2(target_file)

    ds2 = xr.open_dataset(target_file, engine="grib2io")

    for value in ds1.indexes["valueOfFirstFixedSurface"]:
        da1 = ds1["TMP"].sel(indexers={"valueOfFirstFixedSurface": value})
        da2 = ds2["TMP"].sel(indexers={"valueOfFirstFixedSurface": value})
        assert_array_equal(
            da1.attrs["GRIB2IO_section0"][:-1], da2.attrs["GRIB2IO_section0"][:-1]
        )
        assert_array_equal(da1.attrs["GRIB2IO_section1"], da2.attrs["GRIB2IO_section1"])
        assert_array_equal(da1.attrs["GRIB2IO_section3"], da2.attrs["GRIB2IO_section3"])
        assert_array_equal(da1.attrs["GRIB2IO_section4"], da2.attrs["GRIB2IO_section4"])
        # Too many differences in section 5 to easily compare and should be
        # added when/if there is an understanding of the differences.

        assert_allclose(da1.data, da2.data, atol=0.02, rtol=0)


def test_ds_write_leadtime(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds_leadtime.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107" / "00"

    filters = {
        "typeOfFirstFixedSurface": 103,
        "valueOfFirstFixedSurface": 2,
        "productDefinitionTemplateNumber": 0,
        "shortName": "TMP",
    }

    ds1 = xr.open_mfdataset(
        [
            datadir / "gfs.t00z.pgrb2.1p00.f009_subset",
            datadir / "gfs.t00z.pgrb2.1p00.f012_subset",
        ],
        combine="nested",
        concat_dim="leadTime",
        engine="grib2io",
        filters=filters,
    )

    ds1.grib2io.to_grib2(target_file)

    ds2 = xr.open_dataset(target_file, engine="grib2io")

    for value in ds1.indexes["leadTime"]:
        da1 = ds1["TMP"].sel(indexers={"leadTime": value})
        da2 = ds2["TMP"].sel(indexers={"leadTime": value})
        assert_array_equal(
            da1.attrs["GRIB2IO_section0"][:-1], da2.attrs["GRIB2IO_section0"][:-1]
        )
        assert_array_equal(da1.attrs["GRIB2IO_section1"], da2.attrs["GRIB2IO_section1"])
        assert_array_equal(da1.attrs["GRIB2IO_section3"], da2.attrs["GRIB2IO_section3"])
        assert_array_equal(da1.attrs["GRIB2IO_section4"], da2.attrs["GRIB2IO_section4"])
        # Too many differences in section 5 to easily compare and should be
        # added when/if there is an understanding of the differences.

        assert_allclose(da1.data, da2.data, atol=0.02, rtol=0)
