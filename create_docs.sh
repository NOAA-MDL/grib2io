#!/bin/sh
# ---------------------------------------------------------------------------------------- 
# Uses real pdoc (https://github.com/mitmproxy/pdoc)
#
# pip install pdoc
# ---------------------------------------------------------------------------------------- 
sysarch=$(uname -m)
build_dir=$(find . -name "lib.*${sysarch}*" -type d)
echo "Building docs from: $build_dir"
pdoc --docformat numpy -o 'docs' $build_dir/grib2io
