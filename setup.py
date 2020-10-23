from setuptools import setup, Extension
from os import environ
import configparser
import os
import glob
import sys

class _ConfigParser(configparser.ConfigParser):
    def getq(self, s, k, fallback):
        try:
            return self.get(s, k)
        except:
            return fallback

# pyproj is a runtime dependency
try:
    import pyproj
except ImportError:
    try:
        from mpl_toolkits.basemap import pyproj
    except:
        raise ImportError('either pyproj or basemap required')

# Build time dependancy
try:
    from Cython.Distutils import build_ext
    cmdclass = {'build_ext': build_ext}
    redtoreg_pyx = 'redtoreg.pyx'
    g2clib_pyx  = 'g2clib.pyx'
except ImportError:
    cmdclass = {}
    redtoreg_pyx = 'redtoreg.c'
    g2clib_pyx  = 'g2clib.c'

# Read setup.cfg. Contents of setup.cfg will override env vars.
setup_cfg = environ.get('GRIB2IO_SETUP_CONFIG', 'setup.cfg')
config = _ConfigParser()
if os.path.exists(setup_cfg):
    sys.stdout.write('Reading from setup.cfg...')
    config.read(setup_cfg)

# Get Jasper library info
jasper_dir = config.getq('directories', 'jasper_dir', environ.get('JASPER_DIR'))
jasper_libdir = config.getq('directories', 'jasper_libdir', environ.get('JASPER_LIBDIR'))
jasper_incdir = config.getq('directories', 'jasper_incdir', environ.get('JASPER_INCDIR'))

# Get PNG library info
png_dir = config.getq('directories', 'png_dir', environ.get('PNG_DIR'))
png_libdir = config.getq('directories', 'png_libdir', environ.get('PNG_LIBDIR'))
png_incdir = config.getq('directories', 'png_incdir', environ.get('PNG_INCDIR'))

# Get OpenJPEG library info
openjpeg_dir = config.getq('directories', 'openjpeg_dir', environ.get('OPENJPEG_DIR'))
openjpeg_libdir = config.getq('directories', 'openjpeg_libdir', environ.get('OPENJPEG_LIBDIR'))
openjpeg_incdir = config.getq('directories', 'openjpeg_incdir', environ.get('OPENJPEG_INCDIR'))

# Get Z library info
zlib_dir = config.getq('directories', 'zlib_dir', environ.get('ZLIB_DIR'))
zlib_libdir = config.getq('directories', 'zlib_libdir', environ.get('ZLIB_LIBDIR'))
zlib_incdir = config.getq('directories', 'zlib_incdir', environ.get('ZLIB_INCDIR'))

libraries=[]
libdirs=[]
import numpy
incdirs=[numpy.get_include()]

if jasper_dir is not None or jasper_libdir is not None:
    libraries.append('jasper')
if jasper_libdir is None and jasper_dir is not None:
    libdirs.append(os.path.join(jasper_dir,'lib'))
    libdirs.append(os.path.join(jasper_dir,'lib64'))
if jasper_incdir is None and jasper_dir is not None:
    incdirs.append(os.path.join(jasper_dir,'include'))
    incdirs.append(os.path.join(jasper_dir,'include/jasper'))

if openjpeg_dir is not None or openjpeg_libdir is not None:
    libraries.append('openjpeg')
if openjpeg_libdir is None and openjpeg_dir is not None:
    libdirs.append(os.path.join(openjpeg_dir,'lib'))
    libdirs.append(os.path.join(openjpeg_dir,'lib64'))
if openjpeg_incdir is None and openjpeg_dir is not None:
    incdirs.append(os.path.join(openjpeg_dir,'include'))

if png_dir is not None or png_libdir is not None:
    libraries.append('png')
if png_libdir is None and png_dir is not None:
    libdirs.append(os.path.join(png_dir,'lib'))
    libdirs.append(os.path.join(png_dir,'lib64'))
if png_incdir is None and png_dir is not None:
    incdirs.append(os.path.join(png_dir,'include'))

if zlib_dir is not None or zlib_libdir is not None:
    libraries.append('z')
if zlib_libdir is None and zlib_dir is not None:
    libdirs.append(os.path.join(zlib_dir,'lib'))
    libdirs.append(os.path.join(zlib_dir,'lib64'))
if zlib_incdir is None and zlib_dir is not None:
    incdirs.append(os.path.join(zlib_dir,'include'))

# Define g2c sources to compile.  Here we need to remove main.c
# and mainhome.c from the list.
g2clib_deps = glob.glob('g2clib_src/*.c')
g2clib_deps.remove(os.path.join('g2clib_src', 'main.c'))
g2clib_deps.remove(os.path.join('g2clib_src', 'mainhome.c'))
g2clib_deps.append(g2clib_pyx)
incdirs.append('g2clib_src')
macros=[]

# If jasper or openjpeg lib not available...
if 'jasper' not in libraries and 'openjpeg' not in libraries:
    g2clib_deps.remove(os.path.join('g2clib_src', 'jpcpack.c'))
    g2clib_deps.remove(os.path.join('g2clib_src', 'jpcunpack.c'))
else:
    macros.append(('USE_JPEG2000',1))

# If png lib not available...
if 'png' not in libraries:
    g2clib_deps.remove(os.path.join('g2clib_src', 'pngpack.c'))
    g2clib_deps.remove(os.path.join('g2clib_src', 'pngunpack.c'))
else:
    macros.append(('USE_PNG',1))

if hasattr(sys,'maxsize'):
    if sys.maxsize > 2**31-1: macros.append(('__64BIT__',1))
else:
    if sys.maxint > 2**31-1: macros.append(('__64BIT__',1))

# Define extensions
runtime_libdirs = libdirs if os.name != 'nt' else None
g2clibext = Extension('g2clib',g2clib_deps,include_dirs=incdirs,\
            library_dirs=libdirs,libraries=libraries,runtime_library_dirs=runtime_libdirs,
            define_macros=macros)
redtoregext = Extension('redtoreg',[redtoreg_pyx],include_dirs=[numpy.get_include()])

# Data files to install
data_files = None

# Define installable entities
install_scripts = []
install_ext_modules = [g2clibext,redtoregext]
install_py_modules = ['grib2io']

# Import README.md as PyPi long_description
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Run setup.py
setup(name = 'grib2io',
      version = '0.1.0',
      description       = 'Python interface to the NCEP G2C Library for reading/writing GRIB2 files.',
      author            = 'Eric Engle',
      author_email      = 'eric.engle@mac.com',
      url               = 'https://github.com/eengl/grib2io',
      download_url      = 'http://python.org/pypi/grib2io',
      classifiers       = ['Development Status :: 3 - Alpha',
                           'Programming Language :: Python :: 3',
                           'Programming Language :: Python :: 3.6',
                           'Programming Language :: Python :: 3.7',
                           'Programming Language :: Python :: 3.8',
                           'Programming Language :: Python :: 3.9',
                           'Intended Audience :: Science/Research',
                           'License :: OSI Approved',
                           'Topic :: Software Development :: Libraries :: Python Modules'],
      cmdclass          = cmdclass,
      scripts           = install_scripts,
      ext_modules       = install_ext_modules,
      py_modules        = install_py_modules,
      data_files        = data_files,
      install_requires  = ['numpy'],
      python_requires   = '>=3.6',
      long_description  = long_description,
      long_description_content_type = 'text/markdown')
