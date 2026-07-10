import grib2io


def test_iter_messages_read():
    if grib2io.has_interpolation:
        if grib2io.has_openmp_support:
            try:
                from grib2io import iplib
            except ImportError:
                import pytest

                pytest.skip("iplib is available but could not be dynamically loaded/linked (symbol not found).")
                return

            nthreads = 2
            iplib.openmp_set_num_threads(nthreads)
            assert iplib.openmp_get_num_threads() == nthreads
            nthreads = 1
            iplib.openmp_set_num_threads(nthreads)
            assert iplib.openmp_get_num_threads() == nthreads
        else:
            print("grib2io was built with support for NCEPLIBS-ip, but not OpenMP.")
    else:
        print("grib2io was not build with support for NCEPLIBS-ip.")
