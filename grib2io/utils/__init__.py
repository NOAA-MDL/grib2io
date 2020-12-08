"""
Collection of utility functions to assist in the encoding and decoding
of GRIB2 Messages.
"""

import g2clib
import numpy as np

def int2bin(i,nbits=8,output=str):
    """
    Convert integer to binary string or list
    """
    i = int(i) if not isinstance(i,int) else i
    assert nbits in [8,16,32,64]
    bitstr = "{0:b}".format(i).zfill(nbits)
    if output is str:
        return bitstr
    elif output is list:
        return [int(b) for b in bitstr]


def putieeeint(r):
    """
    Convert a float to a IEEE format 32 bit integer
    """
    ra = np.array([r],'f')
    ia = np.empty(1,'i')
    g2clib.rtoi_ieee(ra,ia)
    return ia[0]


def getieeeint(i):
    """
    Convert an IEEE format 32 bit integer to a float
    """
    ia = np.array([i],'i')
    ra = np.empty(1,'f')
    g2clib.itor_ieee(ia,ra)
    return ra[0]


def getmd5str(a):
    """
    Generate a MD5 hash string from input list
    """
    import hashlib
    assert isinstance(a,list) or isinstance(a,bytes)
    return hashlib.md5(''.join([str(i) for i in a]).encode()).hexdigest()
