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


def getdate(year,month,day,hour,minute=None,second=None):
    """
    Build an integer date from component input.

    **`year : int`**

    Year in 4-digit format.

    **`month : int`**

    Month in 2-digit format.

    **`day : int`**

    Day in 2-digit format.

    **`hour : int`**

    Hour in 2-digit format.

    **`minute : int, optional`**

    Minute in 2-digit format. This argument is required if second is provided, otherwise
    it is optional.

    **`second : int, optional`**

    Second in 2-digit format [OPTIONAL].

    """
    year_exp = 6
    month_exp = 4
    day_exp = 2
    hour_exp = 0
    #if second is not None and minute is None:
    #    raise ValueError("Must provide minute argument if second argument is provided.")
    #year_exp = 6
    #month_exp = 4
    #day_exp = 2
    #hour_exp = 0
    #minute_exp = -2
    #second_exp = -4
    #if minute is not None:
    #    assert minute >= 0 and minute <= 60
    #    year_exp += 2
    #    month_exp += 2
    #    day_exp += 2
    #    hour_exp += 2
    #    minute_exp += 2
    #    second_exp += 2
    #if second is not None:
    #    assert second >= 0 and second <= 60
    #    year_exp += 2
    #    month_exp += 2
    #    day_exp += 2
    #    hour_exp += 2
    #    minute_exp += 2
    #    second_exp += 2
    idate = (year*pow(10,year_exp))+(month*pow(10,month_exp))+\
            (day*pow(10,day_exp))+(hour*pow(10,hour_exp))
    #if minute is not None:
    #    idate += minute*pow(10,minute_exp)
    #if second is not None:
    #    idate += second*pow(10,second_exp)
    return idate
