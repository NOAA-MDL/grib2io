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
    Computes the lead time (in units of hours) from using information from
    GRIB2 Identification Section (Section 1), Product Definition Template
    Number, and Product Definition Template (Section 4).

    Parameters
    ----------

    **`idsec`**: seqeunce containing GRIB2 Identification Section (Section 1).

    **`pdtn`**: GRIB2 Product Definition Template Number

    **`idsec`**: seqeunce containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------

    **`lt`**: Lead time in units of hours
    """
    refdate = datetime.datetime(*idsec[5:11])
    if pdtn == 8:
        enddate = datetime.datetime(*pdt[15:21])
        td = enddate - refdate
        lt = (td).total_seconds()/3600.0
    elif pdtn == 9:
        enddate = datetime.datetime(*pdt[22:28])
        td = enddate - refdate
        lt = (td).total_seconds()/3600.0
    elif pdtn == 10:
        enddate = datetime.datetime(*pdt[16:22])
        td = enddate - refdate
        lt = (td).total_seconds()/3600.0
    elif pdtn == 11:
        enddate = datetime.datetime(*pdt[18:24])
        td = enddate - refdate
        lt = (td).total_seconds()/3600.0
    elif pdtn == 12:
        enddate = datetime.datetime(*pdt[17:23])
        td = enddate - refdate
        lt = (td).total_seconds()/3600.0
    else:
        lt = pdt[8]*(tables.get_value_from_table(pdt[7],'scale_time_hours'))
    return int(lt)


def getduration(pdtn,pdt):
    """
    Computes the duration time (in units of hours) from using information from
    Product Definition Template Number, and Product Definition Template (Section 4).

    Parameters
    ----------

    **`pdtn`**: GRIB2 Product Definition Template Number

    **`pdt`**: sequence containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------

    **`dur`**: Duration time in units of hours
    """
    if pdtn == 8:
        dur = pdt[26]*(tables.get_value_from_table(pdt[25],'scale_time_hours'))
    elif pdtn == 9:
        dur = pdt[32]*(tables.get_value_from_table(pdt[31],'scale_time_hours'))
    elif pdtn == 10:
        dur = pdt[27]*(tables.get_value_from_table(pdt[26],'scale_time_hours'))
    elif pdtn == 11:
        dur = pdt[29]*(tables.get_value_from_table(pdt[28],'scale_time_hours'))
    elif pdtn == 12:
        dur = pdt[28]*(tables.get_value_from_table(pdt[27],'scale_time_hours'))
    else:
        dur = 0
    return int(dur)


def decode_mdl_wx_strings(lus):
    """
    Decode GRIB2 Local Use Section to obtain MDL Weather Strings.  The
    decode procedure is defined here:

    https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_mdl_temp2-1.shtml

    Parameters
    ----------

    **`lus`**: GRIB2 Local Use Section containing MDL weather strings.

    Returns
    -------

    **`list`**: List of weather strings.
    """
    assert lus[0] == 1
    # Unpack information related to the simple packing method
    # the packed weather string data.
    ngroups = struct.unpack('>h',lus[1:3])[0]
    nvalues = struct.unpack('>i',lus[3:7])[0]
    refvalue = struct.unpack('>i',lus[7:11])[0]
    dsf = struct.unpack('>h',lus[11:13])[0]
    nbits = lus[13]
    datatype = lus[14]
    if datatype == 0: # Floating point
        refvalue = np.float32(getieeeint(refvalue)*10**-dsf)
    elif datatype == 1: # Integer
        refvalue = np.int32(getieeeint(refvalue)*10**-dsf)
    #print("TEST:",ngroups,nvalues,refvalue,dsf,nbits,datatype)
    # Store the "data" part of the packed weather strings as
    # a binary string.
    b = bin(int.from_bytes(lus[15:],byteorder='big'))
    # Generated begin and end values. Note the offset begins at 2
    # due to the format nature of b (binary string).
    idxb = list(range(2,len(b),nbits))[0:nvalues-1]
    idxe = list(range(2+nbits,len(b)+nbits,nbits))[0:nvalues-1]
    # Iterate over the packed data, converting the nbits space to
    # and integer, then convert integer to an ASCII character.
    wxstring = ''
    for ib,ie in zip(idxb,idxe):
        wxstring += chr(int(b[ib:ie],2)+refvalue)
    # Return string as list, split by null character.
    return wxstring.split('\0')


def decode_ndfd_wx_strings(lus):
    """
    Decode GRIB2 Local Use Section to obtain NDFD Weather Strings.  The
    decode procedure is defined here:

    https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_mdl_temp2-1.shtml

    NOTE: From testing, it seems how the process for packing Section 2 for NDFD
          Weather grids is different than GMOS and thus the need for a different
          method for decoding NDFD Wx vs. GMOS Wx.

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
    ngroups = struct.unpack('>h',lus[1:3])[0]
    nvalues = struct.unpack('>i',lus[3:7])[0]
    refvalue = struct.unpack('>i',lus[7:11])[0]
    dsf = struct.unpack('>h',lus[11:13])[0]
    nbits = lus[13]
    datatype = lus[14]
    if datatype == 0: # Floating point
        refvalue = np.float32(getieeeint(refvalue)*10**-dsf)
    elif datatype == 1: # Integer
        refvalue = np.int32(getieeeint(refvalue)*10**-dsf)
    # Iterate over the data of section 2 in 4-byte (32-bit)
    # words OR 2-byte word at the end. Each word is unpacked
    # as an unsigned integer. Then convert the integer word
    # to a binary string and fill to the appropriate bit
    # size (16 or 32) and concatenate to b (binary string).
    b = ''
    for i in range(15,len(lus),4):
        if len(lus)-i < 4:
            iword = struct.unpack('>H',lus[i:i+2])[0]
            b += bin(iword).split('b')[1].zfill(16)
        else:
            iword = struct.unpack('>I',lus[i:i+4])[0]
            b += bin(iword).split('b')[1].zfill(32)
    # Iterate over the binary string (b). For each nbits
    # chunk, convert to an integer, including the refvalue,
    # and then convert the int to an ASCII character, then
    # concatenate to wxstring.
    wxstring = ''
    for i in range(0,len(b),nbits):
        wxstring += chr(int(b[i:i+nbits],2)+refvalue)
    # Return string as list, split by null character.
    return list(filter(None,wxstring.split('\0')))
