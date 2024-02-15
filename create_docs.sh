#!/bin/sh
# ---------------------------------------------------------------------------------------- 
# Uses real pdoc (https://github.com/mitmproxy/pdoc)
#
# pip install pdoc
# ---------------------------------------------------------------------------------------- 
pdoc --docformat numpy -o 'docs' ./src/grib2io
