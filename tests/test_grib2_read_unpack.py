#!/usr/bin/env python3

import glob
import sysconfig
import sys

def get_build_libdir():
    f = 'lib.{A}-{B}'
    return f.format(A=sysconfig.get_platform(),
                    B=sys.implementation.cache_tag)

if __name__  == '__main__':
    import glob
    sys.path.insert(0,'../build/'+get_build_libdir())
    import grib2io
    print(grib2io.show_config())
    g = grib2io.open('./data/gfs.t00z.pgrb2.1p00.f024')
    for msg in g:
        print(msg)
        msg.data
    g.close()
