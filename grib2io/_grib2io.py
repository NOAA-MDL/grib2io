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

For example usage of grib2io, please see the [Jupyter Notebook](https://github.com/NOAA-MDL/grib2io/blob/master/grib2io-v2-demo.ipynb).
"""

import builtins
import collections
import copy
import datetime
import hashlib
import os
import re
import struct
import sys

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

_AUTO_NANS = True

_latlon_datastore = dict()

_msg_class_store = dict()

class open():
    """
    GRIB2 File Object.  A physical file can contain one or more GRIB2 messages.  When instantiated,
    class `grib2io.open`, the file named `filename` is opened for reading (`mode = 'r'`) and is
    automatically indexed.  The indexing procedure reads some of the GRIB2 metadata for all GRIB2 Messages.

    A GRIB2 Message may contain submessages whereby Section 2-7 can be repeated.  grib2io accommodates
    for this by flattening any GRIB2 submessages into multiple individual messages.

    Attributes
    ----------

    **`mode`** File IO mode of opening the file.

    **`name`** Full path name of the GRIB2 file.

    **`messages`** Count of GRIB2 Messages contained in the file.

    **`current_message`** Current position of the file in units of GRIB2 Messages.

    **`size`** Size of the file in units of bytes.

    **`closed`** `True` is file handle is close; `False` otherwise.

    **`variables`** Tuple containing a unique list of variable short names (i.e. GRIB2 abbreviation names).

    **`levels`** Tuple containing a unique list of wgrib2-formatted level/layer strings.
    """
    __slots__ = ('_filehandle','_hasindex','_index','mode','name','messages',
                 'current_message','size','closed','variables','levels','_pos')
    def __init__(self, filename, mode='r', **kwargs):
        """
        `open` Constructor

        Parameters
        ----------

        **`filename : str`**

        File name containing GRIB2 messages.

        **`mode : str, optional`**

        File access mode where `r` opens the files for reading only; `w` opens the file for writing.
        """
        if mode in {'a','r','w'}:
            mode = mode+'b'
            if 'w' in mode: mode += '+'
        self._filehandle = builtins.open(filename,mode=mode,buffering=ONE_MB)
        self._hasindex = False
        self._index = {}
        self.mode = mode
        self.name = os.path.abspath(filename)
        self.messages = 0
        self.current_message = 0
        self.size = os.path.getsize(self.name)
        self.closed = self._filehandle.closed
        self.levels = None
        self.variables = None
        if 'r' in self.mode:
            try:
                self._build_index(no_data=kwargs['_xarray_backend'])
            except(KeyError):
                self._build_index()
        # FIX: Cannot perform reads on mode='a'
        #if 'a' in self.mode and self.size > 0: self._build_index()


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
        yield from self._index['msg']


    def __len__(self):
        """
        """
        return self.messages


    def __repr__(self):
        """
        """
        strings = []
        for k in self.__slots__:
            if k.startswith('_'): continue
            strings.append('%s = %s\n'%(k,eval('self.'+k)))
        return ''.join(strings)


    def __getitem__(self, key):
        """
        """
        if isinstance(key,int):
            if abs(key) >= len(self._index['msg']):
                raise IndexError("index out of range")
            else:
                return self._index['msg'][key]
        elif isinstance(key,str):
            return self.select(shortName=key)
        elif isinstance(key,slice):
            return self._index['msg'][key]
        else:
            raise KeyError('Key must be an integer, slice, or GRIB2 variable shortName.')


    def _build_index(self, no_data=False):
        """
        Perform indexing of GRIB2 Messages.
        """
        # Initialize index dictionary
        if not self._hasindex:
            self._index['offset'] = []
            self._index['bitmap_offset'] = []
            self._index['data_offset'] = []
            self._index['size'] = []
            self._index['data_size'] = []
            self._index['submessageOffset'] = []
            self._index['submessageBeginSection'] = []
            self._index['isSubmessage'] = []
            self._index['messageNumber'] = []
            self._index['msg'] = []
            self._hasindex = True

        # Iterate
        while True:
            try:
                # Read first 4 bytes and decode...looking for "GRIB"
                pos = self._filehandle.tell()
                header = struct.unpack('>i',self._filehandle.read(4))[0]

                # Test header. Then get information from GRIB2 Section 0: the discipline
                # number, edition number (should always be 2), and GRIB2 message size.
                # Then iterate to check for submessages.
                if header.to_bytes(4,'big') == b'GRIB':

                    _issubmessage = False
                    _submsgoffset = 0
                    _submsgbegin = 0
                    _bmapflag = None

                    # Read the rest of Section 0 using struct.
                    section0 = np.concatenate(([header],list(struct.unpack('>HBBQ',self._filehandle.read(12)))),dtype=np.int64)
                    assert section0[3] == 2

                    # Read and unpack Section 1
                    secsize = struct.unpack('>i',self._filehandle.read(4))[0]
                    secnum = struct.unpack('>B',self._filehandle.read(1))[0]
                    assert secnum == 1
                    self._filehandle.seek(self._filehandle.tell()-5)
                    _grbmsg = self._filehandle.read(secsize)
                    _grbpos = 0
                    section1,_grbpos = g2clib.unpack1(_grbmsg,_grbpos,np.empty)
                    secrange = range(2,8)
                    while 1:
                        section2 = b''
                        for num in secrange:
                            secsize = struct.unpack('>i',self._filehandle.read(4))[0]
                            secnum = struct.unpack('>B',self._filehandle.read(1))[0]
                            if secnum == num:
                                if secnum == 2:
                                    if secsize > 0:
                                        section2 = self._filehandle.read(secsize-5)
                                elif secnum == 3:
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
                                    _numcoord,_pdt,_pdtnum,_coordlist,_grbpos = g2clib.unpack4(_grbmsg,_grbpos,np.empty)
                                    _pdt = _pdt.tolist()
                                    section4 = np.concatenate((np.array((_numcoord,_pdtnum)),_pdt))
                                elif secnum == 5:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 5
                                    _drt,_drtn,_npts,self._pos = g2clib.unpack5(_grbmsg,_grbpos,np.empty)
                                    section5 = np.concatenate((np.array((_npts,_drtn)),_drt))
                                    section5 = np.where(section5==4294967295,-1,section5)
                                elif secnum == 6:
                                    # Unpack Section 6. Not really...just get the flag value.
                                    _bmapflag = struct.unpack('>B',self._filehandle.read(1))[0]
                                    if _bmapflag == 0:
                                        _bmappos = self._filehandle.tell()-6
                                    elif _bmapflag == 254:
                                        pass # Do this to keep the previous position value
                                    else:
                                        _bmappos = None
                                    self._filehandle.seek(self._filehandle.tell()+secsize-6)
                                elif secnum == 7:
                                    # Unpack Section 7. No need to read it, just index the position in file.
                                    _datapos = self._filehandle.tell()-5
                                    _datasize = secsize
                                    self._filehandle.seek(self._filehandle.tell()+secsize-5)
                                else:
                                    self._filehandle.seek(self._filehandle.tell()+secsize-5)
                            else:
                                if num == 2 and secnum == 3:
                                    pass # Allow this.  Just means no Local Use Section.
                                else:
                                    _issubmessage = True
                                    _submsgoffset = (self._filehandle.tell()-5)-(self._index['offset'][-1])
                                    _submsgbegin = secnum
                                self._filehandle.seek(self._filehandle.tell()-5)
                                continue
                        trailer = struct.unpack('>4s',self._filehandle.read(4))[0]
                        if trailer == b'7777':
                            self.messages += 1
                            self._index['offset'].append(pos)
                            self._index['bitmap_offset'].append(_bmappos)
                            self._index['data_offset'].append(_datapos)
                            self._index['size'].append(section0[-1])
                            self._index['data_size'].append(_datasize)
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            if _issubmessage:
                                self._index['submessageOffset'].append(_submsgoffset)
                                self._index['submessageBeginSection'].append(_submsgbegin)
                            else:
                                self._index['submessageOffset'].append(0)
                                self._index['submessageBeginSection'].append(_submsgbegin)

                            # Create Grib2Message with data.
                            msg = Grib2Message(section0,section1,section2,section3,section4,section5,_bmapflag)
                            msg._msgnum = self.messages-1
                            msg._deflist = _deflist
                            msg._coordlist = _coordlist
                            if not no_data:
                                shape = (msg.ny,msg.nx)
                                ndim = 2
                                if msg.typeOfValues == 0:
                                    dtype = 'float32'
                                elif msg.typeOfValues == 1:
                                    dtype = 'int32'
                                msg._data = Grib2MessageOnDiskArray(shape, ndim, dtype, self._filehandle,
                                                                    msg, pos, _bmappos, _datapos)
                            self._index['msg'].append(msg)

                            break
                        else:
                            self._filehandle.seek(self._filehandle.tell()-4)
                            self.messages += 1
                            self._index['offset'].append(pos)
                            self._index['bitmap_offset'].append(_bmappos)
                            self._index['data_offset'].append(_datapos)
                            self._index['size'].append(section0[-1])
                            self._index['data_size'].append(_datasize)
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            self._index['submessageOffset'].append(_submsgoffset)
                            self._index['submessageBeginSection'].append(_submsgbegin)

                            # Create Grib2Message with data.
                            msg = Grib2Message(section0,section1,section2,section3,section4,section5,_bmapflag)
                            msg._msgnum = self.messages-1
                            msg._deflist = _deflist
                            msg._coordlist = _coordlist
                            if not no_data:
                                shape = (msg.ny,msg.nx)
                                ndim = 2
                                if msg.typeOfValues == 0:
                                    dtype = 'float32'
                                elif msg.typeOfValues == 1:
                                    dtype = 'int32'
                                msg._data = Grib2MessageOnDiskArray(shape, ndim, dtype, self._filehandle,
                                                                    msg, pos, _bmappos, _datapos)
                            self._index['msg'].append(msg)

                            continue

            except(struct.error):
                if 'r' in self.mode:
                    self._filehandle.seek(0)
                break

        # Index at end of _build_index()
        if self._hasindex and not no_data:
             self.variables = tuple(sorted(set([msg.shortName for msg in self._index['msg']])))
             self.levels = tuple(sorted(set([msg.level for msg in self._index['msg']])))


    def close(self):
        """
        Close the file handle
        """
        if not self._filehandle.closed:
            self.messages = 0
            self.current_message = 0
            self._filehandle.close()
            self.closed = self._filehandle.closed


    def read(self, size=None):
        """
        Read size amount of GRIB2 messages from the current position. If no argument is
        given, then size is None and all messages are returned from the current position
        in the file. This read method follows the behavior of Python's builtin open()
        function, but whereas that operates on units of bytes, we operate on units of
        GRIB2 messages.

        Parameters
        ----------

        **`size : int, optional`**

        The number of GRIB2 messages to read from the current position. If no argument is
        give, the default value is `None` and remainder of the file is read.

        Returns
        -------

        `Grib2Message` object when size = 1 or a `list` of Grib2Messages when
        size > 1.
        """
        if size is not None and size < 0:
            size = None
        if size is None or size > 1:
            start = self.tell()
            stop = self.messages if size is None else start+size
            if size is None:
                self.current_message = self.messages-1
            else:
                self.current_message += size
            return self._index['msg'][slice(start,stop,1)]
        elif size == 1:
            self.current_message += 1
            return self._index['msg'][self.current_message]
        else:
            None


    def seek(self, pos):
        """
        Set the position within the file in units of GRIB2 messages.

        Parameters
        ----------

        **`pos : int`**

        The GRIB2 Message number to set the file pointer to.
        """
        if self._hasindex:
            self._filehandle.seek(self._index['offset'][pos])
            self.current_message = pos


    def tell(self):
        """
        Returns the position of the file in units of GRIB2 Messages.
        """
        return self.current_message


    def select(self,**kwargs):
        """
        Select GRIB2 messages by `Grib2Message` attributes.
        """
        # TODO: Added ability to process multiple values for each keyword (attribute)
        idxs = []
        nkeys = len(kwargs.keys())
        for k,v in kwargs.items():
            for m in self._index['msg']:
                if hasattr(m,k) and getattr(m,k) == v: idxs.append(m._msgnum)
        idxs = np.array(idxs,dtype=np.int32)
        return [self._index['msg'][i] for i in [ii[0] for ii in collections.Counter(idxs).most_common() if ii[1] == nkeys]]


    def write(self, msg):
        """
        Writes GRIB2 message object to file.

        Parameters
        ----------

        **`msg : Grib2Message or sequence of Grib2Messages`**

        GRIB2 message objects to write to file.
        """
        if isinstance(msg,list):
            for m in msg:
                self.write(m)
            return

        if issubclass(msg.__class__,_Grib2Message):
            if hasattr(msg,'_msg'):
                self._filehandle.write(msg._msg)
            else:
                if msg._signature != msg._generate_signature():
                    msg.pack()
                    self._filehandle.write(msg._msg)
                else:
                    if hasattr(msg._data,'filehandle'):
                        msg._data.filehandle.seek(msg._data.offset)
                        self._filehandle.write(msg._data.filehandle.read(msg.section0[-1]))
                    else:
                        msg.pack()
                        self._filehandle.write(msg._msg)
            self.flush()
            self.size = os.path.getsize(self.name)
            self._filehandle.seek(self.size-msg.section0[-1])
            self._build_index()
        else:
            raise TypeError("msg must be a Grib2Message object.")
        return


    def flush(self):
        """
        Flush the file object buffer.
        """
        self._filehandle.flush()


    def levels_by_var(self,name):
        """
        Return a list of level strings given a variable shortName.

        Parameters
        ----------

        **`name : str`**

        Grib2Message variable shortName

        Returns
        -------

        A list of strings of unique level strings.
        """
        return list(sorted(set([msg.level for msg in self.select(shortName=name)])))


    def vars_by_level(self,level):
        """
        Return a list of variable shortName strings given a level.

        Parameters
        ----------

        **`level : str`**

        Grib2Message variable level

        Returns
        -------

        A list of strings of variable shortName strings.
        """
        return list(sorted(set([msg.shortName for msg in self.select(level=level)])))


class Grib2Message:
    """
    Creation class for a GRIB2 message.
    """
    def __new__(self, section0: np.array = np.array([struct.unpack('>I',b'GRIB')[0],0,0,2,0]),
                      section1: np.array = np.zeros((13),dtype=np.int64),
                      section2: bytes = None,
                      section3: np.array = None,
                      section4: np.array = None,
                      section5: np.array = None, *args, **kwargs):

        bases = list()
        if section3 is None:
            if 'gdtn' in kwargs.keys():
                gdtn = kwargs['gdtn']
                Gdt = templates.gdt_class_by_gdtn(gdtn)
                bases.append(Gdt)
                section3 = np.zeros((Gdt._len+5),dtype=np.int64)
            else:
                raise ValueError("Must provide GRIB2 Grid Definition Template Number or section 3 array")
        else:
            gdtn = section3[4]
            Gdt = templates.gdt_class_by_gdtn(gdtn)
            bases.append(Gdt)

        if section4 is None:
            if 'pdtn' in kwargs.keys():
                pdtn = kwargs['pdtn']
                Pdt = templates.pdt_class_by_pdtn(pdtn)
                bases.append(Pdt)
                section4 = np.zeros((Pdt._len+2),dtype=np.int64)
            else:
                raise ValueError("Must provide GRIB2 Production Definition Template Number or section 4 array")
        else:
            pdtn = section4[1]
            Pdt = templates.pdt_class_by_pdtn(pdtn)
            bases.append(Pdt)

        if section5 is None:
            if 'drtn' in kwargs.keys():
                drtn = kwargs['drtn']
                Drt = templates.drt_class_by_drtn(drtn)
                bases.append(Drt)
                section5 = np.zeros((Drt._len+2),dtype=np.int64)
            else:
                raise ValueError("Must provide GRIB2 Data Representation Template Number or section 5 array")
        else:
            drtn = section5[1]
            Drt = templates.drt_class_by_drtn(drtn)
            bases.append(Drt)

        # attempt to use existing Msg class if it has already been made with gdtn,pdtn,drtn combo
        try:
            Msg = _msg_class_store[f"{gdtn}:{pdtn}:{drtn}"]
        except KeyError:
            @dataclass(init=False, repr=False)
            class Msg(_Grib2Message, *bases):
                pass
            _msg_class_store[f"{gdtn}:{pdtn}:{drtn}"] = Msg



        return Msg(section0, section1, section2, section3, section4, section5, *args)


@dataclass
class _Grib2Message:
    """GRIB2 Message base class"""
    # GRIB2 Sections
    section0: np.array = field(init=True,repr=False)
    section1: np.array = field(init=True,repr=False)
    section2: bytes = field(init=True,repr=False)
    section3: np.array = field(init=True,repr=False)
    section4: np.array = field(init=True,repr=False)
    section5: np.array = field(init=True,repr=False)
    bitMapFlag: templates.Grib2Metadata = field(init=True,repr=False,default=255)

    # Section 0 looked up attributes
    indicatorSection: np.array = field(init=False,repr=False,default=templates.IndicatorSection())
    discipline: templates.Grib2Metadata = field(init=False,repr=False,default=templates.Discipline())

    # Section 1 looked up attributes
    identificationSection: np.array = field(init=False,repr=False,default=templates.IdentificationSection())
    originatingCenter: templates.Grib2Metadata = field(init=False,repr=False,default=templates.OriginatingCenter())
    originatingSubCenter: templates.Grib2Metadata = field(init=False,repr=False,default=templates.OriginatingSubCenter())
    masterTableInfo: templates.Grib2Metadata = field(init=False,repr=False,default=templates.MasterTableInfo())
    localTableInfo: templates.Grib2Metadata = field(init=False,repr=False,default=templates.LocalTableInfo())
    significanceOfReferenceTime: templates.Grib2Metadata = field(init=False,repr=False,default=templates.SignificanceOfReferenceTime())
    year: int = field(init=False,repr=False,default=templates.Year())
    month: int = field(init=False,repr=False,default=templates.Month())
    day: int = field(init=False,repr=False,default=templates.Day())
    hour: int = field(init=False,repr=False,default=templates.Hour())
    minute: int = field(init=False,repr=False,default=templates.Minute())
    second: int = field(init=False,repr=False,default=templates.Second())
    refDate: datetime.datetime = field(init=False,repr=False,default=templates.RefDate())
    productionStatus: templates.Grib2Metadata = field(init=False,repr=False,default=templates.ProductionStatus())
    typeOfData: templates.Grib2Metadata = field(init=False,repr=False,default=templates.TypeOfData())

    @property
    def _isNDFD(self):
        """Check if GRIB2 message is from NWS NDFD"""
        return np.all(self.section1[0:2]==[8,65535])

    # Section 3 looked up common attributes.  Other looked up attributes are available according
    # to the Grid Definition Template.
    gridDefinitionSection: np.array = field(init=False,repr=False,default=templates.GridDefinitionSection())
    sourceOfGridDefinition: int = field(init=False,repr=False,default=templates.SourceOfGridDefinition())
    numberOfDataPoints: int = field(init=False,repr=False,default=templates.NumberOfDataPoints())
    interpretationOfListOfNumbers: templates.Grib2Metadata = field(init=False,repr=False,default=templates.InterpretationOfListOfNumbers())
    gridDefinitionTemplateNumber: templates.Grib2Metadata = field(init=False,repr=False,default=templates.GridDefinitionTemplateNumber())
    gridDefinitionTemplate: list = field(init=False,repr=False,default=templates.GridDefinitionTemplate())
    _earthparams: dict = field(init=False,repr=False,default=templates.EarthParams())
    _dxsign: float = field(init=False,repr=False,default=templates.DxSign())
    _dysign: float = field(init=False,repr=False,default=templates.DySign())
    _llscalefactor: float = field(init=False,repr=False,default=templates.LLScaleFactor())
    _lldivisor: float = field(init=False,repr=False,default=templates.LLDivisor())
    _xydivisor: float = field(init=False,repr=False,default=templates.XYDivisor())
    shapeOfEarth: templates.Grib2Metadata = field(init=False,repr=False,default=templates.ShapeOfEarth())
    earthRadius: float = field(init=False,repr=False,default=templates.EarthRadius())
    earthMajorAxis: float = field(init=False,repr=False,default=templates.EarthMajorAxis())
    earthMinorAxis: float = field(init=False,repr=False,default=templates.EarthMinorAxis())
    resolutionAndComponentFlags: list = field(init=False,repr=False,default=templates.ResolutionAndComponentFlags())
    ny: int = field(init=False,repr=False,default=templates.Ny())
    nx: int = field(init=False,repr=False,default=templates.Nx())
    scanModeFlags: list = field(init=False,repr=False,default=templates.ScanModeFlags())
    projParameters: dict = field(init=False,repr=False,default=templates.ProjParameters())

    # Section 4 attributes. Listed here are "extra" or "helper" attrs that use metadata from
    # the given PDT, but not a formal part of the PDT.
    productDefinitionTemplateNumber: templates.Grib2Metadata = field(init=False,repr=False,default=templates.ProductDefinitionTemplateNumber())
    productDefinitionTemplate: np.array = field(init=False,repr=False,default=templates.ProductDefinitionTemplate())
    _varinfo: list = field(init=False, repr=False, default=templates.VarInfo())
    _fixedsfc1info: list = field(init=False, repr=False, default=templates.FixedSfc1Info())
    _fixedsfc2info: list = field(init=False, repr=False, default=templates.FixedSfc2Info())
    fullName: str = field(init=False, repr=False, default=templates.FullName())
    units: str = field(init=False, repr=False, default=templates.Units())
    shortName: str = field(init=False, repr=False, default=templates.ShortName())
    leadTime: datetime.timedelta = field(init=False,repr=False,default=templates.LeadTime())
    unitOfFirstFixedSurface: str = field(init=False,repr=False,default=templates.UnitOfFirstFixedSurface())
    valueOfFirstFixedSurface: int = field(init=False,repr=False,default=templates.ValueOfFirstFixedSurface())
    unitOfSecondFixedSurface: str = field(init=False,repr=False,default=templates.UnitOfSecondFixedSurface())
    valueOfSecondFixedSurface: int = field(init=False,repr=False,default=templates.ValueOfSecondFixedSurface())
    level: str = field(init=False, repr=False, default=templates.Level())
    duration: datetime.timedelta = field(init=False,repr=False,default=templates.Duration())
    validDate: datetime.datetime = field(init=False,repr=False,default=templates.ValidDate())

    # Section 5 looked up common attributes.  Other looked up attributes are available according
    # to the Data Representation Template.
    numberOfPackedValues: int = field(init=False,repr=False,default=templates.NumberOfPackedValues())
    dataRepresentationTemplateNumber: templates.Grib2Metadata = field(init=False,repr=False,default=templates.DataRepresentationTemplateNumber())
    dataRepresentationTemplate: list = field(init=False,repr=False,default=templates.DataRepresentationTemplate())
    typeOfValues: templates.Grib2Metadata = field(init=False,repr=False,default=templates.TypeOfValues())


    def __post_init__(self):
        """Set some attributes after init"""
        self._msgnum = -1
        self._deflist = None
        self._coordlist = None
        self._signature = self._generate_signature()
        try:
            self._sha1_section3 = hashlib.sha1(self.section3).hexdigest()
        except(TypeError):
            pass
        self.bitMapFlag = templates.Grib2Metadata(self.bitMapFlag,table='6.0')


    @property
    def gdtn(self):
        """Return Grid Definition Template Number"""
        return self.section3[4]


    @property
    def pdtn(self):
        """Return Product Definition Template Number"""
        return self.section4[1]


    @property
    def drtn(self):
        """Return Data Representation Template Number"""
        return self.section5[1]


    @property
    def pdy(self):
        """Return the PDY ('YYYYMMDD')"""
        return ''.join([str(i) for i in self.section1[5:8]])


    @property
    def griddef(self):
        """Return a Grib2GridDef instance for a GRIB2 message"""
        return Grib2GridDef.from_section3(self.section3)


    def __repr__(self):
        info = ''
        for sect in [0,1,3,4,5,6]:
            for k,v in self.attrs_by_section(sect,values=True).items():
                info += f'Section {sect}: {k} = {v}\n'
        return info


    def __str__(self):
        return (f'{self._msgnum}:d={self.refDate}:{self.shortName}:'
                f'{self.fullName} ({self.units}):{self.level}:'
                f'{self.leadTime}')


    def _generate_signature(self):
        """Generature SHA-1 hash string from GRIB2 integer sections"""
        return hashlib.sha1(np.concatenate((self.section0,self.section1,
                                            self.section3,self.section4,
                                            self.section5))).hexdigest()


    def attrs_by_section(self, sect, values=False):
        """
        Provide a tuple of attribute names for the given GRIB2 section.

        Parameters
        ----------

        **`sect : int`**

        The GRIB2 section number.

        **`values : bool, optional`**

        Optional (default is `False`) arugment to return attributes values.

        Returns
        -------

        A List attribute names or Dict if `values = True`.
        """
        if sect in {0,1,6}:
            attrs = templates._section_attrs[sect]
        elif sect in {3,4,5}:
            def _find_class_index(n):
                _key = {3:'Grid', 4:'Product', 5:'Data'}
                for i,c in enumerate(self.__class__.__mro__):
                    if _key[n] in c.__name__:
                        return i
                else:
                    return []
            if sys.version_info.minor <= 8:
                attrs = templates._section_attrs[sect]+\
                        [a for a in dir(self.__class__.__mro__[_find_class_index(sect)]) if not a.startswith('_')]
            else:
                attrs = templates._section_attrs[sect]+\
                        self.__class__.__mro__[_find_class_index(sect)]._attrs
        else:
            attrs = []
        if values:
            return {k:getattr(self,k) for k in attrs}
        else:
            return attrs


    def pack(self):
        """
        Packs GRIB2 section data into a binary message.  It is the user's responsibility
        to populate the GRIB2 section information with appropriate metadata.
        """
        # Create beginning of packed binary message with section 0 and 1 data.
        self._sections = []
        self._msg,self._pos = g2clib.grib2_create(self.indicatorSection[2:4],self.identificationSection)
        self._sections += [0,1]

        # Add section 2 if present.
        if isinstance(self.section2,bytes) and len(self.section2) > 0:
            self._msg,self._pos = g2clib.grib2_addlocal(self._msg,self.section2)
            self._sections.append(2)

        # Add section 3.
        self._msg,self._pos = g2clib.grib2_addgrid(self._msg,self.gridDefinitionSection,
                                                   self.gridDefinitionTemplate,
                                                   self._deflist)
        self._sections.append(3)

        # Prepare data.
        field = np.copy(self.data)
        if self.scanModeFlags is not None:
            if self.scanModeFlags[3]:
                fieldsave = field.astype('f') # Casting makes a copy
                field[1::2,:] = fieldsave[1::2,::-1]
        fld = field.astype('f')

        # Prepare bitmap, if necessary
        bitmapflag = self.bitMapFlag.value
        if bitmapflag == 0:
            bmap = np.ravel(np.where(np.isnan(fld),0,1)).astype(DEFAULT_NUMPY_INT)
        else:
            bmap = None

        # Prepare optional coordinate list
        if self._coordlist is not None:
            crdlist = np.array(self._coordlist,'f')
        else:
            crdlist = None

        # Prepare data for packing if nans are present
        fld = np.ravel(fld)
        if np.isnan(fld).any() and hasattr(self,'_missvalmap'):
            fld = np.where(self._missvalmap==1,self.priMissingValue,fld)
            fld = np.where(self._missvalmap==2,self.secMissingValue,fld)

        # Add sections 4, 5, 6 (if present), and 7.
        self._msg,self._pos = g2clib.grib2_addfield(self._msg,self.pdtn,
                                                    self.productDefinitionTemplate,
                                                    crdlist,
                                                    self.drtn,
                                                    self.dataRepresentationTemplate,
                                                    fld,
                                                    bitmapflag,
                                                    bmap)
        self._sections.append(4)
        self._sections.append(5)
        if bmap is not None: self._sections.append(6)
        self._sections.append(7)

        # Finalize GRIB2 message with section 8.
        self._msg, self._pos = g2clib.grib2_end(self._msg)
        self._sections.append(8)
        self.section0[-1] = len(self._msg)


    @property
    def data(self) -> np.array:
        """
        Accessing the data attribute loads data into memmory
        """
        if not hasattr(self,'_auto_nans'): self._auto_nans = _AUTO_NANS
        if hasattr(self,'_data'):
            if self._auto_nans != _AUTO_NANS:
                self._data = self._ondiskarray
            if isinstance(self._data, Grib2MessageOnDiskArray):
                self._ondiskarray = self._data
                self._data = np.asarray(self._data)
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


    def latlons(self, *args, **kwrgs):
        """Alias for `grib2io.Grib2Message.grid` method"""
        return self.grid(*args, **kwrgs)


    def grid(self, unrotate=True):
        """
        Return lats,lons (in degrees) of grid. Currently can handle reg. lat/lon,
        global Gaussian, mercator, stereographic, lambert conformal, albers equal-area,
        space-view and azimuthal equidistant grids.

        Parameters
        ----------

        **`unrotate : bool`**

        If `True` [DEFAULT], and grid is rotated lat/lon, then unrotate the grid,
        otherwise `False`, do not.

        Returns
        -------

        **`lats, lons : numpy.ndarray`**

        Returns two numpy.ndarrays with dtype=numpy.float32 of grid latitudes and
        longitudes in units of degrees.
        """
        if self._sha1_section3 in _latlon_datastore.keys():
            return _latlon_datastore[self._sha1_section3]
        gdtn = self.gridDefinitionTemplateNumber.value
        gdtmpl = self.gridDefinitionTemplate
        reggrid = self.gridDefinitionSection[2] == 0 # This means regular 2-d grid
        if gdtn == 0:
            # Regular lat/lon grid
            lon1, lat1 = self.longitudeFirstGridpoint, self.latitudeFirstGridpoint
            lon2, lat2 = self.longitudeLastGridpoint, self.latitudeLastGridpoint
            dlon = self.gridlengthXDirection
            dlat = self.gridlengthYDirection
            if lon2 < lon1 and dlon < 0: lon1 = -lon1
            lats = np.linspace(lat1,lat2,self.ny)
            if reggrid:
                lons = np.linspace(lon1,lon2,self.nx)
            else:
                lons = np.linspace(lon1,lon2,self.ny*2)
            lons,lats = np.meshgrid(lons,lats) # Make 2-d arrays.
        elif gdtn == 1: # Rotated Lat/Lon grid
            pj = pyproj.Proj(self.projParameters)
            lat1,lon1 = self.latitudeFirstGridpoint,self.longitudeFirstGridpoint
            lat2,lon2 = self.latitudeLastGridpoint,self.longitudeLastGridpoint
            if lon1 > 180.0: lon1 -= 360.0
            if lon2 > 180.0: lon2 -= 360.0
            lats = np.linspace(lat1,lat2,self.ny)
            lons = np.linspace(lon1,lon2,self.nx)
            lons,lats = np.meshgrid(lons,lats) # Make 2-d arrays.
            if unrotate:
                from grib2io.utils import rotated_grid
                lats,lons = rotated_grid.unrotate(lats,lons,self.anglePoleRotation,
                                                  self.latitudeSouthernPole,
                                                  self.longitudeSouthernPole)
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
        elif gdtn == 32769:
            # Special NCEP Grid, Rotated Lat/Lon, Arakawa E-Grid (Non-Staggered)
            # TODO: Work in progress...
            lons, lats= None, None
        else:
            raise ValueError('Unsupported grid')

        _latlon_datastore[self._sha1_section3] = (lats,lons)

        return lats, lons


    def map_keys(self):
        """
        Returns an unpacked data grid where integer grid values are replaced with
        a string in which the numeric value is a representation of. These types
        of fields are cateogrical or classifications where data values do not
        represent an observable or predictable physical quantity.

        An example of such a field field would be [Dominant Precipitation Type -
        DPTYPE](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-201.shtml)

        Returns
        -------

        **`numpy.ndarray`** of string values per element.
        """
        hold_auto_nans = _AUTO_NANS
        set_auto_nans(False)
        if (np.all(self.section1[0:2]==[7,14]) and self.shortName == 'PWTHER') or \
        (np.all(self.section1[0:2]==[8,65535]) and self.shortName == 'WX'):
            keys = utils.decode_wx_strings(self.section2)
            if hasattr(self,'priMissingValue') and self.priMissingValue not in [None,0]:
                keys[int(self.priMissingValue)] = 'Missing'
            if hasattr(self,'secMissingValue') and self.secMissingValue not in [None,0]:
                keys[int(self.secMissingValue)] = 'Missing'
            u,inv = np.unique(self.data,return_inverse=True)
            fld = np.array([keys[x] for x in u])[inv].reshape(self.data.shape)
        else:
            # For data whose units are defined in a code table (i.e. classification or mask)
            tblname = re.findall(r'\d\.\d+',self.units,re.IGNORECASE)[0]
            fld = self.data.astype(np.int32).astype(str)
            tbl = tables.get_table(tblname,expand=True)
            for val in np.unique(fld):
                fld = np.where(fld==val,tbl[val],fld)
        set_auto_nans(hold_auto_nans)
        return fld


    def to_bytes(self, validate=True):
        """
        Return packed GRIB2 message in bytes format. This will be Useful for
        exporting data in non-file formats.  For example, can be used to
        output grib data directly to S3 using the boto3 client without the
        need to write a temporary file to upload first.

        Parameters
        ----------

        **`validate : bool, optional`**

        If `True` (DEFAULT), validates first/last four bytes for proper
        formatting, else returns None. If `False`, message is output as is.

        Returns
        -------

        Returns GRIB2 formatted message as bytes.
        """
        if validate:
            if self._msg[0:4]+self._msg[-4:] == b'GRIB7777':
                return self._msg
            else:
                return None
        else:
            return self._msg


    def interpolate(self, method, grid_def_out, method_options=None):
        """
        Perform grid spatial interpolation via the [NCEPLIBS-ip library](https://github.com/NOAA-EMC/NCEPLIBS-ip).

        **IMPORTANT:**  This interpolate method only supports scalar interpolation. If you
        need to perform vector interpolation, use the module-level `grib2io.interpolate` function.

        Parameters
        ----------

        **`method : int or str`**

        Interpolate method to use. This can either be an integer or string using
        the following mapping:

        | Interpolate Scheme | Integer Value |
        | :---:              | :---:         |
        | 'bilinear'         | 0             |
        | 'bicubic'          | 1             |
        | 'neighbor'         | 2             |
        | 'budget'           | 3             |
        | 'spectral'         | 4             |
        | 'neighbor-budget'  | 6             |

        **`grid_def_out : grib2io.Grib2GridDef`**

        Grib2GridDef object of the output grid.

        **`method_options : list of ints, optional`**

        Interpolation options. See the NCEPLIBS-ip doucmentation for
        more information on how these are used.

        Returns
        -------

        If interpolating to a grid, a new Grib2Message object is returned.  The GRIB2 metadata of
        the new Grib2Message object is indentical to the input except where required to be different
        because of the new grid specs.

        If interpolating to station points, the interpolated data values are returned as a numpy.ndarray.
        """
        section0 = self.section0
        section0[-1] = 0
        gds = [0, grid_def_out.npoints, 0, 255, grid_def_out.gdtn]
        section3 = np.concatenate((gds,grid_def_out.gdt))

        msg = Grib2Message(section0,self.section1,self.section2,section3,
                           self.section4,self.section5,self.bitMapFlag.value)

        msg._msgnum = -1
        msg._deflist = self._deflist
        msg._coordlist = self._coordlist
        shape = (msg.ny,msg.nx)
        ndim = 2
        if msg.typeOfValues == 0:
            dtype = 'float32'
        elif msg.typeOfValues == 1:
            dtype = 'int32'
        msg._data = interpolate(self.data,method,Grib2GridDef.from_section3(self.section3),grid_def_out,
                                method_options=method_options).reshape(msg.ny,msg.nx)
        return msg


@dataclass
class Grib2MessageOnDiskArray:
    shape: str
    ndim: str
    dtype: str
    filehandle: open
    msg: Grib2Message
    offset: int
    bmap_offset: int
    data_offset: int

    def __array__(self, dtype=None):
        return np.asarray(_data(self.filehandle, self.msg, self.bmap_offset, self.data_offset),dtype=dtype)


def _data(filehandle: open, msg: Grib2Message, bmap_offset: int, data_offset: int)-> np.array:
    """
    Returns an unpacked data grid.

    Returns
    -------

    **`numpy.ndarray`**

    A numpy.ndarray with shape (ny,nx). By default the array dtype=np.float32, but
    could be np.int32 if Grib2Message.typeOfValues is integer.
    """
    gds = msg.section3[0:5]
    gdt = msg.section3[5:]
    drt = msg.section5[2:]
    nx, ny = msg.nx, msg.ny
    scanModeFlags = msg.scanModeFlags

    # Set the fill value according to how we are handling missing values
    msg._auto_nans = _AUTO_NANS
    if msg._auto_nans:
        fill_value = np.nan
    else:
        if hasattr(msg,'typeOfMissingValueManagement'):
            fill_value = msg.priMissingValue if hasattr(msg,'priMissingValue') else np.nan
        else:
            fill_value = np.nan

    # Read bitmap data.
    if bmap_offset is not None:
        filehandle.seek(bmap_offset) # Position file pointer to the beginning of bitmap section.
        bmap_size,num = struct.unpack('>IB',filehandle.read(5))
        filehandle.seek(filehandle.tell()-5)
        ipos = 0
        bmap,bmapflag = g2clib.unpack6(filehandle.read(bmap_size),msg.section3[1],ipos,np.empty)

    try:
        if scanModeFlags[2]:
            storageorder='F'
        else:
            storageorder='C'
    except AttributeError:
        raise ValueError('Unsupported grid definition template number %s'%gridDefinitionTemplateNumber)

    # Position file pointer to the beginning of data section.
    filehandle.seek(data_offset)
    data_size,secnum = struct.unpack('>IB',filehandle.read(5))
    assert secnum == 7
    filehandle.seek(filehandle.tell()-5)
    ipos = 0
    npvals = msg.numberOfPackedValues
    ngrdpts = msg.numberOfDataPoints
    fld1 = g2clib.unpack7(filehandle.read(data_size),msg.gdtn,gdt,msg.drtn,drt,npvals,ipos,
                          np.empty,storageorder=storageorder)

    # Handle the missing values
    if msg.bitMapFlag in {0,254}:
        # Bitmap
        fill_value = np.nan # If bitmap, use nans
        fld = np.full((ngrdpts),fill_value,dtype=np.float32)
        np.put(fld,np.nonzero(bmap),fld1)
    else:
        # No bitmap, check missing values
        if hasattr(msg,'typeOfMissingValueManagement'):
            if msg.typeOfMissingValueManagement in {1,2}:
                msg._missvalmap = np.zeros(fld1.shape,dtype=np.int8)
                if hasattr(msg,'priMissingValue') and msg.priMissingValue is not None:
                    if msg._auto_nans: fill_value = np.nan
                    msg._missvalmap = np.where(fld1==msg.priMissingValue,1,msg._missvalmap)
                    fld1 = np.where(msg._missvalmap==1,fill_value,fld1)
            if msg.typeOfMissingValueManagement == 2:
                if hasattr(msg,'secMissingValue') and msg.secMissingValue is not None:
                    if msg._auto_nans: fill_value = np.nan
                    msg._missvalmap = np.where(fld1==msg.secMissingValue,2,msg._missvalmap)
                    fld1 = np.where(msg._missvalmap==2,fill_value,fld1)
        fld = fld1

    # Check for reduced grid.
    if gds[3] > 0 and gds[4] in {0,40} and msg._deflist is not None:
        from . import redtoreg
        nx = 2*ny
        lonsperlat = msg._deflist
        fld = redtoreg._redtoreg(nx,lonsperlat.astype(np.int64),
                                 fld.astype(np.float64),fill_value)
    else:
        fld = np.reshape(fld,(ny,nx))

    # Check scan modes for rect grids.
    if nx is not None and ny is not None:
        if scanModeFlags[3]:
            fldsave = fld.astype(np.float32) # casting makes a copy
            fld[1::2,:] = fldsave[1::2,::-1]

    # Default data type is np.float32. Convert to np.int32 according GRIB2
    # metadata attribute typeOfValues.
    if msg.typeOfValues == 1:
        fld = fld.astype(np.int32)

    return fld


def set_auto_nans(value):
    """
    Handle missing values in GRIB2 message data.

    Parameters
    ----------

    **`value : bool`**

    If `True` [DEFAULT], missing values in GRIB2 message data will be set to `np.nan` and
    if `False`, missing values will present in the data array.  If a bitmap is used, then `np.nan`
    will be used regardless of this setting.
    """
    global _AUTO_NANS
    if isinstance(value,bool):
        _AUTO_NANS = value
    else:
        raise TypeError(f"Argument must be bool")


def interpolate(a, method, grid_def_in, grid_def_out, method_options=None):
    """
    This is the module-level interpolation function that interfaces with the grib2io_interp
    component pakcage that interfaces to the [NCEPLIBS-ip library](https://github.com/NOAA-EMC/NCEPLIBS-ip).
    It supports scalar and vector interpolation according to the type of object a.  It also
    supports scalar and vector interpolation to station points when grid_def_out is set up
    properly for station interpolation.

    Parameters
    ----------

    **`a : numpy.ndarray or tuple`**

    Input data.  If `a` is a `numpy.ndarray`, scalar interpolation will be
    performed.  If `a` is a `tuple`, then vector interpolation will be performed
    with the assumption that u = a[0] and v = a[1] and are both `numpy.ndarray`.

    These data are expected to be in 2-dimensional form with shape (ny, nx) or
    3-dimensional (:, ny, nx) where the 1st dimension represents another spatial,
    temporal, or classification (i.e. ensemble members) dimension. The function will
    properly flatten the (ny,nx) dimensions into (nx * ny) acceptable for input into
    the interpolation subroutines.

    **`method : int or str`**

    Interpolate method to use. This can either be an integer or string using
    the following mapping:

    | Interpolate Scheme | Integer Value |
    | :---:              | :---:         |
    | 'bilinear'         | 0             |
    | 'bicubic'          | 1             |
    | 'neighbor'         | 2             |
    | 'budget'           | 3             |
    | 'spectral'         | 4             |
    | 'neighbor-budget'  | 6             |

    **`grid_def_in : grib2io.Grib2GridDef`**

    Grib2GridDef object for the input grid.

    **`grid_def_out : grib2io.Grib2GridDef`**

    Grib2GridDef object for the output grid or station points.

    **`method_options : list of ints, optional`**

    Interpolation options. See the NCEPLIBS-ip doucmentation for
    more information on how these are used.

    Returns
    -------

    Returns a `numpy.ndarray` when scalar interpolation is performed or
    a `tuple` of `numpy.ndarray`s when vector interpolation is performed
    with the assumptions that 0-index is the interpolated u and 1-index
    is the interpolated v.
    """
    from grib2io_interp import interpolate

    interp_schemes = {'bilinear':0, 'bicubic':1, 'neighbor':2,
                      'budget':3, 'spectral':4, 'neighbor-budget':6}

    if isinstance(method,int) and method not in interp_schemes.values():
        raise ValueError('Invalid interpolation method.')
    elif isinstance(method,str):
        if method in interp_schemes.keys():
            method = interp_schemes[method]
        else:
            raise ValueError('Invalid interpolation method.')

    if method_options is None:
        method_options = np.zeros((20),dtype=np.int32)
        if method in {3,6}:
            method_options[0:2] = -1

    ni = grid_def_in.npoints
    no = grid_def_out.npoints

    # Adjust shape of input array(s)
    a,newshp = _adjust_array_shape_for_interp(a,grid_def_in,grid_def_out)

    # Set lats and lons if stations, else create array for grids.
    if grid_def_out.gdtn == -1:
        rlat = np.array(grid_def_out.lats,dtype=np.float32)
        rlon = np.array(grid_def_out.lons,dtype=np.float32)
    else:
        rlat = np.zeros((no),dtype=np.float32)
        rlon = np.zeros((no),dtype=np.float32)

    # Call interpolation subroutines according to type of a.
    if isinstance(a,np.ndarray):
        # Scalar
        ibi = np.zeros((a.shape[0]),dtype=np.int32)
        li = np.zeros(a.shape,dtype=np.int32)
        go = np.zeros((a.shape[0],no),dtype=np.float32)
        no,ibo,lo,iret = interpolate.interpolate_scalar(method,method_options,
                                                 grid_def_in.gdtn,grid_def_in.gdt,
                                                 grid_def_out.gdtn,grid_def_out.gdt,
                                                 ibi,li.T,a.T,go.T,rlat,rlon)
        out = go.reshape(newshp)
    elif isinstance(a,tuple):
        # Vector
        ibi = np.zeros((a[0].shape[0]),dtype=np.int32)
        li = np.zeros(a[0].shape,dtype=np.int32)
        uo = np.zeros((a[0].shape[0],no),dtype=np.float32)
        vo = np.zeros((a[1].shape[0],no),dtype=np.float32)
        crot = np.ones((no),dtype=np.float32)
        srot = np.zeros((no),dtype=np.float32)
        no,ibo,lo,iret = interpolate.interpolate_vector(method,method_options,
                                                 grid_def_in.gdtn,grid_def_in.gdt,
                                                 grid_def_out.gdtn,grid_def_out.gdt,
                                                 ibi,li.T,a[0].T,a[1].T,uo.T,vo.T,
                                                 rlat,rlon,crot,srot)
        del crot
        del srot
        out = (uo.reshape(newshp),vo.reshape(newshp))

    del rlat
    del rlon
    return out


def interpolate_to_stations(a, method, grid_def_in, lats, lons, method_options=None):
    """
    This is the module-level interpolation function **for interpolation to stations**
    that interfaces with the grib2io_interp component pakcage that interfaces to
    the [NCEPLIBS-ip library](https://github.com/NOAA-EMC/NCEPLIBS-ip). It supports
    scalar and vector interpolation according to the type of object a.

    Parameters
    ----------

    **`a : numpy.ndarray or tuple`**

    Input data.  If `a` is a `numpy.ndarray`, scalar interpolation will be
    performed.  If `a` is a `tuple`, then vector interpolation will be performed
    with the assumption that u = a[0] and v = a[1] and are both `numpy.ndarray`.

    These data are expected to be in 2-dimensional form with shape (ny, nx) or
    3-dimensional (:, ny, nx) where the 1st dimension represents another spatial,
    temporal, or classification (i.e. ensemble members) dimension. The function will
    properly flatten the (ny,nx) dimensions into (nx * ny) acceptable for input into
    the interpolation subroutines.

    **`method : int or str`**

    Interpolate method to use. This can either be an integer or string using
    the following mapping:

    | Interpolate Scheme | Integer Value |
    | :---:              | :---:         |
    | 'bilinear'         | 0             |
    | 'bicubic'          | 1             |
    | 'neighbor'         | 2             |
    | 'budget'           | 3             |
    | 'spectral'         | 4             |
    | 'neighbor-budget'  | 6             |

    **`grid_def_in : grib2io.Grib2GridDef`**

    Grib2GridDef object for the input grid.

    **`lats : numpy.ndarray or list`**

    Latitudes for station points

    **`lons : numpy.ndarray or list`**

    Longitudes for station points

    **`method_options : list of ints, optional`**

    Interpolation options. See the NCEPLIBS-ip doucmentation for
    more information on how these are used.

    Returns
    -------

    Returns a `numpy.ndarray` when scalar interpolation is performed or
    a `tuple` of `numpy.ndarray`s when vector interpolation is performed
    with the assumptions that 0-index is the interpolated u and 1-index
    is the interpolated v.
    """
    from grib2io_interp import interpolate

    interp_schemes = {'bilinear':0, 'bicubic':1, 'neighbor':2,
                      'budget':3, 'spectral':4, 'neighbor-budget':6}

    if isinstance(method,int) and method not in interp_schemes.values():
        raise ValueError('Invalid interpolation method.')
    elif isinstance(method,str):
        if method in interp_schemes.keys():
            method = interp_schemes[method]
        else:
            raise ValueError('Invalid interpolation method.')

    if method_options is None:
        method_options = np.zeros((20),dtype=np.int32)
        if method in {3,6}:
            method_options[0:2] = -1

    # Check lats and lons
    if isinstance(lats,list):
        nlats = len(lats)
    elif isinstance(lats,np.ndarray) and len(lats.shape) == 1:
        nlats = lats.shape[0]
    else:
        raise ValueError('Station latitudes must be a list or 1-D NumPy array.')
    if isinstance(lons,list):
        nlons = len(lons)
    elif isinstance(lons,np.ndarray) and len(lons.shape) == 1:
        nlons = lons.shape[0]
    else:
        raise ValueError('Station longitudes must be a list or 1-D NumPy array.')
    if nlats != nlons:
        raise ValueError('Station lats and lons must be same size.')

    ni = grid_def_in.npoints
    no = nlats

    # Adjust shape of input array(s)
    a,newshp = _adjust_array_shape_for_interp_stations(a,grid_def_in,no)

    # Set lats and lons if stations
    rlat = np.array(lats,dtype=np.float32)
    rlon = np.array(lons,dtype=np.float32)

    # Use gdtn = -1 for stations and an empty template array
    gdtn = -1
    gdt = np.zeros((200),dtype=np.int32)

    # Call interpolation subroutines according to type of a.
    if isinstance(a,np.ndarray):
        # Scalar
        ibi = np.zeros((a.shape[0]),dtype=np.int32)
        li = np.zeros(a.shape,dtype=np.int32)
        go = np.zeros((a.shape[0],no),dtype=np.float32)
        no,ibo,lo,iret = interpolate.interpolate_scalar(method,method_options,
                                                 grid_def_in.gdtn,grid_def_in.gdt,
                                                 gdtn,gdt,
                                                 ibi,li.T,a.T,go.T,rlat,rlon)
        out = go.reshape(newshp)
    elif isinstance(a,tuple):
        # Vector
        ibi = np.zeros((a[0].shape[0]),dtype=np.int32)
        li = np.zeros(a[0].shape,dtype=np.int32)
        uo = np.zeros((a[0].shape[0],no),dtype=np.float32)
        vo = np.zeros((a[1].shape[0],no),dtype=np.float32)
        crot = np.ones((no),dtype=np.float32)
        srot = np.zeros((no),dtype=np.float32)
        no,ibo,lo,iret = interpolate.interpolate_vector(method,method_options,
                                                 grid_def_in.gdtn,grid_def_in.gdt,
                                                 gdtn,gdt,
                                                 ibi,li.T,a[0].T,a[1].T,uo.T,vo.T,
                                                 rlat,rlon,crot,srot)
        del crot
        del srot
        out = (uo.reshape(newshp),vo.reshape(newshp))

    del rlat
    del rlon
    return out


@dataclass
class Grib2GridDef:
    """
    Class to hold GRIB2 Grid Definition Template Number and Template as
    class attributes. This allows for cleaner looking code when passing these
    metadata around.  For example, the `grib2io._Grib2Message.interpolate`
    method and `grib2io.interpolate` function accepts these objects.
    """
    gdtn: int
    gdt: np.array

    @classmethod
    def from_section3(cls, section3):
        return cls(section3[4],section3[5:])

    @property
    def nx(self):
        return self.gdt[7]

    @property
    def ny(self):
        return self.gdt[8]

    @property
    def npoints(self):
        return self.gdt[7] * self.gdt[8]

    @property
    def shape(self):
        return (self.ny, self.nx)


def _adjust_array_shape_for_interp(a,grid_def_in,grid_def_out):
    """
    Adjust shape of input data array to conform to the dimensionality
    the NCEPLIBS-ip interpolation subroutine arguments for grids.
    """
    if isinstance(a,tuple):
        a0,newshp = _adjust_array_shape_for_interp(a[0],grid_def_in,grid_def_out)
        a1,newshp = _adjust_array_shape_for_interp(a[1],grid_def_in,grid_def_out)
        return (a0,a1),newshp

    if isinstance(a,np.ndarray):
        if len(a.shape) == 2 and a.shape == grid_def_in.shape:
            newshp = (grid_def_out.ny,grid_def_out.nx)
            a = np.expand_dims(a.flatten(),axis=0)
        elif len(a.shape) == 3 and a.shape[-2:] == grid_def_in.shape:
            newshp = (a.shape[0],grid_def_out.ny,grid_def_out.nx)
            a = a.reshape(*a.shape[:-2],-1)
        else:
            raise ValueError("Input array shape must be either (ny,nx) or (:,ny,nx).")

    return a,newshp


def _adjust_array_shape_for_interp_stations(a,grid_def_in,nstations):
    """
    Adjust shape of input data array to conform to the dimensionality
    the NCEPLIBS-ip interpolation subroutine arguments for station points.
    """
    if isinstance(a,tuple):
        a0,newshp = _adjust_array_shape_for_interp_stations(a[0],grid_def_in,nstations)
        a1,newshp = _adjust_array_shape_for_interp_stations(a[1],grid_def_in,nstations)
        return (a0,a1),newshp

    if isinstance(a,np.ndarray):
        if len(a.shape) == 2 and a.shape == grid_def_in.shape:
            newshp = (nstations)
            a = np.expand_dims(a.flatten(),axis=0)
        elif len(a.shape) == 3 and a.shape[-2:] == grid_def_in.shape:
            newshp = (a.shape[0],nstations)
            a = a.reshape(*a.shape[:-2],-1)
        else:
            raise ValueError("Input array shape must be either (ny,nx) or (:,ny,nx).")

    return a,newshp
