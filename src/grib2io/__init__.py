from ._grib2io import *
from ._grib2io import __doc__
from ._grib2io import _Grib2Message

__all__ = ['open', 'show_config', 'interpolate', 'interpolate_to_stations',
           'tables', 'templates', 'utils',
           'Grib2Message', '_Grib2Message', 'Grib2GridDef']

try:
    from . import __config__
    __version__ = __config__.grib2io_version
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
    print(f'grib2io version {__version__} Configuration:\n')
    print(f'\tg2c library version: {__g2clib_version__}')
    print(f'\tJPEG compression support: {has_jpeg_support}')
    print(f'\tPNG compression support: {has_png_support}')
    print(f'\tAEC compression support: {has_aec_support}')
    print(f'')
    print(f'\tNCEP GRIB2 Table Version: {_ncep_grib2_table_version}')
