from ._grib2io import *
from ._grib2io import __doc__
from ._grib2io import _Grib2Message

__all__ = ['open', 'show_config', 'interpolate', 'interpolate_to_stations',
           'tables', 'templates', 'utils',
           'Grib2Message', '_Grib2Message', 'Grib2GridDef']

try:
    from . import __config__
    __version__ = __config__.grib2io_version
    has_interpolation = __config__.has_interpolation
    has_openmp_support = __config__.has_openmp_support
    g2c_static = __config__.g2c_static
    ip_static = __config__.ip_static
    extra_objects = __config__.extra_objects
except(ImportError):
    pass

from .g2clib import __version__ as __g2clib_version__
from .g2clib import _has_jpeg
from .g2clib import _has_png
from .g2clib import _has_aec

has_jpeg_support = bool(_has_jpeg)
has_png_support  = bool(_has_png)
has_aec_support = bool(_has_aec)

from .tables.originating_centers import _ncep_grib2_table_version
ncep_grib2_table_version = _ncep_grib2_table_version
g2c_version = __g2clib_version__

def show_config():
    """Print grib2io build configuration information."""
    print(f'grib2io version {__version__} Configuration:')
    print(f'')
    print(f'NCEPLIBS-g2c library version: {__g2clib_version__}')
    print(f'\tStatic library: {g2c_static}')
    print(f'\tJPEG compression support: {has_jpeg_support}')
    print(f'\tPNG compression support: {has_png_support}')
    print(f'\tAEC compression support: {has_aec_support}')
    print(f'')
    print(f'NCEPLIPS-ip support: {has_interpolation}')
    print(f'\tStatic library: {ip_static}')
    print(f'\tOpenMP support: {has_openmp_support}')
    print(f'')
    print(f'Static libs:')
    for lib in extra_objects:
        print(f'\t{lib}')
    print(f'')
    print(f'NCEP GRIB2 Table Version: {_ncep_grib2_table_version}')
