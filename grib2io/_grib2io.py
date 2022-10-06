"""
Introduction
============

grib2io is a Python package that provides an interface to the [NCEP GRIB2 C (g2c)](https://github.com/NOAA-EMC/NCEPLIBS-g2c)
library for the purpose of reading and writing WMO GRIdded Binary, Edition 2 (GRIB2) messages. A physical file can contain one
or more GRIB2 messages.

GRIB2 file IO is performed directly in Python.  The unpacking/packing of GRIB2 integer, coded metadata and data sections is performed
by the g2c library functions via the g2clib Cython wrapper module.  The decoding/encoding of GRIB2 metadata is translated into more
descriptive, plain language metadata by looking up the integer code values against the appropriate GRIB2 code tables.  These code tables
are a part of the grib2io module.
"""

import builtins
import collections
import copy
import datetime
import os
import re
import struct
import math
import warnings

from dataclasses import dataclass, field
from numpy import ma
import numpy as np
import pyproj

from . import g2clib
from . import tables
from . import templates
from . import utils

DEFAULT_DRT_LEN = 20
DEFAULT_FILL_VALUE = 9.9692099683868690e+36
DEFAULT_NUMPY_INT = np.int64
GRIB2_EDITION_NUMBER = 2
ONE_MB = 1048576 # 1 MB in units of bytes


class open():
    """
    GRIB2 File Object.  A physical file can contain one or more GRIB2 messages.  When instantiated,
    class `grib2io.open`, the file named `filename` is opened for reading (`mode = 'r'`) and is
    automatically indexed.  The indexing procedure reads some of the GRIB2 metadata for all GRIB2 Messages.

    A GRIB2 Message may contain submessages whereby Section 2-7 can be repeated.  grib2io accommodates
    for this by flattening any GRIB2 submessages into multiple individual messages.

    Attributes
    ----------

    **`mode`**: File IO mode of opening the file.

    **`name`**: Full path name of the GRIB2 file.

    **`messages`**: Count of GRIB2 Messages contained in the file.

    **`current_message`**: Current position of the file in units of GRIB2 Messages.

    **`size`**: Size of the file in units of bytes.

    **`closed`** `True` is file handle is close; `False` otherwise.

    **`variables`**: Tuple containing a unique list of variable short names (i.e. GRIB2 abbreviation names).

    **`levels`**: Tuple containing a unique list of wgrib2-formatted level/layer strings.
    """
    __slots__ = ('_filehandle','_hasindex','_index','mode','name','messages',
                 'current_message','size','closed','variables','levels','_pos')
    def __init__(self, filename, mode='r'):
        """
        `open` Constructor

        Parameters
        ----------

        **`filename`**: File name containing GRIB2 messages.

        **`mode `**: File access mode where `r` opens the files for reading only;
        `w` opens the file for writing.

        """
        if mode in ['a','r','w']:
            mode = mode+'b'
        self._filehandle = builtins.open(filename,mode=mode,buffering=ONE_MB)
        self._hasindex = False
        self._index = {}
        self.mode = mode
        self.name = os.path.abspath(filename)
        self.messages = 0
        self.current_message = 0
        self.size = os.path.getsize(self.name)
        self.closed = self._filehandle.closed
        if 'r' in self.mode: self._build_index()
        # FIX: Cannot perform reads on mode='a'
        #if 'a' in self.mode and self.size > 0: self._build_index()
        if self._hasindex:
            self.variables = tuple(sorted(set(filter(None,self._index['shortName']))))
            self.levels = tuple(sorted(set(filter(None,self._index['levelString']))))


    def __delete__(self, instance):
        """
        """
        self.close()
        del self._index


    def __enter__(self):
        """
        """
        return self


    def __exit__(self, atype, value, traceback):
        """
        """
        self.close()


    def __iter__(self):
        """
        """
        return self

    def __len__(self):
        """
        """
        return self.messages


    def __next__(self):
        """
        """
        if self.current_message < self.messages:
            return self.read()[0]
        else:
            self.seek(0)
            raise StopIteration


    def __repr__(self):
        """
        """
        strings = []
        #keys = self.__dict__.keys()
        for k in self.__slots__:
            if k.startswith('_'): continue
            strings.append('%s = %s\n'%(k,eval('self.'+k)))
        return ''.join(strings)


    def __getitem__(self, key):
        """
        """
        if isinstance(key,slice):
            if key.start is None and key.stop is None and key.step is None:
                beg = 1
                end = self.messages+1
                inc = 1
            else:
                beg, end, inc = key.indices(self.messages)
            return [self[i][0] for i in range(beg,end,inc)]
        elif isinstance(key,int):
            if key == 0:
                warnings.warn("GRIB2 Message number 0 does not exist.")
                return None
            self._filehandle.seek(self._index['offset'][key])
            #return [Grib2Message(msg=self._filehandle.read(self._index['size'][key]),
            gdtn = self._index['gridDefinitionTemplateNumber'][key]
            pdtn = self._index['productDefinitionTemplateNumber'][key]
            drtn = self._index['dataRepresentationTemplateNumber'][key]
            msgsize = self._index['dataOffset'][key]-self._index['offset'][key]
            #return [grib2_message_creator(gdtn,pdtn,drtn)(msg=self._filehandle.read(self._index['size'][key]),
            return [grib2_message_creator(gdtn,pdtn,drtn)(msg=self._filehandle.read(msgsize),
                                 source=self,
                                 num=self._index['messageNumber'][key])]
        elif isinstance(key,str):
            return self.select(shortName=key)
        else:
            raise KeyError('Key must be an integer, slice, or GRIB2 variable shortName.')


    def _build_index(self):
        """
        Perform indexing of GRIB2 Messages.
        """
        # Initialize index dictionary
        self._index['offset'] = [None]
        self._index['dataOffset'] = [None]
        self._index['discipline'] = [None]
        self._index['edition'] = [None]
        self._index['size'] = [None]
        self._index['submessageOffset'] = [None]
        self._index['submessageBeginSection'] = [None]
        self._index['isSubmessage'] = [None]
        self._index['messageNumber'] = [None]
        self._index['identificationSection'] = [None]
        self._index['refDate'] = [None]
        self._index['gridDefinitionTemplateNumber'] = [None]
        self._index['productDefinitionTemplateNumber'] = [None]
        self._index['productDefinitionTemplate'] = [None]
        self._index['typeOfFirstFixedSurface'] = [None]
        self._index['valueOfFirstFixedSurface'] = [None]
        self._index['typeOfGeneratingProcess'] = [None]
        self._index['level'] = [None]
        self._index['leadTime'] = [None]
        self._index['duration'] = [None]
        self._index['shortName'] = [None]
        self._index['bitMap'] = [None]
        self._index['levelString'] = [None]
        self._index['probString'] = [None]
        self._index['ny'] = [None]
        self._index['nx'] = [None]
        self._index['dataRepresentationTemplateNumber'] = [None]

        # Iterate
        while True:
            try:
                # Read first 4 bytes and decode...looking for "GRIB"
                pos = self._filehandle.tell()
                header = struct.unpack('>4s',self._filehandle.read(4))[0].decode()

                # Test header. Then get information from GRIB2 Section 0: the discipline
                # number, edition number (should always be 2), and GRIB2 message size.
                # Then iterate to check for submessages.
                if header == 'GRIB':
                    _issubmessage = False
                    _submsgoffset = 0
                    _submsgbegin = 0

                    # Read and unpack Section 0. Note that this is not done through
                    # the g2clib.
                    self._filehandle.seek(self._filehandle.tell()+2)
                    discipline = int(struct.unpack('>B',self._filehandle.read(1))[0])
                    edition = int(struct.unpack('>B',self._filehandle.read(1))[0])
                    assert edition == 2
                    size = struct.unpack('>Q',self._filehandle.read(8))[0]

                    # Read and unpack Section 1
                    secsize = struct.unpack('>i',self._filehandle.read(4))[0]
                    secnum = struct.unpack('>B',self._filehandle.read(1))[0]
                    assert secnum == 1
                    self._filehandle.seek(self._filehandle.tell()-5)
                    _grbmsg = self._filehandle.read(secsize)
                    _grbpos = 0
                    _grbsec1,_grbpos = g2clib.unpack1(_grbmsg,_grbpos,np.empty)
                    _grbsec1 = _grbsec1.tolist()
                    _refdate = datetime.datetime(*_grbsec1[5:11])
                    _isndfd = True if _grbsec1[0:2] == [8,65535] else False
                    secrange = range(2,8)
                    while 1:
                        for num in secrange:
                            secsize = struct.unpack('>i',self._filehandle.read(4))[0]
                            secnum = struct.unpack('>B',self._filehandle.read(1))[0]
                            if secnum == num:
                                if secnum == 3:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 3
                                    _gds,_gdt,_deflist,_grbpos = g2clib.unpack3(_grbmsg,_grbpos,np.empty)
                                    _gds = _gds.tolist()
                                    _gdt = _gdt.tolist()
                                elif secnum == 4:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 4
                                    _pdt,_pdtnum,_coordlist,_grbpos = g2clib.unpack4(_grbmsg,_grbpos,np.empty)
                                    _pdt = _pdt.tolist()
                                    _varinfo = tables.get_varinfo_from_table(discipline,_pdt[0],_pdt[1],isNDFD=_isndfd)
                                elif secnum == 5:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 5
                                    _drt,_drtn,_npts,self._pos = g2clib.unpack5(_grbmsg,_grbpos,np.empty)
                                elif secnum == 6:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 6. Save bitmap
                                    _bmap,_bmapflag = g2clib.unpack6(_grbmsg,_gds[1],_grbpos,np.empty)
                                    if _bmapflag == 0:
                                        _bmap_save = copy.deepcopy(_bmap)
                                    elif _bmapflag == 254:
                                        _bmap = copy.deepcopy(_bmap_save)
                                elif secnum == 7:
                                    # Unpack Section 7. No need to read it, just index the position in file.
                                    _datapos = self._filehandle.tell()-5
                                    self._filehandle.seek(self._filehandle.tell()+secsize-5)
                                else:
                                    self._filehandle.seek(self._filehandle.tell()+secsize-5)
                            else:
                                if num == 2 and secnum == 3:
                                    pass # Allow this.  Just means no Local Use Section.
                                else:
                                    _issubmessage = True
                                    _submsgoffset = (self._filehandle.tell()-5)-(self._index['offset'][self.messages])
                                    _submsgbegin = secnum
                                self._filehandle.seek(self._filehandle.tell()-5)
                                continue
                        trailer = struct.unpack('>4s',self._filehandle.read(4))[0].decode()
                        if trailer == '7777':
                            self.messages += 1
                            self._index['offset'].append(pos)
                            self._index['dataOffset'].append(_datapos)
                            self._index['discipline'].append(discipline)
                            self._index['edition'].append(edition)
                            self._index['size'].append(size)
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            self._index['identificationSection'].append(_grbsec1)
                            self._index['refDate'].append(_refdate)
                            self._index['gridDefinitionTemplateNumber'].append(_gds[-1])
                            self._index['nx'].append(int(_gdt[7]))
                            self._index['ny'].append(int(_gdt[8]))
                            self._index['productDefinitionTemplateNumber'].append(_pdtnum)
                            self._index['productDefinitionTemplate'].append(_pdt)
                            self._index['typeOfFirstFixedSurface'].append(templates.Grib2Metadata(_pdt[9],table='4.5').definition[0])
                            scaleFactorOfFirstFixedSurface = _pdt[10]
                            scaledValueOfFirstFixedSurface = _pdt[11]
                            valueOfFirstFixedSurface = scaledValueOfFirstFixedSurface/(10.**scaleFactorOfFirstFixedSurface)
                            self._index['typeOfGeneratingProcess'].append(_pdt[2])
                            self._index['valueOfFirstFixedSurface'].append(valueOfFirstFixedSurface)
                            self._index['level'].append(tables.get_wgrib2_level_string(*_pdt[9:15]))
                            self._index['leadTime'].append(utils.getleadtime(_grbsec1,_pdtnum,_pdt))
                            self._index['duration'].append(utils.getduration(_pdtnum,_pdt))
                            self._index['shortName'].append(_varinfo[2])
                            self._index['bitMap'].append(_bmap)
                            self._index['levelString'].append(tables.get_wgrib2_level_string(*_pdt[9:15]))
                            if _pdtnum in [5,9]:
                                self._index['probString'].append(utils.get_wgrib2_prob_string(*_pdt[17:22]))
                            else:
                                self._index['probString'].append('')
                            if _issubmessage:
                                self._index['submessageOffset'].append(_submsgoffset)
                                self._index['submessageBeginSection'].append(_submsgbegin)
                            else:
                                self._index['submessageOffset'].append(0)
                                self._index['submessageBeginSection'].append(_submsgbegin)
                            self._index['dataRepresentationTemplateNumber'].append(_drtn)
                            break
                        else:
                            self._filehandle.seek(self._filehandle.tell()-4)
                            self.messages += 1
                            self._index['offset'].append(pos)
                            self._index['dataOffset'].append(_datapos)
                            self._index['discipline'].append(discipline)
                            self._index['edition'].append(edition)
                            self._index['size'].append(size)
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            self._index['identificationSection'].append(_grbsec1)
                            self._index['refDate'].append(_refdate)
                            self._index['gridDefinitionTemplateNumber'].append(_gds[-1])
                            self._index['nx'].append(int(_gdt[7]))
                            self._index['ny'].append(int(_gdt[8]))
                            self._index['productDefinitionTemplateNumber'].append(_pdtnum)
                            self._index['productDefinitionTemplate'].append(_pdt)
                            self._index['leadTime'].append(utils.getleadtime(_grbsec1,_pdtnum,_pdt))
                            self._index['duration'].append(utils.getduration(_pdtnum,_pdt))
                            self._index['shortName'].append(_varinfo[2])
                            self._index['bitMap'].append(_bmap)
                            self._index['levelString'].append(tables.get_wgrib2_level_string(*_pdt[9:15]))
                            if _pdtnum in [5,9]:
                                self._index['probString'].append(utils.get_wgrib2_prob_string(*_pdt[17:22]))
                            else:
                                self._index['probString'].append('')
                            self._index['submessageOffset'].append(_submsgoffset)
                            self._index['submessageBeginSection'].append(_submsgbegin)
                            self._index['dataRepresentationTemplateNumber'].append(_drtn)
                            continue

            except(struct.error):
                self._filehandle.seek(0)
                break

        self._hasindex = True


    def close(self):
        """
        Close the file handle
        """
        if not self._filehandle.closed:
            self._filehandle.close()
            self.closed = self._filehandle.closed


    def read(self, num=1):
        """
        Read num GRIB2 messages from the current position

        Parameters
        ----------

        **`num`**: integer number of GRIB2 Message to read.

        Returns
        -------

        **`list`**: list of `grib2io.Grib2Message` instances.
        """
        msgs = []
        if self.tell() >= self.messages: return msgs
        if num > 0:
            if num == 1:
                msgrange = [self.tell()+1]
            else:
                beg = self.tell()+1
                end = self.tell()+1+num if self.tell()+1+num <= self.messages else self.messages
                msgrange = range(beg,end+1)
            for n in msgrange:
                self._filehandle.seek(self._index['offset'][n])
                #msgs.append(Grib2Message(msg=self._filehandle.read(self._index['size'][n]),
                gdtn = self._index['gridDefinitionTemplateNumber'][n]
                pdtn = self._index['productDefinitionTemplateNumber'][n]
                drtn = self._index['dataRepresentationTemplateNumber'][n]
                msgsize = self._index['dataOffset'][n]-self._index['offset'][n]
                #msgs.append(grib2_message_creator(gdtn,pdtn,drtn)(msg=self._filehandle.read(self._index['size'][n]),
                msgs.append(grib2_message_creator(gdtn,pdtn,drtn)(msg=self._filehandle.read(msgsize),
                                         source=self,
                                         num=self._index['messageNumber'][n]))
                self.current_message += 1
        return msgs


    def rewind(self):
        """
        Set the position of the file to zero in units of GRIB2 messages.
        """
        self.seek(0)


    def seek(self, pos):
        """
        Set the position within the file in units of GRIB2 messages.

        Parameters
        ----------

        **`pos`**: GRIB2 Message number to set the read pointer to.
        """
        if self._hasindex:
            if pos == 0:
                self._filehandle.seek(pos)
                self.current_message = pos
            elif pos > 0:
                self._filehandle.seek(self._index['offset'][pos-1])
                self.current_message = pos


    def tell(self):
        """
        Returns the position of the file in units of GRIB2 Messages.
        """
        return self.current_message


    def select(self,**kwargs):
        """
        Returns a list of `grib2io.Grib2Message` instances based on the selection **`**kwargs`**.

        The following keywords are currently supported:

        **`duration : int`** specifiying the time duration (in unit of hours) of a GRIB2 Message that is
        determined from a period of time.

        **`leadTime : datetime.timedelta`** object representing the lead time.

        **`level : str`** wgrib2-formatted layer/level string.

        **`percentile : int`** specify the percentile value.

        **`refDate : datetime.datetime`** object representing then reference date.

        **`shortName : str`** the GRIB2 `shortName`.  This is the abbreviation name found in the NCEP GRIB2 tables.

        **`threshold : str`** wgrib2-formatted probability threshold string.
        """
        kwargs_allowed = ['duration','leadTime','level','percentile','refDate','shortName','threshold']
        idxs = {}
        for k,v in kwargs.items():
            if k not in kwargs_allowed: continue
            if k == 'duration':
                idxs[k] = np.where(np.asarray([i if i is not None else None for i in self._index['duration']])==v)[0]
            elif k == 'leadTime':
                idxs[k] = np.where(np.asarray([i if i is not None else None for i in self._index['leadTime']])==v)[0]
            elif k == 'level':
                idxs[k] = np.where(np.array(self._index['levelString'])==v)[0]
            elif k == 'percentile':
                tmp1 = np.where(np.asarray(self._index['productDefinitionTemplateNumber'])==6)[0]
                tmp2 = np.where(np.asarray(self._index['productDefinitionTemplateNumber'])==10)[0]
                idxs[k] = [i for i in np.concatenate((tmp1,tmp2)) if self._index['productDefinitionTemplate'][i][15]==v]
                del tmp1,tmp2
            elif k == 'refDate':
                idxs[k] = np.where(np.asarray(self._index['refDate'])==v)[0]
            elif k == 'shortName':
                idxs[k] = np.where(np.array(self._index['shortName'])==v)[0]
            elif k == 'threshold':
                idxs[k] = np.where(np.array(self._index['probString'])==v)[0]
        idxsarr = np.concatenate(tuple(idxs.values()))
        nidxs = len(idxs.keys())
        if nidxs == 1:
            return [self[int(i)][0] for i in idxsarr]
        elif nidxs > 1:
            return [self[int(i)][0] for i in [ii[0] for ii in collections.Counter(idxsarr).most_common() if ii[1] == nidxs]]


    def write(self, msg):
        """
        Writes a packed GRIB2 message to file.

        Parameters
        ----------

        **`msg`**: instance of `Grib2Message`.
        """
        if isinstance(msg,Grib2Message):
            self._filehandle.write(msg._msg)
            self.size = os.path.getsize(self.name)
            self.messages += 1
            self.current_message += 1
        else:
            raise TypeError("msg must be a Grib2Message object.")


@dataclass
class Grib2MessageBase:
    section0: list = field(init=False,repr=True,default=templates.Grib2Section())
    section1: list = field(init=False,repr=True,default=templates.Grib2Section())
    #section2: list = field(init=False,repr=True,default=templates.Grib2Section())
    #section3: list = field(init=False,repr=True,default=templates.Grib2Section())

    discipline = templates.Discipline()

    originatingCenter = templates.OriginatingCenter()
    originatingSubCenter = templates.OriginatingSubCenter()
    masterTableInfo = templates.MasterTableInfo()
    localTableInfo = templates.LocalTableInfo()
    significanceOfReferenceTime = templates.SignificanceOfReferenceTime()
    year = templates.Year()
    month = templates.Month()
    day = templates.Day()
    hour = templates.Hour()
    minute = templates.Minute()
    second = templates.Second()
    refDate = templates.RefDate()
    validDate = templates.ValidDate()
    productionStatus = templates.ProductionStatus()
    typeOfData = templates.TypeOfData()

    gridDefinitionSection: list = field(init=False,repr=True,default=templates.Grib2Section())
    gridDefinitionTemplateNumber = templates.GridDefinitionTemplateNumber()
    gridDefinitionTemplate: list = field(init=False,repr=True,default=templates.GridDefinitionTemplate())

    shapeOfEarth = templates.ShapeOfEarth()
    earthRadius = templates.EarthRadius()
    earthMajorAxis = templates.EarthMajorAxis()
    earthMinorAxis = templates.EarthMinorAxis()
    resolutionAndComponentFlags = templates.ResolutionAndComponentFlags()
    ny = templates.Ny()
    nx = templates.Nx()
    scanModeFlags = templates.ScanModeFlags()

    productDefinitionTemplateNumber = templates.ProductDefinitionTemplateNumber()
    productDefinitionTemplate: list = field(init=False,repr=True,default=templates.ProductDefinitionTemplate())
    parameterCategory = templates.ParameterCategory()
    parameterNumber = templates.ParameterNumber()
    fullName = templates.FullName()
    units = templates.Units()
    shortName = templates.ShortName()
    typeOfGeneratingProcess = templates.TypeOfGeneratingProcess()
    backgroundGeneratingProcessIdentifier = templates.BackgroundGeneratingProcessIdentifier()
    generatingProcess = templates.GeneratingProcess()
    unitOfTimeRange = templates.UnitOfTimeRange()
    leadTime = templates.LeadTime()
    typeOfFirstFixedSurface = templates.TypeOfFirstFixedSurface()
    scaleFactorOfFirstFixedSurface = templates.ScaleFactorOfFirstFixedSurface()
    unitOfFirstFixedSurface = templates.UnitOfFirstFixedSurface()
    scaledValueOfFirstFixedSurface = templates.ScaledValueOfFirstFixedSurface()
    valueOfFirstFixedSurface = templates.ValueOfFirstFixedSurface()
    typeOfSecondFixedSurface = templates.TypeOfSecondFixedSurface()
    scaleFactorOfSecondFixedSurface = templates.ScaleFactorOfSecondFixedSurface()
    unitOfSecondFixedSurface = templates.UnitOfSecondFixedSurface()
    scaledValueOfSecondFixedSurface = templates.ScaledValueOfSecondFixedSurface()
    valueOfSecondFixedSurface = templates.ValueOfSecondFixedSurface()
    level = templates.Level()
    duration = templates.Duration()

    numberOfDataPoints = templates.NumberOfDataPoints()
    dataRepresentationTemplateNumber = templates.DataRepresentationTemplateNumber()
    dataRepresentationTemplate: list = field(init=False,repr=True,default=templates.DataRepresentationTemplate())
    typeOfValues = templates.TypeOfValues()

    def __init__(self, msg=None, source=None, num=-1, discipline=None, idsect=None):
        """
        Class Constructor. Instantiation of this class can handle a GRIB2 message from an existing
        file or the creation of new GRIB2 message.  To create a new GRIB2 message, provide the
        appropriate values to the arguments `discipline` and `idsect`.  When these 2 arguments
        are not `None`, then a new GRIB2 message is created. NOTE: All other keyword arguments
        are ignored when a new message is created.

        ...

        Parameters
        ----------

        **`msg`**: Binary string representing the GRIB2 Message read from file.

        **`source`**: Source of where where this GRIB2 message originated
        from (i.e. the input file). This allow for interaction with the
        instance of `grib2io.open`. Default is None.

        **`num`**: integer GRIB2 Message number from `grib2io.open`. Default value is -1.

        **`discipline`**: integer GRIB2 Discipline [GRIB2 Table 0.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table0-0.shtml)

        **`idsect`**: Sequence containing GRIB1 Identification Section values (Section 1).

        | Index | Description |
        | :---: | :---        |
        | idsect[0] | Id of orginating centre - [ON388 - Table 0](https://www.nco.ncep.noaa.gov/pmb/docs/on388/table0.html)|
        | idsect[1] | Id of orginating sub-centre - [ON388 - Table C](https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablec.html)|
        | idsect[2] | GRIB Master Tables Version Number - [Code Table 1.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-0.shtml)|
        | idsect[3] | GRIB Local Tables Version Number - [Code Table 1.1](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-1.shtml)|
        | idsect[4] | Significance of Reference Time - [Code Table 1.2](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-2.shtml)|
        | idsect[5] | Reference Time - Year (4 digits)|
        | idsect[6] | Reference Time - Month|
        | idsect[7] | Reference Time - Day|
        | idsect[8] | Reference Time - Hour|
        | idsect[9] | Reference Time - Minute|
        | idsect[10] | Reference Time - Second|
        | idsect[11] | Production status of data - [Code Table 1.3](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-3.shtml)|
        | idsect[12] | Type of processed data - [Code Table 1.4](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-4.shtml)|
        """
        self._source = source
        self._msgnum = num
        self._pos = 0
        self._datapos = 0
        self._sections = []
        self.hasLocalUseSection = False
        self.isNDFD = False
        if discipline is not None and idsect is not None:
            # New message
            self._msg,self._pos = g2clib.grib2_create(np.array([discipline,GRIB2_EDITION_NUMBER],DEFAULT_NUMPY_INT),
                                                      np.array(idsect,DEFAULT_NUMPY_INT))
            self._sections += [0,1]
        else:
            # Existing message
            self._msg = msg
        #self.md5 = {}
        if self._msg is not None and self._source is not None: self.unpack()

    def __repr__(self):
        """
        """
        strings = []
        for k,v in self.__dict__.items():
            if k.startswith('_'): continue
            if isinstance(v,str):
                strings.append('%s = \'%s\'\n'%(k,v))
            elif isinstance(v,int):
                strings.append('%s = %d\n'%(k,v))
            elif isinstance(v,float):
                strings.append('%s = %f\n'%(k,v))
            elif isinstance(v,bool):
                strings.append('%s = %s\n'%(k,v))
            else:
                strings.append('%s = %s\n'%(k,v))
        return ''.join(strings)


    def unpack(self):
        """
        Unpacks GRIB2 section data from the packed, binary message.
        """
        # Section 0 - Indicator Section
        self.indicatorSection = []
        self.indicatorSection.append(struct.unpack('>4s',self._msg[0:4])[0])
        self.indicatorSection.append(struct.unpack('>H',self._msg[4:6])[0])
        self.indicatorSection.append(self._msg[6])
        self.indicatorSection.append(self._msg[7])
        self.indicatorSection.append(struct.unpack('>Q',self._msg[8:16])[0])
        self._pos = 16
        self._sections.append(0)
        self._section0 = self.indicatorSection #NEW
        #self.md5[0] = _getmd5str(self.indicatorSection)

        # Section 1 - Identification Section via g2clib.unpack1()
        self.identificationSection,self._pos = g2clib.unpack1(self._msg,self._pos,np.empty)
        self.identificationSection = self.identificationSection.tolist()
        self._section1 = self.identificationSection #NEW
        self._sections.append(1)
        if self.identificationSection[0:2] == [8,65535]: self.isNDFD = True

        # After Section 1, perform rest of GRIB2 Decoding inside while loop
        # to account for sub-messages.
        sectnum = 1
        while True:
            if self._msg[self._pos:self._pos+4].decode('ascii','ignore') == '7777':
                break

            #print(self._pos,len(self._msg))
            if self._pos == len(self._msg):
                break

            # Read the length and section number.
            sectlen = struct.unpack('>i',self._msg[self._pos:self._pos+4])[0]
            prevsectnum = sectnum
            sectnum = struct.unpack('>B',self._msg[self._pos+4:self._pos+5])[0]

            # If the previous section number is > current section number, then
            # we have encountered a submessage.
            if prevsectnum > sectnum: break

            # Handle submessage accordingly.
            if isinstance(self._source,open):
                if self._source._index['isSubmessage'][self._msgnum]:
                    if sectnum == self._source._index['submessageBeginSection'][self._msgnum]:
                        self._pos = self._source._index['submessageOffset'][self._msgnum]

            # Section 2 - Local Use Section.
            if sectnum == 2:
                self._lus = self._msg[self._pos+5:self._pos+sectlen]
                self._pos += sectlen
                self.hasLocalUseSection = True
                self._sections.append(2)
                #self.md5[2] = _getmd5str(self.identificationSection)

            # Section 3 - Grid Definition Section.
            elif sectnum == 3:
                _gds,_gdt,_deflist,self._pos = g2clib.unpack3(self._msg,self._pos,np.empty)
                #self.gridDefinitionSection = _gds.tolist()
                self._gridDefinitionSection = _gds.tolist() #NEW
          #     self.gridDefinitionTemplateNumber = templates.Grib2Metadata(int(_gds[4]),table='3.1')
                #self.gridDefinitionTemplate = _gdt.tolist()
                self._gridDefinitionTemplate = _gdt.tolist() #NEW
                self._dxsign = 1.0
                self._dysign = 1.0
                if self._gridDefinitionSection[4] in [50,51,52,1200]:
                    self._earthparams = None
                else:
                    self._earthparams = tables.earth_params[str(self._gridDefinitionTemplate[0])]
                if self._gridDefinitionSection[4] in [0,1,203,205,32768,32769]:
                    self._llscalefactor = float(self._gridDefinitionTemplate[9])
                    if self._gridDefinitionTemplate[10] == 4294967295:
                        self._gridDefinitionTemplate[10] = -1
                    self._lldivisor = float(self._gridDefinitionTemplate[10])
                    if self._llscalefactor == 0: self._llscalefactor = 1.
                    if self._lldivisor <= 0: self._lldivisor = 1.e6
                    self._xydivisor = self._lldivisor
                    if self._gridDefinitionTemplate[11] > self._gridDefinitionTemplate[14]:
                        self._dysign = -1.0
                    if self._gridDefinitionTemplate[12] > self._gridDefinitionTemplate[15]:
                        self._dxsign = -1.0
                else:
                    self._lldivisor = 1.e6
                    self._xydivisor = 1.e3
                    self._llscalefactor = 1.
                self.defList = _deflist.tolist()
                self._sections.append(3)
                #self.md5[3] = _getmd5str([self.gridDefinitionTemplateNumber]+self.gridDefinitionTemplate)

            # Section 4 - Product Definition Section.
            elif sectnum == 4:
                _pdt,_pdtn,_coordlst,self._pos = g2clib.unpack4(self._msg,self._pos,np.empty)
                #self.productDefinitionTemplate = _pdt.tolist()
                self._productDefinitionTemplate = _pdt.tolist() # NEW
                #self.productDefinitionTemplateNumber = templates.Grib2Metadata(int(_pdtn),table='4.0')
                self._productDefinitionTemplateNumber = int(_pdtn) # NEW
                self.coordinateList = _coordlst.tolist()
                self._varinfo = tables.get_varinfo_from_table(self._section0[2],self._productDefinitionTemplate[0],
                                                              self._productDefinitionTemplate[1],isNDFD=self.isNDFD)
                self._fixedsfc1info = [None, None] if self._productDefinitionTemplate[9] == 255 else \
                                      tables.get_value_from_table(self._productDefinitionTemplate[9],'4.5')
                self._fixedsfc2info = [None, None] if self._productDefinitionTemplate[12] == 255 else \
                                      tables.get_value_from_table(self._productDefinitionTemplate[12],'4.5')
                self._sections.append(4)
                #self.md5[4] = _getmd5str([self.productDefinitionTemplateNumber]+self.productDefinitionTemplate)

            # Section 5 - Data Representation Section.
            elif sectnum == 5:
                _drt,_drtn,_npts,self._pos = g2clib.unpack5(self._msg,self._pos,np.empty)
                self._dataRepresentationTemplate = _drt.tolist()
                self._dataRepresentationTemplateNumber = int(_drtn)
                self._numberOfDataPoints = _npts
                self._sections.append(5)
                #self.md5[5] = _getmd5str([self.dataRepresentationTemplateNumber]+self.dataRepresentationTemplate)

            # Section 6 - Bitmap Section.
            elif sectnum == 6:
                _bmap,_bmapflag = g2clib.unpack6(self._msg,self.gridDefinitionSection[1],self._pos,np.empty)
                self.bitMapFlag = _bmapflag
                if self.bitMapFlag == 0:
                    self.bitMap = _bmap
                elif self.bitMapFlag == 254:
                    # Value of 254 says to use a previous bitmap in the file.
                    self.bitMapFlag = 0
                    if isinstance(self._source,open):
                        self.bitMap = self._source._index['bitMap'][self._msgnum]
                self._pos += sectlen # IMPORTANT: This is here because g2clib.unpack6() does not return updated position.
                self._sections.append(6)
                #self.md5[6] = None

            # Section 7 - Data Section (data unpacked when data() method is invoked).
            elif sectnum == 7:
                self._datapos = self._pos
                self._pos += sectlen # REMOVE THIS WHEN UNPACKING DATA IS IMPLEMENTED
                self._sections.append(7)
                #self.md5[7] = _getmd5str(self._msg[self._datapos:sectlen+1])

            else:
                errmsg = 'Unknown section number = %i' % sectnum
                raise ValueError(errmsg)


    def data(self, fill_value=DEFAULT_FILL_VALUE, masked_array=True, expand=True, order=None,
             map_keys=False):
        """
        Returns an unpacked data grid.

        Parameters
        ----------

        **`fill_value`**: Missing or masked data is filled with this value or default value given by
        `DEFAULT_FILL_VALUE`

        **`masked_array`**: If `True` [DEFAULT], return masked array if there is bitmap for missing
        or masked data.

        **`expand`**: If `True` [DEFAULT], Reduced Gaussian grids are expanded to regular Gaussian grids.

        **`order`**: If 0 [DEFAULT], nearest neighbor interpolation is used if grid has missing
        or bitmapped values. If 1, linear interpolation is used for expanding reduced Gaussian grids.

        **`map_keys`**: If `True`, data values will be mapped to the string-based keys that are stored
        in the Local Use Section (section 2) of the GRIB2 Message or in a code table as specified in the
        units (i.e. "See Table 4.xxx").

        Returns
        -------

        **`numpy.ndarray`**: A numpy.ndarray with shape (ny,nx). By default the array dtype=np.float32,
        but could be np.int32 if Grib2Message.typeOfValues is integer.  The array dtype will be
        string-based if map_keys=True.
        """
        t1 = datetime.datetime.now()
        t2 = datetime.datetime.now()
        if not hasattr(self,'scanModeFlags'):
        #if self.scanModeFlags is None:
            raise ValueError('Unsupported grid definition template number %s'%self.gridDefinitionTemplateNumber)
        else:
            if self.scanModeFlags[2]:
                storageorder='F'
            else:
                storageorder='C'
        #print(f'scan settings before array unpack took: {datetime.datetime.now() - t2}')
        if order is None:
            if (self.dataRepresentationTemplateNumber in [2,3] and
                self.dataRepresentationTemplate[6] != 0) or self.bitMapFlag == 0:
                order = 0
            else:
                order = 1
        drtnum = self.dataRepresentationTemplateNumber.value
        drtmpl = np.asarray(self.dataRepresentationTemplate,dtype=DEFAULT_NUMPY_INT)
        gdtnum = self.gridDefinitionTemplateNumber.value
        gdtmpl = np.asarray(self.gridDefinitionTemplate,dtype=DEFAULT_NUMPY_INT)
        t2 = datetime.datetime.now()
        ndpts = self.numberOfDataPoints
        gds = self.gridDefinitionSection
        ngrdpts = gds[1]
        # TEST
        #ipos = self._datapos
        ##print(f'before array unpack took: {datetime.datetime.now() - t1}')
        #t1 = datetime.datetime.now()
        #fld1 = g2clib.unpack7(self._msg,gdtnum,gdtmpl,drtnum,drtmpl,ndpts,ipos,np.empty,storageorder=storageorder)
        ##print(f'array unpack took: {datetime.datetime.now() - t1}')
        #t1 = datetime.datetime.now()
        # TEST
        # NEW
        self._source._filehandle.seek(self._source._index['dataOffset'][self._msgnum]) # Position file pointer to the beginning of data section.
        ipos = 0
        datasize = (self._source._index['size'][self._msgnum]+self._source._index['offset'][self._msgnum]) - \
                   self._source._index['dataOffset'][self._msgnum]
        fld1 = g2clib.unpack7(self._source._filehandle.read(datasize),gdtnum,gdtmpl,drtnum,drtmpl,ndpts,ipos,np.empty,storageorder=storageorder)
        # NEW
        # Apply bitmap.
        if self.bitMapFlag == 0:
            fld = fill_value*np.ones(ngrdpts,'f')
            np.put(fld,np.nonzero(self.bitMap),fld1)
            if masked_array:
                fld = ma.masked_values(fld,fill_value)
        # Missing values instead of bitmap
        elif masked_array and hasattr(self,'priMissingValue'):
            if hasattr(self,'secMissingValue'):
                mask = np.logical_or(fld1==self.priMissingValue,fld1==self.secMissingValue)
            else:
                mask = fld1 == self.priMissingValue
            fld = ma.array(fld1,mask=mask)
        else:
            fld = fld1
        if self.nx is not None and self.ny is not None: # Rectangular grid.
            if ma.isMA(fld):
                fld = ma.reshape(fld,(self.ny,self.nx))
            else:
                fld = np.reshape(fld,(self.ny,self.nx))
        else:
            if gds[2] and gdtnum == 40: # Reduced global Gaussian grid.
                if expand:
                    from . import redtoreg
                    self.nx = 2*self.ny
                    lonsperlat = self.defList
                    if ma.isMA(fld):
                        fld = ma.filled(fld)
                        fld = redtoreg._redtoreg(self.nx,lonsperlat.astype(np.long),
                                                 fld.astype(np.double),fill_value)
                        fld = ma.masked_values(fld,fill_value)
                    else:
                        fld = redtoreg._redtoreg(self.nx,lonsperlat.astype(np.long),
                                                 fld.astype(np.double),fill_value)
        #print(f'bitmap/missing: {datetime.datetime.now() - t1}')
        # Check scan modes for rect grids.
        if self.nx is not None and self.ny is not None:
            if self.scanModeFlags[3]:
                fldsave = fld.astype('f') # casting makes a copy
                fld[1::2,:] = fldsave[1::2,::-1]
        #print(f'bitmap/missing and scan modes for rect: {datetime.datetime.now() - t1}')

        # Set data to integer according to GRIB metadata
        if self.typeOfValues == "Integer": fld = fld.astype(np.int32)

        # Map the data values to their respective definitions.
        if map_keys:
            fld = fld.astype(np.int32).astype(str)
            if (self.identificationSection[0] == 7 and \
                self.identificationSection[1] == 14 and \
                self.shortName == 'PWTHER') or \
               (self.identificationSection[0] == 8 and \
                self.identificationSection[1] == 65535 and \
                self.shortName == 'WX'):
                keys = utils.decode_wx_strings(self._lus)
                for n,k in enumerate(keys):
                    fld = np.where(fld==str(n+1),k,fld)
            else:
                # For data whose units are defined in a code table
                tbl = re.findall(r'\d\.\d+',self.units,re.IGNORECASE)[0]
                for k,v in tables.get_table(tbl).items():
                    fld = np.where(fld==k,v,fld)
        #print(f'after array unpack took: {datetime.datetime.now() - t1}')
        return fld


    def latlons(self):
        """Alias for `grib2io.Grib2Message.grid` method"""
        return self.grid()


    def grid(self):
        """
        Return lats,lons (in degrees) of grid. Currently can handle reg. lat/lon,
        global Gaussian, mercator, stereographic, lambert conformal, albers equal-area,
        space-view and azimuthal equidistant grids.

        Returns
        -------

        **`lats, lons : numpy.ndarray`**

        Returns two numpy.ndarrays with dtype=numpy.float32 of grid latitudes and
        longitudes in units of degrees.
        """
        gdtn = self.gridDefinitionTemplateNumber.value
        gdtmpl = self.gridDefinitionTemplate
        reggrid = self.gridDefinitionSection[2] == 0 # This means regular 2-d grid
        if self.earthMajorAxis is not None: self.projParameters['a']=self.earthMajorAxis
        if self.earthMajorAxis is not None: self.projParameters['b']=self.earthMinorAxis
        if gdtn == 0:
            # Regular lat/lon grid
            lon1, lat1 = self.longitudeFirstGridpoint, self.latitudeFirstGridpoint
            lon2, lat2 = self.longitudeLastGridpoint, self.latitudeLastGridpoint
            dlon = self.gridlengthXDirection
            dlat = self.gridlengthYDirection
            lats = np.arange(lat1,lat2+dlat,dlat)
            lons = np.arange(lon1,lon2+dlon,dlon)
            # flip if scan mode says to.
            #if self.scanModeFlags[0]:
            #    lons = lons[::-1]
            #if not self.scanModeFlags[1]:
            #    lats = lats[::-1]
            lons,lats = np.meshgrid(lons,lats) # make 2-d arrays.
        elif gdtn == 40: # Gaussian grid (only works for global!)
            from utils.gauss_grids import gaussian_latitudes
            lon1, lat1 = self.longitudeFirstGridpoint, self.latitudeFirstGridpoint
            lon2, lat2 = self.longitudeLastGridpoint, self.latitudeLastGridpoint
            nlats = self.ny
            if not reggrid: # Reduced Gaussian grid.
                nlons = 2*nlats
                dlon = 360./nlons
            else:
                nlons = self.nx
                dlon = self.gridlengthXDirection
            lons = np.arange(lon1,lon2+dlon,dlon)
            # Compute Gaussian lats (north to south)
            lats = gaussian_latitudes(nlats)
            if lat1 < lat2:  # reverse them if necessary
                lats = lats[::-1]
            # flip if scan mode says to.
            #if self.scanModeFlags[0]:
            #    lons = lons[::-1]
            #if not self.scanModeFlags[1]:
            #    lats = lats[::-1]
            lons,lats = np.meshgrid(lons,lats)
        elif gdtn in [10,20,30,31,110]:
            # Mercator, Lambert Conformal, Stereographic, Albers Equal Area, Azimuthal Equidistant
            dx,dy = self.gridlengthXDirection, self.gridlengthYDirection
            lon1,lat1 = self.longitudeFirstGridpoint, self.latitudeFirstGridpoint
            pj = pyproj.Proj(self.projParameters)
            llcrnrx, llcrnry = pj(lon1,lat1)
            x = llcrnrx+dx*np.arange(self.nx)
            y = llcrnry+dy*np.arange(self.ny)
            x,y = np.meshgrid(x, y)
            lons,lats = pj(x, y, inverse=True)
        elif gdtn == 90:
            # Satellite Projection
            dx = self.gridlengthXDirection
            dy = self.gridlengthYDirection
            #self.projParameters['proj']=self.proj4_proj
            #self.projParameters['lon_0']=self.proj4_lon_0
            #self.projParameters['lat_0']=self.proj4_lat_0
            #self.projParameters['h']=self.proj4_h
            pj = pyproj.Proj(self.projParameters)
            x = dx*np.indices((self.ny,self.nx),'f')[1,:,:]
            x -= 0.5*x.max()
            y = dy*np.indices((self.ny,self.nx),'f')[0,:,:]
            y -= 0.5*y.max()
            lons,lats = pj(x,y,inverse=True)
            # Set lons,lats to 1.e30 where undefined
            abslons = np.fabs(lons)
            abslats = np.fabs(lats)
            lons = np.where(abslons < 1.e20, lons, 1.e30)
            lats = np.where(abslats < 1.e20, lats, 1.e30)
        else:
            raise ValueError('Unsupported grid')

        return lats.astype('f'), lons.astype('f')


    def addlocal(self, ludata):
        """
        Add a Local Use Section [(Section 2)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_sect2.shtml)
        to the GRIB2 message.

        Parameters
        ----------

        **`ludata : bytes`**: Local Use data.
        """
        assert isinstance(ludata,bytes)
        self._msg,self._pos = g2clib.grib2_addlocal(self._msg,ludata)
        self.hasLocalUseSection = True
        self._sections.append(2)


    def addgrid(self, gdsinfo, gdtmpl, deflist=None):
        """
        Add a Grid Definition Section [(Section 3)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_doc/grib2_sect3.shtml)
        to the GRIB2 message.

        Parameters
        ----------

        **`gdsinfo`**: Sequence containing information needed for the grid definition section.

        | Index | Description |
        | :---: | :---        |
        | gdsinfo[0] | Source of grid definition - [Code Table 3.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-0.shtml)|
        | gdsinfo[1] | Number of data points|
        | gdsinfo[2] | Number of octets for optional list of numbers defining number of points|
        | gdsinfo[3] | Interpetation of list of numbers defining number of points - [Code Table 3.11](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-11.shtml)|
        | gdsinfo[4] | Grid Definition Template Number - [Code Table 3.1](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-1.shtml)|

        **`gdtmpl`**: Sequence of values for the specified Grid Definition Template. Each
        element of this integer array contains an entry (in the order specified) of Grid
        Definition Template 3.NN

        **`deflist`**: Sequence containing the number of grid points contained in each
        row (or column) of a non-regular grid.  Used if gdsinfo[2] != 0.
        """
        if 3 in self._sections:
            raise ValueError('GRIB2 Message already contains Grid Definition Section.')
        if deflist is not None:
            _deflist = np.array(deflist,dtype=DEFAULT_NUMPY_INT)
        else:
            _deflist = None
        gdtnum = gdsinfo[4]
        if gdtnum in [0,1,2,3,40,41,42,43,44,203,205,32768,32769]:
            self.scanModeFlags = utils.int2bin(gdtmpl[18],output=list)[0:4]
        elif gdtnum == 10: # mercator
            self.scanModeFlags = utils.int2bin(gdtmpl[15],output=list)[0:4]
        elif gdtnum == 20: # stereographic
            self.scanModeFlags = utils.int2bin(gdtmpl[17],output=list)[0:4]
        elif gdtnum == 30: # lambert conformal
            self.scanModeFlags = utils.int2bin(gdtmpl[17],output=list)[0:4]
        elif gdtnum == 31: # albers equal area.
            self.scanModeFlags = utils.int2bin(gdtmpl[17],output=list)[0:4]
        elif gdtnum == 90: # near-sided vertical perspective satellite projection
            self.scanModeFlags = utils.int2bin(gdtmpl[16],output=list)[0:4]
        elif gdtnum == 110: # azimuthal equidistant.
            self.scanModeFlags = utils.int2bin(gdtmpl[15],output=list)[0:4]
        elif gdtnum == 120:
            self.scanModeFlags = utils.int2bin(gdtmpl[6],output=list)[0:4]
        elif gdtnum == 204: # curvilinear orthogonal
            self.scanModeFlags = utils.int2bin(gdtmpl[18],output=list)[0:4]
        elif gdtnum in [1000,1100]:
            self.scanModeFlags = utils.int2bin(gdtmpl[12],output=list)[0:4]
        self._msg,self._pos = g2clib.grib2_addgrid(self._msg,
                                                   np.array(gdsinfo,dtype=DEFAULT_NUMPY_INT),
                                                   np.array(gdtmpl,dtype=DEFAULT_NUMPY_INT),
                                                   _deflist)
        self._sections.append(3)


    def addfield(self, field, pdtnum, pdtmpl, coordlist=None, packing="complex-spdiff", **packing_opts):
        """
        Add a Product Definition, Data Representation, Bitmap, and Data Sections
        to `Grib2Message` instance (i.e. Sections 4-7).  Must be called after the grid
        definition section has been added (`addfield`).

        Parameters
        ----------

        **`field`**: Numpy array of data values to pack.  If field is a masked array, then
        a bitmap is created from the mask.

        **`pdtnum`**: integer Product Definition Template Number - [Code Table 4.0](http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-0.shtml)

        **`pdtmpl`**: Sequence with the data values for the specified Product Definition
        Template (N=pdtnum).  Each element of this integer array contains an entry (in
        the order specified) of Product Definition Template 4.N.

        **`coordlist`**: Sequence containing floating point values intended to document the
        vertical discretization with model data on hybrid coordinate vertical levels. Default is `None`.

        **`packing`**: String to specify the type of packing. Valid options are the following:

        | Packing Scheme | Description |
        | :---:          | :---:       |
        | 'simple'         | [Simple packing](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-0.shtml) |
        | 'complex'        | [Complex packing](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-2.shtml) |
        | 'complex-spdiff' | [Complex packing with Spatial Differencing](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-3.shtml) |
        | 'jpeg'           | [JPEG compression](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-40.shtml) |
        | 'png'            | [PNG compression](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-41.shtml) |
        | 'spectral-simple'| [Spectral Data - Simple packing](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-50.shtml) |
        | 'spectral-complex'| [Spectral Data - Complex packing](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-51.shtml) |

        **`**packing_opts`**: Packing keyword arguments. The keywords are the same as Grib2Message attribute names for
        the Data Representation Template (Section 5) metadata. Valid keywords per packing scheme are the following:

        | Packing Scheme | Keyword Arguments |
        | :---:          | :---:                      |
        | 'simple'     | `binScaleFactor`, `decScaleFactor` |
        | 'complex'     | `binScaleFactor`, `decScaleFactor`, `priMissingValue`, [`secMissingValue`] |
        | 'complex-spdiff'     | `binScaleFactor`, `decScaleFactor`, `spatialDifferenceOrder`, `priMissingValue`, [`secMissingValue`] |
        | 'jpeg'     | `binScaleFactor`, `decScaleFactor` |
        | 'png'     | `binScaleFactor`, `decScaleFactor` |
        | 'spectral-simple'     | `binScaleFactor`, `decScaleFactor` |
        | 'spectral-complex'     | `binScaleFactor`, `decScaleFactor` |
        """
        if self._sections[-1] != 3:
            raise ValueError('addgrid() must be called before addfield()')
        if self.scanModeFlags is not None:
            if self.scanModeFlags[3]:
                fieldsave = field.astype('f') # Casting makes a copy
                field[1::2,:] = fieldsave[1::2,::-1]
        fld = field.astype('f')
        if ma.isMA(field) and ma.count_masked(field) > 0:
            bitmapflag = 0
            bmap = 1-np.ravel(field.mask.astype(DEFAULT_NUMPY_INT))
        else:
            bitmapflag = 255
            bmap = None
        if coordlist is not None:
            crdlist = np.array(coordlist,'f')
        else:
            crdlist = None

        # Set data representation template number and template values
        drtnum = -1
        drtmpl = np.zeros((DEFAULT_DRT_LEN),dtype=DEFAULT_NUMPY_INT)
        if packing == "simple":
            drtnum = 0
            drtmpl[1] = packing_opts["binScaleFactor"]
            drtmpl[2] = packing_opts["decScaleFactor"]
        elif packing == "complex" or packing == "complex-spdiff":
            if packing == "complex":
                drtnum = 2
            if packing == "complex-spdiff":
                drtnum = 3
                drtmpl[16] = packing_opts['spatialDifferenceOrder']
            drtmpl[1] = packing_opts["binScaleFactor"]
            drtmpl[2] = packing_opts["decScaleFactor"]
            if set(("priMissingValue","secMissingValue")).issubset(packing_opts):
                drtmpl[6] = 2
                drtmpl[7] = utils.ieee_float_to_int(packing_opts["priMissingValue"])
                drtmpl[8] = utils.ieee_float_to_int(packing_opts["secMissingValue"])
            else:
                if "priMissingValue" in packing_opts.keys():
                    drtmpl[6] = 1
                    drtmpl[7] = utils.ieee_float_to_int(packing_opts["priMissingValue"])
                else:
                    drtmpl[6] = 0
        elif packing == "jpeg":
            drtnum = 40
            drtmpl[1] = packing_opts["binScaleFactor"]
            drtmpl[2] = packing_opts["decScaleFactor"]
        elif packing == "png":
            drtnum = 41
            drtmpl[1] = packing_opts["binScaleFactor"]
            drtmpl[2] = packing_opts["decScaleFactor"]
        elif packing == "spectral-simple":
            drtnum = 50
            drtmpl[1] = packing_opts["binScaleFactor"]
            drtmpl[2] = packing_opts["decScaleFactor"]
        elif packing == "spectral-complex":
            drtnum = 51
            drtmpl[1] = packing_opts["binScaleFactor"]
            drtmpl[2] = packing_opts["decScaleFactor"]

        pdtnum = pdtnum.value if isinstance(pdtnum,Grib2Metadata) else pdtnum

        self._msg,self._pos = g2clib.grib2_addfield(self._msg,
                                                    pdtnum,
                                                    np.array(pdtmpl,dtype=DEFAULT_NUMPY_INT),
                                                    crdlist,
                                                    drtnum,
                                                    drtmpl,
                                                    np.ravel(fld),
                                                    bitmapflag,
                                                    bmap)
        self._sections.append(4)
        self._sections.append(5)
        if bmap is not None: self._sections.append(6)
        self._sections.append(7)


    def end(self):
        """
        Add End Section (Section 8) to the GRIB2 message. A GRIB2 message
        is not complete without an end section.  Once an end section is added,
        the GRIB2 message can be written to file.
        """
        self._msg, self._pos = g2clib.grib2_end(self._msg)
        self._sections.append(8)

    def to_bytes(self, validate=True):
        """
        Return grib data in byte format. Useful for exporting data in non-file formats.
        For example, can be used to output grib data directly to S3 using the boto3 client
        without the need to write a temporary file to upload first.

        Parameters
        ----------
        **`validate`**: bool (Default: True) If true, validates first/last four bytes for proper formatting, else
        returns None. If False, message is output as is.

        Returns
        -------
        Returns GRIB2 formatted message as bytes.
        """
        if validate:
            if str(self._msg[0:4] + self._msg[-4:], 'utf-8') == 'GRIB7777':
                return self._msg
            else:
                return None
        else:
            return self._msg


def grib2_message_creator(gdtn,pdtn,drtn):
    """
    Dynamically create Grib2Message class inheriting from supported
    grid definition, product definition, and data representation
    templates.  Each template is a dataclass with class variable
    definitions for each attribute related to that template.

    Parameters
    ----------

    **`gdtn : int`**:

    Grid Definition Template Number.

    **`pdtn : int`**:

    Product Definition Template Number.

    **`drtn : int`**:

    Data Representation Template Number.
    """
    Gdt = templates.gdt_class_by_gdtn(gdtn)
    Pdt = templates.pdt_class_by_pdtn(pdtn)
    Drt = templates.drt_class_by_drtn(drtn)
    class Grib2Message(Grib2MessageBase, Gdt, Pdt, Drt):
        pass
    return Grib2Message
