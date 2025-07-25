from ctypes.util import find_library as ctypes_find_library
from pathlib import Path
from setuptools import setup, Extension
import numpy
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
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


def _is_apple_clang(compiler):
    """Returns True if compiler is Apple Clang, not real GCC."""
    try:
        proc = subprocess.run(
            [compiler, '--version'],
            capture_output=True, check=True
        )
        output = proc.stdout.decode(errors='ignore') + proc.stderr.decode(errors='ignore')
        if 'Apple LLVM' in output or 'Apple clang' in output:
            return True
        if 'clang' in output and 'Free Software Foundation' not in output:
            return True
        return False
    except Exception:
        return False


def _find_homebrew_gcc():
    """Return the highest versioned gcc-x in PATH, e.g. 'gcc-13'."""
    for version in reversed(range(10, 16)):  # Try gcc-15..gcc-10 (update as needed)
        exe = shutil.which(f"gcc-{version}")
        if exe:
            return f"gcc-{version}"
    return None


def check_lib_static(name):
    """Check whether or not to build with a static library."""
    bval = False
    env_var_name = name.upper()+'_STATIC'
    if os.environ.get(env_var_name):
        val = os.environ.get(env_var_name)
        if val not in {'True','False'}:
            raise ValueError('Environment variable {env_var_name} must be \'True\' or \'False\'')
        bval = True if val == 'True' else False
    return bval


def get_grib2io_version():
    """Get the grib2ion version string."""
    with open("VERSION","rt") as f:
        ver = f.readline().strip()
    return ver


def get_package_info(
    name,
    incdir="include",
    static=False,
    required=True,
    include_file=None,
    compiler=None
):
    """Get package information."""
    # First try to get package information from env vars
    pkg_dir = os.environ.get(name.upper()+'_DIR')
    pkg_incdir = os.environ.get(name.upper()+'_INCDIR')
    pkg_libdir = os.environ.get(name.upper()+'_LIBDIR')

    # Return if include and lib dir env vars were set.
    if name in {'g2c', 'ip'}:
        if pkg_incdir is not None and pkg_libdir is not None:
            libname = pkgname_to_libname[name][0]
            return libname, pkg_incdir, pkg_libdir

    if pkg_dir is not None:
        if name in {'g2c', 'ip'}:
            libname = pkgname_to_libname[name][0]
            libpath = find_library(libname, dirs=[pkg_dir], static=static, required=required)
            if libpath is None:
                raise ValueError(f"Cannot find {libname}.")
            pkg_libdir = os.path.dirname(libpath)
            incfile = find_include_file(include_file, incdir=incdir, root=pkg_dir)
            pkg_incdir = os.path.dirname(incfile)
    else:
        # No env vars set, now find everything.
        libnames = pkgname_to_libname[name] if name in pkgname_to_libname.keys() else [name]
        for l in libnames:
            libpath = find_library(l, static=static, required=required)
            if libpath is not None:
                break
        libname = l
        if libpath is None:
            pkg_libdir = None
            pkg_incdir = None
        else:
            pkg_libdir = os.path.dirname(libpath)
            # Check if pkg_libdir is inside "lib*". This is common with Intel compilers.
            if "lib" in os.path.dirname(pkg_libdir).split("/")[-1]:
                pkg_libdir_root = os.path.dirname(pkg_libdir)
            else:
                pkg_libdir_root = pkg_libdir

            if os.path.exists(os.path.join(os.path.dirname(pkg_libdir_root),'include')):
                pkg_incdir = os.path.join(os.path.dirname(pkg_libdir_root),'include')
            if include_file is not None:
                incfile = find_include_file(
                    include_file,
                    incdir=incdir,
                    root=os.path.dirname(pkg_libdir_root),
                    compiler=compiler
                )
                if incfile is not None:
                    pkg_incdir = os.path.dirname(incfile)

    return libname, pkg_incdir, pkg_libdir


def find_include_file(
    file,
    incdir="include",
    root=None,
    compiler=None,
):
    """Find absolute path to include file."""
    incfile = None

    if root is None:
        return None

    for path, subdirs, files in os.walk(root):
        if os.path.basename(path) == incdir:
            if file in files:
                incfile = os.path.join(path, file)
                break

    return incfile


def find_library(name,
    dirs=None,
    static=False,
    required=True
):
    """Find absolute path to library file."""
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
        dirs = []
        # No dirs. First check if in a conda env.
        if os.environ.get("CONDA_PREFIX"):
            dirs.append(os.environ["CONDA_PREFIX"])

        # Next, look in various library path env vars.
        if os.environ.get("LD_LIBRARY_PATH"):
            dirs.extend(os.environ["LD_LIBRARY_PATH"].split(":"))
        if sys.platform == "darwin" and os.environ.get("DYLD_LIBRARY_PATH"):
            dirs.extend(os.environ["DYLD_LIBRARY_PATH"].split(":"))

        # Finally, look in common system paths.
        dirs.extend(["/usr", "/usr/local", "/opt/local", "/opt/homebrew", "/opt", "/sw"])

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
    cmd = subprocess.run(['nm',filename],
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


def check_ip_for_bla(ip_lib, static=False, openmp=False):
    """Check for BLAS/LAPACK in NCEPLIBS-ip."""
    # First, check for env var
    bla_dir = ""
    if os.environ.get('BLA_DIR'):
        bla_dir = os.environ.get('BLA_DIR')
    # Check Intel MKL. Need multiple libs.
    if "mkl" in bla_dir:
        libs = ['mkl_intel_lp64', 'mkl_core']
        if openmp:
            libs.append('mkl_intel_thread')
        else:
            libs.append('mkl_intel_sequential')
    else:
        libs = ['lapack']
    bla_lib = find_library(libs[0], dirs=[bla_dir], static=False, required=True)
    bla_libdir = os.path.dirname(bla_lib)
    return libs, bla_libdir


def check_ip_for_openmp(ip_lib, static=False):
    """Check for OpenMP in NCEPLIBS-ip."""
    check = False
    is_apple_clang = False
    info = ''
    libname = ''
    ftnname = None

    # Special check for macOS, based on C compiler to be
    # used here.
    if sys.platform == 'darwin':
        try:
            is_apple_clang = 'clang' in os.environ['CC']
        except(KeyError):
            is_apple_clang = 'clang' in sysconfig.get_config_vars().get('CC')

    if ip_lib.endswith(".a"):
        static = True
    elif ip_lib.endswith(".so") or ip_lib.endswith(".dylib"):
        static = False
    if static:
        if sys.platform in {'darwin','linux'}:
            info = run_nm_command(ip_lib)
            if 'GOMP' in info:
                check = True
                libname = 'gomp'
                ftnname = 'gfortran'
            elif 'kmpc' in info:
                check = True
                libname = 'iomp5'
                ftnname = 'ifcore'
    else:
        if sys.platform == 'darwin':
            info = run_otool_command(ip_lib)
        elif sys.platform == 'linux':
            info = run_ldd_command(ip_lib)
        if 'gomp' in info:
            check = True
            libname = 'gomp'
            ftnname = 'gfortran'
        elif 'iomp5' in info:
            check = True
            libname = 'iomp5'
            ftnname = 'ifcore'
        elif 'omp' in info:
            check = True
            libname = 'omp'
            ftnname = 'gfortran'

    # Final adjustment is macOS and clang.
    if sys.platform == 'darwin' and is_apple_clang:
        check = True
        libname = 'omp'

    return check, libname, ftnname

# ----------------------------------------------------------------------------------------
# Main part of setup.py
# ----------------------------------------------------------------------------------------
VERSION = get_grib2io_version()

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
# Get g2c information (THIS IS REQUIRED)
# ----------------------------------------------------------------------------------------
g2c_static = check_lib_static('g2c')
pkginfo = get_package_info('g2c', static=g2c_static, required=True, include_file="grib2.h")
if None in pkginfo:
    raise ValueError(f"NCEPLIBS-g2c library not found. grib2io will not build.")

extmod_config['g2clib'] = dict(libraries=[pkginfo[0]],
                               incdirs=[pkginfo[1]],
                               libdirs=[pkginfo[2]],
                               extra_objects=[])

if g2c_static:
    staticlib = find_library('g2c', dirs=extmod_config['g2clib']['libdirs'], static=True)
    extmod_config['g2clib']['extra_objects'].append(staticlib)
    symbols = run_ar_command(staticlib)

    dep_libraries = []
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

    for l in dep_libraries:
        libname, incdir, libdir = get_package_info(l, static=g2c_static)
        extmod_config['g2clib']['libraries'].append(libname)
        extmod_config['g2clib']['incdirs'].append(incdir)
        extmod_config['g2clib']['libdirs'].append(libdir)

        l = pkgname_to_libname[l][0]
        extmod_config['g2clib']['extra_objects'].append(find_library(l, dirs=[libdir], static=g2c_static))

    # Clear out libraries and libdirs when using static libs
    extmod_config['g2clib']['libraries'] = []
    extmod_config['g2clib']['libdirs'] = []

extmod_config['g2clib']['incdirs'].append(numpy.get_include())

# ----------------------------------------------------------------------------------------
# Get NCEPLIBS-ip information
# ----------------------------------------------------------------------------------------
ip_static = check_lib_static('ip')
pkginfo = get_package_info('ip', incdir="include_4", static=ip_static, required=False, include_file="iplib.h")

if None in pkginfo:
    warnings.warn(f"NCEPLIBS-ip not found or missing information. grib2io will build without interpolation.")
    build_with_ip = False

if build_with_ip:

    ip_from_homebrew = False

    # Add ip package info to the configuration dictionary.
    extmod_config['iplib'] = dict(
        libraries=[pkginfo[0]],
        incdirs=[pkginfo[1]],
        libdirs=[pkginfo[2]],
        extra_objects=[],
        define_macros=[]
    )

    # Find the full path to the ip library.
    ip_libname = find_library(
        pkgname_to_libname['ip'][0],
        dirs=extmod_config['iplib']['libdirs'],
        static=ip_static
    )

    # Check if on macOS, then check if ip is from Homebrew.
    if sys.platform == 'darwin':
        ip_root = os.path.dirname(os.path.dirname(ip_libname))
        if os.path.exists(os.path.join(ip_root, 'INSTALL_RECEIPT.json')):
            ip_from_homebrew = True

    # Agument the config dict if linking statically to ip.
    if ip_static:
        extmod_config['iplib']['extra_objects'].append(ip_libname)
        extmod_config['iplib']['libraries'] = []
        extmod_config['iplib']['libdirs'] = []

    # At this point, we know where to find ip and how we are linking. Now check
    # if ip was built with OpenMP support.
    build_with_openmp, openmp_libname, ftn_libname = check_ip_for_openmp(ip_libname, static=False)

    if build_with_openmp:

        # If on macOS and ip is from Homebrew, then check the C compiler to be
        # used.  It must be C compiler matching the Fortran. Basically, you cannot
        # build the iplib extension module with Apple clang.
        if sys.platform == 'darwin' and ip_from_homebrew:
            ccomp = os.environ.get('CC', sysconfig.get_config_vars()['CC'])
            if _is_apple_clang(ccomp):
                ccomp = _find_homebrew_gcc()
                if ccomp is None:
                    raise RuntimeError(f"NCEPLIBS-ip is from Homebrew. Must build iplib extension module with Homebrew GCC.")
                else:
                    print(f"NCEPLIBS-ip is from Homebrew. grib2io will use compiler from Homebrew: {ccomp}")
                    os.environ['CC'] = ccomp
        
        # Note that both GNU and Intel support this flag.
        extmod_config['iplib']['define_macros'].append(('IPLIB_WITH_OPENMP', None))
        extmod_config['iplib']['extra_compile_args'] = ['-fopenmp']
        extmod_config['iplib']['extra_link_args'] = ['-fopenmp']

    # Further modifications if linking statically to ip.
    if ip_static:
        if ftn_libname is None:
            pass
        else:
            pkginfo = get_package_info(ftn_libname, static=ip_static, required=False)
            extmod_config['iplib']['libraries'].append(pkginfo[0])
            extmod_config['iplib']['libdirs'].append(pkginfo[2])

        # Need to know if OpenMP support is needed for BLAS/LAPACK, specifically Intel.
        stuff = check_ip_for_bla(ip_libname, static=ip_static, openmp=build_with_openmp)
        extmod_config['iplib']['libraries'].extend(stuff[0]) # Multiple libs...
        extmod_config['iplib']['libdirs'].append(stuff[1])

    # Finally, add the numpy include.
    extmod_config['iplib']['incdirs'].append(numpy.get_include())

# ----------------------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------------------
print(f'Build with NCEPLIBS-g2c static library: {g2c_static}')
print(f'Build with NCEPLIBS-ip: {build_with_ip}')
print(f'Build with NCEPLIBS-ip static library: {ip_static}')
print(f'Needs OpenMP: {build_with_openmp}')
for n, c in extmod_config.items():
    print(f'Extension module name: {n}')
    for k, v in c.items():
        if k == 'extra_objects':
            all_extra_objects.extend(v)
        print(f'\t{k}: {v}')

# ----------------------------------------------------------------------------------------
# Create extension objects.
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

# ----------------------------------------------------------------------------------------
# Create extension object for iplib.
# ----------------------------------------------------------------------------------------
if build_with_ip:
    iplibext = Extension('grib2io.iplib',
                         [iplib_pyx],
                         include_dirs = ['./src/ext']+extmod_config['iplib']['incdirs'],
                         library_dirs = extmod_config['iplib']['libdirs'],
                         libraries = extmod_config['iplib']['libraries'],
                         runtime_library_dirs = extmod_config['iplib']['libdirs'],
                         extra_objects = extmod_config['iplib']['extra_objects'],
                         extra_compile_args = extmod_config['iplib']['extra_compile_args'],
                         extra_link_args = extmod_config['iplib']['extra_link_args'],
                         define_macros = extmod_config['iplib']['define_macros'])
    extension_modules.append(iplibext)

# ----------------------------------------------------------------------------------------
# Create __config__.py
# ----------------------------------------------------------------------------------------
cnt = \
"""# This file is generated by grib2io's setup.py
# It contains configuration information when building this package.
grib2io_version = '%(grib2io_version)s'
g2c_static = %(g2c_static)s
has_interpolation = %(has_interpolation)s
ip_static = %(ip_static)s
has_openmp_support = %(has_openmp_support)s
extra_objects = %(extra_objects)s
"""
a = open('src/grib2io/__config__.py','w')
cfgdict = {}
cfgdict['grib2io_version'] = VERSION
cfgdict['g2c_static'] = g2c_static
cfgdict['has_interpolation'] = build_with_ip
cfgdict['ip_static'] = ip_static
cfgdict['has_openmp_support'] = build_with_openmp
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
