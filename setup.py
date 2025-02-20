from ctypes.util import find_library as ctypes_find_library
from pathlib import Path
from setuptools import setup, Extension
import configparser
import copy
import numpy
import os
import platform
import subprocess
import sys
import warnings

# This maps package names to library names used in the library filename.
pkgname_to_libname = {
    'g2c': ['g2c'],
    'aec': ['aec'],
    'ip': ['ip_4'],
    'jasper': ['jasper'],
    'jpeg': ['turbojpeg', 'jpeg'],
    'openjpeg': ['openjp2'],
    'png': ['png'],
    'z': ['z'],}

def get_grib2io_version():
    with open("VERSION","rt") as f:
        ver = f.readline().strip()
    return ver

def get_package_info(name, config, static=False, required=True, include_file=None):
    pkg_dir = os.environ.get(name.upper()+'_DIR')
    pkg_incdir = os.environ.get(name.upper()+'_INCDIR')
    pkg_libdir = os.environ.get(name.upper()+'_LIBDIR')

    if pkg_dir is None:
        # Env var not set
        pkg_dir = config.get('directories',name+'_dir',fallback=None)
        if pkg_dir is None:
            if static:
                pkg_lib = config.get('static_libs',name+'_lib',fallback=None)
                if pkg_lib is not None:
                    pkg_libdir = os.path.dirname(pkg_lib)
                    pkg_incdir = os.path.join(os.path.dirname(pkg_libdir),'include')
                    pkg_dir = os.path.dirname(pkg_libdir)

        if pkg_dir is None:
            if name not in pkgname_to_libname.keys():
                pkgname_to_libname[name] = [name]
            for l in pkgname_to_libname[name]:
                libname = find_library(l, static=static, required=required)
                if libname is not None: break
            name = l
            if libname is None:
                pkg_libdir = None
                pkg_incdir = None
            else:
                pkg_libdir = os.path.dirname(libname)
                if include_file is None:
                    pkg_incdir = os.path.join(os.path.dirname(pkg_libdir),'include')
                else:
                    incfile = find_include_file(include_file, root=os.path.dirname(pkg_libdir))
                    pkg_incdir = os.path.dirname(incfile)

    else:
        # Env var was set
        if os.path.exists(os.path.join(pkg_dir,'lib')):
            pkg_libdir = os.path.join(pkg_dir,'lib')
        elif os.path.exists(os.path.join(pkg_dir,'lib64')):
            pkg_libdir = os.path.join(pkg_dir,'lib64')
        if os.path.exists(os.path.join(pkg_dir,'include')):
            pkg_incdir = os.path.join(pkg_dir,'include')
        elif os.path.exists(os.path.join(pkg_dir,'include_4')):
            pkg_incdir = os.path.join(pkg_dir,'include_4')
    return (name, pkg_incdir, pkg_libdir)


def find_include_file(file, root=None):
    incfile = ''
    if root is None:
        return None
    for path, subdirs, files in os.walk(root):
        for name in files:
            if name == file:
                incfile = os.path.join(path, name)
                break
    return incfile


def find_library(name, dirs=None, static=False, required=True):
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
        if required:
            raise ValueError(f"""

The library "lib{name}{libext}" could not be found in any of the following
directories:
{dirs}

""")
        else:
            return None
    return out[0].absolute().resolve().as_posix()

def run_ar_command(filename):
    """Run the ar command"""
    cmd = subprocess.run(['ar','-t',filename],
                         stdout=subprocess.PIPE)
    cmdout = cmd.stdout.decode('utf-8')
    return cmdout

def run_nm_command(filename):
    """Run the nm command"""
    cmd = subprocess.run(['nm','-C',filename],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    cmdout = cmd.stdout.decode('utf-8')
    return cmdout

def run_ldd_command(filename):
    """Run the ldd command"""
    cmd = subprocess.run(['ldd',filename],
                         stdout=subprocess.PIPE)
    cmdout = cmd.stdout.decode('utf-8')
    return cmdout

def run_otool_command(filename):
    """Run the otool command"""
    cmd = subprocess.run(['otool','-L',filename],
                         stdout=subprocess.PIPE)
    cmdout = cmd.stdout.decode('utf-8')
    return cmdout

def check_for_openmp(ip_lib, static=False):
    """Check for OpenMP"""
    check = False
    is_apple_clang = False
    info = ''
    libname = ''

    # Special check for macOS
    if sys.platform == 'darwin':
        try:
            is_apple_clang = 'clang' in os.environ['CC']
        except(KeyError):
            is_apple_clang = True
    if is_apple_clang:
        check = True
        libname = 'omp'
        return check, libname
        
    if static:
        if sys.platform in {'darwin','linux'}:
            info = run_nm_command(ip_lib)
            if 'GOMP' in info:
                check = True
                libname = 'gomp'
            elif 'kmpc' in info:
                check = True
                libname = 'iomp5'
    else:
        if sys.platform == 'darwin':
            info = run_otool_command(ip_lib)
        elif sys.platform == 'linux':
            info = run_ldd_command(ip_lib)
        if 'gomp' in info:
            check = True
            libname = 'gomp'
        elif 'iomp5' in info:
            check = True
            libname = 'iomp5'
        elif 'omp' in info:
            check = True
            libname = 'omp'
    return check, libname

# ----------------------------------------------------------------------------------------
# Main part of setup.py
# ----------------------------------------------------------------------------------------
VERSION = get_grib2io_version()

use_static_libs = False
build_with_ip = True
build_with_openmp = False

extmod_config = {}
extension_modules = []
all_extra_objects = []

# ----------------------------------------------------------------------------------------
# Build Cython sources
# ----------------------------------------------------------------------------------------
from Cython.Distutils import build_ext
cmdclass = {'build_ext': build_ext}
redtoreg_pyx = 'src/ext/redtoreg.pyx'
g2clib_pyx  = 'src/ext/g2clib.pyx'
iplib_pyx = 'src/ext/iplib.pyx'
openmp_pyx = 'src/ext/openmp_handler.pyx'

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
    use_static_libs = True if val == 'True' else False
use_static_libs = config.get('options', 'use_static_libs', fallback=use_static_libs)

# ----------------------------------------------------------------------------------------
# Get g2c information (THIS IS REQUIRED)
# ----------------------------------------------------------------------------------------
pkginfo = get_package_info('g2c', config, static=use_static_libs, required=True)
if None in pkginfo:
    raise ValueError(f"NCEPLIBS-g2c library not found. grib2io will not build.")

extmod_config['g2clib'] = dict(libraries=[pkginfo[0]],
                               incdirs=[pkginfo[1]],
                               libdirs=[pkginfo[2]],
                               extra_objects=[])

if use_static_libs:
    staticlib = find_library('g2c', dirs=extmod_config['g2clib']['libdirs'], static=True)
    extmod_config['g2clib']['extra_objects'].append(staticlib)
    cmd = subprocess.run(['ar','-t',staticlib], stdout=subprocess.PIPE)
    symbols = cmd.stdout.decode('utf-8')
    dep_libraries = ['g2c']
    if 'aec' in symbols:
        dep_libraries.append('aec')
    if 'jpeg2000' in symbols:
        dep_libraries.append('jpeg')
        dep_libraries.append('jasper')
    if 'openjpeg' in symbols:
        dep_libraries.append('openjpeg')
    if 'png' in symbols:
        dep_libraries.append('png')
        dep_libraries.append('z')

    # We already found g2c info, so iterate over libraries from [1:]
    for l in dep_libraries[1:]:
        libname, incdir, libdir = get_package_info(l, config, static=use_static_libs)
        extmod_config['g2clib']['libraries'].append(libname)
        extmod_config['g2clib']['incdirs'].append(incdir)
        extmod_config['g2clib']['libdirs'].append(libdir)

        l = pkgname_to_libname[l][0]
        extmod_config['g2clib']['extra_objects'].append(find_library(l, dirs=[libdir], static=use_static_libs))

    # Clear out libraries and libdirs when using static libs
    extmod_config['g2clib']['libraries'] = []
    extmod_config['g2clib']['libdirs'] = []

extmod_config['g2clib']['incdirs'].append(numpy.get_include())

# ----------------------------------------------------------------------------------------
# Get NCEPLIBS-ip information
# ----------------------------------------------------------------------------------------
pkginfo = get_package_info('ip', config, static=use_static_libs, required=False)
if None in pkginfo:
    warnings.warn(f"NCEPLIBS-ip not found. grib2io will build without interpolation.")
    build_with_ip = False

if build_with_ip:
    extmod_config['iplib'] = dict(libraries=[pkginfo[0]],
                                  incdirs=[pkginfo[1]],
                                  libdirs=[pkginfo[2]],
                                  extra_objects=[],
                                  define_macros=[])

    ip_libname = find_library(pkgname_to_libname['ip'][0],
                              dirs=extmod_config['iplib']['libdirs'],
                              static=use_static_libs)

    build_with_openmp, openmp_libname = check_for_openmp(ip_libname, static=use_static_libs)
    if build_with_openmp:
        pkginfo = get_package_info(openmp_libname,
                                   config,
                                   static=use_static_libs,
                                   required=False,
                                   include_file="omp.h")

        extmod_config['iplib']['libraries'].append(pkginfo[0])
        extmod_config['iplib']['incdirs'].append(pkginfo[1])
        extmod_config['iplib']['libdirs'].append(pkginfo[2])
        extmod_config['iplib']['define_macros'].append(('IPLIB_WITH_OPENMP', None))

    if use_static_libs:
        for l in extmod_config['iplib']['libraries']:
            lname = find_library(l, dirs=extmod_config['iplib']['libdirs'], static=use_static_libs)
            extmod_config['iplib']['extra_objects'].append(lname)

        extmod_config['iplib']['libraries'] = []
        extmod_config['iplib']['libdirs'] = []

    extmod_config['iplib']['incdirs'].append(numpy.get_include())

# ----------------------------------------------------------------------------------------
# Summary 
# ----------------------------------------------------------------------------------------
print(f'Use static libs: {use_static_libs}')
print(f'Build with NCEPLIBS-ip: {build_with_ip}')
print(f'Needs OpenMP: {build_with_openmp}')
for n, c in extmod_config.items():
    print(f'Extension module name: {n}')
    for k, v in c.items():
        if k == 'extra_objects':
            all_extra_objects.extend(v)
        print(f'\t{k}: {v}')

# ----------------------------------------------------------------------------------------
# Define extensions
# ----------------------------------------------------------------------------------------
g2clibext = Extension('grib2io.g2clib',
                      [g2clib_pyx],
                      include_dirs = extmod_config['g2clib']['incdirs'],
                      library_dirs = extmod_config['g2clib']['libdirs'],
                      libraries = extmod_config['g2clib']['libraries'],
                      runtime_library_dirs = extmod_config['g2clib']['libdirs'],
                      extra_objects = extmod_config['g2clib']['extra_objects'])
extension_modules.append(g2clibext)

redtoregext = Extension('grib2io.redtoreg',
                        [redtoreg_pyx],
                        include_dirs = [numpy.get_include()])
extension_modules.append(redtoregext)

if build_with_ip:
    iplibext = Extension('grib2io.iplib',
                         [iplib_pyx],
                         include_dirs = ['./src/ext']+extmod_config['iplib']['incdirs'],
                         library_dirs = extmod_config['iplib']['libdirs'],
                         libraries = extmod_config['iplib']['libraries'],
                         runtime_library_dirs = extmod_config['iplib']['libdirs'],
                         extra_objects = extmod_config['iplib']['extra_objects'],
                         define_macros = extmod_config['iplib']['define_macros'])
    extension_modules.append(iplibext)

# ----------------------------------------------------------------------------------------
# Create __config__.py
# ----------------------------------------------------------------------------------------
cnt = \
"""# This file is generated by grib2io's setup.py
# It contains configuration information when building this package.
grib2io_version = '%(grib2io_version)s'
has_interpolation = %(has_interpolation)s
has_openmp_support = %(has_openmp_support)s
use_static_libs = %(use_static_libs)s
extra_objects = %(extra_objects)s
"""
a = open('src/grib2io/__config__.py','w')
cfgdict = {}
cfgdict['grib2io_version'] = VERSION
cfgdict['has_interpolation'] = build_with_ip
cfgdict['has_openmp_support'] = build_with_openmp
cfgdict['use_static_libs'] = use_static_libs
cfgdict['extra_objects'] = all_extra_objects
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
setup(ext_modules = extension_modules,
      cmdclass = cmdclass,
      long_description = long_description,
      long_description_content_type = 'text/markdown')
