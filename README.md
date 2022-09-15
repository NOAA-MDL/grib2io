# grib2io

[![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-360/)
[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![PyPI version](https://badge.fury.io/py/grib2io.svg)](https://badge.fury.io/py/grib2io)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/eengl/grib2io/HEAD)

## Introduction

grib2io provides a Python interface to the [NCEP GRIB2 C library](https://github.com/NOAA-EMC/NCEPLIBS-g2c) for reading and writing GRIB2 files.  The World Meteorological Organization ([WMO](https://www.wmo.int)) **GRI**dded **B**inary, Edition **2** ([GRIB2](https://www.wmo.int/pages/prog/www/WMOCodes/Guides/GRIB/GRIB2_062006.pdf)) is a table-driven, binary data format designed for transmitting large volumes of gridded meteorological and atmospheric data.

grib2io is the successor to [ncepgrib2](https://github.com/jswhit/ncepgrib2) which **_was_** a module within [pygrib](https://github.com/jswhit/pygrib).  As of pygrib v2.1, development of ncepgrib2 was dropped in favor of continued development of the pygrib module which provides an interface to the ECMWF [ecCodes](https://github.com/ecmwf/eccodes) library.  grib2io aims to provide a fast, efficient, and easy-to-use interface to the NCEP g2c library.  One way to accomplish this is to leverage the [NCEP GRIB2 Tables](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/) which are included in grib2io.  With these [tables](./grib2io/tables) included and functions interact with them, grib2io provides a translation of GRIB2's integer coded metadata to human-readable language.

## Required Software
* [NCEP g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) 1.7.0+
* Python 3.6+
* setuptools 34.0+
* NumPy 1.12+
* pyproj 1.9.6+
* C Compiler: GCC, Intel, and Apple Clang have been tested.

### NCEP g2c Library

Beginning with grib2io v1.1.0, the [NCEP g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) library is no longer bundled with grib2io.  Instead, grib2io will link to an external installation of g2c, which as of v1.7.0, includes the ability to build shared-object library files.  Therefore, the previous "optional" compression software is no longer needed to build grib2io.  The caveat to this is you are at the mercy of how g2c was built.  For macOS users, NCEP g2c can be installed via [this Homebrew Tap](https://github.com/eengl/homebrew-nceplibs).


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

* Copy `setup.cfg.template` to `setup.cfg`, open in text editor, follow instructions in comments for editing **_OR_** in your shell environment, define the g2c installation path, `G2C_DIR`.

* Build and install.  Use `--user` to install into personal space (`$HOME/.local`).

```shell
python setup.py build
python setup.py install
```
OR
```shell
pip install .
```

## Development

The intention of grib2io is to become the offical Python interface for the NCEP g2c library.  Therefore, the development evolution of grib2io will mainly focus on how best to serve that purpose and its primary user's -- mainly meteorologist, physical scientists, and software developers supporting the missions within NOAA's National Weather Service (NWS) and National Centers for Environmental Prediction (NCEP).
