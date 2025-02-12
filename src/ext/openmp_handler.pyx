# cython: language_level=3, boundscheck=False
# distutils: define_macros=NPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION
"""
Cython code to provide python interfaces to the OpenMP library that is
being used by the NCEPLIBS-ip library.

IMPORTANT: Make changes to this file, not the C code that Cython generates.
"""

from cython.parallel import prange
from libc.stdlib cimport malloc, free

cdef extern from "omp.h":
    int omp_get_max_threads()
    void omp_set_num_threads(int)
    int omp_get_num_threads()

def openmp_get_max_threads():
    """
    Returns the maximum number of OpenMP threads available.
    """
    return omp_get_max_threads()

def openmp_set_num_threads(int num):
    """
    Sets the number of OpenMP threads to be used.

    Parameters
    ----------
    num
        Number of OpenMP threads to set. 
    """
    omp_set_num_threads(num)

def openmp_get_num_threads():
    """
    Returns the number of threads in a parallel region.
    """
    cdef int num_threads = 1  # Default to 1 (if not in parallel region)
    
    # Parallel block with temporary memory to store thread count
    cdef int *num_threads_ptr = <int*>malloc(sizeof(int))
    if num_threads_ptr == NULL:
        raise MemoryError("Failed to allocate memory for thread count.")
    
    num_threads_ptr[0] = 0  # Initialize

    cdef int i
    with nogil:
        for i in prange(1):  # Start parallel region
            # Acquire GIL before calling omp_get_num_threads
            with gil:
                num_threads_ptr[0] = omp_get_num_threads()

    num_threads = num_threads_ptr[0]
    free(num_threads_ptr)  # Clean up

    return num_threads
