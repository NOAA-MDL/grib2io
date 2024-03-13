# grib2io

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Python 3.11](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

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

## Documentation
* [API documentation](https://noaa-mdl.github.io/grib2io/grib2io.html)
* [User Guide Jupyter Notebook](https://github.com/NOAA-MDL/grib2io/blob/master/grib2io-v2-demo.ipynb)

## Required Software
* [Python](https://python.org) 3.8+
* [NCEPLIBS-g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) 1.7.0+
* setuptools 34.0+
* NumPy 1.22+
* pyproj 1.9.6+
* C compiler: GNU, Intel, and Apple Clang have been tested.

## Optional Software
* [grib2io-interp](https://github.com/NOAA-MDL/grib2io-interp) 1.0.0+ - Provides ability to perform spatial interpolation via the [NCEPLIBS-ip](https://github.com/NOAA-EMC/NCEPLIBS-ip)

## Required External Libraries

### NCEPLIBS-g2c
The [NCEPLIBS-g2c](https://github.com/NOAA-EMC/NCEPLIBS-g2c) library is required for grib2io.  You will have to build and install this yourself, but this is not difficult.  For macOS users, NCEPLIBS-g2c can be installed via [this Homebrew Tap](https://github.com/eengl/homebrew-nceplibs).  If you use the Anaconda ecosystem, then you can install via `conda install -c conda-forge nceplibs-g2c`.

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
> The default behavior for building grib2io is to build against shared-object libraries.  However, in production environments, it is beneficial to build against static library files.  grib2io (v2.2.0+) allows for this type of build configuration.  To build against static library files, set the environment variable, `USE_STATIC_LIBS="True"` before your build/install command.  For example,
> 
>```shell
>export USE_STATIC_LIBS="True"
>pip install .
>```

## Development

The intention of grib2io is to become the offical Python interface for the NCEP g2c library.  Therefore, the development evolution of grib2io will mainly focus on how best to serve that purpose and its primary users -- mainly meteorologists, physical scientists, and software developers supporting the missions within NOAA's National Weather Service (NWS) and National Centers for Environmental Prediction (NCEP), and other NOAA organizations.

## Disclaimer

This repository is a scientific product and is not official communication of the National Oceanic and Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project code is provided on an 'as is' basis and the user assumes responsibility for its use. Any claims against the Department of Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed by all applicable Federal law. Any reference to specific commercial products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by DOC or the United States Government.
