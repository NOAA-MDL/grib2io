"""
grib2io xarray backend is a backend entrypoint for decoding grib2 files with
xarray engine 'grib2io' API is experimental and is subject to change without
backward compatibility.
"""
from grib2io._grib2io import _data
from grib2io import Grib2Message, Grib2GridDef
import grib2io
from xarray.backends.locks import SerializableLock
from xarray.core import indexing
from xarray.backends import (
    BackendArray,
    BackendEntrypoint,
)
from copy import copy
from dataclasses import dataclass, field, astuple
import importlib.metadata
import itertools
import logging
import typing
from warnings import warn

from . import tables

import numpy as np
import pandas as pd
import xarray as xr
import re
from pyproj import CRS
import datetime

# Check if xarray version supports DataTree
HAS_DATATREE = False
try:
    # Try importing DataTree to check if it's available
    xarray_version = importlib.metadata.version('xarray')
    xarray_parts = [int(x) if x.isdigit() else x for x in xarray_version.split('.')]
    min_version_parts = [2024, 10, 0]
    HAS_DATATREE = xarray_parts >= min_version_parts
except (ImportError, ValueError):
    HAS_DATATREE = False


logger = logging.getLogger(__name__)

LOCK = SerializableLock()

AVAILABLE_NON_GEO_COORDS = [
    "duration",
    "leadTime",
    "percentileValue",
    "perturbationNumber",
    "refDate",
    "thresholdLowerLimit",
    "thresholdUpperLimit",
    "valueOfFirstFixedSurface",
    "valueOfSecondFixedSurface",
    "aerosolType",
    "scaledValueOfFirstWavelength",
    "scaledValueOfSecondWavelength",
    "scaledValueOfCentralWaveNumber",
    "scaledValueOfFirstSize",
    "scaledValueOfSecondSize"
]


AVAILABLE_NON_GEO_DIMS = [
    "duration",
    "leadTime",
    "percentileValue",
    "perturbationNumber",
    "refDate",
    "threshold",
    "level",
]


# Lookup table to define surface types that should be parsed as vertical coordinates
VERTICAL_COORDINATE_SURFACES = [
    'Ground or Water Surface',
    'Isothermal Level',
    'Specified radius from the centre of the Sun',
    'Isobaric Surface',
    'Mean Sea Level',
    'Specific Altitude Above Mean Sea Level',
    'Specified Height Level Above Ground',
    'Sigma Level',
    'Hybrid Level',
    'Depth Below Land Surface',
    'Isentropic (theta) Level',
    'Level at Specified Pressure Difference from Ground to Level',
    'Potential Vorticity Surface',
    'Eta Level',
    'Logarithmic Hybrid Level',
    'Sigma height level',
    'Hybrid Height Level',
    'Hybrid Pressure Level',
    'Soil level',
    'Sea-ice level',
    'Depth Below Sea Level',
    'Depth Below Water Surface',
    'Ocean Model Level',
    'Ocean level defined by water density (sigma-theta) difference from near-surface to level',
    'Ocean level defined by water potential temperature difference from near-surface to level',
    'Ocean level defined by vertical eddy diffusivity difference from near-surface to level',
    'Ocean level defined by water density (rho) difference from near-surface to level'
]


# Use custom table to map numeric level codes to human-readable names
LEVEL_NAME_MAPPING = grib2io.tables.get_table('4.5.grib2io.level.name')


# Define the order of hierarchy levels for the DataTree
TREE_HIERARCHY_LEVELS = [
    "typeOfFirstFixedSurface",
    "valueOfFirstFixedSurface",
    "productDefinitionTemplateNumber",
    "perturbationNumber",
    "leadTime",
    "duration",
    "percentileValue",
    "typeOfProbability",
    "thresholdLowerLimit",
    "thresholdUpperLimit"
]

# Levels included in data variables rather than tree structure
VARIABLE_LEVELS = []


def parse_data_model(ds, data_model):

    def _decode_ptype(values):
        """
        Decode precipitation type values into human-readable strings.

        Args:
            values: Array of numeric precipitation type codes

        Returns:
            numpy.ndarray: Array of decoded precipitation type strings

        Uses GRIB2 Table 4.201 to map numeric codes to precipitation type descriptions.
        """
        results = []
        for val in values:
            # Convert each numeric code to string and look up in Table 4.201
            results.append(str(tables.get_value_from_table(str(int(val)), '4.201')))

        # Return array of strings using numpy's string data type
        return np.array(results, dtype=np.dtypes.StringDType)

    # convert coordinates and attributes to CF if requested
    if data_model == 'nws-viz':

        # define regex to convert to snake case
        pattern = re.compile(r'(?<!^)(?=[A-Z])')

        # check for coordinates and rename
        for coord in ds.coords:
            if coord == 'refDate':
                ds = ds.rename({'refDate': 'forecast_reference_time'})

            elif coord == 'leadTime':
                ds = ds.rename({'leadTime': 'lead_time'})

            elif coord == 'validDate':
                ds = ds.rename({'validDate': 'time'})

            elif coord == 'percentileValue':
                ds = ds.rename({'percentileValue': 'percentile'})

            elif coord == 'thresholdLowerLimit':
                ds = ds.rename({'thresholdLowerLimit': 'threshold_lower_limit'})
                ds['threshold_lower_limit'].attrs['long_name'] = 'Threshold Lower Limit'
                ds['threshold_lower_limit'].attrs['units'] = ds[list(ds.data_vars.keys())[0]].attrs['units']

                if 'PTYPE' in ds.data_vars:
                    ds['threshold_lower_limit'] = xr.apply_ufunc(_decode_ptype, ds['threshold_lower_limit'])

                # check if thresholdLowerLimit should be a dimension coordinate
                if 'threshold' in ds.dims:
                    var_key = list(ds.data_vars.keys())[0]
                    prob_types = [
                        'Probability of event below lower limit',
                        'Probability of event above lower limit',
                        'Probability of event equal to lower limit',
                        'Probability of event between upper and lower limits (the range includes lower limit but not the upper limit)'
                    ]
                    if ds[var_key].attrs['typeOfProbability'] in prob_types:
                        ds = ds.swap_dims({'threshold': 'threshold_lower_limit'})

            elif coord == 'thresholdUpperLimit':
                ds = ds.rename({'thresholdUpperLimit': 'threshold_upper_limit'})
                ds['threshold_upper_limit'].attrs['long_name'] = 'Threshold Upper Limit'
                ds['threshold_upper_limit'].attrs['units'] = ds[list(ds.data_vars.keys())[0]].attrs['units']

                if 'PTYPE' in ds.data_vars:
                    ds['threshold_upper_limit'] = xr.apply_ufunc(_decode_ptype, ds['threshold_upper_limit'])

                if 'threshold' in ds.dims:
                    var_key = list(ds.data_vars.keys())[0]
                    prob_types = [
                        'Probability of event below upper limit',
                        'Probability of event above upper limit'
                    ]
                    if ds[var_key].attrs['typeOfProbability'] in prob_types:
                        ds = ds.swap_dims({'threshold': 'threshold_upper_limit'})

            # If the dataset has valueOfFirstFixedSurface as a coordinate
            elif coord == 'valueOfFirstFixedSurface':
                # Get the valueOfFirstFixedSurface coordinate
                da = ds.valueOfFirstFixedSurface

                # Get the definition and units from typeOfFirstFixedSurface
                var_key = list(ds.data_vars.keys())[0]
                definition, units = ds[var_key].attrs['typeOfFirstFixedSurface']

                if definition in VERTICAL_COORDINATE_SURFACES:
                    # Convert definition to lowercase and replace spaces with underscores
                    key = definition.lower().replace(' ', '_')

                    # remove special characters
                    key = re.sub(r'[^a-z0-9_]', '', key)

                    # Add units and grib_name attributes
                    da.attrs['units'] = units
                    da.attrs['grib_name'] = ['valueOfFirstFixedSurface', 'typeOfFirstFixedSurface']

                    # Assign the coordinate with the new key name
                    ds = ds.assign_coords({key: da})

                    # If valueOfFirstFixedSurface is a dimension, swap it with the new key
                    if 'level' in ds.dims:
                        ds = ds.swap_dims({"level": key})

                # Remove the original coordinates
                del ds['valueOfFirstFixedSurface']

            # If the dataset has valueOfSecondFixedSurface as a coordinate
            elif coord == 'valueOfSecondFixedSurface':
                # Get the valueOfSecondFixedSurface coordinate
                da = ds.valueOfSecondFixedSurface

                # Get the definition and units from typeOfSecondFixedSurface
                var_key = list(ds.data_vars.keys())[0]
                definition, units = ds[var_key].attrs['typeOfSecondFixedSurface']

                if definition in VERTICAL_COORDINATE_SURFACES:
                    # Convert definition to lowercase and replace spaces with underscores
                    key = definition.lower().replace(' ', '_')

                    # remove special characters
                    key = re.sub(r'[^a-z0-9_]', '', key)

                    # check if key is already in coords
                    if key in ds.coords:
                        key = key + '_2'

                    # Add units and grib_name attributes
                    da.attrs['units'] = units
                    da.attrs['grib_name'] = ['valueOfSecondFixedSurface', 'typeOfSecondFixedSurface']

                    # Assign the coordinate with the new key name
                    ds = ds.assign_coords({key: da})

                # Remove the original coordinates
                del ds['valueOfSecondFixedSurface']
            else:
                # change coord name to snake case
                new_coord_name = pattern.sub('_', coord).lower()
                ds = ds.rename({coord: new_coord_name})

        # convert all attributes and variable names to snake case
        for var in ds.data_vars:
            da = ds[var]
            record = tables.get_table('shortname_to_cf').get(da.name)
            da.attrs['standard_name'] = 'unknown' if record is None else record['cf_standard_name']
            da.attrs['cell_methods'] = 'unknown' if record is None else record['cf_cell_methods']

            ds[var] = da

            # rename variable
            new_var_name = var.lower()
            ds = ds.rename({var: new_var_name})

            # remove attr for typeOfFirstFixedSurface (applied as coordinate above)
            if 'typeOfFirstFixedSurface' in ds[new_var_name].attrs:
                definition, units = ds[new_var_name].attrs['typeOfFirstFixedSurface']
                ds[new_var_name].attrs['typeOfFirstFixedSurface'] = f'{definition} ({units})'

            if 'typeOfSecondFixedSurface' in ds[new_var_name].attrs:
                definition, units = ds[new_var_name].attrs['typeOfSecondFixedSurface']
                ds[new_var_name].attrs['typeOfSecondFixedSurface'] = f'{definition} ({units})'

            ds[new_var_name].attrs.pop('percentileValue', None)

            if 'threshold_lower_limit' in ds.coords:
                ds[new_var_name].attrs.pop('thresholdLowerLimit', None)

            if 'threshold_upper_limit' in ds.coords:
                ds[new_var_name].attrs.pop('thresholdUpperLimit', None)

            for attr in list(ds[new_var_name].attrs.keys()):
                # skip grib section attrs
                if 'GRIB2IO_section' in attr:
                    # replace GRIB2IO with grib in attr
                    new_attr_name = attr.replace('GRIB2IO', 'grib')
                else:
                    # change attr name to snake case
                    new_attr_name = pattern.sub('_', attr).lower()

                # update new attr name for specific CF names
                if new_attr_name == 'full_name':
                    new_attr_name = 'long_name'

                # change % to percent
                if attr == 'units' and ds[new_var_name].attrs[attr] == '%':
                    ds[new_var_name].attrs[attr] = 'percent'

                if new_var_name == 'ptype' and 'threshold' in new_attr_name:
                    value = ds[new_var_name].attrs.pop(attr)
                    ds[new_var_name].attrs[attr] = _decode_ptype(value)
                else:
                    # change attr name in attrs
                    ds[new_var_name].attrs[new_attr_name] = ds[new_var_name].attrs.pop(attr)


        # change dataset attrs to snake case
        for attr in list(ds.attrs.keys()):
            # change attr name to snake case
            new_attr_name = pattern.sub('_', attr).lower()

            # change attr name in attrs
            ds.attrs[new_attr_name] = ds.attrs.pop(attr)

        # change % to percent
        for coord in ds.coords:
            if 'units' in ds[coord].attrs and ds[coord].attrs['units'] == '%':
                ds[coord].attrs['units'] = 'percent'

    return ds


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
        drop_variables=None,
        filters: typing.Mapping[str, typing.Any] = dict(),
        data_model=None
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
        data_model
            Parse GRIB metadata following a defined data model comvention.

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
        file_index, dim_coords, attrs, coord_attrs = parse_grib_index(file_index, filters)

        # Divide up records by variable
        frames, cube, extra_geo = make_variables(file_index, filename, dim_coords)  # have this return var_attrs

        # return empty dataset if no data
        if frames is None:
            return xr.Dataset()

        # create dataframe and add datarrays without any coords
        ds = xr.Dataset()
        for var_df in frames:
            da = build_da_without_coords(var_df, cube, filename, attrs)
            ds[da.name] = da

        # add coords and dataset meta
        ds = assign_xr_meta(ds, frames, cube, dim_coords, extra_geo, coord_attrs)

        if data_model is not None:
            ds = parse_data_model(ds, data_model)

        # assign attributes
        ds.attrs['engine'] = 'grib2io'

        return ds

    def open_datatree(
        self,
        filename,
        *,
        drop_variables=None,
        filters: typing.Mapping[str, typing.Any] = None,
        stack_vertical: bool = False,
    ):
        """
        Open a GRIB2 file as an xarray DataTree.

        Parameters
        ----------
        filename : str
            Path to the GRIB2 file.
        drop_variables : list, optional
            List of variables to exclude.
        filters : dict, optional
            Filter criteria for GRIB2 messages.
        stack_vertical : bool, optional
            If True, organize the tree with vertical layers stacked in a single dataset.

        Returns
        -------
        xarray.DataTree
            A hierarchical DataTree representation of the GRIB2 data.
        """
        if not HAS_DATATREE:
            raise ImportError("xarray version does not support DataTree functionality.")

        if filters is None:
            filters = {}

        # Open the file without any filters first to get all messages
        with grib2io.open(filename, _xarray_backend=True) as f:
            file_index = pd.DataFrame(f._index)

        # Build tree structure from GRIB messages with specified options
        return build_datatree_from_grib(filename, file_index, filters, stack_vertical=stack_vertical)


class GribBackendArray(BackendArray):

    def __init__(self, array, lock):
        self.array = array
        self.shape = array.shape
        self.dtype = np.dtype(array.dtype)
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


def _asarray_tuplesafe(values):
    """
    Convert values to a numpy array of at most 1-dimension and preserve tuples.

    Adapted from pandas.core.common._asarray_tuplesafe
    """
    if isinstance(values, tuple):
        result = np.empty(1, dtype=object)
        result[0] = values
    else:
        result = np.asarray(values)
        if result.ndim == 2:
            result = np.empty(len(values), dtype=object)
            result[:] = values

    return result


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


def coords_from_cube(cube) -> typing.Dict[str, xr.Variable]:
    keys = list(cube.keys())
    keys.remove('x')
    keys.remove('y')
    coords = dict()
    for k in keys:
        if k is not None:
            if len(cube[k]) > 1:
                coords[k] = xr.Variable(dims=k, data=cube[k], attrs=dict(grib_name=k))
            elif len(cube[k]) == 1:
                coords[k] = xr.Variable(dims=tuple(), data=cube[k][0], attrs=dict(grib_name=k))
    return coords


@dataclass
class OnDiskArray:
    file_name: str
    index: pd.DataFrame = field(repr=False)
    cube: dict = field(repr=False)
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
        index_slicer_inclusive = tuple([exclusive_slice_to_inclusive(
            i) if isinstance(i, slice) else i for i in index_slicer])

        # get records selected by item in new index dataframe
        if len(index_slicer_inclusive) == 1:
            index = self.index.loc[index_slicer_inclusive]
        elif len(index_slicer_inclusive) > 1:
            index = self.index.loc[index_slicer_inclusive, :]
        else:
            index = self.index
        index = index.set_index(index.index)

        # set miloc to new relative locations in sub array
        index['miloc'] = list(
            zip(*[index.index.unique(level=dim).get_indexer(index.index.get_level_values(dim)) for dim in index.index.names]))

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
        array_field = array_field[(Ellipsis,) + item[-self.geo_ndim:]]

        # squeeze array dimensions expressed as integer
        for i, it in reversed(list(enumerate(item[: -self.geo_ndim]))):
            if isinstance(it, int):
                array_field = array_field[(slice(None, None, None),) * i + (0,)]

        return array_field


def dims_to_shape(d) -> tuple:
    if 'nx' in d:
        t = (d['ny'], d['nx'])
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


def parse_grib_index(
    index: pd.DataFrame,
    filters: typing.Mapping[str, typing.Any] = dict(),
):
    """
    Apply filters.

    Evaluate remaining dimensions based on pdtn and parse each out.

    Parameters
    ----------
    index
        Pandas DataFrame containing the GRIB2 message index.
    filters
        Filter GRIB2 messages to single hypercube. Dict keys can be any
        GRIB2 metadata attribute name.

    Returns
    -------
    index
        Modified Pandas DataFrame with added GRIB2 metadata columns.
    dim_coords
        List of GRIB2 attributes that will be used for coordinates and/or dimensions.
    attrs
        Dict of metadata attributes (non-coordinates, non-geo)
    """

    # make a copy of filters, remove filters as they are applied
    filters = copy(filters)

    for k, v in filters.items():
        if k not in index.columns:
            kwarg = {k: index.msg.apply(lambda msg: getattr(msg, k))}
            index = index.assign(**kwarg)
        # adopt parts of xarray's sel logic  so that filters behave similarly
        # allowed to filter to nothing to make empty dataset
        index = filter_index(index, k, v)

    if len(index) == 0:
        return index, list()

    dim_coords = dict()  # key=name of dim, value=list of coord names
    attrs = dict()
    coord_attrs = dict()

    # expand index
    index = index.assign(shortName=index.msg.apply(lambda msg: msg.shortName))
    index = index.assign(nx=index.msg.apply(lambda msg: msg.nx))
    index = index.assign(ny=index.msg.apply(lambda msg: msg.ny))
    index = index.astype({'ny': 'int', 'nx': 'int'})

    # apply common filters(to all definition templates) to reduce dataset to
    # single cube
    # ensure only one of each of the below exists after filters applied
    required_uniques = [
        "productDefinitionTemplateNumber",
        "typeOfGeneratingProcess",
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
    ]

    def meta_check(index, attrs, meta):
        """
        add meta to the datframe index
        check that there is a single type
        add the type to attrs

        returns index, attrs
        """
        index = index.assign(**{meta: index.msg.apply(lambda msg: getattr(msg, meta))})

        unique = index[meta].unique()
        if len(index[meta].unique()) > 1:
            raise ValueError(f'filter to a single {meta}; found: {[str(i) for i in unique]}')
        value = unique.item()
        if type(value) == grib2io.templates.Grib2Metadata:
            value = value.definition

        # None is returned if no value found,
        # check and change to string None
        if value is None:
            value = 'None'

        attrs[meta] = value
        return index, attrs

    for meta in required_uniques:
        index, attrs = meta_check(index, attrs, meta)

    pdtn = index.productDefinitionTemplateNumber.iloc[0].value

    # determine which non geo dimensions can be created from data by this point
    # the index is filtered down to a single type for all required_uniques

    # Dim Name     # matching dim_name for using this data as index coordinate
    dim_coords["refDate"] = ["refDate"]
    coord_attrs["refDate"] = dict(standard_name="forecast_reference_time")
#   dim_coords["refDate"] = ["refDate", "hour"] # non dim name matching items in list are used as non-index coordinates

    dim_coords["leadTime"] = ["leadTime"]
    coord_attrs["leadTime"] = dict(standard_name="forecast_period")

    if 'valueOfFirstFixedSurface' not in index.columns:
        index = index.assign(valueOfFirstFixedSurface=index.msg.apply(lambda msg: msg.valueOfFirstFixedSurface))
    if 'valueOfsecondFixedSurface' not in index.columns:
        index = index.assign(valueOfSecondFixedSurface=index.msg.apply(lambda msg: msg.valueOfSecondFixedSurface))

    # dim name api change, user could run ds = ds.swap_dims(fixedSurface="valueOfFirstFixedSurface")
    index = index.assign(level=list(zip(index['valueOfFirstFixedSurface'], index['valueOfSecondFixedSurface'])))
#   index = index.assign(level=index.msg.apply(lambda msg: msg.level))
    # lack of "level" indeicates don't create extra index coordinate "level"
    dim_coords["level"] = ["valueOfFirstFixedSurface", "valueOfSecondFixedSurface"]

    # logic for parsing possible dims from specific product definition section

    if pdtn in {5, 9}:

        # Probability forecasts at a horizontal level or in a horizontal layer
        # in a continuous or non-continuous time interval.  (see Template
        # 4.9)
        #       AVAILABLE_THRESHOLD = {
        #           0: {'has_lower': True, 'has_upper': False},
        #           1: {'has_lower': False, 'has_upper': True},
        #           2: {'has_lower': True, 'has_upper': True},
        #           3: {'has_lower': True, 'has_upper': False},
        #           4: {'has_lower': False, 'has_upper': True},
        #           5: {'has_lower': True, 'has_upper': False},
        #       }

        index, attrs = meta_check(index, attrs, "typeOfProbability")
        if 'thresholdLowerLimit' not in index.columns:
            index = index.assign(thresholdLowerLimit=index.msg.apply(lambda msg: msg.thresholdLowerLimit))
        if 'thresholdUpperLimit' not in index.columns:
            index = index.assign(thresholdUpperLimit=index.msg.apply(lambda msg: msg.thresholdUpperLimit))
        if 'threshold' not in index.columns:
            # using composite of lower and upper, but could use threshold string from grib2io as long as that is unique and based on lower and upper
            index = index.assign(threshold=list(zip(index['thresholdLowerLimit'], index['thresholdUpperLimit'])))
#           index = index.assign(threshold = index.msg.apply(lambda msg: msg.threshold))

        # ommiting threshold results in no index being assigned for this possible dim
        dim_coords["threshold"] = ["thresholdLowerLimit", "thresholdUpperLimit"]

    if pdtn in {6, 10}:

        # Percentile forecasts at a horizontal level or in a horizontal layer
        # in a continuous or non-continuous time interval.  (see Template
        # 4.10)
        dim_coords["percentileValue"] = ["percentileValue"]
        coord_attrs["percentileValue"] = dict(long_name='percentile', units='percent')

    if pdtn in {8, 9, 10, 11, 12, 13, 14, 42, 43, 45, 46, 47, 61, 62, 63, 67, 68, 72, 73, 78, 79, 82, 83, 84, 85, 87, 91}:
        dim_coords["duration"] = ["duration"]

    if pdtn in {1, 11, 33, 34, 41, 43, 45, 47, 49, 54, 56, 58, 59, 63, 68, 77, 79, 81, 83, 84, 85, 92}:
        dim_coords["perturbationNumber"] = ["perturbationNumber"]

    if pdtn in {2,3,4,12,13,14}:
        index, attrs = meta_check(index, attrs, 'typeOfDerivedForecast')

    if pdtn in {8,15,42,46,62,67,72,78,82,1001,1002,1100,1101}:
        index, attrs = meta_check(index, attrs, 'statisticalProcess')

    # Finish logic by pdtn

    for k, v in dim_coords.items():
        for meta in v:
            if meta not in index.columns:
                index = index.assign(**{meta: index.msg.apply(lambda msg: getattr(msg, meta))})

    return index, dim_coords, attrs, coord_attrs


def build_da_without_coords(index, cube, filename, attrs) -> xr.DataArray:
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
    add_grib_section_attrs
        Include grib section arrays as dataArray attributes

    Returns
    -------
    DataArray
        DataArray without coordinates
    """

    dim_names = [k for k in cube.keys() if cube[k] is not None and len(cube[k]) > 1]
    constant_meta_names = [k for k in cube.keys() if cube[k] is None]
    dims = {k: len(cube[k]) for k in dim_names}

    # guard against bad datarrays being formed
    dims_total = 1
    dims_to_filter = []
    for dim_name, dim_len, in dims.items():
        if dim_name not in {'x', 'y', 'station'}:
            dims_total *= dim_len
            dims_to_filter.append(dim_name)

    # Check number of GRIB2 message indexed compared to non-X/Y
    # dimensions.
    if dims_total != len(index):
        raise ValueError(
            f"DataArray dimensions are not compatible with number of GRIB2 messages; DataArray has {dims_total} "
            f"and GRIB2 index has {len(index)}. Consider applying a filter for dimensions: {dims_to_filter}"
        )

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

    da.encoding['preferred_chunks'] = {'y': -1, 'x': -1}
    msg1 = index.msg.iloc[0]

    # plain language metadata is minimized
    # add grib section metadata
    da.attrs['GRIB2IO_section0'] = msg1.section0
    da.attrs['GRIB2IO_section1'] = msg1.section1
    da.attrs['GRIB2IO_section2'] = msg1.section2 if msg1.section2 else []
    da.attrs['GRIB2IO_section3'] = msg1.section3
    da.attrs['GRIB2IO_section4'] = msg1.section4
    da.attrs['GRIB2IO_section5'] = msg1.section5
    da.attrs['fullName'] = str(msg1.fullName)
    da.attrs['shortName'] = str(msg1.shortName)
    da.attrs['units'] = str(msg1.units)
    da.attrs['originatingCenter'] = str(msg1.originatingCenter.definition)
    da.attrs['originatingSubCenter'] = str(msg1.originatingSubCenter.definition)

    # add master table
    da.attrs['masterTableInfo'] = str(msg1.masterTableInfo.definition)

    da.name = index.shortName.iloc[0]
    for meta_name in constant_meta_names:
        if meta_name in index.columns:
            da.attrs[meta_name] = index[meta_name].iloc[0]

    da.attrs.update(attrs)

    return da


def assign_xr_meta(ds, frames, cube, non_geo_dims, extra_geo, coord_attrs):

    # assign coords from the cube; the cube prevents datarrays with
    # different shapes
    ds = ds.assign_coords(coords_from_cube(cube))
    # assign extra index associated coords
    df = frames[0]  # use first variable as they all have same shape and index metadata
    for dim_name, coord_names in non_geo_dims.items():
        retain_index_coord = False
        for name in coord_names:
            if name == dim_name:
                retain_index_coord = True
            else:
                if ds[dim_name].size == 1:
                    # for assigning scalar coords
                    coord_data = [df[name].unique().item()]
                    ds = ds.assign_coords({name: coord_data}).squeeze()
                else:
                    # "ValueError: can only convert an array of size 1 to a Python scalar" indicates the coord is not compatible with the index
                    coord_data = [df[df.index.get_level_values(f'{dim_name}_ix') == val][name].unique(
                    ).item() for val in range(ds[dim_name].size)]
                    coord = pd.Index(coord_data, name=dim_name)
                    ds = ds.assign_coords({name: coord})
        if not retain_index_coord:
            ds = ds.drop_vars(dim_name)

    # assign extra geo coords
    ds = ds.assign_coords(extra_geo)
    # add crs data from first grib message to each data variable and the dataset
    geo_attrs = {
        'crs_wkt': CRS.from_dict(df.msg.iloc[0].projParameters).to_wkt(),
        'gridlengthXDirection': df.msg.iloc[0].gridlengthXDirection,
        'gridlengthYDirection': df.msg.iloc[0].gridlengthYDirection,
        'latitudeFirstGridpoint': df.msg.iloc[0].latitudeFirstGridpoint,
        'longitudeFirstGridpoint': df.msg.iloc[0].longitudeFirstGridpoint,
    }
    for data_var in ds.data_vars:
        ds[data_var].attrs.update(geo_attrs)
    ds.attrs.update(geo_attrs)

    # add coordinate specific attributes
    for coord, attrs in coord_attrs.items():
        ds[coord].attrs.update(attrs)

    # assign valid date coords
    ds = ds.assign_coords(dict(validDate=ds.coords['refDate']+ds.coords['leadTime']))
    ds.validDate.attrs['standard_name'] = 'time'
    ds.validDate.attrs['long_name'] = 'time'

    # assign attributes
    ds.attrs['engine'] = 'grib2io'

    return ds


def make_variables(index, f, non_geo_dims, allow_uneven_dims=False):
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
    allow_uneven_dims
        If True, allows uneven dimensions (used for DataTree creation)

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
        return None, None, None

    # define the DimCube
    dims = copy(non_geo_dims)

    ordered_meta = list(non_geo_dims.keys())
    cube = None
    ordered_frames = list()
    for key in index.index.unique():
        frame = index.loc[[key]]
        frame = frame.reset_index()
        # frame is a dataframe with all records for one variable
        c = dict()
        # for colname in frame.columns:
        for colname in ordered_meta:
            uniques = pd.Index(frame[colname]).unique()
            if len(uniques) > 1:
                c[colname] = uniques.sort_values()
            else:
                c[colname] = [uniques[0]]

        dims = [k for k in ordered_meta if len(c[k]) > 1]

        for dim in dims:
            if frame[dim].value_counts().nunique() > 1 and not allow_uneven_dims:
                raise ValueError(
                    f'uneven number of grib msgs associated with dimension: {dim}\n unique values for {dim}: {frame[dim].unique()} ')

        if len(dims) >= 1:  # dims may be empty if no extra dims on top of x,y
            frame = frame.sort_values(dims)
            frame = frame.set_index(dims)

        if cube:
            if cube != c and not allow_uneven_dims:
                raise ValueError(f'{cube},\n {c};\n cubes are not the same; filter to a single cube')
        else:
            cube = c

        # miloc is multi-index integer location of msg in nd DataArray
        miloc = list(zip(*[frame.index.unique(level=dim).get_indexer(frame.index.get_level_values(dim))
                     for dim in dims]))

        # set frame multi index
        if len(miloc) >= 1:  # miloc will be empty when no extra dims, thus no multiindex
            dim_ix = tuple([n+'_ix' for n in dims])
            frame = frame.set_index(pd.MultiIndex.from_tuples(miloc, names=dim_ix))

        ordered_frames.append(frame)

    # no variables
    if cube is None:
        cube = dict()

    # check geography of data and assign to cube
    if len(index.ny.unique()) > 1 or len(index.nx.unique()) > 1:
        raise ValueError('multiple grids not accommodated')
    cube["y"] = range(int(index.ny.iloc[0]))
    cube["x"] = range(int(index.nx.iloc[0]))

    extra_geo = None
    msg = index.msg.iloc[0]

    # we want the lat lons; make them via accessing a record; we are assuming
    # all records are the same grid because they have the same shape;
    # may want a unique grid identifier from grib2io to avoid assuming this
    latitude, longitude = msg.latlons()
    latitude = xr.DataArray(latitude, dims=['y', 'x'])
    latitude.attrs['standard_name'] = 'latitude'
    latitude.attrs['units'] = 'degrees_north'
    longitude = xr.DataArray(longitude, dims=['y', 'x'])
    longitude.attrs['standard_name'] = 'longitude'
    longitude.attrs['units'] = 'degrees_east'
    extra_geo = dict(latitude=latitude, longitude=longitude)

    return ordered_frames, cube, extra_geo


def interp_nd(a, *, method, grid_def_in, grid_def_out, method_options=None, num_threads=1):
    front_shape = a.shape[:-2]
    a = a.reshape(-1, a.shape[-2], a.shape[-1])
    a = grib2io.interpolate(a, method, grid_def_in, grid_def_out, method_options=method_options,
                            num_threads=num_threads)
    a = a.reshape(front_shape + (a.shape[-2], a.shape[-1]))
    return a


def interp_nd_stations(a, *, method, grid_def_in, lats, lons, method_options=None, num_threads=1):
    front_shape = a.shape[:-2]
    a = a.reshape(-1, a.shape[-2], a.shape[-1])
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

    def update_attrs(self, **kwargs):
        """
        Raises an error because Datasets don't have a .attrs attribute.

        Parameters
        ----------
        attrs
            Attributes to update.
        """
        raise ValueError(
            f"Datasets do not have a .attrs attribute; use .grib2io.update_attrs({kwargs}) on a DataArray instead."
        )

    def subset(self, lats, lons) -> xr.Dataset:
        """
        Subset the DataSet to a region defined by latitudes and longitudes.

        Parameters
        ----------
        lats
            Latitude bounds of the region.
        lons
            Longitude bounds of the region.

        Returns
        -------
        subset
            DataSet subset to the region.
        """
        ds = self._obj

        newds = xr.Dataset()
        for shortName in ds:
            newds[shortName] = ds[shortName].grib2io.subset(lats, lons).copy()

        return newds


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
        s3_new = np.array([0, npoints, 0, 0, grid_def_out.gdtn] + list(grid_def_out.gdt))

        # make new lat lons
        lats, lons = Grib2Message(section3=s3_new, pdtn=0, drtn=0).grid()
        latitude = xr.DataArray(lats, dims=['y', 'x'])
        longitude = xr.DataArray(lons, dims=['y', 'x'])

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
                             method_options=method_options, num_threads=num_threads)
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
        # TODO ensure that y, x are rightmost dims; they should be if opening
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

        coords_keys = sorted(da.coords.keys())
        coords_keys = [k for k in coords_keys if k in AVAILABLE_NON_GEO_COORDS]

        # If there are dimension coordinates, the DataArray is a hypercube of
        # grib2 messages.

        # Create `indexes` which is a list of lists of dictionaries for all
        # dimension coordinates. Each dictionary key is the dimension
        # coordinate name and the value is a list of the dimension coordinate
        # values.  This allows for easy iteration over all possible grib2
        # messages in the DataArray by using itertools.product.
        #
        # For example:
        # indexes = [
        #     [
        #         {"leadTime": 9},
        #         {"leadTime": 12},
        #     ],
        #     [
        #         {"valueOfFirstFixedSurface": 900},
        #         {"valueOfFirstFixedSurface": 925},
        #         {"valueOfFirstFixedSurface": 950},
        #     ],
        # ]

        # assign loc indexes to dimensions without indexes for uniform selection by name
        loc_indexes = list()
        for dim in da.dims:
            if dim not in da.indexes:
                da = da.assign_coords({dim: range(da[dim].size)})
                loc_indexes.append(dim)

        indexes = []
        for index in [i for i in AVAILABLE_NON_GEO_DIMS if i in da.dims]:
            values = da.coords[index].values
            if len(values) != len(set(values)):
                raise ValueError(
                    f"Dimension coordinate '{index}' has duplicate values, but to_grib2 requires unique values to find each GRIB2 message in the DataArray."
                )
            listeach = [{index: value} for value in sorted(values)]
            indexes.append(listeach)

        # If `dim_coords` is [], then the DataArray is a single grib2 message and
        # itertools.product(*dim_coords) will run once with `selectors = ()`.
        for selectors in itertools.product(*indexes):
            # Need to find the correct data in the DataArray based on the
            # dimension coordinates.
            filters = {k: v for d in selectors for k, v in d.items()}

            # If `filters` is {}, then the DataArray is a single grib2 message
            # and da.sel(indexers={}) returns the DataArray.
            selected = da.sel(indexers=filters)

            newmsg = Grib2Message(
                selected.attrs["GRIB2IO_section0"],
                selected.attrs["GRIB2IO_section1"],
                selected.attrs["GRIB2IO_section2"],
                selected.attrs["GRIB2IO_section3"],
                selected.attrs["GRIB2IO_section4"],
                selected.attrs["GRIB2IO_section5"],
            )
            newmsg.data = np.array(selected.data)

            # For dimension coordinates, set the grib2 message metadata to the
            # dimension coordinate value.
            for index, value in filters.items():
                if index not in loc_indexes:
                    setattr(newmsg, index, value)

            # For non-dimension coordinates, set the grib2 message metadata to
            # the DataArray coordinate value.
            for index in [i for i in coords_keys if i not in da.dims]:
                setattr(newmsg, index, selected.coords[index].values)

            # Set section 5 attributes to the da.encoding dictionary.
            for key, value in selected.encoding.items():
                if key in ["dtype", "chunks", "original_shape"]:
                    continue
                setattr(newmsg, key, value)

            # write the message to file
            with grib2io.open(filename, mode=mode) as f:
                f.write(newmsg)
            mode = "a"

    def update_attrs(self, **kwargs):
        """
        Update many of the attributes of the DataArray.

        Parameters
        ----------
        **kwargs
            Attributes to update.  This can include many of the GRIB2IO message
            attributes that you can find when you print a GRIB2IO message. For
            conflicting updates, the last keyword will be used.

            +-----------------------+------------------------------------------+
            | kwargs                | Description                              |
            +=======================+==========================================+
            | shortName="VTMP"      | Set shortName to "VTMP", along with      |
            |                       | appropriate discipline,                  |
            |                       | parameterCategory, parameterNumber,      |
            |                       | fullName and units.                      |
            +-----------------------+------------------------------------------+
            | discipline=0,         | Set shortName, discipline,               |
            | parameterCategory=0,  | parameterCategory, parameterNumber,      |
            | parameterNumber=1     | fullName and units appropriate for       |
            |                       | "Virtual Temperature".                   |
            +-----------------------+------------------------------------------+
            | discipline=0,         | Conflicting keywords but                 |
            | parameterCategory=0,  | 'shortName="TMP"' wins.  Set shortName,  |
            | parameterNumber=1,    | discipline, parameterCategory,           |
            | shortName="TMP"       | parameterNumber, fullName and units      |
            |                       | appropriate for "Temperature".           |
            +-----------------------+------------------------------------------+

        Returns
        -------
        DataArray
            DataArray with updated attributes.
        """
        da = self._obj.copy(deep=True)

        newmsg = Grib2Message(
            da.attrs["GRIB2IO_section0"],
            da.attrs["GRIB2IO_section1"],
            da.attrs["GRIB2IO_section2"],
            da.attrs["GRIB2IO_section3"],
            da.attrs["GRIB2IO_section4"],
            da.attrs["GRIB2IO_section5"],
        )

        coords_keys = [
            k
            for k in da.coords.keys()
            if k in AVAILABLE_NON_GEO_COORDS
        ]

        for grib2_name, value in kwargs.items():
            if grib2_name == "gridDefinitionTemplateNumber":
                raise ValueError(
                    "The gridDefinitionTemplateNumber attribute cannot be updated.  The best way to change to a different grid is to interpolate the data to a new grid using the grib2io interpolate functions."
                )
            if grib2_name == "productDefinitionTemplateNumber":
                raise ValueError(
                    "The productDefinitionTemplateNumber attribute cannot be updated."
                )
            if grib2_name == "dataRepresentationTemplateNumber":
                raise ValueError(
                    "The dataRepresentationTemplateNumber attribute cannot be updated."
                )
            if grib2_name in coords_keys:
                warn(
                    f"Skipping attribute '{grib2_name}' because it is a coordinate. Use da.assign_coords() to change coordinate values."
                )
                continue
            if hasattr(newmsg, grib2_name):
                setattr(newmsg, grib2_name, value)
            else:
                warn(
                    f"Skipping attribute '{grib2_name}' because it is not a valid GRIB2 attribute for this message and cannot be updated."
                )
                continue

        da.attrs["GRIB2IO_section0"] = newmsg.section0
        da.attrs["GRIB2IO_section1"] = newmsg.section1
        da.attrs["GRIB2IO_section2"] = newmsg.section2 or []
        da.attrs["GRIB2IO_section3"] = newmsg.section3
        da.attrs["GRIB2IO_section4"] = newmsg.section4
        da.attrs["GRIB2IO_section5"] = newmsg.section5
        da.attrs["fullName"] = newmsg.fullName
        da.attrs["shortName"] = newmsg.shortName
        da.attrs["units"] = newmsg.units

        return da

    def subset(self, lats, lons) -> xr.DataArray:
        """
        Subset the DataArray to a region defined by latitudes and longitudes.

        Parameters
        ----------
        lats
            Latitude bounds of the region.
        lons
            Longitude bounds of the region.

        Returns
        -------
        subset
            DataArray subset to the region.
        """
        da = self._obj.copy(deep=True)

        newmsg = Grib2Message(
            da.attrs["GRIB2IO_section0"],
            da.attrs["GRIB2IO_section1"],
            da.attrs["GRIB2IO_section2"],
            da.attrs["GRIB2IO_section3"],
            da.attrs["GRIB2IO_section4"],
            da.attrs["GRIB2IO_section5"],
        )
        newmsg.data = np.copy(da.values)

        newmsg = newmsg.subset(lats, lons)

        da.attrs["GRIB2IO_section3"] = newmsg.section3

        mask_lat = (da.latitude >= newmsg.latitudeLastGridpoint) & (
            da.latitude <= newmsg.latitudeFirstGridpoint
        )
        mask_lon = (da.longitude >= newmsg.longitudeFirstGridpoint) & (
            da.longitude <= newmsg.longitudeLastGridpoint
        )

        return da.where((mask_lon & mask_lat).compute(), drop=True)


# Custom open_datatree function to open grib files as DataTree
def open_datatree(filename, *, filters: typing.Mapping[str, typing.Any] = None, engine="grib2io"):
    """
    Open a GRIB2 file as an xarray DataTree.

    Parameters
    ----------
    filename : str
        Path to the GRIB2 file.
    filters : dict, optional
        Filter criteria for GRIB2 messages.
    engine : str, optional
        Engine to use for opening the file, defaults to "grib2io".

    Returns
    -------
    xarray.DataTree
        A hierarchical DataTree representation of the GRIB2 data.
    """
    if not HAS_DATATREE:
        raise ImportError("xarray version does not support DataTree functionality.")

    if filters is None:
        filters = {}

    # Open the file without any filters first to get all messages
    with grib2io.open(filename, _xarray_backend=True) as f:
        file_index = pd.DataFrame(f._index)

    # Create a DataTree root
    tree = xr.DataTree()

    # Build tree structure from GRIB messages
    return build_datatree_from_grib(filename, file_index, filters)


def build_datatree_from_grib(filename, file_index, filters=None, stack_vertical=False):
    """
    Build a DataTree from GRIB2 messages.

    Parameters
    ----------
    filename : str
        Path to the GRIB2 file.
    file_index : pandas.DataFrame
        DataFrame of GRIB2 message index.
    filters : dict, optional
        Filter criteria for GRIB2 messages.
    stack_vertical : bool, optional
        If True, vertical levels will be stacked in a single dataset
        instead of being organized in separate tree nodes.

    Returns
    -------
    xarray.DataTree
        A hierarchical DataTree representation of the GRIB2 data.
    """
    if filters is None:
        filters = {}

    # Apply any filters from user
    for k, v in filters.items():
        if k not in file_index.columns:
            file_index = file_index.copy()
            file_index[k] = file_index.msg.apply(lambda msg: getattr(msg, k, None))
        file_index = filter_index(file_index, k, v)

    # Make a copy to avoid the SettingWithCopyWarning
    file_index = file_index.copy()

    # Extract metadata needed for tree organization
    # Use a safer approach to handle missing attributes
    def safe_getattr(obj, name):
        try:
            attr = getattr(obj, name)
            # Need to test if the attribute is Grib2Metadata. If so,
            # then get the value attribute.
            if isinstance(attr, grib2io.templates.Grib2Metadata):
                attr = attr.value
            return attr
        except (AttributeError, KeyError):
            return None

    for attr in TREE_HIERARCHY_LEVELS:
        if (attr not in file_index.columns) and (attr != 'valueOfFirstFixedSurface'):
            file_index[attr] = file_index.msg.apply(lambda msg: safe_getattr(msg, attr))

    # Also extract shortName for variable naming
    if 'shortName' not in file_index.columns:
        file_index = file_index.assign(shortName=file_index.msg.apply(lambda msg: getattr(msg, 'shortName', None)))
        file_index = file_index.assign(nx=file_index.msg.apply(lambda msg: getattr(msg, 'nx', None)))
        file_index = file_index.assign(ny=file_index.msg.apply(lambda msg: getattr(msg, 'ny', None)))

    # Create root DataTree
    root = xr.DataTree()

    # Adjust hierarchy levels if we're stacking vertical levels
    hierarchy_levels = list(TREE_HIERARCHY_LEVELS)
    if stack_vertical and "valueOfFirstFixedSurface" in hierarchy_levels:
        hierarchy_levels.remove("valueOfFirstFixedSurface")

    # First group by level type
    level_groups = {}

    # Create a dictionary to group data by level type
    for level_type in file_index['typeOfFirstFixedSurface'].unique():
        if pd.notna(level_type):  # Skip None/NaN values
            level_info = LEVEL_NAME_MAPPING.get(level_type, f"level_{level_type}")
            level_name = level_info[0]
            level_source = level_info[1]
            # Get all rows for this level type
            level_data = file_index[file_index['typeOfFirstFixedSurface'] == level_type]
            level_groups[level_type] = {'name': level_name, 'data': level_data}

    # Process each level group
    for level_type, group_info in level_groups.items():
        level_name = group_info['name']
        level_df = group_info['data']

        # Create a branch for this level type
        level_tree = xr.DataTree()

        # Process this branch based on PDTN, perturbation number, etc.
        process_level_branch(level_tree, level_df, filename)

        # Add this branch to the main tree
        root[level_name] = level_tree

    return root


def process_level_branch(level_tree, df, filename):
    """
    Process a level type branch of the data tree, organizing by PDTN and other attributes.

    Parameters
    ----------
    level_tree : xarray.DataTree
        The DataTree node for this level type
    df : pandas.DataFrame
        DataFrame of messages for this level type
    filename : str
        Path to the GRIB2 file
    """
    # Group by PDTN
    pdtn_groups = {}

    # Group data by PDTN first
    for pdtn_value in df['productDefinitionTemplateNumber'].unique():
        if pd.notna(pdtn_value):
            pdtn_df = df[df['productDefinitionTemplateNumber'] == pdtn_value]
            pdtn_groups[pdtn_value] = pdtn_df

    # If there's only one PDTN value, skip creating PDTN branch level
    if len(pdtn_groups) == 1:
        pdtn, pdtn_df = next(iter(pdtn_groups.items()))

        pdtn_name = f"pdtn_{int(pdtn)}"

        # Check if we need to further subdivide by perturbation number
        has_perturbations = ('perturbationNumber' in pdtn_df.columns and
                             len(pdtn_df['perturbationNumber'].dropna().unique()) > 1)

        # Check if we need to further subdivide by probabilities unique for each variable.
        has_probabilities = ('typeOfProbability' in pdtn_df.columns and
                             len(pdtn_df['typeOfProbability'].dropna().unique()) > 1)

        if has_perturbations:
            # Process perturbations directly on the level tree
            process_perturbation_groups(level_tree, pdtn_df, filename)
        elif has_probabilities:
            # Process probability groups
            process_probability_groups(level_tree, pdtn_df, filename)
        else:
            # Try to create dataset directly on level
            try:
                dss = create_datasets_from_df(pdtn_df, filename)
                if dss is not None:
                    dt = xr.DataTree()
                    ds_dict = {f"var_{ds.data_vars[0]}": ds for i, ds in enumerate(dss)}
                    for k, v in ds_dict.items():
                        dt[k] = v
                    level_tree[pdtn_name] = dt
            except Exception as e:
                print(f"Error creating dataset for level with pdtn {int(pdtn)}: {e}")

                # Try to separate by variable name as a fallback
                try_process_by_variables(level_tree, pdtn_df, filename)
    else:
        # Multiple PDTN values, process each group with PDTN branch nodes
        for pdtn, pdtn_df in pdtn_groups.items():
            # Use a simple node name that's easy to use in code
            pdtn_name = f"pdtn_{int(pdtn)}"

            # Check if we need to further subdivide by perturbation number
            has_perturbations = ('perturbationNumber' in pdtn_df.columns and
                                 len(pdtn_df['perturbationNumber'].dropna().unique()) > 1)

            # Check if we need to further subdivide by probabilities unique for each variable.
            has_probabilities = ('typeOfProbability' in pdtn_df.columns and
                                 len(pdtn_df['typeOfProbability'].dropna().unique()) > 1)

            if has_perturbations:
                # Create a branch for this PDTN
                pdtn_tree = xr.DataTree()

                # Process perturbation groups
                process_perturbation_groups(pdtn_tree, pdtn_df, filename)

                # Only add the PDTN branch if it has children
                if len(pdtn_tree.children) > 0 or pdtn_tree.ds is not None:
                    level_tree[pdtn_name] = pdtn_tree
            elif has_probabilities:
                # Create a branch for this PDTN
                pdtn_tree = xr.DataTree()

                # Process probability groups
                process_probability_groups(pdtn_tree, pdtn_df, filename)

                # Only add the PDTN branch if it has children
                if len(pdtn_tree.children) > 0 or pdtn_tree.ds is not None:
                    level_tree[pdtn_name] = pdtn_tree
            else:
                # Create a subtree for this PDTN
                pdtn_tree = xr.DataTree()

                # Try to separate by variable name as a fallback
                if try_process_by_variables(pdtn_tree, pdtn_df, filename):
                    level_tree[pdtn_name] = pdtn_tree
                #else:
                #
                # For single perturbation case, try to group by variable if needed
                # try:
                #    print(f"\nTEST...INSIDE try....")
                #    ds = create_datasets_from_df(pdtn_df, filename, verbose=True)
                #    print(f"\nTEST: AFTER create_dataset_from_df, {ds = }")
                #    if ds is not None:
                #        level_tree[pdtn_name] = ds
                # except Exception as e:
                #    print(f"Error creating dataset for {pdtn_name}: {e}")

                #    # Create a subtree for this PDTN
                #    pdtn_tree = xr.DataTree()

                #    # Try to separate by variable name as a fallback
                #    if try_process_by_variables(pdtn_tree, pdtn_df, filename):
                #        level_tree[pdtn_name] = pdtn_tree


def process_probability_groups(target_tree, pdtn_df, filename):
    """
    """
    success = False
    # Group by type of probability
    prob_groups = {}
    for prob_value in pdtn_df['typeOfProbability'].unique():
        if pd.notna(prob_value):
            prob_df = pdtn_df[pdtn_df['typeOfProbability'] == prob_value]
            prob_groups[prob_value] = prob_df

    # Process each probability group
    prob_dict = {}
    for prob_num, prob_df in prob_groups.items():
        prob_name = f"prob_{int(prob_num)}"

        # Try to create dataset for this probability group
        try:
            dss = create_datasets_from_df(prob_df, filename)
            dt = xr.DataTree()
            if len(dss) == 1:
                dt.ds = dss[0]
                target_tree[prob_name] = dt
            elif len(dss) > 1:
                for ds in dss:
                    dt[f"var_{ds.data_vars[0]}"] = ds
            target_tree[prob_name] = dt
        except Exception as e:
            # Log error but continue processing other groups
            print(f"Error creating dataset for type of probability {prob_name}: {e}")

    return success


def process_perturbation_groups(target_tree, pdtn_df, filename):
    """
    Process perturbation groups and add them to the target tree.

    Parameters
    ----------
    target_tree : xarray.DataTree
        The tree node to add perturbation groups to
    pdtn_df : pandas.DataFrame
        DataFrame of messages for a specific PDTN
    filename : str
        Path to the GRIB2 file

    Returns
    -------
    bool
        True if at least one perturbation was successfully processed
    """
    success = False
    # Group by perturbation number
    pert_groups = {}
    for pert_value in pdtn_df['perturbationNumber'].unique():
        if pd.notna(pert_value):
            pert_df = pdtn_df[pdtn_df['perturbationNumber'] == pert_value]
            pert_groups[pert_value] = pert_df

    # Process each perturbation group
    for pert_num, pert_df in pert_groups.items():
        pert_name = f"pert_{int(pert_num)}"

        ## Try to create dataset for this perturbation group
        #try:
        #    dss = create_datasets_from_df(pert_df, filename)
        #    if dss is not None:
        #        if len(dss) == 1:
        #            target_tree.ds = dss[0]
        #        else:
        #            dss_dict = {f"ds_{i}": ds for i, ds in enumerate(dss)}
        #            atree = xr.DataTree(dss_dict)
        #            target_tree[prob_name] = atree
        #        success = True
        #except Exception as e:
        #    # Log error but continue processing other groups
        #    print(f"Error creating dataset for perturbation {pert_name}: {e}")

        # Try to create dataset for this perturbation group
        try:
            dss = create_datasets_from_df(pert_df, filename)
            dt = xr.DataTree()
            if len(dss) == 1:
                dt.ds = dss[0]
                target_tree[pert_name] = dt
            elif len(dss) > 1:
                for ds in dss:
                    dt[f"pert{ds.data_vars[0]}"] = ds
            target_tree[pert_name] = dt
        except Exception as e:
            # Log error but continue processing other groups
            print(f"Error creating dataset for perturbation {pert_name}: {e}")

    return success


def try_process_by_variables(target_tree, df, filename):
    """
    Try to separate data by variable names and create datasets.

    Parameters
    ----------
    target_tree : xarray.DataTree
        The tree node to add variable datasets to
    df : pandas.DataFrame
        DataFrame of messages
    filename : str
        Path to the GRIB2 file

    Returns
    -------
    bool
        True if at least one variable was successfully processed
    """
    success = False

    try:
        for var_name in df['shortName'].unique():
            if pd.notna(var_name):
                var_df = df[df['shortName'] == var_name]
                try:
                    var_ds = create_datasets_from_df(var_df, filename)
                    if var_ds is not None:
                        target_tree[f"var_{var_name}"] = var_ds[0]
                        success = True
                except Exception as var_e:
                    print(f"Error creating dataset for variable {var_name}: {var_e}")
    except Exception as nested_e:
        print(f"Failed to process variables: {nested_e}")

    return success


def create_datasets_from_df(
    df,
    filename,
    verbose=False
) -> typing.Optional[typing.List[xr.Dataset]]:
    """
    Create a list of xarray Datasets from a DataFrame of messages.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame of GRIB messages
    filename : str
        Path to the GRIB2 file
    verbose : bool, optional
        If True, prints detailed debugging information

    Returns
    -------
    dss
        List of Datasets, or None if creation failed
    """
    try:
        if verbose:
            print(f"\n==== VERBOSE DEBUG INFO ====")
            print(f"Creating dataset from DataFrame with {len(df)} messages")
            print(f"DataFrame columns: {df.columns.tolist()}")

            if 'shortName' in df.columns:
                print(f"Variables in group: {df['shortName'].unique().tolist()}")

            if 'valueOfFirstFixedSurface' in df.columns:
                print(f"Vertical levels: {df['valueOfFirstFixedSurface'].unique().tolist()}")

        # Process by variables
        datasets = {}

        # Process each variable separately, regardless of whether there are vertical levels
        for var_name, var_df in df.groupby('shortName'):
            if verbose:
                print(
                    f"\n  Processing variable: {var_name} with {len(var_df)} messages, with pdtn(s) = {var_df['productDefinitionTemplateNumber'].unique()}")

            # Process vertical levels if present
            if 'valueOfFirstFixedSurface' in var_df.columns and len(var_df['valueOfFirstFixedSurface'].unique()) > 1:
                if verbose:
                    print(f"  Variable {var_name} has multiple vertical levels")
                # Process each level separately
                level_das = []

                for level, level_df in var_df.groupby('valueOfFirstFixedSurface'):
                    if verbose:
                        print(f"    Processing level {level} with {len(level_df)} messages")
                    try:
                        # Parse the index and get dimensions for this level
                        file_index, non_geo_dims, attrs, coord_attrs = parse_grib_index(level_df, {})
                        # Remove valueOfFirstFixedSurface from dimensions since we're handling it separately
                        non_geo_dims = [d for d in non_geo_dims if d.__name__ != "ValueOfFirstFixedSurfaceDim"]

                        frames, cube, extra_geo = make_variables(
                            file_index, filename, non_geo_dims, allow_uneven_dims=True)

                        if frames is not None and len(frames) == 1:
                            level_da = build_da_without_coords(frames[0], cube, filename, attrs)
                            # Add this level to the list with its level value as coord
                            level_da = level_da.assign_coords(valueOfFirstFixedSurface=level)
                            level_das.append(level_da)
                    except Exception as e:
                        if verbose:
                            print(f"    Error processing level {level} for {var_name}: {e}")

                if level_das:
                    # Combine all levels into a single DataArray along the valueOfFirstFixedSurface dimension
                    if verbose:
                        print(f"    Combining {len(level_das)} levels for {var_name}")
                    try:
                        combined_da = xr.concat(level_das, dim='valueOfFirstFixedSurface')
                        # Create a simple dataset with just this variable
                        var_ds = xr.Dataset({var_name: combined_da})
                        # Assign the coords from the first level's cube
                        var_ds = assign_xr_meta(var_ds, frames, cube, non_geo_dims, extra_geo, coord_attrs)
                       # TODO: is the below code all now in assign_xr_meta? was there instances where refDate and leadTime were not coords?
                       # var_ds = var_ds.assign_coords(coords_from_cube(cube))
                       # Add extra geo coords
                       # if extra_geo:
                       #    var_ds = var_ds.assign_coords(extra_geo)
                       # Add valid date coords if available
                       # if 'refDate' in var_ds.coords and 'leadTime' in var_ds.coords:
                       #    var_ds = var_ds.assign_coords(dict(validDate=var_ds.coords['refDate']+var_ds.coords['leadTime']))

                        # Store this variable's dataset
                        datasets[var_name] = var_ds
                        if verbose:
                            print(f"    Created dataset for {var_name} with levels")
                    except Exception as e:
                        if verbose:
                            print(f"    Error combining levels for {var_name}: {e}")
            else:
                # Single level or no vertical levels
                if verbose:
                    print(f"  Variable {var_name} is a single level or has no vertical dimension")
                try:
                    # Parse the index and get dimensions
                    file_index, non_geo_dims, attrs, coord_attrs = parse_grib_index(var_df, {})
                    frames, cube, extra_geo = make_variables(file_index, filename, non_geo_dims, allow_uneven_dims=True)

                    if frames is not None and len(frames) == 1:
                        # Create dataset with this variable
                        var_ds = xr.Dataset()
                        da = build_da_without_coords(frames[0], cube, filename, attrs)
                        var_ds[da.name] = da

                        # Assign coords
                        var_ds = assign_xr_meta(var_ds, frames, cube, non_geo_dims, extra_geo, coord_attrs)
                       # TODO: is the below code all now in assign_xr_meta? was there instances where refDate and leadTime were not coords?
                       # var_ds = var_ds.assign_coords(coords_from_cube(cube))
                       # if extra_geo:
                       #    var_ds = var_ds.assign_coords(extra_geo)
                       # if 'refDate' in var_ds.coords and 'leadTime' in var_ds.coords:
                       #    var_ds = var_ds.assign_coords(dict(validDate=var_ds.coords['refDate']+var_ds.coords['leadTime']))

                        # Store this variable's dataset
                        datasets[var_name] = var_ds
                        if verbose:
                            print(f"  Created dataset for {var_name}")
                    elif frames is not None and len(frames) > 1:
                        if verbose:
                            print(f"  Variable {var_name} has multiple frames, possibly different parameters")
                        # Just use the first frame for now (simplified approach)
                        var_ds = xr.Dataset()
                        da = build_da_without_coords(frames[0], cube, filename, attrs)
                        var_ds[da.name] = da

                        # Assign coords
                        var_ds = assign_xr_meta(var_ds, frames, cube, non_geo_dims, extra_geo, coord_attrs)
                       # TODO: is the below code all now in assign_xr_meta? was there instances where refDate and leadTime were not coords?
                       # var_ds = var_ds.assign_coords(coords_from_cube(cube))
                       # if extra_geo:
                       #    var_ds = var_ds.assign_coords(extra_geo)
                       # if 'refDate' in var_ds.coords and 'leadTime' in var_ds.coords:
                       #    var_ds = var_ds.assign_coords(dict(validDate=var_ds.coords['refDate']+var_ds.coords['leadTime']))

                        datasets[var_name] = var_ds
                        if verbose:
                            print(f"  Created dataset with first frame for {var_name}")
                except Exception as e:
                    if verbose:
                        print(f"  Error processing variable {var_name}: {e}")

        # Attempt to merge all the variable datasets
        if datasets:
            try:
                if verbose:
                    print(f"\nMerging {len(datasets)} datasets...")
                # Get the list of datasets to merge
                ds_list = list(datasets.values())

                # Try merging them all at once
                try:
                    combined_ds = xr.merge(ds_list)
                    if verbose:
                        print(f"Successfully merged all datasets into one.")
                        print(f"Final dataset has variables: {list(combined_ds.data_vars)}")
                        print(f"==== END VERBOSE DEBUG INFO ====\n")
                    return [combined_ds]
                except Exception as merge_error:
                    if verbose:
                        print(f"Error merging all datasets: {merge_error}")
                    return ds_list
            except Exception as e:
                if verbose:
                    print(f"Error in final merge process: {e}")
                    print(f"==== END VERBOSE DEBUG INFO ====\n")
                return None
        else:
            if verbose:
                print(f"No datasets were created for any variables")
                print(f"==== END VERBOSE DEBUG INFO ====\n")
            return None

    except Exception as e:
        # If there's an error, log it and return None
        if verbose:
            print(f"Error creating dataset: {e}")
            import traceback
            traceback.print_exc()
            print(f"==== END VERBOSE DEBUG INFO ====\n")
        return None


# Only register the DataTree accessor if DataTree is supported
if HAS_DATATREE:
    @xr.register_datatree_accessor("grib2io")
    class Grib2ioDataTree:
        """
        DataTree accessor for GRIB2 files.

        This accessor provides methods for working with GRIB2 data organized
        in a hierarchical tree structure.
        """

        def __init__(self, datatree_obj):
            self._obj = datatree_obj

        def to_grib2(self, filename, mode: typing.Literal["x", "w", "a"] = "x"):
            """
            Write all datasets in the DataTree to a GRIB2 file.

            Parameters
            ----------
            filename : str
                Name of the GRIB2 file to write to.
            mode : {"x", "w", "a"}, optional
                Persistence mode, default is "x" (create, fail if exists)
            """
            # Start with the specified mode
            current_mode = mode

            # Function to recursively process the tree
            def process_tree(node):
                nonlocal current_mode

                # If this is a Dataset node with data variables
                if node.ds is not None and node.ds.data_vars:
                    # Write dataset to GRIB2 file
                    node.ds.grib2io.to_grib2(filename, mode=current_mode)
                    # Switch to append mode after first write
                    current_mode = "a"

                # Process children
                for child_name, child_node in node.children.items():
                    process_tree(child_node)

            # Start processing from the root
            process_tree(self._obj)

        def griddef(self):
            """
            Get the grid definition from the first dataset in the tree that has one.

            Returns
            -------
            grib2io.Grib2GridDef
                Grid definition object
            """
            # Function to find first dataset with GRIB2IO_section3
            def find_griddef(node):
                if node.ds is not None and node.ds.data_vars:
                    for var_name in node.ds.data_vars:
                        if 'GRIB2IO_section3' in node.ds[var_name].attrs:
                            return Grib2GridDef.from_section3(node.ds[var_name].attrs['GRIB2IO_section3'])

                # Check children
                for child_name, child_node in node.children.items():
                    griddef = find_griddef(child_node)
                    if griddef is not None:
                        return griddef

                return None

            return find_griddef(self._obj)

        def interp(self, method, grid_def_out, method_options=None, num_threads=1):
            """
            Interpolate all datasets in the tree to a new grid.

            Parameters
            ----------
            method : str or int
                Interpolation method to use
            grid_def_out : grib2io.Grib2GridDef
                Target grid definition
            method_options : list, optional
                Options for interpolation method
            num_threads : int, optional
                Number of threads to use for interpolation

            Returns
            -------
            xarray.DataTree
                New DataTree with interpolated data
            """
            new_tree = xr.DataTree()

            # Function to recursively process the tree
            def process_tree(node, new_parent):
                # If this is a Dataset node with data variables
                if node.ds is not None and node.ds.data_vars:
                    # Interpolate dataset
                    interp_ds = node.ds.grib2io.interp(method, grid_def_out,
                                                       method_options=method_options,
                                                       num_threads=num_threads)

                    # Add to new tree at the same path
                    if node == self._obj:  # Root node
                        new_parent.ds = interp_ds
                    else:
                        new_parent.ds = interp_ds

                # Process children
                for child_name, child_node in node.children.items():
                    # Create same child in new tree
                    new_child = xr.DataTree()
                    new_parent[child_name] = new_child
                    process_tree(child_node, new_child)

            # Start processing from the root
            process_tree(self._obj, new_tree)

            return new_tree

        def subset(self, lats, lons):
            """
            Subset all datasets in the tree to a region.

            Parameters
            ----------
            lats : list or tuple
                Latitude bounds [min_lat, max_lat]
            lons : list or tuple
                Longitude bounds [min_lon, max_lon]

            Returns
            -------
            xarray.DataTree
                New DataTree with subset data
            """
            new_tree = xr.DataTree()

            # Function to recursively process the tree
            def process_tree(node, new_parent):
                # If this is a Dataset node with data variables
                if node.ds is not None and node.ds.data_vars:
                    # Subset dataset
                    subset_ds = node.ds.grib2io.subset(lats, lons)

                    # Add to new tree at the same path
                    if node == self._obj:  # Root node
                        new_parent.ds = subset_ds
                    else:
                        new_parent.ds = subset_ds

                # Process children
                for child_name, child_node in node.children.items():
                    # Create same child in new tree
                    new_child = xr.DataTree()
                    new_parent[child_name] = new_child
                    process_tree(child_node, new_child)

            # Start processing from the root
            process_tree(self._obj, new_tree)

            return new_tree
