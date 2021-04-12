#!/bin/sh
#set -x

# ---------------------------------------------------------------------------------------- 
# Uses pdoc (https://github.com/mitmproxy/pdoc)
# ---------------------------------------------------------------------------------------- 

libdir=$(find $PWD/build -name "lib*$(uname -m)*" -type d)
pdoc -o 'docs' $libdir/grib2io/*
