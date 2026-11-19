# grib2io

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
[![Python 3.15](https://img.shields.io/badge/python-3.15-blue.svg)](https://www.python.org/downloads/release/python-3150/)

![Build Linux](https://github.com/NOAA-MDL/grib2io/actions/workflows/build_linux.yml/badge.svg)
![Build macOS](https://github.com/NOAA-MDL/grib2io/actions/workflows/build_macos.yml/badge.svg)

![PyPI](https://img.shields.io/pypi/v/grib2io?label=pypi%20package)
![PyPI - Downloads](https://img.shields.io/pypi/dm/grib2io)

[![Anaconda-Server Badge](https://anaconda.org/conda-forge/grib2io/badges/version.svg)](https://anaconda.org/conda-forge/grib2io)
[![Anaconda-Server Badge](https://anaconda.org/conda-forge/grib2io/badges/platforms.svg)](https://anaconda.org/conda-forge/grib2io)
[![Anaconda-Server Badge](https://anaconda.org/conda-forge/grib2io/badges/downloads.svg)](https://anaconda.org/conda-forge/grib2io)

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/NOAA-MDL/grib2io/HEAD)

## Introduction

grib2io provides a Python interface to the [NCEP GRIB2 C library](https://github.com/NOAA-EMC/NCEPLIBS-g2c) for reading and writing GRIB2 files.  The World Meteorological Organization ([WMO](https://www.wmo.int)) **GRI**dded **B**inary, Edition **2** ([GRIB2](https://www.wmo.int/pages/prog/www/WMOCodes/Guides/GRIB/GRIB2_062006.pdf)) is a table-driven, binary data format designed for transmitting large volumes of gridded meteorological and atmospheric data.

grib2io is the successor to [ncepgrib2](https://github.com/jswhit/ncepgrib2) which **_was_** a module within [pygrib](https://github.com/jswhit/pygrib).  As of pygrib v2.1, development of ncepgrib2 was dropped in favor of continued development of the pygrib module which provides an interface to the ECMWF [ecCodes](https://github.com/ecmwf/eccodes) library.  grib2io aims to provide a fast, efficient, and easy-to-use interface to the NCEP g2c library.  One way to accomplish this is to leverage the [NCEP GRIB2 Tables](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/) which are included in grib2io.  With these [tables](./grib2io/tables) included and functions interact with them, grib2io provides a translation of GRIB2's integer coded metadata to human-readable language.

Optionally (but recommended), grib2io supports spatial interpolation via its internal Cython extension module, `iplib`, which provides an interface to the Fortran-based [NCEPLIBS-ip](https://github.com/NOAA-EMC/NCEPLIBS-ip).  Grid to grid and grid to station points are supported with OpenMP threading, provided that NCEPLIBS-ip was built with OpenMP support.

> [!IMPORTANT]
> **Beginning with grib2io v2.4.0, grib2io-interp component package is no longer supported.  Interpolation support is available in grib2io via Cython interface to [NCEPLIBS-ip](https://github.com/NOAA-EMC/NCEPLIBS-ip).**

## Documentation
* [API documentation](https://noaa-mdl.github.io/grib2io/grib2io.html)
* [User Guide Jupyter Notebook](https://github.com/NOAA-MDL/grib2io/blob/master/demos/grib2io-v2.ipynb)

## Install

Install from PyPI with pip or add grib2io to a uv project:

```shell
python -m pip install grib2io
uv add grib2io
```

When a compatible wheel is available, it supplies NCEPLIBS-g2c and supports
JPEG2000, PNG, and AEC compression. A compiler, system NCEPLIBS-g2c installation,
and NCEPLIBS-ip installation are unnecessary for wheel users. Interpolation is
available through a source build with NCEPLIBS-ip.

The [wheel workflow](https://github.com/NOAA-MDL/grib2io/actions/workflows/build_wheels.yml)
lists verified artifacts by operating system, architecture, and Python version.
The [PyPI files list](https://pypi.org/project/grib2io/#files) shows which wheels
are available for a published version.

Conda users can install from conda-forge:

```shell
conda install -c conda-forge grib2io
```

### Build from source

A source build requires a C compiler, CMake 3.18 or newer, and
[NCEPLIBS-g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) 1.7.0 or newer with
headers. The Python build backend installs Cython and NumPy in the isolated
build environment. Install g2c from source, from the
[Homebrew tap](https://github.com/eengl/homebrew-nceplibs) on macOS, or with
`conda install -c conda-forge nceplibs-g2c`.

From a checkout, run either command:

```shell
python -m pip install .
uv pip install .
```

For a custom g2c installation, point `G2C_DIR` at its prefix. Alternatively,
set `G2C_INCDIR` and `G2C_LIBDIR` directly.

### Enable interpolation

To include interpolation, install the double-precision (`ip_d`) library and
headers from [NCEPLIBS-ip](https://github.com/NOAA-EMC/NCEPLIBS-ip) 5.1.0 or newer
before building grib2io. Set `IP_DIR` to its prefix if it is outside the
standard search paths, or set `IP_INCDIR` and `IP_LIBDIR` directly. The source
build includes interpolation when it finds both the library and header. It
builds core GRIB2 support when either is missing.

To disable interpolation explicitly, pass the CMake setting to the installer:

```shell
python -m pip install . --config-settings=cmake.define.GRIB2IO_WITH_IP=OFF
uv pip install . --config-settings=cmake.define.GRIB2IO_WITH_IP=OFF
```

Check the installed package with
`python -c "import grib2io; grib2io.show_config()"`.

### Build with static libraries

The source build looks for shared libraries by default. Set `G2C_STATIC=True`
or `IP_STATIC=True` to select static libraries for an environment that requires
them. Static interpolation also requires a compatible Fortran toolchain and
the link dependencies of the supplied IP library.

## Development

grib2io is the de facto Python interface to the NCEPLIBS-g2c library. Therefore, its development and evolution will primarily focus on serving that purpose and supporting its core users—mainly meteorologists, physical scientists, and software developers working within NOAA’s National Weather Service (NWS), the National Centers for Environmental Prediction (NCEP), and other NOAA and U.S. Government organizations.

## Disclaimer

This repository is a scientific product and is not official communication of the National Oceanic and Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project code is provided on an 'as is' basis and the user assumes responsibility for its use. Any claims against the Department of Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed by all applicable Federal law. Any reference to specific commercial products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by DOC or the United States Government.

Generative AI tools are used to assist with developing this code. The code has been reviewed, edited, and validated by NWS staff.
