# grib2io

[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PyPI version](https://badge.fury.io/py/grib2io.svg)](https://badge.fury.io/py/grib2io)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/eengl/grib2io/HEAD)

## Introduction

grib2io provides a Python interface to the [NCEP GRIB2 C library](https://github.com/NOAA-EMC/NCEPLIBS-g2c) for reading and writing GRIB2 files.  The World Meteorological Organization ([WMO](https://www.wmo.int)) **GRI**dded **B**inary, Edition **2** ([GRIB2](https://www.wmo.int/pages/prog/www/WMOCodes/Guides/GRIB/GRIB2_062006.pdf)) is a table-driven, binary data format designed for transmitting large volumes of gridded meteorological and atmospheric data.

grib2io is the successor to [ncepgrib2](https://github.com/jswhit/ncepgrib2) which **_was_** a module within [pygrib](https://github.com/jswhit/pygrib).  As of pygrib v2.1, development of ncepgrib2 was dropped in favor of continued development of the pygrib module which provides an interface to the ECMWF [ecCodes](https://github.com/ecmwf/eccodes) library.  grib2io aims to provide a fast, efficient, and easy-to-use interface to the NCEP g2c library.  One way to accomplish this is to leverage the [NCEP GRIB2 Tables](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/) which are included in grib2io.  With these [tables](./grib2io/tables) included and functions interact with them, grib2io provides a translation of GRIB2's integer coded metadata to human-readable language.

## Documentation
[NOAA-MDL/grib2io](https://noaa-mdl.github.io/grib2io/grib2io.html)

## Required Software
* Python 3.8+
* [NCEPLIBS-g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) 1.7.0+
* [NCEPLIBS-sp](https://github.com/NOAA-EMC/NCEPLIBS-sp) 2.4.0+ _(required for interpolation)_
* [NCEPLIBS-ip](https://github.com/NOAA-EMC/NCEPLIBS-ip) 4.1.0+ _(required for interpolation)_
* setuptools 34.0+
* NumPy 1.22+
* pyproj 1.9.6+
* C and Fortran Compiler: GNU, Intel, and Apple Clang have been tested.

## NCEPLIBS Libraries

### g2c
Beginning with grib2io v1.1.0, the [NCEPLIBS-g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) library is no longer bundled with grib2io.  Instead, grib2io will link to an external installation of g2c, which as of v1.7.0, includes the ability to build shared-object library files.  Therefore, the previous "optional" compression software is no longer needed to build grib2io.  The caveat to this is you are at the mercy of how g2c was built.  For macOS users, NCEPLIBS-g2c can be installed via [this Homebrew Tap](https://github.com/eengl/homebrew-nceplibs).

### sp and ip
The NCEP Spectral Interpolation (NCEPLIBS-sp) library is a dependency for the NCEP Interpolation (NCEPLIBS-ip) library.  Both of these libraries are Fortran-based and contains OpenMP directives.

## Installation

For system installations:
```shell
sudo pip install grib2io
```
For user installations:
```shell
pip install grib2io --user
```

## Build and Install from Source

* Clone GitHub repository or download a source release from [GitHub](https://github.com/NOAA-MDL/grib2io) or [PyPI](https://pypi.python.org/pypi/grib2io).

* Edit `setup.cfg` to define the g2c, sp, and ip library installation paths __OR__ define `G2C_DIR`, `SP_DIR`, and `IP_DIR` environment variables.

* Build and install.  Use `--user` to install into personal space (`$HOME/.local`).

```shell
python setup.py build --fcompiler=[gnu95|intelem] # GNU or Intel compilers
python setup.py install
```
OR
```shell
pip install . --global-option="build" --global-option="--fcompiler=[gnu95|intelem]"
```

## Development

The intention of grib2io is to become the offical Python interface for the NCEP g2c library.  Therefore, the development evolution of grib2io will mainly focus on how best to serve that purpose and its primary user's -- mainly meteorologist, physical scientists, and software developers supporting the missions within NOAA's National Weather Service (NWS) and National Centers for Environmental Prediction (NCEP).
