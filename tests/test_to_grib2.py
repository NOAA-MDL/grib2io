import itertools

import pytest
import xarray as xr
from numpy.testing import assert_allclose, assert_array_equal


def _del_list_inplace(input_list, indices):
    for index in sorted(indices, reverse=True):
        del input_list[index]
    return input_list


def _test_any_differences(da1, da2):
    assert_array_equal(
        da1.attrs["GRIB2IO_section0"][:-1], da2.attrs["GRIB2IO_section0"][:-1]
    )
    assert_array_equal(da1.attrs["GRIB2IO_section1"], da2.attrs["GRIB2IO_section1"])
    assert_array_equal(da1.attrs["GRIB2IO_section2"], da2.attrs["GRIB2IO_section2"])
    assert_array_equal(da1.attrs["GRIB2IO_section3"], da2.attrs["GRIB2IO_section3"])
    assert_array_equal(da1.attrs["GRIB2IO_section4"], da2.attrs["GRIB2IO_section4"])
    skip = [2, 9, 10, 11, 16, 17]
    assert_array_equal(
        _del_list_inplace(list(da1.attrs["GRIB2IO_section5"]), skip),
        _del_list_inplace(list(da2.attrs["GRIB2IO_section5"]), skip),
    )
    assert_allclose(da1.data, da2.data, atol=0.02, rtol=0)


def test_da_write(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_da.grib2"

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

    ds1["TMP"].grib2io.to_grib2(target_file)

    ds2 = xr.open_dataset(target_file, engine="grib2io")

    _test_any_differences(ds1["TMP"], ds2["TMP"])


def test_ds_write(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

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
        _test_any_differences(ds1[var], ds2[var])


def test_ds_write_levels(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds_levels.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

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
        _test_any_differences(da1, da2)


def test_ds_write_leadtime(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds_leadtime.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

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
        _test_any_differences(da1, da2)


def test_ds_write_leadtime_and_layers(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds_leadtime_and_layers.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

    filters = {
        "typeOfFirstFixedSurface": 100,
        "shortName": "TMP",
        "productDefinitionTemplateNumber": 0,
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

    lists = []
    for index, values in ds2.indexes.items():
        listeach = []
        for value in values:
            listeach.append({index: value})
        lists.append(listeach)

    for selectors in itertools.product(*lists):
        filters = {k: v for d in selectors for k, v in d.items()}
        da1 = ds1["TMP"].sel(indexers=filters)
        da2 = ds2["TMP"].sel(indexers=filters)
        _test_any_differences(da1, da2)


def test_ds_write_leadtime_and_refdate(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds_leadtime_and_refdate.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

    filters = {
        "typeOfFirstFixedSurface": 103,
        "valueOfFirstFixedSurface": 2,
        "shortName": "TMP",
        "productDefinitionTemplateNumber": 0,
    }

    ds1 = xr.open_mfdataset(
        [
            [
                datadir / "gfs.t00z.pgrb2.1p00.f009_subset",
                datadir / "gfs.t00z.pgrb2.1p00.f012_subset",
            ],
            [
                datadir / "gfs.t06z.pgrb2.1p00.f009_subset",
                datadir / "gfs.t06z.pgrb2.1p00.f012_subset",
            ],
        ],
        combine="nested",
        concat_dim=["refDate", "leadTime"],
        engine="grib2io",
        filters=filters,
    )

    ds1.grib2io.to_grib2(target_file)

    ds2 = xr.open_dataset(target_file, engine="grib2io")

    lists = []
    for index, values in ds2.indexes.items():
        listeach = []
        for value in values:
            listeach.append({index: value})
        lists.append(listeach)

    for selectors in itertools.product(*lists):
        filters = {k: v for d in selectors for k, v in d.items()}
        da1 = ds1["TMP"].sel(indexers=filters)
        da2 = ds2["TMP"].sel(indexers=filters)
        _test_any_differences(da1, da2)


def test_ds_write_messed_up(tmp_path, request):
    target_dir = tmp_path / "test_to_grib2"
    target_dir.mkdir()
    target_file = target_dir / "test_to_grib2_ds_messed_up.grib2"

    datadir = request.config.rootdir / "tests" / "data" / "gfs_20221107"

    filters = {
        "typeOfFirstFixedSurface": 103,
        "valueOfFirstFixedSurface": 2,
        "shortName": "TMP",
        "productDefinitionTemplateNumber": 0,
    }

    ds1 = xr.open_mfdataset(
        [
            datadir / "gfs.t00z.pgrb2.1p00.f009_subset",
            datadir / "gfs.t06z.pgrb2.1p00.f009_subset",
            datadir / "gfs.t00z.pgrb2.1p00.f012_subset",
            datadir / "gfs.t06z.pgrb2.1p00.f012_subset",
        ],
        combine="nested",
        concat_dim="leadTime",
        engine="grib2io",
        filters=filters,
    )

    with pytest.raises(ValueError):
        ds1.grib2io.to_grib2(target_file)
