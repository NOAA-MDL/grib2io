#!/bin/sh
# ---------------------------------------------------------------------------------------- 
# Uses real pdoc (https://github.com/mitmproxy/pdoc), not pdoc3
#
# pip install pdoc
# ---------------------------------------------------------------------------------------- 

# Build in place
python setup.py build_ext --inplace

# Build docs
PYTHONPATH=$PWD/src pdoc --docformat numpy -o docs grib2io 

# Clean up
find src/grib2io -name "*.so" -delete
find src/grib2io -name "*.pyd" -delete
find src/grib2io -name "*.pyc" -delete
find src/grib2io -name "__pycache__" -type d -exec rm -r {} +
