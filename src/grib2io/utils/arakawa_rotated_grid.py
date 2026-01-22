"""
Functions for handling an Arakawa Rotated Lat/Lon Grids.

This grid is not often used, but is currently used for the NCEP/RAP using
[GRIB2 Grid Definition Template 32769](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-32769.shtml)

These functions are adapted from the NCAR Command Language (ncl),
from [NcGRIB2.c](https://github.com/NCAR/ncl/blob/develop/ni/src/ncl/NclGRIB2.c)
"""
import math
import numpy as np

from . import rotated_grid

DEG2RAD = rotated_grid.DEG2RAD
RAD2DEG = rotated_grid.RAD2DEG

def ll2rot(latin: float, lonin: float, latpole: float, lonpole: float) -> tuple[float, float]:
    """
    Rotate a latitude/longitude pair.

    Parameters
    ----------
    latin
        Unrotated latitude in units of degrees.
    lonin
        Unrotated longitude in units of degrees.
    latpole
        Latitude of Pole.
    lonpole
        Longitude of Pole.

    Returns
    -------
    tlat
        Rotated latitude in units of degrees.
    tlons
        Rotated longitude in units of degrees.
    """
    tlon = lonin - lonpole

    # Convert to xyz coordinates
    x = math.cos(latin * DEG2RAD) * math.cos(tlon * DEG2RAD)
    y = math.cos(latin * DEG2RAD) * math.sin(tlon * DEG2RAD)
    z = math.sin(latin * DEG2RAD)

    # Rotate around y axis
    rotang = (latpole + 90) * DEG2RAD
    sinrot = math.sin(rotang)
    cosrot = math.cos(rotang)
    ry = y
    rx = x * cosrot + z * sinrot
    rz = -x * sinrot + z * cosrot

    # Convert back to lat/lon
    tlat = math.asin(rz) / DEG2RAD
    if math.fabs(rx) > 0.0001:
        tlon = math.atan2(ry,rx) / DEG2RAD
    elif ry > 0:
        tlon = 90.0
    else:
        tlon = -90.0

    if tlon < -180:
        tlon += 360.0
    if tlon >= 180:
        tlon -= 360.0

    return tlat, tlon


def rot2ll(latin: float, lonin: float, latpole: float, lonpole: float) -> tuple[float, float]:
    """
    Unrotate a latitude/longitude pair.

    Parameters
    ----------
    latin
        Rotated latitude in units of degrees.
    lonin
        Rotated longitude in units of degrees.
    latpole
        Latitude of Pole.
    lonpole
        Longitude of Pole.

    Returns
    -------
    tlat
        Unrotated latitude in units of degrees.
    tlons
        Unrotated longitude in units of degrees.
    """
    tlon = lonin

    # Convert to xyz coordinates
    x = math.cos(latin * DEG2RAD) * math.cos(lonin * DEG2RAD)
    y = math.cos(latin * DEG2RAD) * math.sin(lonin * DEG2RAD)
    z = math.sin(latin * DEG2RAD)

    # Rotate around y axis
    rotang = -(latpole + 90) * DEG2RAD
    sinrot = math.sin(rotang)
    cosrot = math.cos(rotang)
    ry = y
    rx = x * cosrot + z * sinrot
    rz = -x * sinrot + z * cosrot

    # Convert back to lat/lon
    tlat = math.asin(rz) / DEG2RAD
    if math.fabs(rx) > 0.0001:
        tlon = math.atan2(ry,rx) / DEG2RAD
    elif ry > 0:
        tlon = 90.0
    else:
        tlon = -90.0

    # Remove the longitude rotation
    tlon += lonpole
    if tlon < 0:
        tlon += 360.0
    if tlon > 360:
        tlon -= 360.0

    return tlat, tlon


def vector_rotation_angles(
    tlat: float,
    tlon: float,
    clat: float,
    losp: float,
    xlat: float,
) -> float:
    """
    Generate a rotation angle value.

    The rotation angle value can be applied to a vector quantity to make it
    Earth-oriented.

    Parameters
    ----------
    tlat
        True latitude in units of degrees.
    tlon
        True longitude in units of degrees..
    clat
        Latitude of center grid point in units of degrees.
    losp
        Longitude of the southern pole in units of degrees.
    xlat
        Latitude of the rotated grid in units of degrees.

    Returns
    -------
    rot
        Rotation angle in units of radians.
    """
    slon = math.sin((tlon-losp)*DEG2RAD)
    cgridlat = math.cos(xlat*DEG2RAD)
    if cgridlat <= 0.0:
        rot = 0.0
    else:
        crot = (math.cos(clat*DEG2RAD)*math.cos(tlat*DEG2RAD)+
                math.sin(clat*DEG2RAD)*math.sin(tlat*DEG2RAD)*
                math.cos(tlon*DEG2RAD))/cgridlat
        srot = (-1.0*math.sin(clat*DEG2RAD)*slon)/cgridlat
        rot = math.atan2(srot,crot)
    return rot
