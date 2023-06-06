from setuptools import setup, Extension, find_packages, Command
from setuptools.command.install_egg_info import install_egg_info
from setuptools.command.build_ext import build_ext
from os import environ
import configparser
import glob
import numpy
import os
import platform
import sys
import sysconfig

VERSION = '2.0.0b2.post1'

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
    def _find_library_linux(name):
        import subprocess
        result = subprocess.run(['/sbin/ldconfig','-p'],stdout=subprocess.PIPE)
        libs = [i.replace(' => ','#').split('#')[1] for i in result.stdout.decode('utf-8').splitlines()[1:-1]]
        try:
            return [l for l in libs if name in l][0]
        except IndexError:
            return None
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
# Read setup.cfg. Contents of setup.cfg will override env vars.
# ----------------------------------------------------------------------------------------
setup_cfg = environ.get('GRIB2IO_SETUP_CONFIG', 'setup.cfg')
config = _ConfigParser()
if os.path.exists(setup_cfg):
    sys.stdout.write('Reading from setup.cfg...')
    config.read(setup_cfg)

# ---------------------------------------------------------------------------------------- 
# Define lists for build
# ---------------------------------------------------------------------------------------- 
incdirs=[]
libdirs=[]

# ---------------------------------------------------------------------------------------- 
# Get NCEPLIBS-g2c library info
# ---------------------------------------------------------------------------------------- 
g2c_dir = config.getq('directories', 'g2c_dir', environ.get('G2C_DIR'))
g2c_libdir = config.getq('directories', 'g2c_libdir', environ.get('G2C_LIBDIR'))
g2c_incdir = config.getq('directories', 'g2c_incdir', environ.get('G2C_INCDIR'))
if g2c_libdir is None and g2c_dir is not None:
    libdirs.append(os.path.join(g2c_dir,'lib'))
    libdirs.append(os.path.join(g2c_dir,'lib64'))
else:
    libdirs.append(g2c_libdir)
if g2c_incdir is None and g2c_dir is not None:
    incdirs.append(os.path.join(g2c_dir,'include'))
else:
    incdirs.append(g2c_incdir)

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
g2clibext = Extension('grib2io.g2clib',[g2clib_pyx],include_dirs=incdirs,\
            library_dirs=libdirs,libraries=['g2c'],runtime_library_dirs=runtime_libdirs)
redtoregext = Extension('grib2io.redtoreg',[redtoreg_pyx],include_dirs=[numpy.get_include()])

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
grib2io_version = '%(grib2io_version)s'
"""
a = open('grib2io/__config__.py','w')
cfgdict = {}
cfgdict['grib2io_version'] = VERSION
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
      author_email      = 'eric.engle@noaa.gov',
      url               = 'https://github.com/NOAA-MDL/grib2io',
      download_url      = 'http://python.org/pypi/grib2io',
      classifiers       = ['Development Status :: 4 - Beta',
                           'Environment :: Console',
                           'Programming Language :: Python :: 3',
                           'Programming Language :: Python :: 3 :: Only',
                           'Programming Language :: Python :: 3.8',
                           'Programming Language :: Python :: 3.9',
                           'Programming Language :: Python :: 3.10',
                           'Programming Language :: Python :: 3.11',
                           'Intended Audience :: Science/Research',
                           'License :: OSI Approved',
                           'Topic :: Software Development :: Libraries :: Python Modules'],
      cmdclass          = cmdclass,
      scripts           = install_scripts,
      ext_modules       = install_ext_modules,
      py_modules        = install_py_modules,
      entry_points      = {'xarray.backends':['grib2io=grib2io.xarray_backend:GribBackendEntrypoint']},
      packages          = find_packages(),
      data_files        = data_files,
      setup_requires    = ['cython','setuptools'],
      install_requires  = ['setuptools','numpy>=1.22.0','pyproj>=1.9.5'],
      python_requires   = '>=3.8',
      zip_safe          = False,
      long_description  = long_description,
      long_description_content_type = 'text/markdown')
