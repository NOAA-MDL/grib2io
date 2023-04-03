from ._grib2io import *
from ._grib2io import __doc__
from ._grib2io import _Grib2Message

try:
    from . import __config__
    __version__ = __config__.grib2io_version
except(ImportError):
    pass

__all__ = ['open','Grib2Message','_Grib2Message','show_config','interpolate','tables','templates','utils',
           'Grib2GridDef']

def show_config():
    """
    Print grib2io build configuration information.
    """
    from g2clib import __version__ as g2clib_version
    from g2clib import _has_png as have_png
    from g2clib import _has_jpeg as have_jpeg
    print("grib2io version %s Configuration:\n"%(__version__))
    print("\tg2c library version:".expandtabs(4),g2clib_version)
    print("\tJPEG compression support:".expandtabs(4),bool(have_jpeg))
    print("\tPNG compression support:".expandtabs(4),bool(have_png))
