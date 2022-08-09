#!/usr/bin/env python3
# TdlpackBackend is a backend entrypoint for decoding sequential tdlpack files with xarray engine 'grib'
# TdlpackBackend is pre-release and the API is subject to change without backward compatability
from pathlib import Path
import shutil
import datetime
import numbers
from dataclasses import dataclass, field, astuple
import typing
from copy import copy
from abc import ABC, abstractmethod
from itertools import product
import logging
import numpy as np
import pandas as pd
import xarray as xr
from xarray.backends.common import (
    BACKEND_ENTRYPOINTS,
    AbstractDataStore,
    BackendArray,
    BackendEntrypoint,
)
from xarray.core import indexing
from xarray.backends.locks import SerializableLock
import grib2io
from grib2io import Grib2Message
import pytdlpack
import TdlpackIO

logger = logging.getLogger(__name__)

ONE_MB = 1048576 # 1 MB in units of bytes
LOCK = SerializableLock()

class GribBackendEntrypoint(BackendEntrypoint):
    ''' xarray backend engine entrypoint for opening and decoding grib files.

    .. warning::
            This backend is pre-release and its signature may change without backward comaptability.

    Parameters
    __________

    filename: str, Path, file-like
        grib file to be opened
    filters: dict, optional for filtering grib2 msgs to single hypercube
    '''
    def open_dataset(
        self,
        filename,
        *,
        drop_variables = None,
        filters: typing.Mapping[str, any] = dict(),
    ):

        # read and parse metadata from grib file
        f = grib2io.open(filename)
        file_index = pd.DataFrame(f._index)

        initial_filters = copy(filters)

        # apply common filters(to all definition templates) to reduce dataset to single cube

        # apply product definition template number filter
        if 'productDefinitionTemplateNumber' in filters:
            if not isinstance(filters['productDefinitionTemplateNumber'], int):
                raise TypeError('productDefinitionTemplateNumber filter must be of type int')
            file_index = file_index.loc[file_index['productDefinitionTemplateNumber'] == filters['productDefinitionTemplateNumber']]
        if len(file_index.productDefinitionTemplateNumber.unique()) != 1:
            raise ValueError(f'filter to a single productDefinitionTemplateNumber; found: {file_index.productDefinitionTemplateNumber.unique()}')

        # apply type of first fixed surface filter
        if 'typeOfFirstFixedSurface' in filters:
            if not isinstance(filters['typeOfFirstFixedSurface'], str):
                raise TypeError('typeOfFirstFixedSurface filter must be of type str')
            file_index = file_index.loc[file_index['typeOfFirstFixedSurface'] == filters['typeOfFirstFixedSurface']]
        if len(file_index.typeOfFirstFixedSurface.unique()) != 1:
            raise ValueError(f'filter to a single typeOfFirstFixedSurface; found: {file_index.typeOfFirstFixedSurface.unique()}')


        file_index, non_geo_dims = parse_grib_index(file_index, filters)

        # Apply rest of filters and divide up records by variable
        frames, cube, extra_geo = make_variables(file_index, filters, f, non_geo_dims)
        # return empty dataset if no data
        if frames is None:
            return xr.Dataset()

        # create dataframe and add datarrays without any coords
        ds = xr.Dataset()
        for var_df in frames:
            da = build_da_without_coords(var_df, cube, f)
            ds[da.name] = da

        # done with open file
        f.close()

        # assign coords from the cube; the cube prevents datarrays with different shapes
        ds = ds.assign_coords(cube.coords())
        # assign extra geo coords
        ds = ds.assign_coords(extra_geo)

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
        # thread safe method implementing access to data on disk
        with self.lock:
            return self.array[key]


def exclusive_slice_to_inclusive(item):
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
    """Check if a and b are equal, even if they are numpy arrays"""
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
    """checks if two dataclasses which hold numpy arrays are equal"""
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
            if k is not None and len(self[k]) > 1:
                coords[k] = xr.Variable(dims=k, data=self[k], attrs=dict(tdlp_name=k))
            elif k is not None and len(self[k]) == 1:
                coords[k] = xr.Variable(dims=tuple(), data=np.array(self[k]).squeeze(), attrs=dict(tdlp_name=k))
        #coords = {k: xr.Variable(dims=k, data=self[k], attrs=dict(tdlp_name=k)) for k in keys if self[k] is not None and}
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
        geo_shape = (int(self.index.iloc[0].ny), int(self.index.iloc[0].nx))  # multiple grids not allowed so can just use first

        self.geo_shape = geo_shape
        self.geo_ndim = len(geo_shape)

        #print(self.index.index.name)
        if self.index.index.name is None:
            #self.shape = (len(self.index),) + geo_shape
            self.shape = geo_shape
        else:
            if self.index.index.nlevels == 1:
                self.shape = tuple([len(self.index.index)]) + geo_shape
            else:
                self.shape = tuple([len(i) for i in self.index.index.levels]) + geo_shape
        self.ndim = len(self.shape)


    def __getitem__(self, item) -> np.array:
        # dimensions not in index are internal to tdlpack records; 2 dims for grids; 1 dim for stations
        filehandle = open(self.file_name, mode='rb', buffering=ONE_MB)

        index_slicer = item[:-self.geo_ndim]
        index_slicer = tuple([[i] if isinstance(i, int) else i for i in index_slicer]) # maintain all multindex levels
        # pandas loc slicing is inclusive, therefore convert slices into explicit lists
        index_slicer_inclusive = tuple([ exclusive_slice_to_inclusive(i) if isinstance(i, slice) else i for i in index_slicer])

        # get records selected by item in new index dataframe
        if len(index_slicer_inclusive) == 1:
            index = self.index.loc[index_slicer_inclusive]
        elif len(index_slicer_inclusive) > 1:
            index = self.index.loc[index_slicer_inclusive, :]
        else:
            index = self.index
        index = index.set_index(index.index)

        # reset miloc to new relative locations in sub array
        index['miloc'] = list(zip(*[index.index.unique(level=dim).get_indexer(index.index.get_level_values(dim)) for dim in index.index.names]))

        if len(index_slicer_inclusive) == 1:
            array_field_shape = tuple([len(index.index)]) + self.geo_shape
        elif len(index_slicer_inclusive) > 1:
            array_field_shape = index.index.levshape + self.geo_shape
        else:
            array_field_shape = self.geo_shape

        array_field = np.full(array_field_shape, fill_value=np.nan, dtype="float32")

        with open(self.file_name, mode='rb', buffering=ONE_MB) as filehandle:
            for key, row in index.iterrows():
                t2 = datetime.datetime.now()
                filehandle.seek(int(row['offset']))
                t3 = datetime.datetime.now()
                msg = Grib2Message(msg=filehandle.read(int(row['size'])),
                    source='grib file',
                    num=row['messageNumber'],
                    decode=False,
                    )
                #print(f'msg create took: {datetime.datetime.now() - t3}')

                # data method sometimes returns masked array and sometimes ndarray
                # convert to ndarray with nan values where masked
                a = msg.data()
                if isinstance(a, np.ndarray):
                    values = a
                else:
                    values = a.filled(np.nan)

                if len(index_slicer_inclusive) >= 1:
                    array_field[row.miloc] = values
                else:
                    array_field = values
                #print(f'msg load took: {datetime.datetime.now() - t2}')

        # handle geo dim slicing
        #print(f'data load took: {datetime.datetime.now() - t1}')
        array_field = array_field[(Ellipsis,) + item[-self.geo_ndim :]]

        # squeeze array dimensions expressed as integer
        for i, it in reversed(list(enumerate(item[: -self.geo_ndim]))):
            if isinstance(it, int):
                array_field = array_field[(slice(None, None, None),) * i + (0,)]
        #f.close()
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
			label_value = label[()] if label.dtype.kind in "mM" else label.item() # see https://github.com/pydata/xarray/pull/4292 for details
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


def parse_grib_index(df, filters):
    '''
    from product definition template number, evaluate what dimesnions are possible and parse each out
    '''
    df['refDate'] = pd.to_datetime(df['refDate'], format='%Y%m%d%H')
    df['leadTime'] = pd.to_timedelta(df['leadTime'], unit='hour')

    # by this point the index is filtered down to a single typeOfFirstFixedSurface and productDefinitionTemplateNumber
    non_geo_dims = list()

    @dataclass(init=False)
    class RefDateDim:
        refDate: pd.Index = PdIndex()
    non_geo_dims.append(RefDateDim)

    @dataclass(init=False)
    class LeadTimeDim:
        leadTime: pd.Index = PdIndex()
    non_geo_dims.append(LeadTimeDim)

    if 'valueOfFirstFixedSurface' in filters:
        df = filter_index(df, 'valueOfFirstFixedSurface', filters['valueOfFirstFixedSurface'])
        del filters['valueOfFirstFixedSurface']

    if len(df['valueOfFirstFixedSurface'].unique()) > 1:
        # we have multiple levels
        @dataclass(init=False)
        class ValueOfFirstFixedSurfaceDim:
            valueOfFirstFixedSurface: pd.Index = PdIndex()
        non_geo_dims.append(ValueOfFirstFixedSurfaceDim)

    # logic for parsing possible dims from product definition section

    return df, non_geo_dims


def build_da_without_coords(index, cube, file) -> xr.DataArray:
    dim_names = [k for k in cube.__dataclass_fields__.keys() if cube[k] is not None and len(cube[k]) > 1]
    constant_meta_names = [k for k in cube.__dataclass_fields__.keys() if cube[k] is None]
    dims = {k: len(cube[k]) for k in dim_names}

    data = OnDiskArray(file.name, index, cube)
    lock = LOCK
    data = GribBackendArray(data, lock)
    data = indexing.LazilyIndexedArray(data)
    da = xr.DataArray(data, dims=dim_names)

    da.encoding['original_shape'] = data.shape

    da.encoding['preffered_chunks'] = {'y':-1, 'x':-1}
    msg1 = file[int(index.messageNumber.iloc[0])][0]
    for attr in msg1.__dict__.keys():
        if not attr.startswith('_'):
            at = f'GRIB_{attr}'
            try:
                if not msg1.__dict__[attr]:
                    continue
            except ValueError:
                continue  # encountered np arrays; ignore for now
            if isinstance(msg1.__dict__[attr], grib2io.Grib2Metadata):
                v = msg1.__dict__[attr].value
            elif isinstance(msg1.__dict__[attr], (str, numbers.Number, np.ndarray, list, tuple)):
                v = msg1.__dict__[attr]
                if isinstance(v, bool):
                    if v:
                        v = 1
                    else:
                        v = 0
            else:
                continue
            if at not in cube:
                da.attrs[at] = v
            elif cube[at] is None:
                da.attrs[at] = v



    da.name = index.shortName.iloc[0]
    for meta_name in constant_meta_names:
        if meta_name in index.columns:
            da.attrs[meta_name] = index[meta_name].iloc[0]
            #da.encoding[f'tdlp_{meta_name}'] = da.attrs[meta_name]

    return da

zfil = {
        'cccfff' : 6,
        'ccc' : 3,
        'fff' : 3,
        'b' : 1,
        'dd' : 2,
        'v' : 1,
        'llll' : 4,
        'uuuu' : 4,
        't' : 1,
        'o' : 1,
        'thresh' : 7,
        }
def _asarray_tuplesafe(values):
    """
    Convert values into a numpy array of at most 1-dimension, while preserving
    tuples.

    Adapted from pandas.core.common._asarray_tuplesafe
    grabbed from xarray because prefixed with _
    """
    if isinstance(values, tuple):
        result = utils.to_0d_object_array(values)
    else:
        result = np.asarray(values)
        if result.ndim == 2:
            result = np.empty(len(values), dtype=object)
            result[:] = values

    return result

def make_variables(index, filters, f, non_geo_dims):
    ''' from index as dataframe, separate by variable
        create an individual dataframe index and cube for each variable'''

    # let shortName determine the variables

    # adopt parts of xarray's sel logic  so that filters behave similarly
    # allowed to filter to nothing to make empty dataset
    if filters:
        for k, v in filters.items():
            index = filter_index(index, k, v)

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
            if len(frame[colname].unique()) > 1:
                c[colname] = frame[colname].sort_values().unique()

        if c.refDate is None:
            # case where only one date; use date as unit dimesnion
            c['refDate'] = [frame.refDate.iloc[0]]
            #setattr(cube, 'date', [frame.date.iloc[0]])

        if c.leadTime is None:
            # case where only one lead; use lead as unit dimesnion
            c['leadTime'] = [frame.leadTime.iloc[0]]


        dims = [k for k in ordered_meta if c[k] is not None and len(c[k]) > 1]

        if len(dims) >= 1: # dims may be empty if no extra dims on top of x,y
            frame = frame.sort_values(dims)
            frame = frame.set_index(dims)

        if cube:
            if cube != c:
                raise ValueError(f'{cube},\n {c};\n cubes are not the same; filter to a single cube')
        else:
            cube = c

        # miloc is multi-index integer location
        miloc = list(zip(*[frame.index.unique(level=dim).get_indexer(frame.index.get_level_values(dim)) for dim in dims]))
        if len(miloc) >= 1:  # miloc will be empty when no extra dims
            frame = frame.assign(miloc=miloc)
        dim_ix = tuple([n+'_ix' for n in dims])
        if len(miloc) >= 1:  # miloc will be empty when no extra dims
            frame = frame.set_index(pd.MultiIndex.from_tuples(frame.miloc, names=dim_ix))

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
    rec = f[int(ordered_frames[0].messageNumber.iloc[0])][0]

    # we want the lat lons; make them via accessing a record; we are asuming all records are the same grid because they have the same shape;
    # may want a unique grid identifier from grib2io to avoid assuming this
    latitude, longitude = rec.latlons()
    latitude = xr.DataArray(latitude, dims=['y','x'])
    latitude.attrs['standard_name'] = 'latitude'
    longitude = xr.DataArray(longitude * -1, dims=['y','x'])
    longitude.attrs['standard_name'] = 'longitude'
    extra_geo = dict(latitude=latitude, longitude=longitude)
    return ordered_frames, cube, extra_geo
