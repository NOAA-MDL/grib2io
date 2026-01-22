import grib2io
import pytest

def test_iter_messages_read():
    if grib2io.has_interpolation:
        if grib2io.has_openmp_support:
            from grib2io import iplib
            nthreads = 2
            iplib.openmp_set_num_threads(nthreads)
            assert iplib.openmp_get_num_threads() == nthreads
            nthreads = 1
            iplib.openmp_set_num_threads(nthreads)
            assert iplib.openmp_get_num_threads() == nthreads
        else:
            print(f"grib2io was built with support for NCEPLIBS-ip, but not OpenMP.")
    else:
        print(f"grib2io was not build with support for NCEPLIBS-ip.")
