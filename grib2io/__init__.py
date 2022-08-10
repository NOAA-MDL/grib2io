from ._grib2io import *
from ._grib2io import __doc__

try:
    from . import __config__
    __version__ = __config__.grib2io_version
except(ImportError):
    pass

__all__ = ['open','Grib2Message','Grib2Metadata','show_config','tables','utils']

def show_config():
    """
    Print grib2io build configuration information.
    """
    from g2clib import __version__ as g2clib_version
    print("grib2io version %s Configuration:\n"%(__version__))
    print("\tg2c library version:".expandtabs(4),g2clib_version)
    #print("\tJPEG compression support:".expandtabs(4),have_jpeg)
    #print("\tPNG compression support:".expandtabs(4),have_png)
