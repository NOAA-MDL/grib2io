# cython: language_level=3, boundscheck=False
# distutils: define_macros=NPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION
"""
Cython code to provide python interfaces to functions in the NCEPLIBS-ip library.

IMPORTANT: Make changes to this file, not the C code that Cython generates.
"""

from libc.stdint cimport uint8_t, int32_t
import numpy as np
cimport numpy as np

cdef extern from "<stdbool.h>":
    ctypedef int bool


cdef extern from "iplib.h":
    void ipolates_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni, 
                        int *igdtnumo, int *igdtmplo, int *igdtleno, 
                        int *mi, int *mo, int *km, int *ibi, bool *li, float *gi, 
                        int *no, float *rlat, float *rlon, int *ibo, bool *lo, float *go, int *iret)
    void ipolatev_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni, 
                        int *igdtnumo, int *igdtmplo, int *igdtleno, 
                        int *mi, int *mo, int *km, int *ibi, bool *li, float *ui, float *vi,
                        int *no, float *rlat, float *rlon, float *crot, float *srot, int *ibo, bool *lo,
                        float *uo, float *vo, int *iret)
    

def interpolate_scalar(int ip,
                   np.ndarray[np.int32_t, ndim=1] ipopt,
                   int igdtnumi,
                   np.ndarray[np.int32_t, ndim=1] igdtmpli,
                   int igdtnumo,
                   np.ndarray[np.int32_t, ndim=1] igdtmplo,
                   int mi,
                   int mo,
                   int km,
                   np.ndarray[np.int32_t, ndim=1] ibi,
                   np.ndarray[np.uint8_t, ndim=2] li,
                   np.ndarray[np.float32_t, ndim=2] gi,
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
    cdef np.ndarray[np.float32_t, ndim=1] rlat = np.zeros(mo, dtype=np.float32)
    cdef np.ndarray[np.float32_t, ndim=1] rlon = np.zeros(mo, dtype=np.float32)
    cdef np.ndarray[np.int32_t, ndim=1] ibo = np.zeros(km, dtype=np.int32)
    cdef np.ndarray[np.uint8_t, ndim=2] lo = np.zeros((mo, km), dtype=np.uint8)
    cdef np.ndarray[np.float32_t, ndim=2] go = np.zeros((mo, km), dtype=np.float32)
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
                   np.ndarray[np.int32_t, ndim=1] ipopt,
                   int igdtnumi,
                   np.ndarray[np.int32_t, ndim=1] igdtmpli,
                   int igdtnumo,
                   np.ndarray[np.int32_t, ndim=1] igdtmplo,
                   int mi,
                   int mo,
                   int km,
                   np.ndarray[np.int32_t, ndim=1] ibi,
                   np.ndarray[np.uint8_t, ndim=2] li,
                   np.ndarray[np.float32_t, ndim=2] ui,
                   np.ndarray[np.float32_t, ndim=2] vi,
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
    cdef np.ndarray[np.float32_t, ndim=1] rlat = np.zeros(mo, dtype=np.float32)
    cdef np.ndarray[np.float32_t, ndim=1] rlon = np.zeros(mo, dtype=np.float32)
    cdef np.ndarray[np.float32_t, ndim=1] crot = np.ones(mo, dtype=np.float32)
    cdef np.ndarray[np.float32_t, ndim=1] srot = np.zeros(mo, dtype=np.float32)
    cdef np.ndarray[np.int32_t, ndim=1] ibo = np.zeros(km, dtype=np.int32)
    cdef np.ndarray[np.uint8_t, ndim=2] lo = np.zeros((mo, km), dtype=np.uint8)
    cdef np.ndarray[np.float32_t, ndim=2] uo = np.zeros((mo, km), dtype=np.float32)
    cdef np.ndarray[np.float32_t, ndim=2] vo = np.zeros((mo, km), dtype=np.float32)
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
