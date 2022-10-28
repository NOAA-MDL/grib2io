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
import typing


from dataclasses import dataclass, field
from numpy import ma
import numpy as np
import pyproj

from . import g2clib
from . import tables
from . import templates
from grib2io.templates import Grib2Metadata
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
        if mode in {'a','r','w'}:
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
            return [Grib2Message.from_grib2io_openfile(self,key)]
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
        self._index['data_offset'] = [None]
        self._index['section0'] = [None]
        self._index['section1'] = [None]
        self._index['section3'] = [None]
        self._index['section4'] = [None]
        self._index['section5'] = [None]
        self._index['discipline'] = [None]
        self._index['edition'] = [None]
        self._index['size'] = [None]
        self._index['indicatorSection'] = [None]
        self._index['submessageOffset'] = [None]
        self._index['submessageBeginSection'] = [None]
        self._index['isSubmessage'] = [None]
        self._index['messageNumber'] = [None]
        self._index['identificationSection'] = [None]
        self._index['refDate'] = [None]
        self._index['gridDefinitionTemplateNumber'] = [None]
        self._index['gridDefinitionTemplate'] = [None]
        self._index['gridDefinitionSection'] = [None]
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
        self._index['bitMapFlag'] = [None]
        self._index['levelString'] = [None]
        self._index['probString'] = [None]
        self._index['ny'] = [None]
        self._index['nx'] = [None]
        self._index['dataRepresentationTemplateNumber'] = [None]
        self._index['dataRepresentationTemplate'] = [None]

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
                                    section3 = np.concatenate((_gds,_gdt))
                                    section3 = np.where(section3==4294967295,-1,section3)
                                elif secnum == 4:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 4
                                    _numcoord, _pdt,_pdtnum,_coordlist,_grbpos = g2clib.unpack4(_grbmsg,_grbpos,np.empty)
                                    _pdt = _pdt.tolist()
                                    _varinfo = tables.get_varinfo_from_table(discipline,_pdt[0],_pdt[1],isNDFD=_isndfd)
                                    section4 = np.concatenate((np.array((_numcoord,_pdtnum)),_pdt))
                                elif secnum == 5:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 5
                                    _drt,_drtn,_npts,self._pos = g2clib.unpack5(_grbmsg,_grbpos,np.empty)
                                    section5 = np.concatenate((np.array((_npts,_drtn)),_drt))
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
                            self._index['data_offset'].append(_datapos)
                            self._index['discipline'].append(discipline)
                            self._index['edition'].append(edition)
                            self._index['size'].append(size)
                            self._index['indicatorSection'].append(['GRIB',0,discipline,edition,size])
                            self._index['section0'].append(['GRIB',0,discipline,edition,size])
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            self._index['identificationSection'].append(_grbsec1)
                            self._index['section1'].append(_grbsec1)
                            self._index['section3'].append(section3)
                            self._index['section4'].append(section4)
                            self._index['section5'].append(section5)
                            self._index['refDate'].append(_refdate)
                            self._index['gridDefinitionTemplateNumber'].append(_gds[-1])
                            self._index['gridDefinitionTemplate'].append(_gdt)
                            self._index['gridDefinitionSection'].append(_gds)
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
                            self._index['bitMapFlag'].append(_bmapflag)
                            self._index['levelString'].append(tables.get_wgrib2_level_string(*_pdt[9:15]))
                            if _pdtnum in {5,9}:
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
                            self._index['dataRepresentationTemplate'].append(_drt)
                            break
                        else:
                            self._filehandle.seek(self._filehandle.tell()-4)
                            self.messages += 1
                            self._index['offset'].append(pos)
                            self._index['data_offset'].append(_datapos)
                            self._index['discipline'].append(discipline)
                            self._index['edition'].append(edition)
                            self._index['size'].append(size)
                            self._index['indicatorSection'].append(['GRIB',0,discipline,edition,size])
                            self._index['section0'].append(['GRIB',0,discipline,edition,size])
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            self._index['identificationSection'].append(_grbsec1)
                            self._index['section1'].append(_grbsec1)
                            self._index['section3'].append(section3)
                            self._index['section4'].append(section4)
                            self._index['section5'].append(section5)
                            self._index['refDate'].append(_refdate)
                            self._index['gridDefinitionTemplateNumber'].append(_gds[-1])
                            self._index['gridDefinitionTemplate'].append(_gdt)
                            self._index['gridDefinitionSection'].append(_gds)
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
                            self._index['bitMapFlag'].append(_bmapflag)
                            if _pdtnum in {5,9}:
                                self._index['probString'].append(utils.get_wgrib2_prob_string(*_pdt[17:22]))
                            else:
                                self._index['probString'].append('')
                            self._index['submessageOffset'].append(_submsgoffset)
                            self._index['submessageBeginSection'].append(_submsgbegin)
                            self._index['dataRepresentationTemplateNumber'].append(_drtn)
                            self._index['dataRepresentationTemplate'].append(_drt)
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

        **`num : int`**: GRIB2 message number to read.

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
                msgs.append(Grib2Message.from_grib2io_openfile(self,self._index['messageNumber'][n]))
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

        **`pos : int`**: GRIB2 Message number to set the read pointer to.
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

        **`msg`**: `Grib2Message` object to write.
        """
        if isinstance(msg,Grib2Message):
            self._filehandle.write(msg._msg)
            self.size = os.path.getsize(self.name)
            self.messages += 1
            self.current_message += 1
        else:
            raise TypeError("msg must be a Grib2Message object.")


@dataclass
class Grib2Message:
    # GRIB2 Sections
    section0: np.array = field(init=True,repr=True)
    section1: np.array = field(init=True,repr=True)
    section3: np.array = field(init=True,repr=True)
    section4: np.array = field(init=True,repr=True)
    section5: np.array = field(init=True,repr=True)
    bitMapFlag: int = field(init=True,repr=False,default=255)

    # Section 0 looked up attributes
    indicatorSection: np.array = field(init=False,repr=False,default=templates.IndicatorSection())
    discipline: Grib2Metadata = field(init=False,repr=False,default=templates.Discipline())

    # Section 1 looked up attributes
    identificationSection: np.array = field(init=False,repr=False,default=templates.IdentificationSection)
    originatingCenter: Grib2Metadata = field(init=False,repr=False,default=templates.OriginatingCenter())
    originatingSubCenter: Grib2Metadata = field(init=False,repr=False,default=templates.OriginatingSubCenter())
    masterTableInfo: Grib2Metadata = field(init=False,repr=False,default=templates.MasterTableInfo())
    localTableInfo: Grib2Metadata = field(init=False,repr=False,default=templates.LocalTableInfo())
    significanceOfReferenceTime: Grib2Metadata = field(init=False,repr=False,default=templates.SignificanceOfReferenceTime())
    year: int = field(init=False,repr=False,default=templates.Year())
    month: int = field(init=False,repr=False,default=templates.Month())
    day: int = field(init=False,repr=False,default=templates.Day())
    hour: int = field(init=False,repr=False,default=templates.Hour())
    minute: int = field(init=False,repr=False,default=templates.Minute())
    second: int = field(init=False,repr=False,default=templates.Second())
    refDate: datetime.datetime = field(init=False,repr=True,default=templates.RefDate())
    productionStatus: Grib2Metadata = field(init=False,repr=False,default=templates.ProductionStatus())
    typeOfData: Grib2Metadata = field(init=False,repr=False,default=templates.TypeOfData())

    # Section 3 looked up common attributes.  Other looked up attributes are available according
    # to the Grid Definition Template.
    gridDefinitionSection: np.array = field(init=False,repr=True,default=templates.GridDefinitionSection())
    gridDefinitionTemplateNumber: Grib2Metadata = field(init=False,repr=True,default=templates.GridDefinitionTemplateNumber())
    gridDefinitionTemplate: list = field(init=False,repr=True,default=templates.GridDefinitionTemplate())
    _earthparams: dict = field(init=False,repr=False,default=templates.EarthParams())
    _dxsign: float = field(init=False,repr=False,default=templates.DxSign())
    _dysign: float = field(init=False,repr=False,default=templates.DySign())
    _llscalefactor: float = field(init=False,repr=False,default=templates.LLScaleFactor())
    _lldivisor: float = field(init=False,repr=False,default=templates.LLDivisor())
    _xydivisor: float = field(init=False,repr=False,default=templates.XYDivisor())
    shapeOfEarth: Grib2Metadata = field(init=False,repr=False,default=templates.ShapeOfEarth())
    earthRadius: float = field(init=False,repr=False,default=templates.EarthRadius())
    earthMajorAxis: float = field(init=False,repr=False,default=templates.EarthMajorAxis())
    earthMinorAxis: float = field(init=False,repr=False,default=templates.EarthMinorAxis())
    resolutionAndComponentFlags: list = field(init=False,repr=False,default=templates.ResolutionAndComponentFlags())
    ny: int = field(init=False,repr=True,default=templates.Ny())
    nx: int = field(init=False,repr=True,default=templates.Nx())
    scanModeFlags: list = field(init=False,repr=True,default=templates.ScanModeFlags())

    # Section 4 looked up common attributes.  Other looked up attributes are available according
    # to the Product Definition Template.
    productDefinitionTemplateNumber: Grib2Metadata = field(init=False,repr=True,default=templates.ProductDefinitionTemplateNumber())
    productDefinitionTemplate: np.array = field(init=False,repr=True,default=templates.ProductDefinitionTemplate())
    _varinfo: list = field(init=False, repr=True, default=templates.VarInfo())
    _fixedsfc1info: list = field(init=False, repr=True, default=templates.FixedSfc1Info())
    _fixedsfc2info: list = field(init=False, repr=True, default=templates.FixedSfc2Info())
    parameterCategory: int = field(init=False,repr=False,default=templates.ParameterCategory())
    parameterNumber: int = field(init=False,repr=False,default=templates.ParameterNumber())
    fullName: str = field(init=False, repr=True, default=templates.FullName())
    units: str = field(init=False, repr=True, default=templates.Units())
    shortName: str = field(init=False, repr=True, default=templates.ShortName())
    typeOfGeneratingProcess: Grib2Metadata = field(init=False,repr=False,default=templates.TypeOfGeneratingProcess())
    generatingProcess: Grib2Metadata = field(init=False, repr=False, default=templates.GeneratingProcess())
    backgroundGeneratingProcessIdentifier: int = field(init=False,repr=False,default=templates.BackgroundGeneratingProcessIdentifier())
    unitOfTimeRange: Grib2Metadata = field(init=False,repr=True,default=templates.UnitOfTimeRange())
    leadTime: datetime.timedelta = field(init=False,repr=True,default=templates.LeadTime())
    typeOfFirstFixedSurface: Grib2Metadata = field(init=False,repr=True,default=templates.TypeOfFirstFixedSurface())
    scaleFactorOfFirstFixedSurface: int = field(init=False,repr=False,default=templates.ScaleFactorOfFirstFixedSurface())
    scaledValueOfFirstFixedSurface: int = field(init=False,repr=False,default=templates.ScaledValueOfFirstFixedSurface())
    unitOfFirstFixedSurface: str = field(init=False,repr=True,default=templates.UnitOfFirstFixedSurface())
    valueOfFirstFixedSurface: int = field(init=False,repr=True,default=templates.ValueOfFirstFixedSurface())
    typeOfSecondFixedSurface: Grib2Metadata = field(init=False,repr=True,default=templates.TypeOfSecondFixedSurface())
    scaleFactorOfSecondFixedSurface: int = field(init=False,repr=False,default=templates.ScaleFactorOfSecondFixedSurface())
    scaledValueOfSecondFixedSurface: int = field(init=False,repr=False,default=templates.ScaledValueOfSecondFixedSurface())
    unitOfSecondFixedSurface: str = field(init=False,repr=True,default=templates.UnitOfSecondFixedSurface())
    valueOfSecondFixedSurface: int = field(init=False,repr=True,default=templates.ValueOfSecondFixedSurface())
    level: str = field(init=False, repr=True, default=templates.Level())
    duration: datetime.timedelta = field(init=False,repr=True,default=templates.Duration())
    validDate: datetime.datetime = field(init=False,repr=True,default=templates.ValidDate())

    # Section 5 looked up common attributes.  Other looked up attributes are available according
    # to the Data Representation Template.
    numberOfDataPoints: int = field(init=False,repr=False,default=templates.NumberOfDataPoints())
    dataRepresentationTemplateNumber: Grib2Metadata = field(init=False,repr=False,default=templates.DataRepresentationTemplateNumber())
    dataRepresentationTemplate: list = field(init=False,repr=False,default=templates.DataRepresentationTemplate())
    typeOfValues: Grib2Metadata = field(init=False,repr=True,default=templates.TypeOfValues())

    @classmethod
    def from_grib2io_openfile(cls, openfile, loc):

        index = openfile._index

        Msg = create_message_cls(index['gridDefinitionTemplateNumber'][loc],
                index['productDefinitionTemplateNumber'][loc],
                index['dataRepresentationTemplateNumber'][loc])

        msg = Msg(index['section0'][loc],
                index['section1'][loc],
                index['section3'][loc],
                index['section4'][loc],
                index['section5'][loc],
                index['bitMapFlag'][loc])
        msg.bitMap = index['bitMap'][loc]

        shape = (msg.ny,msg.nx)
        ndim = 2
        dtype = 'float32'
        data_offset = index['data_offset'][loc]
        data_size = (index['offset'][loc] + index['size'][loc]) - data_offset
        msg._isNDFD = np.all(msg.section1[0:2]==[8,65535])
        msg._msgnum = loc
        msg._data = Grib2MessageOnDiskArray(shape, ndim, dtype, openfile._filehandle, msg, data_offset, data_size)

        return msg


    def __repr__(self):
        ''' easier to read repr'''
        strings = []
        for k,field in self.__dataclass_fields__.items():
            if field.repr:
                strings.append(f'{k} = {getattr(self,k)}\n')
        return ''.join(strings)


    def attrs_by_section(self, sect):
        """
        Provide a tuple of attribute names for the given GRIB2 section.

        Parameters
        ----------

        **`sect : int`** GRIB2 section number.

        Returns
        -------

        Tuple of strings of attribute names for the given GRIB2 section.
        """
        if sect in {0,1}:
            return tuple(templates._section_attrs[sect])
        elif sect in {3,4,5}:
            def _find_class_index(n):
                _key = {3:'Grid', 4:'Product', 5:'Data'}
                for i,c in enumerate(self.__class__.__mro__):
                    if _key[n] in c.__name__:
                        return i
                else:
                    return None
            return tuple(templates._section_attrs[sect]+
                         self.__class__.__mro__[_find_class_index(sect)].attrs)
        else:
            return tuple([])


    def pack(self, field, local=None):
        """
        Packs GRIB2 section data into a binary message.  It is the user's responsibility
        to populate the GRIB2 section information.

        Parameters
        ----------

        **`field`**: Numpy array of data values to pack.  If field is a masked array, then
        a bitmap is created from the mask.

        **`local`**: Local use data.  If the GRIB2 message is to contain local use informatiom,
        provide as bytes.
        """
        self._msg,self._pos = g2clib.grib2_create(np.array(self.indicatorSection[2:4],DEFAULT_NUMPY_INT),
                                                  np.array(self.identificationSection,DEFAULT_NUMPY_INT))
        self._sections += [0,1]

        if local is not None:
            assert isinstance(local,bytes)
            self._msg,self._pos = g2clib.grib2_addlocal(self._msg,local)
            self.hasLocalUseSection = True
            self._sections.append(2)

        self._msg,self._pos = g2clib.grib2_addgrid(self._msg,np.array(self.gridDefinitionSection,dtype=DEFAULT_NUMPY_INT),
                                                   np.array(self.gridDefinitionTemplate,dtype=DEFAULT_NUMPY_INT),self._deflist)
        self._sections.append(3)

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
            self._msg,self._pos = g2clib.grib2_addfield(self._msg,self.productDefinitionTemplateNumber,
                                                        np.array(self.productDefinitionTemplate,dtype=DEFAULT_NUMPY_INT),
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

        self._msg, self._pos = g2clib.grib2_end(self._msg)
        self._sections.append(8)


    @property
    def data(self) -> np.array:
        ''' accessing the data attribute loads data into memmory '''
        if hasattr(self,'_data'):
            if isinstance(self._data, Grib2MessageOnDiskArray):
                t = datetime.datetime.now()
                self._data = np.asarray(self._data)
                print(f'load took {datetime.datetime.now() - t}')
            return self._data
        raise ValueError

    @data.setter
    def data(self, data):
        if not isinstance(data, np.ndarray):
            raise ValueError('Grib2Message data only supports numpy arrays')
        self._data = data


    def __getitem__(self, item):
        return self.data[item]


    def __setitem__(self, item):
        raise NotImplementedError('assignment of data not supported via setitem')


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
        elif gdtn in {10,20,30,31,110}:
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
        if gdtnum in {0,1,2,3,40,41,42,43,44,203,205,32768,32769}:
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
        elif gdtnum in {1000,1100}:
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
        Return packed GRIB2 message in bytes format. This will be Useful for
        exporting data in non-file formats.  For example, can be used to
        output grib data directly to S3 using the boto3 client without the
        need to write a temporary file to upload first.

        Parameters
        ----------

        **`validate : bool`**:

        If `True` (DEFAULT), validates first/last four bytes for proper
        formatting, else returns None. If `False`, message is output as is.

        Returns
        -------
        Returns GRIB2 formatted message as bytes.
        """
        if validate:
            if str(self._msg[0:4]+self._msg[-4:],'utf-8') == 'GRIB7777':
                return self._msg
            else:
                return None
        else:
            return self._msg


@dataclass
class Grib2MessageOnDiskArray:
    shape: str
    ndim: str
    dtype: str
    filehandle: open
    msg: Grib2Message
    data_offset: int
    data_size: int

    def __array__(self, dtype=None):
        data =  _data(self.filehandle, self.msg, self.data_offset, self.data_size)
        return np.asarray(data, dtype=dtype)


def _data(filehandle: open, msg: Grib2Message, data_offset: int, data_size: int)-> np.array:
    """
    Returns an unpacked data grid.

    Returns
    -------

    **`numpy.ndarray`**: A numpy.ndarray with shape (ny,nx). By default the array dtype=np.float32,
    but could be np.int32 if Grib2Message.typeOfValues is integer.
    """
    gridDefinitionTemplate = msg.section3[5:]
    gridDefinitionSection = msg.section3[0:5]
    dataRepresentationTemplate = msg.section5[2:]
    drtnum = msg.section5[1]
    nx, ny = msg.nx, msg.ny
    bitmapflag = msg.bitMapFlag
    bitmap = msg.bitMap
    scanModeFlags = msg.scanModeFlags
    # is there any missing value stored other than the bitmask?
#   priMissingValue = 9999.0 #msg.priMissingValue
#   secMissingValue = 9998.0 #msg.secMissingValue

    try:
        if scanModeFlags[2]:
            storageorder='F'
        else:
            storageorder='C'
    except AttributeError:
        raise ValueError('Unsupported grid definition template number %s'%gridDefinitionTemplateNumber)

   #'''    **`order`**: If 0 [DEFAULT], nearest neighbor interpolation is used if grid has missing
   #            or bitmapped values. If 1, linear interpolation is used for expanding reduced Gaussian grids.
   #'''
    # I didn't see where order gets used?
    if (drtnum in {2,3} and
        dataRepresentationTemplate[6] != 0) or bitmapflag == 0:
        order = 0
    else:
        order = 1

    drtmpl = np.asarray(dataRepresentationTemplate,dtype=DEFAULT_NUMPY_INT)
    gdtnum = gridDefinitionSection[4]
    gdtmpl = np.asarray(gridDefinitionTemplate,dtype=DEFAULT_NUMPY_INT)
    gds = gridDefinitionSection
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
    filehandle.seek(data_offset) # Position file pointer to the beginning of data section.
    ipos = 0
    fld = g2clib.unpack7(filehandle.read(data_size),gdtnum,gdtmpl,drtnum,drtmpl,ngrdpts,ipos,np.empty,storageorder=storageorder)
    #fld = np.ones(ngrdpts)
    # NEW
#   # convert missing values to nan
#   if priMissingValue is not None:
#       fld[fld==priMissingValue] = np.nan
#   if secMissingValue is not None:
#       fld[fld==secMissingValue] = np.nan
    # Apply bitmap.
    if bitmapflag == 0:
        #fld = fill_value*np.ones(ngrdpts,'f')
        np.put(fld,np.nonzero(bitmap),np.nan)
#       if masked_array:
#           fld = ma.masked_values(fld,fill_value)
    # Missing values instead of bitmap
#   elif masked_array and hasattr(msg,'priMissingValue'):
#       if hasattr(msg,'secMissingValue'):
#           mask = np.logical_or(fld1==msg.priMissingValue,fld1==msg.secMissingValue)
#       else:
#           mask = fld1 == msg.priMissingValue
#       fld = ma.array(fld1,mask=mask)
#   else:
#       fld = fld1
    if nx is not None and ny is not None: # Rectangular grid.
#       if ma.isMA(fld):
#           fld = ma.reshape(fld,(ny,nx))
#       else:
        fld = np.reshape(fld,(ny,nx))
    else:
        if gds[2] and gdtnum == 40: # Reduced global Gaussian grid.
            if expand:
                from . import redtoreg
                nx = 2*ny
                lonsperlat = msg.defList
#               if ma.isMA(fld):
#                   fld = ma.filled(fld)
#                   fld = redtoreg._redtoreg(nx,lonsperlat.astype(np.long),
#                                            fld.astype(np.double),fill_value)
#                   fld = ma.masked_values(fld,fill_value)
#               else:
                fld = redtoreg._redtoreg(nx,lonsperlat.astype(np.long),
                                         fld.astype(np.double),fill_value)
    #print(f'bitmap/missing: {datetime.datetime.now() - t1}')
    # Check scan modes for rect grids.
    if nx is not None and ny is not None:
        if scanModeFlags[3]:
            fldsave = fld.astype('f') # casting makes a copy
            fld[1::2,:] = fldsave[1::2,::-1]
    #print(f'bitmap/missing and scan modes for rect: {datetime.datetime.now() - t1}')

    # Set data to integer according to GRIB metadata
    if dataRepresentationTemplate[4] == 1: fld = fld.astype(np.int32)

#   # Map the data values to their respective definitions.
#   if map_keys:
#       fld = fld.astype(np.int32).astype(str)
#       if (msg.identificationSection[0] == 7 and \
#           msg.identificationSection[1] == 14 and \
#           msg.shortName == 'PWTHER') or \
#          (msg.identificationSection[0] == 8 and \
#           msg.identificationSection[1] == 65535 and \
#           msg.shortName == 'WX'):
#           keys = utils.decode_wx_strings(msg._lus)
#           for n,k in enumerate(keys):
#               fld = np.where(fld==str(n+1),k,fld)
#       else:
#           # For data whose units are defined in a code table
#           tbl = re.findall(r'\d\.\d+',msg.units,re.IGNORECASE)[0]
#           for k,v in tables.get_table(tbl).items():
#               fld = np.where(fld==k,v,fld)
    #print(f'after array unpack took: {datetime.datetime.now() - t1}')
    return fld

def create_message_cls(gdtn: int, pdtn: int, drtn: int) -> Grib2Message:
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

    The class is returned that contains the appropriate
    inherited section templates given by the input arguments.

    Returns
    -------
    Returns Grib2Message class or instance according to `init`.
    """
    Gdt = templates.gdt_class_by_gdtn(gdtn)
    Pdt = templates.pdt_class_by_pdtn(pdtn)
    Drt = templates.drt_class_by_drtn(drtn)
    class Msg(Grib2Message, Gdt, Pdt, Drt):
        pass
    return Msg
