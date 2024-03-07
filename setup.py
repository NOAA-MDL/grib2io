from ctypes.util import find_library as ctypes_find_library
from pathlib import Path
from setuptools import setup, Extension
import configparser
import numpy
import os
import platform
import subprocess
import sys

with open("VERSION","rt") as f:
    VERSION = f.readline().strip()

usestaticlibs = False
extra_objects = []
libdirs = []
incdirs = []
libraries = ['g2c']


# ----------------------------------------------------------------------------------------
# find_library.
# ----------------------------------------------------------------------------------------
def find_library(name, dirs=None, static=False):
    _libext_by_platform = {"linux": ".so", "darwin": ".dylib"}
    out = []

    # According to the ctypes documentation Mac and Windows ctypes_find_library
    # returns the full path.
    #
    # IMPORTANT: The following does not work at this time (Jan. 2024) for macOS on
    # Apple Silicon.
    if (os.name, sys.platform) != ("posix", "linux"):
        if (sys.platform, platform.machine()) == ("darwin", "arm64"):
            pass
        else:
            out.append(ctypes_find_library(name))

    # For Linux and macOS (Apple Silicon), we have to search ourselves.
    libext = _libext_by_platform[sys.platform]
    if static: libext = '.a'
    if dirs is None:
        if os.environ.get("CONDA_PREFIX"):
            dirs = [os.environ["CONDA_PREFIX"]]
        else:
            dirs = ["/usr/local", "/sw", "/opt", "/opt/local", "/opt/homebrew", "/usr"]
    if os.environ.get("LD_LIBRARY_PATH"):
        dirs = dirs + os.environ.get("LD_LIBRARY_PATH").split(":")

    out = []
    for d in dirs:
        libs = Path(d).rglob(f"lib{name}{libext}")
        out.extend(libs)
    if not out:
        raise ValueError(f"""

The library "lib{name}{libext}" could not be found in any of the following
directories:
{dirs}

""")
    return out[0].absolute().resolve().as_posix()


# ----------------------------------------------------------------------------------------
# Build Cython sources
# ----------------------------------------------------------------------------------------
from Cython.Distutils import build_ext
cmdclass = {'build_ext': build_ext}
redtoreg_pyx = 'src/ext/redtoreg.pyx'
g2clib_pyx  = 'src/ext/g2clib.pyx'

# ----------------------------------------------------------------------------------------
# Read setup.cfg
# ----------------------------------------------------------------------------------------
setup_cfg = 'setup.cfg'
config = configparser.ConfigParser()
config.read(setup_cfg)

# ----------------------------------------------------------------------------------------
# Get NCEPLIBS-g2c library info.
# ----------------------------------------------------------------------------------------
if os.environ.get('G2C_DIR'):
    g2c_dir = os.environ.get('G2C_DIR')
    if os.path.exists(os.path.join(g2c_dir,'lib')):
        g2c_libdir = os.path.join(g2c_dir,'lib')
    elif os.path.exists(os.path.join(g2c_dir,'lib64')):
        g2c_libdir = os.path.join(g2c_dir,'lib64')
    g2c_incdir = os.path.join(g2c_dir,'include')
else:
    g2c_dir = config.get('directories','g2c_dir',fallback=None)
    if g2c_dir is None:
       g2c_libdir = os.path.dirname(find_library('g2c'))
       g2c_incdir = os.path.join(os.path.dirname(g2c_libdir),'include')
libdirs.append(g2c_libdir)
incdirs.append(g2c_incdir)

libdirs = list(set(libdirs))
incdirs = list(set(incdirs))
incdirs.append(numpy.get_include())

# ----------------------------------------------------------------------------------------
# Check if static library linking is preferred.
# ----------------------------------------------------------------------------------------
if os.environ.get('USE_STATIC_LIBS'):
    val = os.environ.get('USE_STATIC_LIBS')
    if val not in {'True','False'}:
        raise ValueError('Environment variable USE_STATIC_LIBS must be \'True\' or \'False\'')
    usestaticlibs = True if val == 'True' else False

if usestaticlibs:
    for libdir in libdirs:
        staticlib = find_library('g2c', dirs=[libdir], static=True)
    extra_objects.append(staticlib)
    cmd = subprocess.run(['ar','-t',staticlib], stdout=subprocess.PIPE)
    symbols = cmd.stdout.decode('utf-8')
    if 'aec' in symbols:
        extra_objects.append(find_library('aec', static=True))
    if 'jpeg2000' in symbols:
        extra_objects.append(find_library('jasper', static=True))
    if 'openjpeg' in symbols:
        extra_objects.append(find_library('openjp2', static=True))
    if 'png' in symbols:
        extra_objects.append(find_library('png', static=True))
    extra_objects.append(find_library('z', static=True))
    libdirs = []
    libraries = []

# ----------------------------------------------------------------------------------------
# Define extensions
# ----------------------------------------------------------------------------------------
g2clibext = Extension('grib2io.g2clib',
                      [g2clib_pyx],
                      include_dirs = incdirs,
                      library_dirs = libdirs,
                      libraries = libraries,
                      runtime_library_dirs = libdirs,
                      extra_objects = extra_objects)
redtoregext = Extension('grib2io.redtoreg',
                        [redtoreg_pyx],
                        include_dirs = [numpy.get_include()])

# ----------------------------------------------------------------------------------------
# Create __config__.py
# ----------------------------------------------------------------------------------------
cnt = \
"""# This file is generated by grib2io's setup.py
# It contains configuration information when building this package.
grib2io_version = '%(grib2io_version)s'
"""
a = open('src/grib2io/__config__.py','w')
cfgdict = {}
cfgdict['grib2io_version'] = VERSION
try:
    a.write(cnt % cfgdict)
finally:
    a.close()

# ----------------------------------------------------------------------------------------
# Import README.md as PyPi long_description
# ----------------------------------------------------------------------------------------
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# ----------------------------------------------------------------------------------------
# Run setup.py.  See pyproject.toml for package metadata.
# ----------------------------------------------------------------------------------------
setup(ext_modules = [g2clibext,redtoregext],
      cmdclass = cmdclass,
      long_description = long_description,
      long_description_content_type = 'text/markdown')
