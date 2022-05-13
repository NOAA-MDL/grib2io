from setuptools import setup, Extension, find_packages, Command
from os import environ
import configparser
import glob
import numpy
import os
import platform
import sys

VERSION = '0.9.3'

# ---------------------------------------------------------------------------------------- 
# Function to provide the absolute path for a shared object library,
# ---------------------------------------------------------------------------------------- 
def _find_library_linux(name):
    import subprocess
    result = subprocess.run(['/sbin/ldconfig','-p'],stdout=subprocess.PIPE)
    libs = [i.replace(' => ','#').split('#')[1] for i in result.stdout.decode('utf-8').splitlines()[1:-1]]
    try:
        return [l for l in libs if name in l][0]
    except IndexError:
        return None

# ---------------------------------------------------------------------------------------- 
# Class to parse the setup.cfg
# ---------------------------------------------------------------------------------------- 
class _ConfigParser(configparser.ConfigParser):
    def getq(self, s, k, fallback):
        try:
            return self.get(s, k)
        except:
            return fallback

# ---------------------------------------------------------------------------------------- 
# Setup find_library functions according system.
# ---------------------------------------------------------------------------------------- 
system = platform.system()
if system == 'Linux':
    find_library = _find_library_linux
elif system == 'Darwin':
    from ctypes.util import find_library

# ---------------------------------------------------------------------------------------- 
# Build time dependancy
# ---------------------------------------------------------------------------------------- 
try:
    from Cython.Distutils import build_ext
    cmdclass = {'build_ext': build_ext}
    redtoreg_pyx = 'redtoreg.pyx'
    g2clib_pyx  = 'g2clib.pyx'
except ImportError:
    cmdclass = {}
    redtoreg_pyx = 'redtoreg.c'
    g2clib_pyx  = 'g2clib.c'

# ---------------------------------------------------------------------------------------- 
# Default libraries
# ---------------------------------------------------------------------------------------- 
DEFAULT_LIBRARIES = ['openjp2','png','z']

# ---------------------------------------------------------------------------------------- 
# Read setup.cfg. Contents of setup.cfg will override env vars.
# ---------------------------------------------------------------------------------------- 
setup_cfg = environ.get('GRIB2IO_SETUP_CONFIG', 'setup.cfg')
config = _ConfigParser()
if os.path.exists(setup_cfg):
    sys.stdout.write('Reading from setup.cfg...')
    config.read(setup_cfg)

# ---------------------------------------------------------------------------------------- 
# Get Jasper library info
# ---------------------------------------------------------------------------------------- 
jasper_dir = config.getq('directories', 'jasper_dir', environ.get('JASPER_DIR'))
jasper_libdir = config.getq('directories', 'jasper_libdir', environ.get('JASPER_LIBDIR'))
jasper_incdir = config.getq('directories', 'jasper_incdir', environ.get('JASPER_INCDIR'))

# ---------------------------------------------------------------------------------------- 
# Get OpenJPEG library info
# ---------------------------------------------------------------------------------------- 
openjpeg_dir = config.getq('directories', 'openjpeg_dir', environ.get('OPENJPEG_DIR'))
openjpeg_libdir = config.getq('directories', 'openjpeg_libdir', environ.get('OPENJPEG_LIBDIR'))
openjpeg_incdir = config.getq('directories', 'openjpeg_incdir', environ.get('OPENJPEG_INCDIR'))

# ---------------------------------------------------------------------------------------- 
# Get PNG library info
# ---------------------------------------------------------------------------------------- 
png_dir = config.getq('directories', 'png_dir', environ.get('PNG_DIR'))
png_libdir = config.getq('directories', 'png_libdir', environ.get('PNG_LIBDIR'))
png_incdir = config.getq('directories', 'png_incdir', environ.get('PNG_INCDIR'))

# ---------------------------------------------------------------------------------------- 
# Get Z library info
# ---------------------------------------------------------------------------------------- 
zlib_dir = config.getq('directories', 'zlib_dir', environ.get('ZLIB_DIR'))
zlib_libdir = config.getq('directories', 'zlib_libdir', environ.get('ZLIB_LIBDIR'))
zlib_incdir = config.getq('directories', 'zlib_incdir', environ.get('ZLIB_INCDIR'))

# ---------------------------------------------------------------------------------------- 
# Define lists for build
# ---------------------------------------------------------------------------------------- 
libraries=[]
incdirs=[]
libdirs=[]
macros=[]

# ---------------------------------------------------------------------------------------- 
# Expand Jasper library and include paths.
# ---------------------------------------------------------------------------------------- 
if jasper_dir is not None or jasper_libdir is not None:
    libraries.append('jasper')
if jasper_libdir is None and jasper_dir is not None:
    libdirs.append(os.path.join(jasper_dir,'lib'))
    libdirs.append(os.path.join(jasper_dir,'lib64'))
else:
    libdirs.append(jasper_libdir)
if jasper_incdir is None and jasper_dir is not None:
    incdirs.append(os.path.join(jasper_dir,'include'))
    incdirs.append(os.path.join(jasper_dir,'include/jasper'))
else:
    incdirs.append(jasper_incdir)

# ---------------------------------------------------------------------------------------- 
# Expand OpenJPEG library and include paths.
#
# For OpenJPEG, the string 'openjp2' is used for the library name because that is the
# name of the OpenJPEG library name (libopenjp2.[a,dylib,so]).
# ---------------------------------------------------------------------------------------- 
if openjpeg_dir is not None or openjpeg_libdir is not None:
    libraries.append('openjp2')
if openjpeg_libdir is None and openjpeg_dir is not None:
    libdirs.append(os.path.join(openjpeg_dir,'lib'))
    libdirs.append(os.path.join(openjpeg_dir,'lib64'))
else:
    libdirs.append(openjpeg_libdir)
if openjpeg_incdir is None and openjpeg_dir is not None:
    incdirs.append(os.path.join(openjpeg_dir,'include'))
    incdirs.append(os.path.join(openjpeg_dir,'include/openjpeg'))
else:
    incdirs.append(openjpeg_incdir)

# ---------------------------------------------------------------------------------------- 
# Check if both JPEG libraries were specified....pick one!
# ---------------------------------------------------------------------------------------- 
if 'jasper' in libraries and 'openjp2' in libraries:
    raise RuntimeError('Cannot build with both jasper and openjpeg.')

# ---------------------------------------------------------------------------------------- 
# Expand PNG library and include paths.
# ---------------------------------------------------------------------------------------- 
if png_dir is not None or png_libdir is not None:
    libraries.append('png')
if png_libdir is None and png_dir is not None:
    libdirs.append(os.path.join(png_dir,'lib'))
    libdirs.append(os.path.join(png_dir,'lib64'))
else:
    libdirs.append(png_libdir)
if png_incdir is None and png_dir is not None:
    incdirs.append(os.path.join(png_dir,'include'))
else:
    incdirs.append(png_incdir)

# ---------------------------------------------------------------------------------------- 
# Expand Z library and include paths.
# ---------------------------------------------------------------------------------------- 
if zlib_dir is not None or zlib_libdir is not None:
    libraries.append('z')
if zlib_libdir is None and zlib_dir is not None:
    libdirs.append(os.path.join(zlib_dir,'lib'))
    libdirs.append(os.path.join(zlib_dir,'lib64'))
else:
    libdirs.append(zlib_libdir)
if zlib_incdir is None and zlib_dir is not None:
    incdirs.append(os.path.join(zlib_dir,'include'))
else:
    incdirs.append(zlib_incdir)

# ---------------------------------------------------------------------------------------- 
# Check for empty library list.  If libraries is empty here, then a setup.cfg and/or
# library-specific env var were not used.  In this scenario, lets find the appropriate
# library and include paths for the DEFAULT_LIBRARIES.
# ---------------------------------------------------------------------------------------- 
if len(libraries) == 0:
    for lib in DEFAULT_LIBRARIES:
        lib_path = find_library(lib)
        if isinstance(lib_path, str):
            lib_dir = os.path.dirname(os.path.realpath(lib_path))
        else:
            continue
        if len(lib_dir) > 0:
            libraries.append(lib)
            libdirs.append(lib_dir)
            if system == 'Linux':
                incpath = glob.glob(lib_dir.replace('/lib/x86_64-linux-gnu','/include').replace('/lib64','/include')+\
                          '/**/*'+lib.replace('jp2','jpeg')+'.h',recursive=True)
            else:
                if lib == 'openjp2':
                    incpath = glob.glob(lib_dir.replace('/lib','/include')+'/**/*'+lib.replace('jp2','jpeg')+'.h',recursive=True)
                elif lib == 'png':
                    incpath = glob.glob(lib_dir.replace('/lib','/include').replace('includepng','libpng')+'/**/*'+lib+'.h',recursive=True)
                else:
                    incpath = glob.glob(lib_dir.replace('/lib','/include')+'/**/*'+lib+'.h',recursive=True)
                print(lib,lib_dir,incpath)
            if len(incpath) > 0:
                incdirs.append(os.path.dirname(incpath[0]))

# ---------------------------------------------------------------------------------------- 
# Define g2c sources to compile.
# ---------------------------------------------------------------------------------------- 
g2clib_deps = glob.glob('NCEPLIBS-g2c/src/*.c')
g2clib_deps.append(g2clib_pyx)
incdirs.append('NCEPLIBS-g2c/src')

# ---------------------------------------------------------------------------------------- 
# Add macro for JPEG Encoding/Decoding if a JPEG library
# has been defined, otherwise remove JPEG sources from
# g2c source list.
# ---------------------------------------------------------------------------------------- 
if 'jasper' in libraries:
    macros.append(('USE_JPEG2000',1))
    # Using Jasper, remove OpenJPEG from source
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'decenc_openjpeg.c'))
elif 'openjp2' in libraries:
    macros.append(('USE_OPENJPEG',1))
    # Using OpenJPEG, remove Jasper from source
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'dec_jpeg2000.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'enc_jpeg2000.c'))
else:
    # Remove all JPEG from source
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'decenc_openjpeg.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'dec_jpeg2000.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'enc_jpeg2000.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'jpcpack.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'jpcunpack.c'))

# ---------------------------------------------------------------------------------------- 
# Add macro for PNG Encoding/Decoding if a PNG library
# has been defined, otherwise remove PNG sources from
# g2c source list.
# ---------------------------------------------------------------------------------------- 
if 'png' in libraries:
    macros.append(('USE_PNG',1))
else:
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'dec_png.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'enc_png.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'pngpack.c'))
    g2clib_deps.remove(os.path.join('NCEPLIBS-g2c/src', 'pngunpack.c'))

# ---------------------------------------------------------------------------------------- 
# Cleanup library and include path lists to remove duplicates and None.
# ---------------------------------------------------------------------------------------- 
libdirs = [l for l in set(libdirs) if l is not None]
incdirs = [i for i in set(incdirs) if i is not None]
runtime_libdirs = libdirs if os.name != 'nt' else None
incdirs.append(numpy.get_include())

# ---------------------------------------------------------------------------------------- 
# Define extensions
# ---------------------------------------------------------------------------------------- 
print('Libraries: ',libraries)
print('libdirs: ',libdirs)
print('incdirs: ',incdirs)
print('macros: ',macros)
g2clibext = Extension('g2clib',g2clib_deps,include_dirs=incdirs,\
            library_dirs=libdirs,libraries=libraries,runtime_library_dirs=runtime_libdirs,
            define_macros=macros)
redtoregext = Extension('redtoreg',[redtoreg_pyx],include_dirs=[numpy.get_include()])

# ---------------------------------------------------------------------------------------- 
# Data files to install
# ---------------------------------------------------------------------------------------- 
data_files = None

# ---------------------------------------------------------------------------------------- 
# Define installable entities
# ---------------------------------------------------------------------------------------- 
install_scripts = []
install_ext_modules = [g2clibext,redtoregext]
install_py_modules = []

# ---------------------------------------------------------------------------------------- 
# Create __config__.py
# ---------------------------------------------------------------------------------------- 
cnt = \
"""# This file is generated by grib2io's setup.py
# It contains configuration information when building this package.
libraries = %(libraries)s
grib2io_version = '%(grib2io_version)s'
"""
a = open('grib2io/__config__.py','w')
cfgdict = {}
cfgdict['grib2io_version'] = VERSION
cfgdict['libraries'] = libraries
try:
    a.write(cnt % cfgdict)
finally:
    a.close()

# ---------------------------------------------------------------------------------------- 
# Define testing class
# ---------------------------------------------------------------------------------------- 
class TestCommand(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        import sys, subprocess
        for f in glob.glob('./tests/*.py'):
            raise SystemExit(subprocess.call([sys.executable,f]))
cmdclass['test'] = TestCommand

# ---------------------------------------------------------------------------------------- 
# Import README.md as PyPi long_description
# ---------------------------------------------------------------------------------------- 
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# ---------------------------------------------------------------------------------------- 
# Run setup.py
# ---------------------------------------------------------------------------------------- 
setup(name = 'grib2io',
      version = VERSION,
      description       = 'Python interface to the NCEP G2C Library for reading/writing GRIB2 files.',
      author            = 'Eric Engle',
      author_email      = 'eric.engle@mac.com',
      url               = 'https://github.com/eengl/grib2io',
      download_url      = 'http://python.org/pypi/grib2io',
      classifiers       = ['Development Status :: 4 - Beta',
                           'Programming Language :: Python :: 3',
                           'Programming Language :: Python :: 3.6',
                           'Programming Language :: Python :: 3.7',
                           'Programming Language :: Python :: 3.8',
                           'Programming Language :: Python :: 3.9',
                           'Programming Language :: Python :: 3.10',
                           'Intended Audience :: Science/Research',
                           'License :: OSI Approved',
                           'Topic :: Software Development :: Libraries :: Python Modules'],
      cmdclass          = cmdclass,
      scripts           = install_scripts,
      ext_modules       = install_ext_modules,
      py_modules        = install_py_modules,
      packages          = find_packages(),
      data_files        = data_files,
      install_requires  = ['setuptools>=34.0','numpy>=1.12.0','pyproj>=1.9.5'],
      python_requires   = '>=3.6',
      long_description  = long_description,
      long_description_content_type = 'text/markdown')
