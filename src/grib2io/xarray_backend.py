"""
grib2io xarray backend is a backend entrypoint for decoding grib2 files with
xarray engine 'grib2io' API is experimental and is subject to change without
backward compatibility.
"""
from copy import copy
from dataclasses import dataclass, field, astuple
import itertools
import logging
from pathlib import Path
import typing

import numpy as np
import pandas as pd
import xarray as xr
from xarray.backends.common import (
    BackendArray,
    BackendEntrypoint,
)
from xarray.core import indexing
from xarray.backends.locks import SerializableLock

import grib2io
from grib2io import Grib2Message, Grib2GridDef
from grib2io._grib2io import _data

logger = logging.getLogger(__name__)

LOCK = SerializableLock()


class GribBackendEntrypoint(BackendEntrypoint):
    """
    xarray backend engine entrypoint for opening and decoding grib2 files.

    .. warning::

       This backend is experimental and the API/behavior may change without
       backward compatibility.
    """
    def open_dataset(
        self,
        filename,
        *,
        drop_variables = None,
        filters: typing.Mapping[str, typing.Any] = dict(),
    ):
        """
        Read and parse metadata from grib file.

        Parameters
        ----------
        filename
            GRIB2 file to be opened.
        filters
            Filter GRIB2 messages to single hypercube. Dict keys can be any
            GRIB2 metadata attribute name.

        Returns
        -------
        open_dataset
            Xarray dataset of grib2 messages.
        """
        with grib2io.open(filename, _xarray_backend=True) as f:
            file_index = pd.DataFrame(f._index)

        # parse grib2io _index to dataframe and acquire non-geo possible dims
        # (scalar coord when not dim due to squeeze) parse_grib_index applies
        # filters to index and expands metadata based on product definition
        # template number
        file_index, non_geo_dims = parse_grib_index(file_index, filters)

        # Divide up records by variable
        frames, cube, extra_geo = make_variables(file_index, filename, non_geo_dims)
        # return empty dataset if no data
        if frames is None:
            return xr.Dataset()

        # create dataframe and add datarrays without any coords
        ds = xr.Dataset()
        for var_df in frames:
            da = build_da_without_coords(var_df, cube, filename)
            ds[da.name] = da

        # assign coords from the cube; the cube prevents datarrays with
        # different shapes
        ds = ds.assign_coords(cube.coords())
        # assign extra geo coords
        ds = ds.assign_coords(extra_geo)
        # assign valid date coords
        ds = ds.assign_coords(dict(validDate=ds.coords['refDate']+ds.coords['leadTime']))
        # assign attributes
        ds.attrs['engine'] = 'grib2io'

        return ds


class GribBackendArray(BackendArray):

    def __init__(self, array, lock):
        self.array = array
        self.shape = array.shape
        self.dtype = array.dtype
        self.lock = lock


    def __getitem__(self, key: xr.core.indexing.ExplicitIndexer) -> np.typing.ArrayLike:
        return xr.core.indexing.explicit_indexing_adapter(
            key,
            self.shape,
            indexing.IndexingSupport.BASIC,
            self._raw_getitem,
        )

    def _raw_getitem(self, key: tuple):
        """Implement thread safe access to data on disk."""
        with self.lock:
            return self.array[key]


def exclusive_slice_to_inclusive(item: slice):
    """
    Convert a slice with exclusive stop to an inclusive slice.

    If the slice has a step, the stop is reduced by the step, so that both
    interpretations would yield the same result.

    The means that [start, stop) is converted to [start, stop - step].

    Parameters
    ----------
    item
        The slice to convert.

    Returns
    -------
    slice
        The converted slice.
    """
    # return the None slice
    if item.start is None and item.stop is None and item.step is None:
        return item
    if not isinstance(item, slice):
        raise ValueError(f'item must be a slice; it was of type {type(item)}')
    # if step is None, it's one
    step = 1 if item.step is None else item.step
    if item.stop < item.start or step < 1:
        raise ValueError(f'slice {item} not accounted for')
    # handle case where slice has one item
    if abs(item.stop - item.start) == step:
        return [item.start]
    # other cases require reducing the stop by the step
    s = slice(item.start, item.stop - step, step)
    return s


class Validator:
    def __set_name__(self, owner, name):
        self.private_name = f'_{name}'
        self.name = name

    def __get__(self, obj, objtype=None):
        try:
            value = getattr(obj, self.private_name)
        except AttributeError:
            value = None
        return value


class PdIndex(Validator):

    def __set__(self, obj, value):
        try:
            value = pd.Index(value)
        except TypeError:
            value = pd.Index([value])
        setattr(obj, self.private_name, value)


def array_safe_eq(a, b) -> bool:
    """Check if a and b are equal, even if they are numpy arrays."""
    if a is b:
        return True
    if hasattr(a, 'equals'):
        return a.equals(b)
    if hasattr(a, 'all') and hasattr(b, 'all'):
        return a.shape == b.shape and (a == b).all()
    if hasattr(a, 'all') or hasattr(b, 'all'):
        return False
    try:
        return a == b
    except TypeError:
        return NotImplementedError


def dc_eq(dc1, dc2) -> bool:
    """Check if two dataclasses which hold numpy arrays are equal."""
    if dc1 is dc2:
        return True
    if dc1.__class__ is not dc2.__class__:
        return NotImplementedError
    t1 = astuple(dc1)
    t2 = astuple(dc2)
    return all(array_safe_eq(a1, a2) for a1, a2 in zip(t1, t2))


@dataclass(init=False)
class Cube:
    y: pd.Index = PdIndex()
    x: pd.Index = PdIndex()

    def __setitem__(self, key, value):
        #super().__setitem__(key, value)
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __eq__(self, other):
        return dc_eq(self, other)

    def __contains__(self, item):
        return item in self.__dataclass_fields__.keys()

    def coords(self) -> typing.Dict[str, xr.Variable]:
        keys = list(self.__dataclass_fields__.keys())
        keys.remove('x')
        keys.remove('y')
        coords = dict()
        for k in keys:
            if k is not None:
                if len(self[k]) > 1:
                    coords[k] = xr.Variable(dims=k, data=self[k], attrs=dict(grib_name=k))
                elif len(self[k]) == 1:
                    coords[k] = xr.Variable(dims=tuple(), data=np.array(self[k]).squeeze(), attrs=dict(grib_name=k))
        return coords


@dataclass
class OnDiskArray:
    file_name: str
    index: pd.DataFrame = field(repr=False)
    cube: Cube = field(repr=False)
    shape: typing.Tuple[int, ...] = field(init=False)
    ndim: int = field(init=False)
    geo_ndim: int = field(init=False)
    dtype = 'float32'

    def __post_init__(self):
        # multiple grids not allowed so can just use first
        geo_shape = (self.index.iloc[0].ny, self.index.iloc[0].nx)

        self.geo_shape = geo_shape
        self.geo_ndim = len(geo_shape)

        if len(self.index) == 1:
            self.shape = geo_shape
        else:
            if self.index.index.nlevels == 1:
                self.shape = tuple([len(self.index.index)]) + geo_shape
            else:
                self.shape = tuple([len(i) for i in self.index.index.levels]) + geo_shape
        self.ndim = len(self.shape)

        cols = ['msg', 'sectionOffset']
        self.index = self.index[cols]

    def __getitem__(self, item) -> np.array:
        # dimensions not in index are internal to tdlpack records; 2 dims for
        # grids; 1 dim for stations

        index_slicer = item[:-self.geo_ndim]
        # maintain all multindex levels
        index_slicer = tuple([[i] if isinstance(i, int) else i for i in index_slicer])

        # pandas loc slicing is inclusive, therefore convert slices into
        # explicit lists
        index_slicer_inclusive = tuple([ exclusive_slice_to_inclusive(i) if isinstance(i, slice) else i for i in index_slicer])

        # get records selected by item in new index dataframe
        if len(index_slicer_inclusive) == 1:
            index = self.index.loc[index_slicer_inclusive]
        elif len(index_slicer_inclusive) > 1:
            index = self.index.loc[index_slicer_inclusive, :]
        else:
            index = self.index
        index = index.set_index(index.index)

        # set miloc to new relative locations in sub array
        index['miloc'] = list(zip(*[index.index.unique(level=dim).get_indexer(index.index.get_level_values(dim)) for dim in index.index.names]))

        if len(index_slicer_inclusive) == 1:
            array_field_shape = tuple([len(index.index)]) + self.geo_shape
        elif len(index_slicer_inclusive) > 1:
            array_field_shape = index.index.levshape + self.geo_shape
        else:
            array_field_shape = self.geo_shape

        array_field = np.full(array_field_shape, fill_value=np.nan, dtype="float32")

        with open(self.file_name, mode='rb') as filehandle:
            for key, row in index.iterrows():

                bitmap_offset = None if pd.isna(row['sectionOffset'][6]) else int(row['sectionOffset'][6])
                values = _data(filehandle, row.msg, bitmap_offset, row['sectionOffset'][7])

                if len(index_slicer_inclusive) >= 1:
                    array_field[row.miloc] = values
                else:
                    array_field = values

        # handle geo dim slicing
        array_field = array_field[(Ellipsis,) + item[-self.geo_ndim :]]

        # squeeze array dimensions expressed as integer
        for i, it in reversed(list(enumerate(item[: -self.geo_ndim]))):
            if isinstance(it, int):
                array_field = array_field[(slice(None, None, None),) * i + (0,)]

        return array_field


def dims_to_shape(d) -> tuple:
    if 'nx' in d:
        t = (d['ny'],d['nx'])
    else:
        t = (d['nsta'],)
    return t


def filter_index(index, k, v):
    if isinstance(v, slice):
        index = index.set_index(k)
        index = index.loc[v]
        index = index.reset_index()
    else:
        label = (
            v
            if getattr(v, "ndim", 1) > 1  # vectorized-indexing
            else _asarray_tuplesafe(v)
            )
        if label.ndim == 0:
            # see https://github.com/pydata/xarray/pull/4292 for details
            label_value = label[()] if label.dtype.kind in "mM" else label.item()
            try:
                indexer = pd.Index(index[k]).get_loc(label_value)
                if isinstance(indexer, int):
                    index = index.iloc[[indexer]]
                else:
                    index = index.iloc[indexer]
            except KeyError:
                index = index.iloc[[]]
        else:
            indexer = pd.Index(index[k]).get_indexer_for(np.ravel(v))
            index = index.iloc[indexer[indexer >= 0]]

    return index


def parse_grib_index(index, filters):
    """
    Apply filters.

    Evaluate remaining dimensions based on pdtn and parse each out.
    """

    # make a copy of filters, remove filters as they are applied
    filters = copy(filters)

    for k, v in filters.items():
        if k not in index.columns:
            kwarg = {k:index.msg.apply(lambda msg: getattr(msg, k))}
            index = index.assign(**kwarg)
        # adopt parts of xarray's sel logic  so that filters behave similarly
        # allowed to filter to nothing to make empty dataset
        index = filter_index(index, k, v)

    # expand index
    index = index.assign(shortName=index.msg.apply(lambda msg: msg.shortName))
    index = index.assign(nx=index.msg.apply(lambda msg: msg.nx))
    index = index.assign(ny=index.msg.apply(lambda msg: msg.ny))
    index = index.assign(typeOfGeneratingProcess=index.msg.apply(lambda msg: msg.typeOfGeneratingProcess))
    index = index.assign(productDefinitionTemplateNumber=index.msg.apply(lambda msg: msg.productDefinitionTemplateNumber))
    index = index.assign(typeOfFirstFixedSurface=index.msg.apply(lambda msg: msg.typeOfFirstFixedSurface))
    index = index.astype({'ny':'int','nx':'int'})
    # apply common filters(to all definition templates) to reduce dataset to
    # single cube

    # ensure only one of each of the below exists after filters applied
    unique_pdtn = index.productDefinitionTemplateNumber.unique()
    if len(index.productDefinitionTemplateNumber.unique()) > 1:
        raise ValueError(f'filter to a single productDefinitionTemplateNumber; found: {[str(i) for i in unique_pdtn]}')
    if len(index) == 0:
        return index, list()
    pdtn = unique_pdtn[0]

    unique = index.typeOfGeneratingProcess.unique()
    if len(index.typeOfGeneratingProcess.unique()) > 1:
        raise ValueError(f'filter to a single typeOfGeneratingProcess; found: {[str(i) for i in unique]}')

    unique = index.typeOfFirstFixedSurface.unique()
    if len(index.typeOfFirstFixedSurface.unique()) > 1:
        raise ValueError(f'filter to a single typeOfFirstFixedSurface; found: {[str(i) for i in unique]}')

    # determine which non geo dimensions can be created from data by this point
    # the index is filtered down to a single typeOfFirstFixedSurface and
    # productDefinitionTemplateNumber
    non_geo_dims = list()

    #TODO Eventually re-work this section making 'non_geo_dims'

    # refDate always added for now (could add only based on
    # typOfGeneratingProcess)
    if 'refDate' not in index.columns:
        index = index.assign(refDate=index.msg.apply(lambda msg: msg.refDate))
    @dataclass(init=False)
    class RefDateDim:
        refDate: pd.Index = PdIndex()
    non_geo_dims.append(RefDateDim)

    # leadTime always added for now (could add only based on
    # typOfGeneratingProcess)
    if 'leadTime' not in index.columns:
        index = index.assign(leadTime=index.msg.apply(lambda msg: msg.leadTime))
    @dataclass(init=False)
    class LeadTimeDim:
        leadTime: pd.Index = PdIndex()
    non_geo_dims.append(LeadTimeDim)

    if 'valueOfFirstFixedSurface' not in index.columns:
        index = index.assign(valueOfFirstFixedSurface=index.msg.apply(lambda msg: msg.valueOfFirstFixedSurface))
    @dataclass(init=False)
    class ValueOfFirstFixedSurfaceDim:
        valueOfFirstFixedSurface: pd.Index = PdIndex()
    non_geo_dims.append(ValueOfFirstFixedSurfaceDim)

    # logic for parsing possible dims from specific product definition section

    if pdtn in {5,9}:
        # Probability forecasts at a horizontal level or in a horizontal layer
        # in a continuous or non-continuous time interval.  (see Template
        # 4.9)
        index = index.assign(thresholdLowerLimit = index.msg.apply(lambda msg: msg.thresholdLowerLimit))
        index = index.assign(thresholdUpperLimit = index.msg.apply(lambda msg: msg.thresholdUpperLimit))

        if index['thresholdLowerLimit'].nunique() > 1:
            @dataclass(init=False)
            class ThresholdLowerLimitDim:
                thresholdLowerLimit: pd.Index = PdIndex()
            non_geo_dims.append(ThresholdLowerLimitDim)
        if index['thresholdUpperLimit'].nunique() > 1:
            @dataclass(init=False)
            class ThresholdUpperLimitDim:
                thresholdUpperLimit: pd.Index = PdIndex()
            non_geo_dims.append(ThresholdUpperLimitDim)

    if pdtn in {6,10}:
        # Percentile forecasts at a horizontal level or in a horizontal layer
        # in a continuous or non-continuous time interval.  (see Template
        # 4.10)
        index = index.assign(percentileValue = index.msg.apply(lambda msg: msg.percentileValue))

        @dataclass(init=False)
        class PercentileValueDim:
            percentileValue: pd.Index = PdIndex()
        non_geo_dims.append(PercentileValueDim)

    if pdtn in {8,9,10,11,12,13,14,42,43,45,46,47,61,62,63,67,68,72,73,78,79,82,83,84,85,87,91}:
        if 'duration' not in index.columns:
            index = index.assign(duration=index.msg.apply(lambda msg: msg.duration))

        @dataclass(init=False)
        class Duration:
            duration: pd.Index = PdIndex()
        non_geo_dims.append(Duration)

    if pdtn in {1,11,33,34,41,43,45,47,49,54,56,58,59,63,68,77,79,81,83,84,85,92}:
        if 'perturbationNumber' not in index.columns:
            index = index.assign(perturbationNumber = index.msg.apply(lambda msg: msg.perturbationNumber))
        @dataclass(init=False)
        class perturbationNumber:
            perturbationNumber: pd.Index = PdIndex()
        non_geo_dims.append(perturbationNumber)

    return index, non_geo_dims


def build_da_without_coords(index, cube, filename) -> xr.DataArray:
    """
    Build a DataArray without coordinates from a cube of grib2 messages.

    Parameters
    ----------
    index
        Index of cube.
    cube
        Cube of grib2 messages.
    filename
        Filename of grib2 file

    Returns
    -------
    DataArray
        DataArray without coordinates
    """
    dim_names = [k for k in cube.__dataclass_fields__.keys() if cube[k] is not None and len(cube[k]) > 1]
    constant_meta_names = [k for k in cube.__dataclass_fields__.keys() if cube[k] is None]
    dims = {k: len(cube[k]) for k in dim_names}

    data = OnDiskArray(filename, index, cube)
    lock = LOCK
    data = GribBackendArray(data, lock)
    data = indexing.LazilyIndexedArray(data)
    if len(dim_names) != len(data.shape):
        raise ValueError(
            "different number of dimensions on data "
            f"and dims: {len(data.shape)} vs {len(dim_names)}\n"
            "Grib2 messages could not be formed into a data cube; "
            "It's possible extra messages exist along a non-accounted for dimension based on PDTN\n"
            "It might be possible to get around this by applying a filter on the non-accounted for dimension"
            )
    da = xr.DataArray(data, dims=dim_names)

    da.encoding['original_shape'] = data.shape

    da.encoding['preferred_chunks'] = {'y':-1, 'x':-1}
    msg1 = index.msg.iloc[0]

    # plain language metadata is minimized
    da.attrs['GRIB2IO_section0'] = msg1.section0
    da.attrs['GRIB2IO_section1'] = msg1.section1
    da.attrs['GRIB2IO_section2'] = msg1.section2 if msg1.section2 else []
    da.attrs['GRIB2IO_section3'] = msg1.section3
    da.attrs['GRIB2IO_section4'] = msg1.section4
    da.attrs['GRIB2IO_section5'] = msg1.section5
    da.attrs['fullName'] = msg1.fullName
    da.attrs['shortName'] = msg1.shortName
    da.attrs['units'] = msg1.units

    da.name = index.shortName.iloc[0]
    for meta_name in constant_meta_names:
        if meta_name in index.columns:
            da.attrs[meta_name] = index[meta_name].iloc[0]

    return da


def _asarray_tuplesafe(values):
    """
    Convert values to a numpy array of at most 1-dimension and preserve tuples.

    Adapted from pandas.core.common._asarray_tuplesafe grabbed from xarray
    because prefixed with _
    """
    if isinstance(values, tuple):
        result = utils.to_0d_object_array(values)
    else:
        result = np.asarray(values)
        if result.ndim == 2:
            result = np.empty(len(values), dtype=object)
            result[:] = values

    return result


def make_variables(index, f, non_geo_dims):
    """
    Create an individual dataframe index and cube for each variable.

    Parameters
    ----------
    index
        Index of cube.
    f
        ?
    non_geo_dims
        Dimensions not associated with the x,y grid

    Returns
    -------
    ordered_frames
        List of dataframes, one for each variable.
    cube
        Cube of grib2 messages.
    extra_geo
        Extra geographic coordinates.
    """
    # let shortName determine the variables

    # set the index to the name
    index = index.set_index('shortName').sort_index()
    # return nothing if no data
    if index.empty:
        return None,None,None

    # define the DimCube
    dims = copy(non_geo_dims)
    dims.append(Cube)
    dims.reverse()

    @dataclass(init=False)
    class DimCube(*dims):
        def __eq__(self, other):
            return dc_eq(self, other)

    ordered_meta = list(DimCube.__dataclass_fields__.keys())
    cube = None
    ordered_frames = list()
    for key in index.index.unique():
        frame = index.loc[[key]]
        frame = frame.reset_index()
        # frame is a dataframe with all records for one variable
        c = DimCube()
        #for colname in frame.columns:
        for colname in ordered_meta[:-2]:
            uniques = pd.Index(frame[colname]).unique()
            if len(uniques) > 1:
                c[colname] = uniques.sort_values()
            else:
                c[colname] = [uniques[0]]

        dims = [k for k in ordered_meta if k not in {'y','x'} and len(c[k]) > 1]

        for dim in dims:
            if frame[dim].value_counts().nunique() > 1:
                raise ValueError(f'uneven number of grib msgs associated with dimension: {dim}\n unique values for {dim}: {frame[dim].unique()} ')

        if len(dims) >= 1: # dims may be empty if no extra dims on top of x,y
            frame = frame.sort_values(dims)
            frame = frame.set_index(dims)

        if cube:
            if cube != c:
                raise ValueError(f'{cube},\n {c};\n cubes are not the same; filter to a single cube')
        else:
            cube = c

        # miloc is multi-index integer location of msg in nd DataArray
        miloc = list(zip(*[frame.index.unique(level=dim).get_indexer(frame.index.get_level_values(dim)) for dim in dims]))

        # set frame multi index
        if len(miloc) >= 1:  # miloc will be empty when no extra dims, thus no multiindex
            dim_ix = tuple([n+'_ix' for n in dims])
            frame = frame.set_index(pd.MultiIndex.from_tuples(miloc, names=dim_ix))

        ordered_frames.append(frame)

    # no variables
    if cube is None:
        cube = DimCube()

    # check geography of data and assign to cube
    if len(index.ny.unique()) > 1 or len(index.nx.unique()) > 1:
        raise ValueError('multiple grids not accommodated')
    cube.y = range(int(index.ny.iloc[0]))
    cube.x = range(int(index.nx.iloc[0]))

    extra_geo = None
    msg = index.msg.iloc[0]

    # we want the lat lons; make them via accessing a record; we are assuming
    # all records are the same grid because they have the same shape;
    # may want a unique grid identifier from grib2io to avoid assuming this
    latitude, longitude = msg.latlons()
    latitude = xr.DataArray(latitude, dims=['y','x'])
    latitude.attrs['standard_name'] = 'latitude'
    longitude = xr.DataArray(longitude, dims=['y','x'])
    longitude.attrs['standard_name'] = 'longitude'
    extra_geo = dict(latitude=latitude, longitude=longitude)

    return ordered_frames, cube, extra_geo


def interp_nd(a,*, method, grid_def_in, grid_def_out, method_options=None, num_threads=1):
    front_shape = a.shape[:-2]
    a = a.reshape(-1,a.shape[-2],a.shape[-1])
    a = grib2io.interpolate(a, method, grid_def_in, grid_def_out, method_options=method_options,
                            num_threads=num_threads)
    a = a.reshape(front_shape + (a.shape[-2], a.shape[-1]))
    return a


def interp_nd_stations(a,*, method, grid_def_in, lats, lons, method_options=None, num_threads=1):
    front_shape = a.shape[:-2]
    a = a.reshape(-1,a.shape[-2],a.shape[-1])
    a = grib2io.interpolate_to_stations(a, method, grid_def_in, lats, lons, method_options=method_options,
                                        num_threads=num_threads)
    a = a.reshape(front_shape + (len(lats),))
    return a


@xr.register_dataset_accessor("grib2io")
class Grib2ioDataSet:

    def __init__(self, xarray_obj):
        self._obj = xarray_obj


    def griddef(self):
        return Grib2GridDef.from_section3(self._obj[list(self._obj.data_vars)[0]].attrs['GRIB2IO_section3'])


    def interp(self, method, grid_def_out, method_options=None, num_threads=1) -> xr.Dataset:
        # see interp method of class Grib2ioDataArray
        da = self._obj.to_array()
        da.attrs['GRIB2IO_section3'] = self._obj[list(self._obj.data_vars)[0]].attrs['GRIB2IO_section3']
        da = da.grib2io.interp(method, grid_def_out, method_options=method_options,
                               num_threads=num_threads)
        ds = da.to_dataset(dim='variable')
        return ds


    def interp_to_stations(self, method, calls, lats, lons, method_options=None, num_threads=1) -> xr.Dataset:
        # see interp_to_stations method of class Grib2ioDataArray
        da = self._obj.to_array()
        da.attrs['GRIB2IO_section3'] = self._obj[list(self._obj.data_vars)[0]].attrs['GRIB2IO_section3']
        da = da.grib2io.interp_to_stations(method, calls, lats, lons, method_options=method_options,
                                           num_threads=num_threads)
        ds = da.to_dataset(dim='variable')
        return ds

    def to_grib2(self, filename, mode: typing.Literal["x", "w", "a"] = "x"):
        """
        Write a DataSet to a grib2 file.

        Parameters
        ----------
        filename
            Name of the grib2 file to write to.
        mode: {"x", "w", "a"}, optional, default="x"
            Persistence mode

            +------+-----------------------------------+
            | mode | Description                       |
            +======+===================================+
            | x    | create (fail if exists)           |
            +------+-----------------------------------+
            | w    | create (overwrite if exists)      |
            +------+-----------------------------------+
            | a    | append (create if does not exist) |
            +------+-----------------------------------+

        """
        ds = self._obj

        for shortName in sorted(ds):
            # make a DataArray from the "Data Variables" in the DataSet
            da = ds[shortName]

            da.grib2io.to_grib2(filename, mode=mode)
            mode = "a"


@xr.register_dataarray_accessor("grib2io")
class Grib2ioDataArray:

    def __init__(self, xarray_obj):
        self._obj = xarray_obj


    def griddef(self):
        return Grib2GridDef.from_section3(self._obj.attrs['GRIB2IO_section3'])


    def interp(self, method, grid_def_out, method_options=None, num_threads=1) -> xr.DataArray:
        """
        Perform grid spatial interpolation.

        Uses the [NCEPLIBS-ip library](https://github.com/NOAA-EMC/NCEPLIBS-ip).

        Parameters
        ----------
        method
            Interpolate method to use. This can either be an integer or string
            using the following mapping:

            | Interpolate Scheme | Integer Value |
            | :---:              | :---:         |
            | 'bilinear'         | 0             |
            | 'bicubic'          | 1             |
            | 'neighbor'         | 2             |
            | 'budget'           | 3             |
            | 'spectral'         | 4             |
            | 'neighbor-budget'  | 6             |
        grid_def_out
            Grib2GridDef object of the output grid.
        method_options : list of ints, optional
            Interpolation options. See the NCEPLIBS-ip documentation for
            more information on how these are used.
        num_threads : int, optional
            Number of OpenMP threads to use for interpolation. The default
            value is 1. If grib2io_interp was not built with OpenMP, then
            this keyword argument and value will have no impact.

        Returns
        -------
        interp
            DataSet interpolated to new grid definition.  The attribute
            GRIB2IO_section3 is replaced with the section3 array from the new
            grid definition.
        """
        da = self._obj
        # ensure that y, x are rightmost dims; they should be if opening with
        # grib2io engine

        # gdtn and gdt is not the entirety of the new s3
        npoints = grid_def_out.npoints
        s3_new = np.array([0,npoints,0,0,grid_def_out.gdtn] + list(grid_def_out.gdt))

        # make new lat lons
        lats, lons = Grib2Message(section3=s3_new, pdtn=0, drtn=0).grid()
        latitude = xr.DataArray(lats, dims=['y','x'])
        longitude = xr.DataArray(lons, dims=['y','x'])

        # create new coords
        new_coords = dict(da.coords)
        del new_coords['latitude']
        del new_coords['longitude']
        new_coords['longitude'] = longitude
        new_coords['latitude'] = latitude

        # make grid def in from section3 on da.attrs
        grid_def_in = self.griddef()

        if da.chunks is None:
            data = interp_nd(da.data, method=method, grid_def_in=grid_def_in,
                             grid_def_out=grid_def_out,
                             method_options=method_options,num_threads=num_threads)
        else:
            import dask
            front_shape = da.shape[:-2]
            data = da.data.map_blocks(interp_nd, method=method, grid_def_in=grid_def_in,
                                      grid_def_out=grid_def_out, method_options=method_options,
                                      chunks=da.chunks[:-2]+latitude.shape, dtype=da.dtype)

        new_da = xr.DataArray(data, dims=da.dims, coords=new_coords, attrs=da.attrs)

        new_da.attrs['GRIB2IO_section3'] = s3_new
        new_da.name = da.name
        return new_da


    def interp_to_stations(self, method, calls, lats, lons, method_options=None, num_threads=1) -> xr.DataArray:
        """
        Perform spatial interpolation to station points.

        Parameters
        ----------
        method
            Interpolate method to use. This can either be an integer or string
            using the following mapping:

            | Interpolate Scheme | Integer Value |
            | :---:              | :---:         |
            | 'bilinear'         | 0             |
            | 'bicubic'          | 1             |
            | 'neighbor'         | 2             |
            | 'budget'           | 3             |
            | 'spectral'         | 4             |
            | 'neighbor-budget'  | 6             |

        calls
            Station calls used for labeling new station index coordinate
        lats
            Latitudes of the station points.
        lons
            Longitudes of the station points.

        Returns
        -------
        interp_to_stations
            DataArray interpolated to lat and lon locations and labeled with
            dimension and coordinate 'station'. (..., y, x) -> (..., station)
        """
        da = self._obj
        #TODO ensure that y, x are rightmost dims; they should be if opening
        # with grib2io engine

        calls = np.asarray(calls)
        lats = np.asarray(lats)
        lons = np.asarray(lons)
        latitude = xr.DataArray(lats, dims=['station'])
        longitude = xr.DataArray(lons, dims=['station'])

        # create new coords
        new_coords = dict(da.coords)
        del new_coords['latitude']
        del new_coords['longitude']
        new_coords['longitude'] = longitude
        new_coords['latitude'] = latitude
        new_coords['station'] = calls

        new_dims = da.dims[:-2] + ('station',)

        # make grid def in from section3 on da attrs
        grid_def_in = self.griddef()

        if da.chunks is None:
            data = interp_nd_stations(da.data, method=method, grid_def_in=grid_def_in, lats=lats,
                                      lons=lons, method_options=method_options, num_threads=num_threads)
        else:
            import dask
            front_shape = da.shape[:-1]
            data = da.data.map_blocks(interp_nd_stations, method=method, grid_def_in=grid_def_in,
                                      lats=lats, lons=lons, method_options=method_options,
                                      drop_axis=-1, chunks=da.chunks[:-2]+latitude.shape,
                                      dtype=da.dtype)

        new_da = xr.DataArray(data, dims=new_dims, coords=new_coords, attrs=da.attrs)

        new_da.name = da.name
        return new_da

    def to_grib2(self, filename, mode: typing.Literal["x", "w", "a"] = "x"):
        """
        Write a DataArray to a grib2 file.

        Parameters
        ----------
        filename
            Name of the grib2 file to write to.
        mode: {"x", "w", "a"}, optional, default="x"
            Persistence mode

            +------+-----------------------------------+
            | mode | Description                       |
            +======+===================================+
            | x    | create (fail if exists)           |
            +------+-----------------------------------+
            | w    | create (overwrite if exists)      |
            +------+-----------------------------------+
            | a    | append (create if does not exist) |
            +------+-----------------------------------+

        """
        da = self._obj.copy(deep=True)

        # If there are indexes, the DataArray is a hypercube of grib2
        # messages.  Loop through the indexes and write each message to the
        # file, setting the appropriate grib2 message metadata to the index
        # values.
        index_keys = list(da.coords.keys())
        index_keys = [
            k for k in index_keys if k not in ["latitude", "longitude", "validDate"]
        ]
        indexes = []
        for index in sorted(index_keys):
            values = da.coords[index].values
            if not isinstance(values, np.ndarray):
                continue
            if values.ndim != 1:
                continue
            listeach = [{index: value} for value in sorted(set(values))]
            indexes.append(listeach)

        for selectors in itertools.product(*indexes):
            filters = {k: v for d in selectors for k, v in d.items()}
            try:
                selected = da.sel(**filters)
            except KeyError:
                raise ValueError(
                    f"The shape of the xarray doesn't allow a selection of a single grib2 message with '{filters}'"
                )

            newmsg = Grib2Message(
                selected.attrs["GRIB2IO_section0"],
                selected.attrs["GRIB2IO_section1"],
                selected.attrs["GRIB2IO_section2"],
                selected.attrs["GRIB2IO_section3"],
                selected.attrs["GRIB2IO_section4"],
                selected.attrs["GRIB2IO_section5"],
            )
            newmsg.data = np.array(selected.data)

            for index, value in filters.items():
                setattr(newmsg, index, value)

            # write the message to file
            with grib2io.open(filename, mode=mode) as f:
                f.write(newmsg)
            mode = "a"
