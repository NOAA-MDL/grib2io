#!/usr/bin/env python3

import numpy as np
import setuptools
import sys

platform = setuptools.distutils.util.get_platform()
build_path = './build/lib.'+platform+'-'+str(sys.version_info.major)+'.'+str(sys.version_info.minor)
sys.path.insert(0,build_path)

import grib2io
import glob

for f in sorted(glob.glob('./data/*.grib2')):

    g2file = grib2io.open(f)

    for msg in g2file:

        msg.data()

    g2file.close()
