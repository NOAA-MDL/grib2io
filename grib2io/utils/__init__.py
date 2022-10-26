"""
Collection of utility functions to assist in the encoding and decoding
of GRIB2 Messages.
"""

import g2clib
import datetime
import numpy as np
import struct

from .. import tables

def int2bin(i,nbits=8,output=str):
    """
    Convert integer to binary string or list

    Parameters
    ----------

    **`i`**: Integer value to convert to binary representation.

    **`nbits`**: Number of bits to return.  Valid values are 8 [DEFAULT], 16,
    32, and 64.

    **`output`**: Return data as `str` [DEFAULT] or `list` (list of ints).

    Returns
    -------

    `str` or `list` (list of ints) of binary representation of the integer value.
    """
    i = int(i) if not isinstance(i,int) else i
    assert nbits in [8,16,32,64]
    bitstr = "{0:b}".format(i).zfill(nbits)
    if output is str:
        return bitstr
    elif output is list:
        return [int(b) for b in bitstr]


def ieee_float_to_int(f):
    """
    Convert an IEEE 32-bit float to a 32-bit integer.

    Parameters
    ----------

    **`f`**: Float value.

    Returns
    -------

    Numpy Int32 representation of an IEEE 32-bit float.
    """
    i = struct.unpack('>i',struct.pack('>f',np.float32(f)))[0]
    return np.int32(i)



def ieee_int_to_float(i):
    """
    Convert a 32-bit integer to an IEEE 32-bit float.

    Parameters
    ----------

    **`i`**: Integer value.

    Returns
    -------

    Numpy float32
    """
    f = struct.unpack('>f',struct.pack('>i',np.int32(i)))[0]
    return np.float32(f)



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

    **`year`**: Year in 4-digit format.

    **`month`**: Month in 2-digit format.

    **`day`**: Day in 2-digit format.

    **`hour`**: Hour in 2-digit format.

    **`minute`**: Minute in 2-digit format. This argument is required if second is provided, otherwise
    it is optional.

    **`second`**: Second in 2-digit format [OPTIONAL].
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


def getleadtime(idsec,pdtn,pdt):
    """
    Computes lead time as a datetime.timedelta object using information from
    GRIB2 Identification Section (Section 1), Product Definition Template
    Number, and Product Definition Template (Section 4).

    Parameters
    ----------

    **`idsec`**: seqeunce containing GRIB2 Identification Section (Section 1).

    **`pdtn`**: GRIB2 Product Definition Template Number

    **`idsec`**: seqeunce containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------

    **`datetime.timedelta`** object representing the lead time of the GRIB2 message.
    """
    _key = {8:slice(15,21), 9:slice(22,28), 10:slice(16,22), 11:slice(18,24), 12:slice(17,23)}
    refdate = datetime.datetime(*idsec[5:11])
    try:
        return datetime.datetime(*pdt[_key[pdtn]])-refdate
    except(KeyError):
        return datetime.timedelta(hours=pdt[8]*(tables.get_value_from_table(pdt[7],'scale_time_hours')))


def getduration(pdtn,pdt):
    """
    Computes a time duration as a datetime.timedelta using information from
    Product Definition Template Number, and Product Definition Template (Section 4).

    Parameters
    ----------

    **`pdtn`**: GRIB2 Product Definition Template Number

    **`pdt`**: sequence containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------

    **`datetime.timedelta`** object representing the time duration of the GRIB2 message.
    """
    _key = {8:25, 9:32, 10:26, 11:28, 12:27}
    try:
        return datetime.timedelta(hours=pdt[_key[pdtn]+1]*tables.get_value_from_table(pdt[_key[pdtn]],'scale_time_hours'))
    except(KeyError):
        return None


def decode_wx_strings(lus):
    """
    Decode GRIB2 Local Use Section to obtain NDFD/MDL Weather Strings.  The
    decode procedure is defined here:

    https://vlab.noaa.gov/web/mdl/nbm-gmos-grib2-wx-info

    Parameters
    ----------

    **`lus`**: GRIB2 Local Use Section containing NDFD weather strings.

    Returns
    -------

    **`list`**: List of NDFD weather strings.
    """
    assert lus[0] == 1
    # Unpack information related to the simple packing method
    # the packed weather string data.
    ngroups = struct.unpack('>H',lus[1:3])[0]
    nvalues = struct.unpack('>i',lus[3:7])[0]
    refvalue = struct.unpack('>i',lus[7:11])[0]
    dsf = struct.unpack('>h',lus[11:13])[0]
    nbits = lus[13]
    datatype = lus[14]
    if datatype == 0: # Floating point
        refvalue = np.float32(ieee_int_to_float(refvalue)*10**-dsf)
    elif datatype == 1: # Integer
        refvalue = np.int32(ieee_int_to_float(refvalue)*10**-dsf)
    # Upack each byte starting at byte 15 to end of the local use
    # section, create a binary string and append to the full
    # binary string.
    b = ''
    for i in range(15,len(lus)):
        iword = struct.unpack('>B',lus[i:i+1])[0]
        b += bin(iword).split('b')[1].zfill(8)
    # Iterate over the binary string (b). For each nbits
    # chunk, convert to an integer, including the refvalue,
    # and then convert the int to an ASCII character, then
    # concatenate to wxstring.
    wxstring = ''
    for i in range(0,len(b),nbits):
        wxstring += chr(int(b[i:i+nbits],2)+refvalue)
    # Return string as list, split by null character.
    return list(filter(None,wxstring.split('\0')))


def get_wgrib2_prob_string(probtype,sfacl,svall,sfacu,svalu):
    """
    Return a wgrib2-formatted string explaining probabilistic
    threshold informaiton.  Logic from wgrib2 source, [Prob.c](https://github.com/NOAA-EMC/NCEPLIBS-wgrib2/blob/develop/wgrib2/Prob.c),
    is replicated here.

    Parameters
    ----------

    **`probtype`**: `int` type of probability (Code Table 4.9).

    **`sfacl`**: `int` scale factor of lower limit.

    **`svall`**: `int` scaled value of lower limit.

    **`sfacu`**: `int` scale factor of upper limit.

    **`svalu`**: `int` scaled value of upper limit.

    Returns
    -------

    **`str`**: wgrib2-formatted string of probability threshold.
    """
    probstr = ''
    lower = svall/(10**sfacl)
    upper = svalu/(10**sfacu)
    if probtype == 0:
        probstr = 'prob <%g' % (lower)
    elif probtype == 1:
        probstr = 'prob >%g' % (upper)
    elif probtype == 2:
        if lower == upper:
            probstr = 'prob =%g' % (lower)
        else:
            probstr = 'prob >=%g <%g' % (lower,upper)
    elif probtype == 3:
        probstr = 'prob >%g' % (lower)
    elif probtype == 4:
        probstr = 'prob <%g' % (upper)
    else:
        probstr = ''
    return probstr


