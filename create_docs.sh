#!/bin/sh
# ---------------------------------------------------------------------------------------- 
# Uses pdoc (https://github.com/mitmproxy/pdoc)
# ---------------------------------------------------------------------------------------- 
sysarch=$(uname -m)
build_dir=$(find . -name "lib.*${sysarch}*" -type d)
echo "Building docs from: $build_dir"
pdoc --show-source -o 'docs' $build_dir/grib2io
