# cython: language_level=3, boundscheck=False
# distutils: define_macros=NPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION
"""
Cython interfaces to functions in the NCEPLIBS-g2c library.

IMPORTANT: Make changes to this file, not the C code that Cython generates.
"""

cimport cython
from cpython.buffer cimport Py_buffer, PyObject_GetBuffer, PyBuffer_Release, PyBUF_SIMPLE, PyBUF_WRITABLE
from libc.stdlib cimport free
from libc.string cimport memcpy

import numpy as np
cimport numpy as cnp

# ----------------------------------------------------------------------------------------
# Some helper definitions from the Python API
# ----------------------------------------------------------------------------------------
cdef extern from "Python.h":
    char * PyBytes_AsString(object string)
    object PyBytes_FromString(char *s)
    object PyBytes_FromStringAndSize(char *s, size_t size)

# ----------------------------------------------------------------------------------------
# Definitions from NCEPLIBS-g2c.
#
# IMPORTANT: The preprocessing directives inside the cdef triple quotes allows for custom
# definitions to be set from the parent "grib2.h". The definition of the g2c version
# string will change from G2_VERSION to G2C_VERSION from g2c v1.7.0 to v1.8.0. The ifdef
# check accommodates before and after the change.
# ----------------------------------------------------------------------------------------
cdef extern from "grib2.h":
    """
    #ifndef G2_PNG_ENABLED
        #define G2_PNG_ENABLED 0
    #endif
    #ifndef G2_JPEG2000_ENABLED
        #define G2_JPEG2000_ENABLED 0
    #endif
    #ifndef G2_AEC_ENABLED
        #define G2_AEC_ENABLED 0
    #endif
    #ifdef G2_VERSION
        #define G2C_VERSION G2_VERSION
    #endif
    """
    cdef char *G2C_VERSION
    cdef int G2_PNG_ENABLED
    cdef int G2_JPEG2000_ENABLED
    cdef int G2_AEC_ENABLED
    ctypedef long g2int      # 64-bit signed integer
    ctypedef float g2float   # 32-bit floating-point
    g2int g2_unpack1(unsigned char *, g2int *, g2int **, g2int *)
    g2int g2_unpack3(unsigned char *, g2int *, g2int **, g2int **,
                     g2int *, g2int **, g2int *)
    g2int g2_unpack4(unsigned char *, g2int *, g2int *, g2int **,
                     g2int *, g2float **, g2int *)
    g2int g2_unpack5(unsigned char *, g2int *, g2int *, g2int *, g2int **, g2int *)
    g2int g2_unpack6(unsigned char *, g2int *, g2int, g2int *, g2int **)
    g2int g2_unpack7(unsigned char *, g2int *, g2int ,g2int *, g2int , g2int *,
                     g2int, g2float **)
    g2int g2_create(unsigned char *, g2int *, g2int *)
    g2int g2_addlocal(unsigned char *, unsigned char *, g2int)
    g2int g2_addgrid(unsigned char *, g2int *, g2int *, g2int *, g2int)
    g2int g2_addfield(unsigned char *, g2int , g2int *, g2float *, g2int, g2int,
                      g2int *, g2float *, g2int, g2int , g2int *)
    g2int g2_gribend(unsigned char *)

# ----------------------------------------------------------------------------------------
# Define some g2clib attributes
# ----------------------------------------------------------------------------------------
__version__ = G2C_VERSION.decode("utf-8")[-5:]
_has_png = G2_PNG_ENABLED
_has_jpeg = G2_JPEG2000_ENABLED
_has_aec = G2_AEC_ENABLED

# ----------------------------------------------------------------------------------------
# Python wrappers for g2c functions.
# ----------------------------------------------------------------------------------------
cdef _toarray(void *items, object a):
    """
    Function to fill a Numpy array with data from GRIB2 unpacking.
    """
    cdef char *abuf
    cdef Py_ssize_t buflen
    cdef Py_buffer view
    cdef Py_ssize_t itemsize

    # Get pointer to data buffer.
    if PyObject_GetBuffer(a, &view, PyBUF_WRITABLE) == -1:
        raise ValueError("Object does not support writable buffer protocol")

    try:
        abuf = <char *>view.buf
        buflen = view.len

        # Determine item size based on dtype
        itemsize = a.itemsize  # NumPy dtype item size

        # Ensure the sizes match before copying
        if buflen != len(a) * itemsize:
            PyBuffer_Release(&view)
            free(items)
            raise RuntimeError("Buffer size mismatch")

        # Use memcpy to copy data efficiently
        memcpy(abuf, items, buflen)

        return a

    finally:
        free(items)
        PyBuffer_Release(&view)


# ----------------------------------------------------------------------------------------
# Routine for reading GRIB2 files.
# ----------------------------------------------------------------------------------------
def unpack1(gribmsg):
    """
    Unpacks GRIB2 Section 1 (Identification Section)

    This is Cython function serves as a wrapper to the NCEPLIBS-g2c function,
    g2_unpack1().

    Parameters
    ----------
    gribmsg : bytes
        Python bytes object containing packed section 1 of the GRIB2 message.

    Returns
    -------
    ids : np.ndarray
        1D Numpy array containing unpacked section1 values.

    ipos : int
        Number of bytes read/processed from unpacking.
    """
    cdef unsigned char *cgrib
    cdef g2int iret
    cdef g2int iofst
    cdef g2int idslen
    cdef g2int *ids_ptr

    iret = 0
    iofst = 0
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_unpack1(
        cgrib,
        &iofst,
        &ids_ptr,
        &idslen,
    )
    if iret != 0:
       msg = f"Error unpacking section 1, error code = {iret}"
       raise RuntimeError(msg)

    ids = _toarray(ids_ptr, np.empty(idslen, np.int64))

    return ids, iofst//8


def unpack3(gribmsg):
    """
    Unpacks GRIB2 Section 3 (Grid Definition Section)

    This is Cython function serves as a wrapper to the NCEPLIBS-g2c function,
    g2_unpack3().

    Parameters
    ----------
    gribmsg : bytes
        Python bytes object containing packed section 3 of the GRIB2 message.

    Returns
    -------
    gds : np.ndarray
        1D Numpy array containing the grid defintion section values.

    gdtmpl : np.ndarray
        1D Numpy array containing the grid defintion template values.

    deflist : np.ndarray
        Used if gds[2] != 0, 1D Numpy array containing the number of
        grid points contained in each row or column.

    ipos : int
        Number of bytes read/processed from unpacking.
    """
    cdef unsigned char *cgrib
    cdef g2int iret
    cdef g2int igdtlen
    cdef g2int idefnum
    cdef g2int iofst
    cdef g2int *gds_ptr
    cdef g2int *gdtmpl_ptr
    cdef g2int *deflist_ptr

    iret = 0
    iofst = 0
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_unpack3(
        cgrib,
        &iofst,
        &gds_ptr,
        &gdtmpl_ptr,
        &igdtlen,
        &deflist_ptr,
        &idefnum,
    )
    if iret != 0:
       msg = f"Error unpacking section 3, error code = {iret}"
       raise RuntimeError(msg)

    gds = _toarray(gds_ptr, np.empty(5, np.int64))
    gdtmpl = _toarray(gdtmpl_ptr, np.empty(igdtlen, np.int64))
    deflist = _toarray(deflist_ptr, np.empty(idefnum, np.int64))

    return gds, gdtmpl, deflist, iofst//8


def unpack4(gribmsg):
    """
    Unpacks GRIB2 Section 4 (Product Definition Section)

    This is Cython function serves as a wrapper to the NCEPLIBS-g2c function,
    g2_unpack4().

    Parameters
    ----------
    gribmsg : bytes
        Python bytes object containing packed section 4 of the GRIB2 message.

    Returns
    -------
    pdtnum : int
        GRIB2 Product Definition Template number.

    pdtmpl : np.ndarray
        1D Numpy array containing the product defintion template values.

    coordlist : np.ndarray
        1D Numpy array containing floating point values intended to document
        the vertical discretisation associated to model data on hybrid 
        coordinate vertical levels.

    numcoord : int
        Number of coordinate values after template.

    ipos : int
        Number of bytes read/processed from unpacking.
    """
    cdef unsigned char *cgrib
    cdef g2int iret
    cdef g2int iofst
    cdef g2int pdtnum
    cdef g2int pdtlen
    cdef g2int numcoord
    cdef g2int *pdtmpl_ptr
    cdef g2float *coordlist_ptr

    iret = 0
    iofst = 0
    numcoord = 0
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_unpack4(
        cgrib,
        &iofst,
        &pdtnum,
        &pdtmpl_ptr,
        &pdtlen,
        &coordlist_ptr,
        &numcoord,
    )
    if iret != 0:
       msg = f"Error unpacking section 4,error code = {iret}"
       raise RuntimeError(msg)

    pdtmpl = _toarray(pdtmpl_ptr, np.empty(pdtlen, np.int64))
    coordlist = _toarray(coordlist_ptr, np.empty(numcoord, np.float32))

    return pdtnum, pdtmpl, coordlist, numcoord, iofst//8


def unpack5(gribmsg):
    """
    Unpacks GRIB2 Section 5 (Data Representation Section)

    This is Cython function serves as a wrapper to the NCEPLIBS-g2c function,
    g2_unpack5().

    Parameters
    ----------
    gribmsg : bytes
        Python bytes object containing packed section 4 of the GRIB2 message.

    Returns
    -------
    drtnum : int
        GRIB2 Data Representation Template number.

    drtmpl : np.ndarray
        1D Numpy array containing the data representation template values.

    coordlist : np.ndarray
        1D Numpy array containing floating point values intended to document
        the vertical discretisation associated to model data on hybrid
        coordinate vertical levels.

    ndpts : int
        Number of data points to be unpacked.

    ipos : int
        Number of bytes read/processed from unpacking.
    """
    cdef unsigned char *cgrib
    cdef g2int iret
    cdef g2int iofst
    cdef g2int ndpts
    cdef g2int drtnum
    cdef g2int drtlen
    cdef g2int *drtmpl_ptr

    iret = 0
    iofst = 0
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)
    iret = g2_unpack5(
        cgrib,
        &iofst,
        &ndpts,
        &drtnum,
        &drtmpl_ptr,
        &drtlen)
    if iret != 0:
       msg = f"Error unpacking section 5, error code = {iret}"
       raise RuntimeError(msg)

    drtmpl = _toarray(drtmpl_ptr, np.empty(drtlen, np.int64))

    return drtnum, drtmpl, ndpts, iofst//8


def unpack6(gribmsg,
            int ndpts):
    """
    Unpacks GRIB2 Section 6 (Bitmap Section)

    This is Cython function serves as a wrapper to the NCEPLIBS-g2c function,
    g2_unpack6().

    Parameters
    ----------
    gribmsg : bytes
        Python bytes object containing packed section 4 of the GRIB2 message.

    ndpts : int
        Number of data points to be unpacked.

    Returns
    -------
    ibitmap : int
        Bit map indicator.

    bitmap : np.ndarray
        1D Numpy array containing the decoded bitmap.

    ipos : int
        Number of bytes read/processed from unpacking.
    """
    cdef unsigned char *cgrib
    cdef g2int iret
    cdef g2int iofst
    cdef g2int ibitmap
    cdef g2int *bitmap_ptr

    iret = 0
    ibitmap = 0
    iofst = 0
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_unpack6(
        cgrib,
        &iofst,
        <g2int>ndpts,
        <g2int *>&ibitmap,
        &bitmap_ptr,
    )
    if iret != 0:
        msg = f"Error unpacking section 6, error code = {iret}"
        raise RuntimeError(msg)

    if ibitmap == 0:
        bitmap = _toarray(bitmap_ptr, np.empty(ndpts, np.int64))
    else:
        bitmap = None
        free(bitmap_ptr)

    return ibitmap, bitmap, iofst//8


def unpack7(gribmsg,
            int gdtnum,
            cnp.ndarray[cnp.int64_t, ndim=1] gdtmpl,
            int drtnum,
            cnp.ndarray[cnp.int64_t, ndim=1] drtmpl,
            int ndpts,
            storageorder="C"):
    """
    Unpacks GRIB2 Section 6 (Bitmap Section)

    This is Cython function serves as a wrapper to the NCEPLIBS-g2c function,
    g2_unpack6().

    Parameters
    ----------
    gribmsg : bytes
        Python bytes object containing packed section 4 of the GRIB2 message.

    gdtnum : int
        Grid Defintion Template number.

    gdtmpl : np.ndarray
        1D Numpy array containing the grid defintion template values.

    drtnum : int
        Data Representation Template number.

    drtmpl : np.ndarray
        1D Numpy array containing the data representation template values.

    ndpts : int
        Number of data points to be unpacked.

    storageorder : {'C', 'F'}, optional
        Specify memory layout of unpacked data. The newly created array
        will be in 'C' order (row major) unless 'F' is specified, in which
        case it will be in Fortran order (column major). 

    Returns
    -------
    fld : np.ndarray
        1D Numpy array of floating-point values of the unpacked grid.

    ipos : int
        Number of bytes read/processed from unpacking.
    """
    cdef unsigned char *cgrib
    cdef g2int iofst
    cdef g2int iret
    cdef g2float *fld_ptr
    cdef g2int[:] igdstmpl_view = gdtmpl
    cdef g2int[:] idrtmpl_view = drtmpl

    iret = 0
    iofst = 0
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_unpack7(
        cgrib,
        &iofst,
        <g2int>gdtnum,
        <g2int *>&igdstmpl_view[0],
        <g2int>drtnum,
        <g2int *>&idrtmpl_view[0],
        <g2int>ndpts,
        &fld_ptr
    )
    if iret != 0:
       msg = f"Error in unpack7, error code = {iret}"
       raise RuntimeError(msg)

    fld = _toarray(fld_ptr, np.empty(ndpts, np.float32, order=storageorder))

    return fld, iofst//8

# ----------------------------------------------------------------------------------------
# Routines for creating a GRIB2 message
# ----------------------------------------------------------------------------------------
def grib2_create(cnp.ndarray[cnp.int64_t, ndim=1] sec0,
                 cnp.ndarray[cnp.int64_t, ndim=1] sec1):
    """
    Initializes a new GRIB2 message.

    This Cython function serves as a wrapper to NCEPLIBS-g2c function,
    g2_create() which packs GRIB2 sections 0 (Indicator Section) and 1
    (Identification Section).

    Parameters
    ----------
    sec0 : np.ndarray
        1D Numpy array of length 2 containing the GRIB2 discipline [0] and
        GRIB Edition Number [1] which is 2 for GRIB2.
    
    sec1 : np.ndarray
        1D Numpy array containing section 1 values. 

    Returns
    -------
    gribmsg : bytes
        Byte string containing the new GRIB2 message.

    iret : int
        When > 0, the current size of new GRIB2 message or if < 0, then
        an error code.
    """
    cdef g2int iret
    cdef unsigned char *cgrib
    cdef g2int[:] sec0_view = sec0
    cdef g2int[:] sec1_view = sec1

    iret = 0
    lengrib = 16 + (4*len(sec1)) # Section 0 is always 16 bytes.
    gribmsg = lengrib * b" "
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_create(
        cgrib,
        <g2int *>&sec0_view[0],
        <g2int *>&sec1_view[0],
    )
    if iret < 0:
        msg = f"Error in grib2_create, error code = {iret}"
        raise RuntimeError(msg)

    gribmsg = PyBytes_FromStringAndSize(<char *>cgrib, iret)

    return gribmsg, iret


def grib2_addlocal(gribmsg,
                   sec2):
    """
    Adds section 2 data to GRIB2 message.

    This Cython function serves as a wrapper to NCEPLIBS-g2c function,
    grib2_addlocal() which adds a Local Use Section (Section 2) to a
    GRIB2 message.

    It should be noted here that is the repsonsibility of the user
    to provide code and/or instructions for decoding and encoding
    content of section 2 specific to your use case. 

    Parameters
    ----------
    gribmsg : bytes
        Bytes string containing the new GRIB2 message, returned from
        grib2_create().

    sec2 : bytes
        Bytes string containing section 2 content. 

    Returns
    -------
    gribmsg : bytes
        Byte string containing the updated GRIB2 message with section
        2 data added.

    iret : int
        When > 0, the current size of new GRIB2 message or if < 0, then
        an error code.
    """
    cdef unsigned char *cgrib
    cdef unsigned char *csec2
    cdef g2int lensec2
    cdef g2int iret

    iret = 0
    lensec2 = len(sec2)
    gribmsg = gribmsg + (5+lensec2)*b" "
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)
    csec2 = <unsigned char *>PyBytes_AsString(sec2)

    iret = g2_addlocal(
        cgrib,
        csec2,
        lensec2,
    )
    if iret < 0:
       msg = f"Error in grib2_addlocal, error code = {iret}"
       raise RuntimeError(msg)

    gribmsg = PyBytes_FromStringAndSize(<char *>cgrib, iret)
    return gribmsg, iret


def grib2_addgrid(gribmsg,
                  cnp.ndarray[cnp.int64_t, ndim=1] gds,
                  cnp.ndarray[cnp.int64_t, ndim=1] gdstmpl,
                  cnp.ndarray[cnp.int64_t, ndim=1] deflist):
    """
    Adds section 3 data to GRIB2 message.

    This Cython function serves as a wrapper to NCEPLIBS-g2c function,
    grib2_addgrid() which adds a Grid Definition Section (Section 3).

    Parameters
    ----------
    gribmsg : bytes
        Bytes string containing the new GRIB2 message, returned from
        grib2_create() or grib2_addlocal() if there contains local
        use content.

    gds : np.ndarray
        1D Numpy array containing the grid defintion section values.

    gdtmpl : np.ndarray
        1D Numpy array containing the grid defintion template values.

    deflist : np.ndarray
        Used if gds[2] != 0, 1D Numpy array containing the number of
        grid points contained in each row or column.

    Returns
    -------
    gribmsg : bytes
        Byte string containing the updated GRIB2 message with section
        3 data added.

    iret : int
        When > 0, the current size of new GRIB2 message or if < 0, then
        an error code.
    """
    cdef unsigned char *cgrib
    cdef g2int[:] gds_view = gds
    cdef g2int[:] gdstmpl_view = gdstmpl
    cdef g2int[:] deflist_view = deflist
    cdef g2int iret

    iret = 0
    gribmsg = gribmsg + 4*(256+4+gds[2]+1)*b" "
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_addgrid(
        cgrib,
        <g2int *>&gds_view[0],
        <g2int *>&gdstmpl_view[0],
        <g2int *>&deflist_view[0],
        <g2int>len(deflist),
    )
    if iret < 0:
       msg = f"Error in grib2_addgrid, error code {iret}"
       raise RuntimeError(msg)

    gribmsg = PyBytes_FromStringAndSize(<char *>cgrib, iret)
    return gribmsg, iret


def grib2_addfield(gribmsg,
                   int pdtnum,
                   cnp.ndarray[cnp.int64_t, ndim=1] pdtmpl,
                   cnp.ndarray[cnp.float32_t, ndim=1] coordlist,
                   int drtnum,
                   cnp.ndarray[cnp.int64_t, ndim=1] drtmpl,
                   cnp.ndarray[cnp.float32_t, ndim=1] fld,
                   int ibitmap,
                   cnp.ndarray[cnp.int64_t, ndim=1] bitmap):
    """
    Adds sections 4 (Product Definition Section), 5 (Data Representation
    Section), 6 (Bitmap Section), and 7 (Data Section) data to GRIB2
    message.

    This Cython function serves as a wrapper to NCEPLIBS-g2c function,
    grib2_addfield(). 

    Parameters
    ----------
    gribmsg : bytes
        Bytes string containing the new GRIB2 message, returned from
        grib2_addgrid().

    pdtnum : int
        GRIB2 Product Definition Template number.

    pdtmpl : np.ndarray
        1D Numpy array containing the product defintion template values.

    coordlist : np.ndarray
        1D Numpy array containing floating point values intended to document
        the vertical discretisation associated to model data on hybrid
        coordinate vertical levels.

    drtnum : int
        GRIB2 Data Representation Template number.

    drtmpl : np.ndarray
        1D Numpy array containing the data representation template values.

    fld : np.ndarray
        1D Numpy array of floating-point values of the data to be packed.

    ibitmap : int
        Bit map indicator.

    bitmap : np.ndarray
        1D Numpy array containing the decoded bitmap.

    Returns
    -------
    gribmsg : bytes
        Byte string containing the updated GRIB2 message with sections
        4, 5, 6, and 7 added.

    iret : int
        When > 0, the current size of new GRIB2 message or if < 0, then
        an error code.
    """
    cdef unsigned char *cgrib
    cdef g2int iret
    cdef g2int[:] pdtmpl_view = pdtmpl
    cdef float[:] coordlist_view = coordlist
    cdef g2int[:] drtmpl_view = drtmpl
    cdef float[:] fld_view = fld
    cdef g2int[:] bitmap_view = bitmap

    iret = 0
    gribmsg = gribmsg + 4*(len(drtmpl)+len(fld)+4)*b" "
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_addfield(
        cgrib,
        pdtnum,
        <g2int *>&pdtmpl_view[0],
        <float *>&coordlist_view[0],
        <g2int>len(coordlist),
        drtnum,
        <g2int *>&drtmpl_view[0],
        <float *>&fld_view[0],
        <g2int>len(fld),
        ibitmap,
        <g2int *>&bitmap_view[0],
    )
    if iret < 0:
       msg = f"Error in grib2_addfield, error code = {iret}"
       raise RuntimeError(msg)

    gribmsg = PyBytes_FromStringAndSize(<char *>cgrib, iret)
    return gribmsg, iret


def grib2_end(gribmsg):
    """
    Finalizes GRIB2 message.

    This Cython function serves as a wrapper to NCEPLIBS-g2c function,
    grib2_end() which adds the End Section ( "7777" ) to the end of the
    GRIB message and calculates the length and stores it in the appropriate
    place in Section 0.

    Parameters
    ----------
    gribmsg : bytes
        Bytes string containing the new GRIB2 message.

    Returns
    -------
    gribmsg : bytes
        Byte string containing the complete GRIB2 message.

    iret : int
        When > 0, the current size of new GRIB2 message or if < 0, then
        an error code.
    """
    cdef g2int iret
    cdef unsigned char *cgrib

    iret = 0
    gribmsg = gribmsg + 8*b" "
    cgrib = <unsigned char *>PyBytes_AsString(gribmsg)

    iret = g2_gribend(cgrib)
    if iret < 0:
       msg = f"Error in grib2_end, error code = {iret}"
       raise RuntimeError(msg)

    gribmsg = PyBytes_FromStringAndSize(<char *>cgrib, iret)

    return gribmsg, iret
