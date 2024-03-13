from ctypes.util import find_library as ctypes_find_library
from pathlib import Path
from setuptools import setup, Extension
import configparser
import numpy
import os
import platform
import subprocess
import sys

# This maps package names to library names used in the
# library filename.
pkgname_to_libname = {
    'g2c': ['g2c'],
    'aec': ['aec'],
    'jasper': ['jasper'],
    'jpeg': ['turbojpeg', 'jpeg'],
    'openjpeg': ['openjp2'],
    'png': ['png'],
    'z': ['z'],}

def get_grib2io_version():
    with open("VERSION","rt") as f:
        ver = f.readline().strip()
    return ver

def get_package_info(name, config, static=False):
    pkg_dir = os.environ.get(name.upper()+'_DIR')
    pkg_incdir = os.environ.get(name.upper()+'_INCDIR')
    pkg_libdir = os.environ.get(name.upper()+'_LIBDIR')

    if pkg_dir is None:
        # Env var not set
        pkg_dir = config.get('directories',name+'_dir',fallback=None)
        if pkg_dir is None:
            if static:
                pkg_lib = config.get('static_libs',name+'_lib',fallback=None)
                pkg_libdir = os.path.dirname(pkg_lib)
                pkg_incdir = os.path.join(os.path.dirname(pkg_libdir),'include')
                pkg_dir = os.path.dirname(pkg_libdir)

        if pkg_dir is None:
            for l in pkgname_to_libname[name]:
                libname = os.path.dirname(find_library(l, static=static))
                if libname is not None: break
            pkg_libdir = libname
            pkg_incdir = os.path.join(os.path.dirname(pkg_libdir),'include')

    else:
        # Env var was set
        if os.path.exists(os.path.join(pkg_dir,'lib')):
            pkg_libdir = os.path.join(pkg_dir,'lib')
        elif os.path.exists(os.path.join(pkg_dir,'lib64')):
            pkg_libdir = os.path.join(pkg_dir,'lib64')
        if os.path.exists(os.path.join(pkg_dir,'include')):
            pkg_incdir = os.path.join(pkg_dir,'include')
    return (pkg_incdir, pkg_libdir)

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
# Main part of setup.py
# ----------------------------------------------------------------------------------------
VERSION = get_grib2io_version()

usestaticlibs = False
libraries = ['g2c']

extra_objects = []
incdirs = []
libdirs = []

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
# Check if static library linking is preferred.
# ----------------------------------------------------------------------------------------
if os.environ.get('USE_STATIC_LIBS'):
    val = os.environ.get('USE_STATIC_LIBS')
    if val not in {'True','False'}:
        raise ValueError('Environment variable USE_STATIC_LIBS must be \'True\' or \'False\'')
    usestaticlibs = True if val == 'True' else False
usestaticlibs = config.get('options', 'use_static_libs', fallback=usestaticlibs)

# ----------------------------------------------------------------------------------------
# Get g2c information
# ----------------------------------------------------------------------------------------
pkginfo = get_package_info(libraries[0], config, static=usestaticlibs)
incdirs.append(pkginfo[0])
libdirs.append(pkginfo[1])

# ----------------------------------------------------------------------------------------
# Perform work to determine required static library files.
# ----------------------------------------------------------------------------------------
if usestaticlibs:
    staticlib = find_library('g2c', dirs=libdirs, static=True)
    extra_objects.append(staticlib)
    cmd = subprocess.run(['ar','-t',staticlib], stdout=subprocess.PIPE)
    symbols = cmd.stdout.decode('utf-8')
    if 'aec' in symbols:
        libraries.append('aec')
    if 'jpeg2000' in symbols:
        libraries.append('jpeg')
        libraries.append('jasper')
    if 'openjpeg' in symbols:
        libraries.append('openjpeg')
    if 'png' in symbols:
        libraries.append('png')
        libraries.append('z')

    # We already found g2c info, so iterate over libraries from [1:]
    dep_libraries = [] if len(libraries) == 1 else libraries[1:]
    for l in dep_libraries:
        incdir, libdir = get_package_info(l, config, static=usestaticlibs)
        incdirs.append(incdir)
        libdirs.append(libdir)
        if usestaticlibs:
            l = pkgname_to_libname[l][0]
            extra_objects.append(find_library(l, dirs=[libdir], static=usestaticlibs))

libraries = [] if usestaticlibs else list(set(libraries))
incdirs = list(set(incdirs))
incdirs.append(numpy.get_include())
libdirs = [] if usestaticlibs else list(set(libdirs))
extra_objects = list(set(extra_objects)) if usestaticlibs else []

print(f'Use static libs: {usestaticlibs}')
print(f'\t{incdirs = }')
print(f'\t{libdirs = }')
print(f'\t{extra_objects = }')

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
