# cython: language_level=3, boundscheck=False
# distutils: define_macros=NPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION
"""
Cython code to provide python interfaces to functions in the NCEPLIBS-ip library.

IMPORTANT: Make changes to this file, not the C code that Cython generates.
"""

import cython
from cython.parallel import parallel, prange
from cython.cimports.openmp import omp_get_max_threads, omp_get_num_threads, omp_set_num_threads

from libc.stdint cimport uint8_t, int32_t
from libc.stdlib cimport malloc, free

import numpy as np
cimport numpy as cnp

import warnings

cdef extern from "<stdbool.h>":
    ctypedef int bool


cdef extern from "iplib.h":
    void gdswzd(int igdtnum, int *igdtmpl, int igdtlen, int iopt, int npts, float fill,
                float *xpts, float *ypts, float *rlon, float *rlat, int *nret, float *crot,
                float *srot, float *xlon, float *xlat, float *ylon, float *ylat, float *area)
    void ipolates_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni,
                        int *igdtnumo, int *igdtmplo, int *igdtleno,
                        int *mi, int *mo, int *km, int *ibi, bool *li, float *gi,
                        int *no, float *rlat, float *rlon, int *ibo, bool *lo, float *go, int *iret)
    void ipolatev_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni,
                        int *igdtnumo, int *igdtmplo, int *igdtleno,
                        int *mi, int *mo, int *km, int *ibi, bool *li, float *ui, float *vi,
                        int *no, float *rlat, float *rlon, float *crot, float *srot, int *ibo, bool *lo,
                        float *uo, float *vo, int *iret)
    void use_ncep_post_arakawa()
    void unuse_ncep_post_arakawa()


def interpolate_scalar(int ip,
                   cnp.ndarray[cnp.int32_t, ndim=1] ipopt,
                   int igdtnumi,
                   cnp.ndarray[cnp.int32_t, ndim=1] igdtmpli,
                   int igdtnumo,
                   cnp.ndarray[cnp.int32_t, ndim=1] igdtmplo,
                   int mi,
                   int mo,
                   int km,
                   cnp.ndarray[cnp.int32_t, ndim=1] ibi,
                   cnp.ndarray[cnp.uint8_t, ndim=2] li,
                   cnp.ndarray[cnp.float32_t, ndim=2] gi,
                   lats = None,
                   lons = None):
    """
    Cython function wrapper for NCEPLIBS-ip subroutine, ipolates_grib2, to perform
    interpolation for scalar fields.

    This function calls ipolates_grib2 via the C interface. Only
    horizontal interpolation is performed and OpenMP threading is
    supported through this function so long as NCEPLIBS-ip was
    built with OpenMP.

    Parameters
    ----------
    ip
        Interpolation method
    ipopt
        Interpolation options
    igdtnumi
        Grid definition template number for the input grid.
    igdtmpli
        Grid definition template array input grid.
    igdtnumo
        Grid definition template number for the output grid. Note: igdtnumo<0
        means interpolate to random station points.
    igdtmplo
        Grid definition template array for the output grid.
    mi
        Skip number between input grid fields if km>1 or dimension of input grid fields if km=1.
    mo
        Skip number between output grid fields if km>1 or dimension of output grid fields if km=1.
    km
        Number of fields to interpolate.
    ibi
        Input bitmap flags.
    li
        Input bitmaps (if respective ibi(k)=1).
    gi
        Input fields to interpolate.
    lats
        Optional 1D array of input station latitudes.
    lons
        Optional 1D array of input station longitudes.

    Returns
    -------
    no
        Number of output points (only if kgdso(1)<0).
    rlat
        Output latitudes in degrees (if kgdso(1)<0).
    rlon
        Output longitudes in degrees (if kgdso(1)<0).
    ibo
        Output bitmap flags.
    lo
        Output bitmaps (always output).
    go
        Output fields interpolated.
    iret
        Return code.
    """
    # Define output variables; allocate output arrays with correct types.
    cdef int no
    cdef cnp.ndarray[cnp.float32_t, ndim=1] rlat = np.zeros(mo, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] rlon = np.zeros(mo, dtype=np.float32)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ibo = np.zeros(km, dtype=np.int32)
    cdef cnp.ndarray[cnp.uint8_t, ndim=2] lo = np.zeros((mo, km), dtype=np.uint8)
    cdef cnp.ndarray[cnp.float32_t, ndim=2] go = np.zeros((mo, km), dtype=np.float32)
    cdef int iret

    # Get lengths of the input and output GRIB2 Grid Definition template arrays.
    cdef int igdtleni = igdtmpli.shape[0]
    cdef int igdtleno = igdtmplo.shape[0]
    cdef int i

    # Use memoryviews for direct C access to array data.
    cdef float *rlat_ptr = &rlat[0]
    cdef float *rlon_ptr = &rlon[0]
    cdef int32_t *ibo_ptr = &ibo[0]
    cdef uint8_t *lo_ptr = &lo[0,0]
    cdef float *go_ptr = &go[0,0]

    if lats is not None and lons is not None and igdtnumo == -1:
        for i in range(lats.shape[0]):
            rlon[i] = lons[i]
            rlat[i] = lats[i]

    # Call the Fortran scalar field interpolation subroutine.
    ipolates_grib2(&ip, <int *>&ipopt[0], &igdtnumi, <int *>&igdtmpli[0], &igdtleni,
                   &igdtnumo, <int *>&igdtmplo[0], &igdtleno,
                   &mi, &mo, &km, <int *>&ibi[0], <bool*>&li[0,0], &gi[0,0],
                   &no, rlat_ptr, rlon_ptr, <int *>ibo_ptr, <bool*>lo_ptr, go_ptr, &iret)

    return no, rlat, rlon, ibo, lo, go, iret


def interpolate_vector(int ip,
                   cnp.ndarray[cnp.int32_t, ndim=1] ipopt,
                   int igdtnumi,
                   cnp.ndarray[cnp.int32_t, ndim=1] igdtmpli,
                   int igdtnumo,
                   cnp.ndarray[cnp.int32_t, ndim=1] igdtmplo,
                   int mi,
                   int mo,
                   int km,
                   cnp.ndarray[cnp.int32_t, ndim=1] ibi,
                   cnp.ndarray[cnp.uint8_t, ndim=2] li,
                   cnp.ndarray[cnp.float32_t, ndim=2] ui,
                   cnp.ndarray[cnp.float32_t, ndim=2] vi,
                   lats = None,
                   lons = None):
    """
    Cython function wrapper for NCEPLIBS-ip subroutine, ipolatev_grib2, to perform
    interpolation for vector fields.

    This function calls ipolatev_grib2 via the C interface. Only
    horizontal interpolation is performed and OpenMP threading is
    supported through this function so long as NCEPLIBS-ip was
    built with OpenMP.

    Parameters
    ----------
    ip
        Interpolation method
    ipopt
        Interpolation options
    igdtnumi
        Grid definition template number for the input grid.
    igdtmpli
        Grid definition template array input grid.
    igdtnumo
        Grid definition template number for the output grid. Note: igdtnumo<0
        means interpolate to random station points.
    igdtmplo
        Grid definition template array for the output grid.
    mi
        Skip number between input grid fields if km>1 or dimension of input grid fields if km=1.
    mo
        Skip number between output grid fields if km>1 or dimension of output grid fields if km=1.
    km
        Number of fields to interpolate.
    ibi
        Input bitmap flags.
    li
        Input bitmaps (if respective ibi(k)=1).
    ui
        Input u-component fields to interpolate.
    vi
        Input v-component fields to interpolate.
    lats
        Optional 1D array of input station latitudes.
    lons
        Optional 1D array of input station longitudes.

    Returns
    -------
    no
        Number of output points (only if kgdso(1)<0).
    rlat
        Output latitudes in degrees (if kgdso(1)<0).
    rlon
        Output longitudes in degrees (if kgdso(1)<0).
    crot
        Vector rotation cosines (if igdtnumo>=0).
    srot
        Vector rotation sines (if igdtnumo>=0).
    ibo
        Output bitmap flags.
    lo
        Output bitmaps (always output).
    uo
        Output u-component fields interpolated.
    vo
        Output v-component fields interpolated.
    iret
        Return code.
    """
    # Define output variables; allocate output arrays with correct types.
    cdef int no
    cdef cnp.ndarray[cnp.float32_t, ndim=1] rlat = np.zeros(mo, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] rlon = np.zeros(mo, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] crot = np.ones(mo, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] srot = np.zeros(mo, dtype=np.float32)
    cdef cnp.ndarray[cnp.int32_t, ndim=1] ibo = np.zeros(km, dtype=np.int32)
    cdef cnp.ndarray[cnp.uint8_t, ndim=2] lo = np.zeros((mo, km), dtype=np.uint8)
    cdef cnp.ndarray[cnp.float32_t, ndim=2] uo = np.zeros((mo, km), dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=2] vo = np.zeros((mo, km), dtype=np.float32)
    cdef int iret

    # Get lengths of the input and output GRIB2 Grid Definition template arrays.
    cdef int igdtleni = igdtmpli.shape[0]
    cdef int igdtleno = igdtmplo.shape[0]
    cdef int i

    # Use memoryviews for direct C access to array data.
    cdef float *rlat_ptr = &rlat[0]
    cdef float *rlon_ptr = &rlon[0]
    cdef float *crot_ptr = &crot[0]
    cdef float *srot_ptr = &srot[0]
    cdef int32_t *ibo_ptr = &ibo[0]
    cdef uint8_t *lo_ptr = &lo[0,0]
    cdef float *uo_ptr = &uo[0,0]
    cdef float *vo_ptr = &vo[0,0]

    if lats is not None and lons is not None and igdtnumo == -1:
        for i in range(lats.shape[0]):
            rlon[i] = lons[i]
            rlat[i] = lats[i]

    # Call the Fortran vector field interpolation subroutine.
    ipolatev_grib2(&ip, <int *>&ipopt[0], &igdtnumi, <int *>&igdtmpli[0], &igdtleni,
                   &igdtnumo, <int *>&igdtmplo[0], &igdtleno,
                   &mi, &mo, &km, <int *>&ibi[0], <bool*>&li[0,0], &ui[0,0], &vi[0,0],
                   &no, rlat_ptr, rlon_ptr, crot_ptr, srot_ptr, <int *>ibo_ptr, <bool*>lo_ptr,
                   uo_ptr, vo_ptr, &iret)

    return no, rlat, rlon, crot, srot, ibo, lo, uo, vo, iret


def set_ncep_post_arakawa_flag(bint flag):
    """
    """
    if flag:
        use_ncep_post_arakawa()
    else:
        unuse_ncep_post_arakawa()


def get_ncep_post_arakawa_flag():
    """
    """
    msg = f"Cannot get ncep_post_arakawa_flag from iplib. This will be supported in a future version."
    warnings.warn(msg)


#ifdef IPLIB_WITH_OPENMP
def openmp_get_max_threads():
    """
    Returns the maximum number of OpenMP threads available.
    """
    cdef int num_threads = 1
    with cython.nogil:
        for _ in prange(1):
            num_threads = omp_get_max_threads()
    return num_threads


def openmp_get_num_threads():
    """
    Returns the number of threads in a parallel region.
    """
    cdef int num_threads = 1
    with cython.nogil:
        for _ in prange(1):
            num_threads = omp_get_num_threads()
    return num_threads


def openmp_set_num_threads(int n):
    """
    Sets the number of OpenMP threads to be used.

    Parameters
    ----------
    num
        Number of OpenMP threads to set.
    """
    omp_set_num_threads(n)
#endif


def latlon_to_ij(
    int igdtnumi,
    cnp.ndarray[cnp.int32_t, ndim=1] igdtmpli,
    cnp.ndarray[cnp.float32_t, ndim=1] lats,
    cnp.ndarray[cnp.float32_t, ndim=1] lons,
    float missing_value = np.nan,
):
    """
    Convert latitude/longitude coordinates to grid (i, j) indices using the
    GRIB2 Grid Definition Section (GDS) and the NCEPLIBS-ip `gdswzd` subroutine.

    Parameters
    ----------
    igdtnumi : int
        GRIB2 grid definition template number.
    igdtmpli : ndarray of int32
        GRIB2 grid definition template values.
    lats : ndarray of float32
        Array of latitude coordinates in degrees.
    lons : ndarray of float32
        Array of longitude coordinates in degrees.
    missing_value : float, optional
        Missing value to represent when latitude/longitude coordinate is
        outside the grid domain.

    Returns
    -------
    xpts : ndarray of float32
        Grid x-coordinates (i-indices) corresponding to the input
        latitude/longitude points.
    ypts : ndarray of float32
        Grid y-coordinates (j-indices) corresponding to the input
        latitude/longitude points.

    Notes
    -----
    This function wraps the NCEPLIBS-ip `gdswzd` routine (accessed via a Fortran
    BIND(C) interface) to perform the forward transformation from geodetic
    coordinates (lat/lon) to grid-relative indices (i/j). The transformation
    adheres to the GRIB2 GDS template conventions used in NCEP operational
    models and post-processing systems.

    The caller must supply a consistent pair of grid definition inputs:
    `igdtnumi` (GDS template number) and `igdtmpli` (its template values).
    Incorrect or mismatched GDS inputs will result in invalid coordinate
    transformations.
    """
    # Define some scalars.
    cdef int igdtleni = igdtmpli.shape[0]
    cdef int iopt = -1 # This signals gdswzd to convert lats/lons to grid i/j.
    cdef int npts = lats.shape[0]
    cdef int nret = 0

    # Define and allocate arrays to pass to gdswzd().
    cdef cnp.ndarray[cnp.float32_t, ndim=1] xpts = np.zeros(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] ypts = np.zeros(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] crot = np.ones(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] srot = np.zeros(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] xlon = np.zeros(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] xlat = np.zeros(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] ylon = np.zeros(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] ylat = np.zeros(npts, dtype=np.float32)
    cdef cnp.ndarray[cnp.float32_t, ndim=1] area = np.zeros(npts, dtype=np.float32)

    # Use memoryviews for direct C access to array data.
    cdef float *xpts_ptr = &xpts[0]
    cdef float *ypts_ptr = &ypts[0]
    cdef float *crot_ptr = &crot[0]
    cdef float *srot_ptr = &srot[0]
    cdef float *xlon_ptr = &xlon[0]
    cdef float *xlat_ptr = &xlat[0]
    cdef float *ylon_ptr = &ylon[0]
    cdef float *ylat_ptr = &ylat[0]
    cdef float *area_ptr = &area[0]

    # Call NCEPLIBS-ip, gdswzd().
    gdswzd(
        igdtnumi,
        <int *>&igdtmpli[0],
        igdtleni,
        iopt,
        npts,
        missing_value,
        xpts_ptr,
        ypts_ptr,
        &lons[0],
        &lats[0],
        &nret,
        crot_ptr,
        srot_ptr,
        xlon_ptr,
        xlat_ptr,
        ylon_ptr,
        ylat_ptr,
        area_ptr,
    )
    if nret == -1:
        msg = f"Error converting lat/lons to grid i/j, error code = {nret}"
        raise RuntimeError(msg)

    return xpts, ypts
