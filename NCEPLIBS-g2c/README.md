
# NCEPLIBS-g2c

This library contains C decoder/encoder routines for GRIB edition 2.

This is related to the
[NCEPLIBS](https://github.com/NOAA-EMC/NCEPLIBS) project.

For complete documentation see
https://noaa-emc.github.io/NCEPLIBS-g2c/. For the NCEP WMO GRIB2
Documentation see
https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/.

## Authors

Stephen Gilbert, Wesley Ebisuzaki, Boi Vuong

Code Manager: Hang Lei, Edward Hartnett

## Prerequisites

- [libjasper.a](http://www.ece.uvic.ca/~mdadams/jasper/) - This
  library is a C implementation of the JPEG-2000 Part-1 standard
  (i.e., ISO/IEC 15444-1). Tested version: jasper-1.900.1. More
  information about JPEG2000 can be found at
  http://www.jpeg.org/JPEG2000.html.

- [libpng.a](http://www.libpng.org/pub/png/libpng.html) - This library
  is a C implementation of the Portable Network Graphics PNG image
  compression format. Tested version: libpng-1.2.44. More information
  about PNG can be found at http://www.libpng.org/pub/png/.

- [libz.a](http://www.gzip.org/zlib/) - This library contains
  compression/decompression routines used by libpng.a for PNG image
  compression support. Tested version: zlib-1.2.6.

- [openjpeg.a](https://www.openjpeg.org/) - OpenJPEG is an open-source
  JPEG 2000 codec written in C language. OpenJPEG is only used if
  CMake build option USE_OpenJPEG is turned on.

## Installing

This C source code conatins many uses of the C++ comment style "//".
Please make sure you include the appropriate compiler option in the
CFLAGS variable in the makefile to allow the use of "//" comment
indicators.

We have added support for PNG and JPEG2000 image compression
algorithms within the GRIB2 standard. You will need to download and
install the external libraries listed above, if they are not already
installed on your system.

If you do not wish to bother with the external libs and don't need PNG
and JPEG2000 support, you can use the CMake options USE_PNG,
USE_Jasper, and USE_OpenJPEG.

## References

Kumar, V. Krishna, Gilbert, Stephen A., [GRIB2 conversion and its
usage at NCEP](docs/GRIB2_conversion_and_its_usage_at_NCEP.pdf), 14-18
November 2005, 10th Workshop on Meteorological Operational Systems
ECMWF User Orientation, retrieved on July 27, 2021 from
https://www.yumpu.com/en/document/view/11925806/grib2-conversion-and-its-usage-at-ncep.

## Disclaimer

The United States Department of Commerce (DOC) GitHub project code is
provided on an "as is" basis and the user assumes responsibility for
its use. DOC has relinquished control of the information and no longer
has responsibility to protect the integrity, confidentiality, or
availability of the information. Any claims against the Department of
Commerce stemming from the use of its GitHub project will be governed
by all applicable Federal law. Any reference to specific commercial
products, processes, or services by service mark, trademark,
manufacturer, or otherwise, does not constitute or imply their
endorsement, recommendation or favoring by the Department of
Commerce. The Department of Commerce seal and logo, or the seal and
logo of a DOC bureau, shall not be used in any manner to imply
endorsement of any commercial product or activity by DOC or the United
States Government.
