# grib2io

[![Build Status](https://travis-ci.com/eengl/grib2io.svg?branch=master)](https://travis-ci.com/eengl/grib2io)
[![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-360/)
[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![PyPI version](https://badge.fury.io/py/grib2io.svg)](https://badge.fury.io/py/grib2io)

## Introduction

grib2io provides a Python interface to the [NCEP GRIB2 C library](https://github.com/NOAA-EMC/NCEPLIBS-g2c) for reading and writing GRIB2 files.  The World Meteorological Organization ([WMO](https://www.wmo.int)) **GRI**dded **B**inary, Edition **2** ([GRIB2](https://www.wmo.int/pages/prog/www/WMOCodes/Guides/GRIB/GRIB2_062006.pdf)) is a table-driven, binary data format designed for transmitting large volumes of gridded meteorological data.

Initially this project was forked from [pygrib](https://github.com/jswhit/pygrib) which provides interfaces to the ECMWF (via module pygrib) and NCEP GRIB2 (via module ncepgrib2) libraries.  The motivation for grib2io is to bring together the best ideas from pygrib and ncepgrib2 together while being dependent only on the NCEP GRIB2 C library.

**IMPORTANT:** As of [pygrib v2.1](https://github.com/jswhit/pygrib/releases/tag/v2.1rel), module ncepgrib2 has been ***removed*** from the pygrib project and is no longer being actively developed.

grib2io leverages the [NCEP GRIB2 Tables](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/).  The GRIB2 tables have been converted into Python dictionaries and functions provided to fetch a given table and return values from it.

## Requirements
* Python 3.6+
* setuptools 34.0+
* NumPy 1.12+
* pyproj 1.9.6+
* C Compiler (GNU or Intel recommended)
* Compression libraries: [zlib](https://zlib.net), [jasper](https://github.com/jasper-software/jasper), [libpng](http://libpng.org)

GRIB2 has the ability to compress data using JPEG (via [Jasper](https://github.com/jasper-software/jasper)) or [PNG](https://sourceforge.net/projects/libpng/) compression.  Most \*NIX systems provide these libraries through their respective package management systems.  On macOS, please use [homebrew](https://brew.sh) to install all required compression libraries.

For macOS, please install GNU compilers via homebrew.  The NCEP G2 C Library will not install using Apple's LLVM clang.

## Installation

```shell
pip3 install grib2io
```
On macOS, please prepend the pip3 with setting `CC` to the full path to GNU C compiler (i.e. gcc).  If gcc has been installed via [homebrew](https://brew.sh), the gcc compiler name will have the major version appended (e.g. `/usr/local/bin/gcc-10`).

```shell
CC=/path/to/gcc pip3 install grib2io
```

### Build from Source

* Clone GitHub repository or download a source release from GitHub or [PyPI](https://pypi.python.org/pypi/grib2io).

* Copy `setup.cfg.template` to `setup.cfg`, open in text editor, follow instructions in comments for editing.

* Build

```shell
python3 setup.py build
```

* Install

```shell
[sudo] python3 setup.py install [--user | --prefix=PREFIX]
```

### Optional: GitPod
For an even easier way to begin developing with grib2io, you can use the included Gitpod configuration file.
You can quickly get started by doing one of the following:
- Fork the repository and open it as a new project in the [Gitpod](https://gitpod.io/) dashboard.
- Or...open the repo directly by adding the Gitpod url prefix `gitpod.io/#` to the beginning of the project URL like so: [gitpod.io/#https://github.com/eengl/grib2io](gitpod.io/#https://github.com/eengl/grib2io).

Gitpod will spin up a new throw-away containerized development environment just for you with all of required dependencies already installed, then launch Visual Studio Code in your browser...You're Ready to Code!

Best of all, Gitpod is **free** for up to 50hrs per month!

Learn more about Gitpod [here](https://gitpod.io) or take a look at their [FAQ](https://community.gitpod.io/faq)
