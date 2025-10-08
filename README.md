# grib2io

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)

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

## Required Software
* [Python](https://python.org) 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
* [NCEPLIBS-g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) 1.7.0+
* setuptools 34.0+
* Cython 3.0+
* NumPy 1.22+
* pyproj 1.9.6+
* C compiler: GNU, Intel, and Apple Clang have been tested.

## Required External Libraries

### NCEPLIBS-g2c
The [NCEPLIBS-g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) library is required for grib2io.  You will have to build and install this yourself, but this is not difficult.  For macOS users, NCEPLIBS-g2c can be installed via [this Homebrew Tap](https://github.com/eengl/homebrew-nceplibs).  If you use the *conda ecosystems, then you can install via `conda install -c conda-forge nceplibs-g2c`.

## Optional External Libraries

### NCEPLIBS-ip (v5.1.0 or newer)
The [NCEPLIBS-ip](https://github.com/NOAA-EMC/NCEPLIBS-ip) Fortran library provides interpolation support.  You will have to build and install this yourself, but this is not difficult.  For macOS users, NCEPLIBS-ip can be installed via [this Homebrew Tap](https://github.com/eengl/homebrew-nceplibs).  If you use the *conda ecosystems, then you can install via `conda install -c conda-forge nceplibs-ip`.

## Install

Once again, this assumes that NCEPLIBS-g2c has been installed.  If NCEPLIBS-g2c has been installed into a "common" installation path, then it will be found, otherwise define environment variable `G2C_DIR` with the installation path.

* From [PyPI](https://pypi.python.org/pypi/grib2io) via pip:

```
pip install grib2io
```
* From [conda-forge](https://anaconda.org/conda-forge/grib2io) via conda:

```
conda install -c conda-forge grib2io
```

* From source:
```shell
pip install .
```

> [!NOTE]
> ### Building with static libraries
> **_It is recommended to not build with static libraries, but in NOAA HPC production environments, this is preferred._**  Beginning with grib2io v2.4.0, the process to build with static libs as changed.  The environment variable, `USE_STATIC_LIBS` has been removed and replaced with library-specific env vars, `G2C_STATIC` and `IP_STATIC` with acceptable values of `True` or `False`.  The default value is `False` (i.e. build with shared libs).  If statically linking to NCEPLIBS-ip, then provide the path to of the BLAS/LAPACK library via env var `BLA_DIR`. 
> 
>```shell
>export G2C_STATIC=True
>export IP_STATIC=True
>export G2C_DIR=<path to g2c> # Optional
>export IP_DIR=<path to ip> # Optional
>export BLA_DIR=<path to BLAS/LAPACK used for ip> # Needed if IP_STATIC=True
>pip install .
>```

## Development

grib2io is the de facto Python interface to the NCEPLIBS-g2c library. Therefore, its development and evolution will primarily focus on serving that purpose and supporting its core users—mainly meteorologists, physical scientists, and software developers working within NOAA’s National Weather Service (NWS), the National Centers for Environmental Prediction (NCEP), and other NOAA and U.S. Government organizations.

## Disclaimer

This repository is a scientific product and is not official communication of the National Oceanic and Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project code is provided on an 'as is' basis and the user assumes responsibility for its use. Any claims against the Department of Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed by all applicable Federal law. Any reference to specific commercial products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by DOC or the United States Government.
