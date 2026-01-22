import pytest
import xarray as xr
import importlib.metadata

# Check if xarray version supports DataTree
HAS_DATATREE = False
try:
    # Try importing DataTree to check if it's available
    xarray_version = importlib.metadata.version('xarray')
    xarray_parts = [int(x) if x.isdigit() else x for x in xarray_version.split('.')]
    min_version_parts = [2024, 10, 0]
    HAS_DATATREE = xarray_parts >= min_version_parts
    # Also verify DataTree class exists
    if HAS_DATATREE and not hasattr(xr, 'DataTree'):
        HAS_DATATREE = False
except (ImportError, ValueError):
    HAS_DATATREE = False

# Skip all tests if DataTree is not available
pytestmark = pytest.mark.skipif(not HAS_DATATREE,
                               reason="xarray version does not support DataTree functionality")

TOTAL_COUNT_EXPECTED = 294

def _get_dataset(node):
    # xarray.DataTree exposes .dataset; older datatree used .ds
    return getattr(node, "dataset", None) or getattr(node, "ds", None)

def iter_dataarrays(node: "xr.DataTree"):
    """Yield (path, var_name, DataArray) for every data_var in the tree."""
    ds = _get_dataset(node)
    if ds is not None:
        for var_name, da in ds.data_vars.items():
            yield node.path, var_name, da
    for child in node.children.values():
        yield from iter_dataarrays(child)

def leftmost_dim_count(da: xr.DataArray):
    """Return (leftmost_dim_name, count). Scalars return (None, 1)."""
    if da.ndim == 0:
        return None, 1
    if da.ndim == 2:
        return None, 1
    else:
        left = da.dims[0]
    return left, da.sizes[left]

def test_datatree_resolve_all_messages(request):
    """Test Datatree backend to resolve all GRIB2 messages in a NBM Core GRIB2 file."""
    data = request.config.rootdir / 'tests' / 'input_data'

    # Open the file as a DataTree
    tree = xr.open_datatree(data / 'blend.t00z.core.f001.co_4x_reduce.grib2', engine='grib2io')

    # Verify the basic structure
    assert isinstance(tree, xr.DataTree)

    total_count = 0
    names = []
    for path, var, da in iter_dataarrays(tree):
        left_dim, count = leftmost_dim_count(da)
        total_count += count
    names += [var for _ in range(count)]

    assert total_count == TOTAL_COUNT_EXPECTED
