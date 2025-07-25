"""
Collection of utility functions to assist in the encoding and decoding
of GRIB2 Messages.
"""

import datetime
import struct
from decimal import Decimal, localcontext
from typing import Dict, List, Optional, Tuple, Type, Union

import numpy as np
from numpy.typing import ArrayLike

from .. import tables
from .. import templates


def decimal_to_scaled_int(
    value: Union[float, str, int],
    scale_factor: Optional[int] = None,
) -> Tuple[int, int]:
    """
    Convert a float-like value to a scaled integer using the minimal decimal scaling factor.

    The input value is internally converted to a `Decimal` to ensure precise scaling.

    Parameters
    ----------
    value : float, str, or int
        The numeric value to scale.
    scaled_value : int
        The integer result of scaling the original value by `10**scale_factor`.

    Returns
    -------
    scale_factor : int
        The smallest power of 10 such that `value * 10**scale_factor` is an exact integer.
    scaled_value : int
        The integer result of scaling the original value by `10**scale_factor`.
    """
    dec_value = Decimal(str(value))  # Preserve exact decimal representation

    with localcontext() as ctx:
        ctx.prec = 28

        if scale_factor is not None:
            scaled = dec_value * (10 ** scale_factor)
            if scaled != scaled.to_integral_value():
                raise ValueError(
                    f"Value {value} cannot be exactly scaled by 10^{scale_factor}"
                )
            return scale_factor, int(scaled)
        else:
            scale_factor = 0
            while dec_value != dec_value.to_integral_value():
                dec_value *= 10
                scale_factor += 1
                if scale_factor > 20:
                    raise ValueError(
                        f"Could not find exact scale factor for value {value} within bounds."
                    )
            return scale_factor, int(dec_value)


def int2bin(i: int, nbits: int=8, output: Union[Type[str], Type[List]]=str):
    """
    Convert integer to binary string or list

    The struct module unpack using ">i" will unpack a 32-bit integer from a
    binary string.

    Parameters
    ----------
    i
        Integer value to convert to binary representation.
    nbits : default=8
        Number of bits to return.  Valid values are 8 [DEFAULT], 16, 32, and
        64.
    output : default=str
        Return data as `str` [DEFAULT] or `list` (list of ints).

    Returns
    -------
    int2bin
        `str` or `list` (list of ints) of binary representation of the integer
        value.
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
    Convert an IEEE 754 32-bit float to a 32-bit integer.

    Parameters
    ----------
    f : float
        Floating-point value.

    Returns
    -------
    ieee_float_to_int
        `numpy.int32` representation of an IEEE 32-bit float.
    """
    i = struct.unpack('>i',struct.pack('>f',np.float32(f)))[0]
    return np.int32(i)


def ieee_int_to_float(i):
    """
    Convert a 32-bit integer to an IEEE 32-bit float.

    Parameters
    ----------
    i : int
        Integer value.

    Returns
    -------
    ieee_int_to_float
        `numpy.float32` representation of a 32-bit int.
    """
    f = struct.unpack('>f',struct.pack('>i',np.int32(i)))[0]
    return np.float32(f)


def get_leadtime(pdtn: int, pdt: ArrayLike) -> datetime.timedelta:
    """
    Compute lead time as a datetime.timedelta object.

    Using information from GRIB2 Product Definition Template
    Number, and Product Definition Template (Section 4).

    Parameters
    ----------
    pdtn
        GRIB2 Product Definition Template Number
    pdt
        Sequence containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------
    leadTime
        datetime.timedelta object representing the lead time of the GRIB2 message.
    """
    lt = tables.get_value_from_table(pdt[templates.UnitOfForecastTime._key[pdtn]], 'scale_time_seconds')
    lt *= pdt[templates.ValueOfForecastTime._key[pdtn]]
    return datetime.timedelta(seconds=int(lt))


def get_duration(pdtn: int, pdt: ArrayLike) -> datetime.timedelta:
    """
    Compute a time duration as a datetime.timedelta.

    Uses information from Product Definition Template Number, and Product
    Definition Template (Section 4).

    Parameters
    ----------
    pdtn
        GRIB2 Product Definition Template Number
    pdt
        Sequence containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------
    get_duration
        datetime.timedelta object representing the time duration of the GRIB2
        message.
    """
    if pdtn in templates._timeinterval_pdtns:
        ntime = pdt[templates.NumberOfTimeRanges._key[pdtn]]
        duration_unit = tables.get_value_from_table(
            pdt[templates.UnitOfTimeRangeOfStatisticalProcess._key[pdtn]],
            'scale_time_seconds')
        d = ntime * duration_unit * pdt[
            templates.TimeRangeOfStatisticalProcess._key[pdtn]]
    else:
        d = 0
    return datetime.timedelta(seconds=int(d))


def decode_wx_strings(lus: bytes) -> Dict[int, str]:
    """
    Decode GRIB2 Local Use Section to obtain NDFD/MDL Weather Strings.

    The decode procedure is defined
    [here](https://vlab.noaa.gov/web/mdl/nbm-gmos-grib2-wx-info).

    Parameters
    ----------
    lus
        GRIB2 Local Use Section containing NDFD weather strings.

    Returns
    -------
    decode_wx_strings
        Dict of NDFD/MDL weather strings. Keys are an integer value that
        represent the sequential order of the key in the packed local use
        section and the value is the weather key.
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
    #return list(filter(None,wxstring.split('\0')))
    return {n:k for n,k in enumerate(list(filter(None,wxstring.split('\0'))))}


def get_wgrib2_prob_string(
    probtype: int,
    sfacl: int,
    svall: int,
    sfacu: int,
    svalu: int,
) -> str:
    """
    Return a wgrib2-styled string of probabilistic threshold information.

    Logic from wgrib2 source,
    [Prob.c](https://github.com/NOAA-EMC/NCEPLIBS-wgrib2/blob/develop/wgrib2/Prob.c),
    is replicated here.

    Parameters
    ----------
    probtype
        Type of probability (Code Table 4.9).
    sfacl
        Scale factor of lower limit.
    svall
        Scaled value of lower limit.
    sfacu
        Scale factor of upper limit.
    svalu
        Scaled value of upper limit.

    Returns
    -------
    get_wgrib2_prob_string
        wgrib2-formatted string of probability threshold.
    """
    probstr = ''
    if sfacl == -127: sfacl = 0
    if sfacu == -127: sfacu = 0
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
