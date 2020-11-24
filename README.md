# grib2io

[![Build Status](https://travis-ci.com/eengl/grib2io.svg?branch=master)](https://travis-ci.com/eengl/grib2io)

grib2io is a Python package for reading and writing GRIB2 files (WMO GRIdded Binary, Edition 2), leveraging the NCEP GRIB2 C library.  This is a fork of the ncepgrib2 module of [pygrib](https://github.com/jswhit/pygrib), but functionally, grib2io behaves more like the pygrib module.

Provided with this package are the [NCEP GRIB2 Tables](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/) in Python dictionary form.  Functions are provided to return strings that represent a given GRIB2 code table value.  It is the intention to add tables from other meteorological centers in the future.

Quickstart:

* Clone the github repository, or download a source release from https://pypi.python.org/pypi/grib2io. **NOT YET**

* Copy setup.cfg.template to setup.cfg, open in text editor, follow instructions in
comments for editing.

* Run 'python setup.py build'

* Run 'python setup.py install' (with sudo if necessary)

* Run 'python test.py' to test your grib2io installation.

For full installation instructions and API documentation, __INSERT URL HERE__

Questions or comments - contact __INSERT CONTACT INFO__
