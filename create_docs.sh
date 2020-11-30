#!/bin/sh
set -x

python3 setup.py build

unset PYTHONPATH
BUILD_DIR=$(find $PWD/build -mindepth 1 -name "lib.*" -type d)
export PYTHONPATH=$BUILD_DIR:$PYTHONPATH
pdoc --html -c show_source_code=True --force --output-dir 'docs' grib2io
