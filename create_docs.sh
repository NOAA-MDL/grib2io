#!/bin/sh
# ---------------------------------------------------------------------------------------- 
# Uses real pdoc (https://github.com/mitmproxy/pdoc)
#
# pip install pdoc
# ---------------------------------------------------------------------------------------- 
BUILD_LIB=$(find . -name "lib*" -type d)
pdoc --docformat numpy -o 'docs' $BUILD_LIB/grib2io 
