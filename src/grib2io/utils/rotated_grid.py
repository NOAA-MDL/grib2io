"""Tools for working with Rotated Lat/Lon Grids."""

import numpy as np
from numpy.typing import NDArray

RAD2DEG = 57.29577951308232087684
DEG2RAD = 0.01745329251994329576

def rotate(
    latin: NDArray[np.float32],
    lonin: NDArray[np.float32],
    aor: NDArray[np.float32],
    splat: NDArray[np.float32],
    splon: NDArray[np.float32],
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """
    Perform grid rotation.

    This function is adapted from ECMWF's ecCodes library void function,
    rotate().

    https://github.com/ecmwf/eccodes/blob/develop/src/grib_geography.cc

    Parameters
    ----------
    latin
        Latitudes in units of degrees.
    lonin
        Longitudes in units of degrees.
    aor
        Angle of rotation as defined in GRIB2 GDTN 4.1.
    splat
        Latitude of South Pole as defined in GRIB2 GDTN 4.1.
    splon
        Longitude of South Pole as defined in GRIB2 GDTN 4.1.

    Returns
    -------
    lats
        `numpy.ndarrays` with `dtype=numpy.float32` of grid latitudes in units
        of degrees.
    lons
        `numpy.ndarrays` with `dtype=numpy.float32` of grid longitudes in units
        of degrees.
    """
    zsycen = np.sin(DEG2RAD * (splat + 90.))
    zcycen = np.cos(DEG2RAD * (splat + 90.))
    zxmxc  = DEG2RAD * (lonin - splon)
    zsxmxc = np.sin(zxmxc)
    zcxmxc = np.cos(zxmxc)
    zsyreg = np.sin(DEG2RAD * latin)
    zcyreg = np.cos(DEG2RAD * latin)
    zsyrot = zcycen * zsyreg - zsycen * zcyreg * zcxmxc

    zsyrot = np.where(zsyrot>1.0,1.0,zsyrot)
    zsyrot = np.where(zsyrot<-1.0,-1.0,zsyrot)

    pyrot = np.arcsin(zsyrot) * RAD2DEG

    zcyrot = np.cos(pyrot * DEG2RAD)
    zcxrot = (zcycen * zcyreg * zcxmxc + zsycen * zsyreg) / zcyrot
    zcxrot = np.where(zcxrot>1.0,1.0,zcxrot)
    zcxrot = np.where(zcxrot<-1.0,-1.0,zcxrot)
    zsxrot = zcyreg * zsxmxc / zcyrot

    pxrot = np.arccos(zcxrot) * RAD2DEG

    pxrot = np.where(zsxrot<0.0,-pxrot,pxrot)

    return pyrot, pxrot


def unrotate(
    latin: NDArray[np.float32],
    lonin: NDArray[np.float32],
    aor: NDArray[np.float32],
    splat: NDArray[np.float32],
    splon: NDArray[np.float32],
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """
    Perform grid un-rotation.

    This function is adapted from ECMWF's ecCodes library void function,
    unrotate().

    https://github.com/ecmwf/eccodes/blob/develop/src/grib_geography.cc

    Parameters
    ----------
    latin
        Latitudes in units of degrees.
    lonin
        Longitudes in units of degrees.
    aor
        Angle of rotation as defined in GRIB2 GDTN 4.1.
    splat
        Latitude of South Pole as defined in GRIB2 GDTN 4.1.
    splon
        Longitude of South Pole as defined in GRIB2 GDTN 4.1.

    Returns
    -------
    lats
        `numpy.ndarrays` with `dtype=numpy.float32` of grid latitudes in units
        of degrees.
    lons
        `numpy.ndarrays` with `dtype=numpy.float32` of grid longitudes in units
        of degrees.
    """
    lon_x = lonin
    lat_y = latin

    latr = lat_y * DEG2RAD
    lonr = lon_x * DEG2RAD

    xd = np.cos(lonr) * np.cos(latr)
    yd = np.sin(lonr) * np.cos(latr)
    zd = np.sin(latr)

    t = -(90.0 + splat)
    o = -splon

    sin_t = np.sin(DEG2RAD * t)
    cos_t = np.cos(DEG2RAD * t)
    sin_o = np.sin(DEG2RAD * o)
    cos_o = np.cos(DEG2RAD * o)

    x = cos_t * cos_o * xd + sin_o * yd + sin_t * cos_o * zd
    y = -cos_t * sin_o * xd + cos_o * yd - sin_t * sin_o * zd
    z = -sin_t * xd + cos_t * zd

    ret_lat = 0
    ret_lon = 0

    # Then convert back to 'normal' (lat,lon)
    # Uses arcsin, to convert back to degrees, put in range -1 to 1 in case of slight rounding error
    # avoid error on calculating e.g. asin(1.00000001)
    z = np.where(z>1.0,1.0,z)
    z = np.where(z<-1.0,-1.0,z)

    ret_lat = np.arcsin(z) * RAD2DEG
    ret_lon = np.arctan2(y, x) * RAD2DEG

    # Still get a very small rounding error, round to 6 decimal places
    ret_lat = np.round(ret_lat * 1000000.0) / 1000000.0
    ret_lon = np.round(ret_lon * 1000000.0) / 1000000.0

    ret_lon -= aor

    return ret_lat, ret_lon
