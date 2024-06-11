"""
Introduction
============
grib2io is a Python package that provides an interface to the [NCEP GRIB2 C
(g2c)](https://github.com/NOAA-EMC/NCEPLIBS-g2c) library for the purpose of
reading and writing WMO GRIdded Binary, Edition 2 (GRIB2) messages. A physical
file can contain one or more GRIB2 messages.

GRIB2 file IO is performed directly in Python.  The unpacking/packing of GRIB2
integer, coded metadata and data sections is performed by the g2c library
functions via the g2clib Cython wrapper module.  The decoding/encoding of GRIB2
metadata is translated into more descriptive, plain language metadata by looking
up the integer code values against the appropriate GRIB2 code tables.  These
code tables are a part of the grib2io module.

Tutorials
=========
The following Jupyter Notebooks are available as tutorials:

* [General Usage](https://github.com/NOAA-MDL/grib2io/blob/master/demos/grib2io-v2.ipynb)
* [Plotting Arakawa Rotated Lat/Lon Grids](https://github.com/NOAA-MDL/grib2io/blob/master/demos/plot-arakawa-rotlatlon-grids.ipynb)
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Union
import builtins
import collections
import copy
import datetime
import hashlib
import os
import re
import struct
import sys
import warnings

from numpy.typing import NDArray
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
TYPE_OF_VALUES_DTYPE = ('float32','int32')

_interp_schemes = {'bilinear':0, 'bicubic':1, 'neighbor':2,
                   'budget':3, 'spectral':4, 'neighbor-budget':6}

_AUTO_NANS = True

_latlon_datastore = dict()
_msg_class_store = dict()

class open():
    """
    GRIB2 File Object.

    A physical file can contain one or more GRIB2 messages.  When instantiated,
    class `grib2io.open`, the file named `filename` is opened for reading (`mode
    = 'r'`) and is automatically indexed.  The indexing procedure reads some of
    the GRIB2 metadata for all GRIB2 Messages.  A GRIB2 Message may contain
    submessages whereby Section 2-7 can be repeated.  grib2io accommodates for
    this by flattening any GRIB2 submessages into multiple individual messages.

    It is important to note that GRIB2 files from some Meteorological agencies
    contain other data than GRIB2 messages.  GRIB2 files from ECMWF can contain
    GRIB1 and GRIB2 messages.  grib2io checks for these and safely ignores them.

    Attributes
    ----------
    closed : bool
        `True` is file handle is close; `False` otherwise.
    current_message : int
        Current position of the file in units of GRIB2 Messages.
    levels : tuple
        Tuple containing a unique list of wgrib2-formatted level/layer strings.
    messages : int
        Count of GRIB2 Messages contained in the file.
    mode : str
        File IO mode of opening the file.
    name : str
        Full path name of the GRIB2 file.
    size : int
        Size of the file in units of bytes.
    variables : tuple
        Tuple containing a unique list of variable short names (i.e. GRIB2
        abbreviation names).
    """

    __slots__ = ('_fileid', '_filehandle', '_hasindex', '_index', '_nodata',
                 '_pos', 'closed', 'current_message', 'messages', 'mode',
                 'name', 'size')

    def __init__(self, filename: str, mode: Literal["r", "w", "x"] = "r", **kwargs):
        """
        Initialize GRIB2 File object instance.

        Parameters
        ----------
        filename
            File name containing GRIB2 messages.
        mode: default="r"
            File access mode where "r" opens the files for reading only; "w"
            opens the file for overwriting and "x" for writing to a new file.
        """
        # Manage keywords
        if "_xarray_backend" not in kwargs:
            kwargs["_xarray_backend"] = False
            self._nodata = False
        else:
            self._nodata = kwargs["_xarray_backend"]

        # All write modes are read/write.
        # All modes are binary.
        if mode in ("a", "x", "w"):
            mode += "+"
        mode = mode + "b"

        # Some GRIB2 files are gzipped, so check for that here, but
        # raise error when using xarray backend.
        if 'r' in mode:
            self._filehandle = builtins.open(filename, mode=mode)
            # Gzip files contain a 2-byte header b'\x1f\x8b'.
            if self._filehandle.read(2) == b'\x1f\x8b':
                self._filehandle.close()
                if kwargs["_xarray_backend"]:
                    raise RuntimeError('Gzip GRIB2 files are not supported by the Xarray backend.')
                import gzip
                self._filehandle = gzip.open(filename, mode=mode)
            else:
                self._filehandle = builtins.open(filename, mode=mode)
        else:
            self._filehandle = builtins.open(filename, mode=mode)

        self.name = os.path.abspath(filename)
        fstat = os.stat(self.name)
        self._hasindex = False
        self._index = {}
        self.mode = mode
        self.messages = 0
        self.current_message = 0
        self.size = fstat.st_size
        self.closed = self._filehandle.closed
        self._fileid = hashlib.sha1((self.name+str(fstat.st_ino)+
                                     str(self.size)).encode('ASCII')).hexdigest()
        if 'r' in self.mode:
            self._build_index()
        # FIX: Cannot perform reads on mode='a'
        #if 'a' in self.mode and self.size > 0: self._build_index()


    def __delete__(self, instance):
        self.close()
        del self._index


    def __enter__(self):
        return self


    def __exit__(self, atype, value, traceback):
        self.close()


    def __iter__(self):
        yield from self._index['msg']


    def __len__(self):
        return self.messages


    def __repr__(self):
        strings = []
        for k in self.__slots__:
            if k.startswith('_'): continue
            strings.append('%s = %s\n'%(k,eval('self.'+k)))
        return ''.join(strings)


    def __getitem__(self, key):
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


    def _build_index(self):
        """Perform indexing of GRIB2 Messages."""
        # Initialize index dictionary
        if not self._hasindex:
            self._index['sectionOffset'] = []
            self._index['sectionSize'] = []
            self._index['msgSize'] = []
            self._index['msgNumber'] = []
            self._index['msg'] = []
            self._index['isSubmessage'] = []
            self._hasindex = True

        # Iterate
        while True:
            try:
                # Initialize
                bmapflag = None
                pos = self._filehandle.tell()
                section2 = b''
                trailer = b''
                _secpos = dict.fromkeys(range(8))
                _secsize = dict.fromkeys(range(8))
                _isSubmessage = False

                # Ignore headers (usually text) that are not part of the GRIB2
                # file.  For example, NAVGEM files have a http header at the
                # beginning that needs to be ignored.

                # Read a byte at a time until "GRIB" is found.  Using
                # "wgrib2" on a NAVGEM file, the header was 421 bytes and
                # decided to go to 2048 bytes to be safe. For normal GRIB2
                # files this should be quick and break out of the first
                # loop when "test_offset" is 0.
                for test_offset in range(2048):
                    self._filehandle.seek(pos + test_offset)
                    header = struct.unpack(">I", self._filehandle.read(4))[0]
                    if header.to_bytes(4, "big") == b"GRIB":
                        pos = pos + test_offset
                        break
                else:
                    # NOTE: Coming here means that no "GRIB" message identifier
                    # was found in the previous 2048 bytes. So here we continue
                    # the while True loop.
                    continue

                # Read the rest of Section 0 using struct.
                _secpos[0] = self._filehandle.tell()-4
                _secsize[0] = 16
                secmsg = self._filehandle.read(12)
                section0 = np.concatenate(([header],list(struct.unpack('>HBBQ',secmsg))),dtype=np.int64)

                # Make sure message is GRIB2.
                if section0[3] != 2:
                    # Check for GRIB1 and ignore.
                    if secmsg[3] == 1:
                        warnings.warn("GRIB version 1 message detected.  Ignoring...")
                        grib1_size = int.from_bytes(secmsg[:3],"big")
                        self._filehandle.seek(self._filehandle.tell()+grib1_size-16)
                        continue
                    else:
                        raise ValueError("Bad GRIB version number.")

                # Read and unpack sections 1 through 8 which all follow a
                # pattern of section size, number, and content.
                while 1:
                    # Read first 5 bytes of the section which contains the size
                    # of the section (4 bytes) and the section number (1 byte).
                    secmsg = self._filehandle.read(5)
                    secsize, secnum = struct.unpack('>iB',secmsg)

                    # Record the offset of the section number and "append" the
                    # rest of the section to secmsg.
                    _secpos[secnum] = self._filehandle.tell()-5
                    _secsize[secnum] = secsize
                    if secnum in {1,3,4,5}:
                        secmsg += self._filehandle.read(secsize-5)
                    grbpos = 0

                    # Unpack section
                    if secnum == 1:
                        # Unpack Section 1
                        section1, grbpos = g2clib.unpack1(secmsg,grbpos,np.empty)
                    elif secnum == 2:
                        # Unpack Section 2
                        section2 = self._filehandle.read(secsize-5)
                    elif secnum == 3:
                        # Unpack Section 3
                        gds, gdt, deflist, grbpos = g2clib.unpack3(secmsg,grbpos,np.empty)
                        gds = gds.tolist()
                        gdt = gdt.tolist()
                        section3 = np.concatenate((gds,gdt))
                        section3 = np.where(section3==4294967295,-1,section3)
                    elif secnum == 4:
                        # Unpack Section 4
                        numcoord, pdt, pdtnum, coordlist, grbpos = g2clib.unpack4(secmsg,grbpos,np.empty)
                        pdt = pdt.tolist()
                        section4 = np.concatenate((np.array((numcoord,pdtnum)),pdt))
                    elif secnum == 5:
                        # Unpack Section 5
                        drt, drtn, npts, self._pos = g2clib.unpack5(secmsg,grbpos,np.empty)
                        section5 = np.concatenate((np.array((npts,drtn)),drt))
                        section5 = np.where(section5==4294967295,-1,section5)
                    elif secnum == 6:
                        # Unpack Section 6 - Just the bitmap flag
                        bmapflag = struct.unpack('>B',self._filehandle.read(1))[0]
                        if bmapflag == 0:
                            bmappos = self._filehandle.tell()-6
                        elif bmapflag == 254:
                            # Do this to keep the previous position value
                            pass
                        else:
                            bmappos = None
                        self._filehandle.seek(self._filehandle.tell()+secsize-6)
                    elif secnum == 7:
                        # Do not unpack section 7 here, but move the file pointer
                        # to after section 7.
                        self._filehandle.seek(self._filehandle.tell()+secsize-5)

                        # Update the file index.
                        self.messages += 1
                        self._index['sectionOffset'].append(copy.deepcopy(_secpos))
                        self._index['sectionSize'].append(copy.deepcopy(_secsize))
                        self._index['msgSize'].append(section0[-1])
                        self._index['msgNumber'].append(self.messages)
                        self._index['isSubmessage'].append(_isSubmessage)

                        # Create Grib2Message with data.
                        msg = Grib2Message(section0,section1,section2,section3,section4,section5,bmapflag)
                        msg._msgnum = self.messages-1
                        msg._deflist = deflist
                        msg._coordlist = coordlist
                        if not self._nodata:
                            msg._ondiskarray = Grib2MessageOnDiskArray((msg.ny,msg.nx), 2,
                                                                TYPE_OF_VALUES_DTYPE[msg.typeOfValues],
                                                                self._filehandle,
                                                                msg, pos, _secpos[6], _secpos[7])
                        self._index['msg'].append(msg)

                        # If here, then we have moved through GRIB2 section 1-7.
                        # Now we need to check the next 4 bytes after section 7.
                        trailer = struct.unpack('>i',self._filehandle.read(4))[0]

                        # If we reach the GRIB2 trailer string ('7777'), then we
                        # can break begin processing the next GRIB2 message.  If
                        # not, then we continue within the same iteration to
                        # process a GRIB2 submessage.
                        if trailer.to_bytes(4, "big") == b'7777':
                            break
                        else:
                            # If here, trailer should be the size of the first
                            # section of the next submessage, then the next byte
                            # is the section number.  Check this value.
                            nextsec = struct.unpack('>B',self._filehandle.read(1))[0]
                            if nextsec not in {2,3,4}:
                                raise ValueError("Bad GRIB2 message structure.")
                            self._filehandle.seek(self._filehandle.tell()-5)
                            _isSubmessage = True
                            continue
                    else:
                        raise ValueError("Bad GRIB2 section number.")

            except(struct.error):
                if 'r' in self.mode:
                    self._filehandle.seek(0)
                break


    @property
    def levels(self):
        if self._hasindex and not self._nodata:
            return tuple(sorted(set([msg.level for msg in self._index['msg']])))
        else:
            return None


    @property
    def variables(self):
        if self._hasindex and not self._nodata:
            return tuple(sorted(set([msg.shortName for msg in self._index['msg']])))
        else:
            return None


    def close(self):
        """Close the file handle."""
        if not self._filehandle.closed:
            self.messages = 0
            self.current_message = 0
            self._filehandle.close()
            self.closed = self._filehandle.closed


    def read(self, size: Optional[int]=None):
        """
        Read size amount of GRIB2 messages from the current position.

        If no argument is given, then size is None and all messages are returned
        from the current position in the file. This read method follows the
        behavior of Python's builtin open() function, but whereas that operates
        on units of bytes, we operate on units of GRIB2 messages.

        Parameters
        ----------
        size: default=None
            The number of GRIB2 messages to read from the current position. If
            no argument is give, the default value is None and remainder of
            the file is read.

        Returns
        -------
        read
            ``Grib2Message`` object when size = 1 or a list of Grib2Messages
            when size > 1.
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


    def seek(self, pos: int):
        """
        Set the position within the file in units of GRIB2 messages.

        Parameters
        ----------
        pos
            The GRIB2 Message number to set the file pointer to.
        """
        if self._hasindex:
            self._filehandle.seek(self._index['sectionOffset'][0][pos])
            self.current_message = pos


    def tell(self):
        """Returns the position of the file in units of GRIB2 Messages."""
        return self.current_message


    def select(self, **kwargs):
        """Select GRIB2 messages by `Grib2Message` attributes."""
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
        msg
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
        """Flush the file object buffer."""
        self._filehandle.flush()


    def levels_by_var(self, name: str):
        """
        Return a list of level strings given a variable shortName.

        Parameters
        ----------
        name
            Grib2Message variable shortName

        Returns
        -------
        levels_by_var
            A list of unique level strings.
        """
        return list(sorted(set([msg.level for msg in self.select(shortName=name)])))


    def vars_by_level(self, level: str):
        """
        Return a list of variable shortName strings given a level.

        Parameters
        ----------
        level
            Grib2Message variable level

        Returns
        -------
        vars_by_level
            A list of unique variable shortName strings.
        """
        return list(sorted(set([msg.shortName for msg in self.select(level=level)])))


class Grib2Message:
    """
    Creation class for a GRIB2 message.

    This class returns a dynamically-created Grib2Message object that
    inherits from `_Grib2Message` and grid, product, data representation
    template classes according to the template numbers for the respective
    sections. If `section3`, `section4`, or `section5` are omitted, then
    the appropriate keyword arguments for the template number `gdtn=`,
    `pdtn=`, or `drtn=` must be provided.

    Parameters
    ----------
    section0
        GRIB2 section 0 array.
    section1
        GRIB2 section 1 array.
    section2
        Local Use section data.
    section3
        GRIB2 section 3 array.
    section4
        GRIB2 section 4 array.
    section5
        GRIB2 section 5 array.

    Returns
    -------
    Msg
        A dynamically-create Grib2Message object that inherits from
        _Grib2Message, a grid definition template class, product
        definition template class, and a data representation template
        class.
    """
    def __new__(self, section0: NDArray = np.array([struct.unpack('>I',b'GRIB')[0],0,0,2,0]),
                      section1: NDArray = np.zeros((13),dtype=np.int64),
                      section2: Optional[bytes] = None,
                      section3: Optional[NDArray] = None,
                      section4: Optional[NDArray] = None,
                      section5: Optional[NDArray] = None, *args, **kwargs):

        if np.all(section1==0):
            try:
                # Python >= 3.10
                section1[5:11] = datetime.datetime.fromtimestamp(0, datetime.UTC).timetuple()[:6]
            except(AttributeError):
                # Python < 3.10
                section1[5:11] = datetime.datetime.utcfromtimestamp(0).timetuple()[:6]

        bases = list()
        if section3 is None:
            if 'gdtn' in kwargs.keys():
                gdtn = kwargs['gdtn']
                Gdt = templates.gdt_class_by_gdtn(gdtn)
                bases.append(Gdt)
                section3 = np.zeros((Gdt._len+5),dtype=np.int64)
                section3[4] = gdtn
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
                section4[1] = pdtn
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
                section5[1] = drtn
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
    """
    GRIB2 Message base class.
    """
    # GRIB2 Sections
    section0: NDArray = field(init=True,repr=False)
    section1: NDArray = field(init=True,repr=False)
    section2: bytes = field(init=True,repr=False)
    section3: NDArray = field(init=True,repr=False)
    section4: NDArray = field(init=True,repr=False)
    section5: NDArray = field(init=True,repr=False)
    bitMapFlag: templates.Grib2Metadata = field(init=True,repr=False,default=255)

    # Section 0 looked up attributes
    indicatorSection: NDArray = field(init=False,repr=False,default=templates.IndicatorSection())
    discipline: templates.Grib2Metadata = field(init=False,repr=False,default=templates.Discipline())

    # Section 1 looked up attributes
    identificationSection: NDArray = field(init=False,repr=False,default=templates.IdentificationSection())
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

    # Section 3 looked up common attributes.  Other looked up attributes are available according
    # to the Grid Definition Template.
    gridDefinitionSection: NDArray = field(init=False,repr=False,default=templates.GridDefinitionSection())
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
    earthShape: str = field(init=False,repr=False,default=templates.EarthShape())
    earthRadius: float = field(init=False,repr=False,default=templates.EarthRadius())
    earthMajorAxis: float = field(init=False,repr=False,default=templates.EarthMajorAxis())
    earthMinorAxis: float = field(init=False,repr=False,default=templates.EarthMinorAxis())
    resolutionAndComponentFlags: list = field(init=False,repr=False,default=templates.ResolutionAndComponentFlags())
    ny: int = field(init=False,repr=False,default=templates.Ny())
    nx: int = field(init=False,repr=False,default=templates.Nx())
    scanModeFlags: list = field(init=False,repr=False,default=templates.ScanModeFlags())
    projParameters: dict = field(init=False,repr=False,default=templates.ProjParameters())

    # Section 4
    productDefinitionTemplateNumber: templates.Grib2Metadata = field(init=False,repr=False,default=templates.ProductDefinitionTemplateNumber())
    productDefinitionTemplate: NDArray = field(init=False,repr=False,default=templates.ProductDefinitionTemplate())

    # Section 5 looked up common attributes.  Other looked up attributes are
    # available according to the Data Representation Template.
    numberOfPackedValues: int = field(init=False,repr=False,default=templates.NumberOfPackedValues())
    dataRepresentationTemplateNumber: templates.Grib2Metadata = field(init=False,repr=False,default=templates.DataRepresentationTemplateNumber())
    dataRepresentationTemplate: list = field(init=False,repr=False,default=templates.DataRepresentationTemplate())
    typeOfValues: templates.Grib2Metadata = field(init=False,repr=False,default=templates.TypeOfValues())

    def __post_init__(self):
        """Set some attributes after init."""
        self._auto_nans = _AUTO_NANS
        self._coordlist = None
        self._data = None
        self._deflist = None
        self._msgnum = -1
        self._ondiskarray = None
        self._orig_section5 = np.copy(self.section5)
        self._signature = self._generate_signature()
        try:
            self._sha1_section3 = hashlib.sha1(self.section3).hexdigest()
        except(TypeError):
            pass
        self.bitMapFlag = templates.Grib2Metadata(self.bitMapFlag,table='6.0')
        self.bitmap = None


    @property
    def _isNDFD(self):
        """Check if GRIB2 message is from NWS NDFD"""
        return np.all(self.section1[0:2]==[8,65535])


    @property
    def gdtn(self):
        """Return Grid Definition Template Number"""
        return self.section3[4]


    @property
    def gdt(self):
        """Return Grid Definition Template."""
        return self.gridDefinitionTemplate


    @property
    def pdtn(self):
        """Return Product Definition Template Number."""
        return self.section4[1]


    @property
    def pdt(self):
        """Return Product Definition Template."""
        return self.productDefinitionTemplate


    @property
    def drtn(self):
        """Return Data Representation Template Number."""
        return self.section5[1]


    @property
    def drt(self):
        """Return Data Representation Template."""
        return self.dataRepresentationTemplate


    @property
    def pdy(self):
        """Return the PDY ('YYYYMMDD')."""
        return ''.join([str(i) for i in self.section1[5:8]])


    @property
    def griddef(self):
        """Return a Grib2GridDef instance for a GRIB2 message."""
        return Grib2GridDef.from_section3(self.section3)


    @property
    def lats(self):
        """Return grid latitudes."""
        return self.latlons()[0]


    @property
    def lons(self):
        """Return grid longitudes."""
        return self.latlons()[1]

    @property
    def min(self):
        """Return minimum value of data."""
        return np.nanmin(self.data)


    @property
    def max(self):
        """Return maximum value of data."""
        return np.nanmax(self.data)


    @property
    def mean(self):
        """Return mean value of data."""
        return np.nanmean(self.data)


    @property
    def median(self):
        """Return median value of data."""
        return np.nanmedian(self.data)


    def __repr__(self):
        """
        Return an unambiguous string representation of the object.

        Returns
        -------
        repr
            A string representation of the object, including information from
            sections 0, 1, 3, 4, 5, and 6.
        """
        info = ''
        for sect in [0,1,3,4,5,6]:
            for k,v in self.attrs_by_section(sect,values=True).items():
                info += f'Section {sect}: {k} = {v}\n'
        return info

    def __str__(self):
        """
        Return a readable string representation of the object.

        Returns
        -------
        str
            A formatted string representation of the object, including
            selected attributes.
        """
        return (f'{self._msgnum}:d={self.refDate}:{self.shortName}:'
                f'{self.fullName} ({self.units}):{self.level}:'
                f'{self.leadTime}')


    def _generate_signature(self):
        """Generature SHA-1 hash string from GRIB2 integer sections."""
        return hashlib.sha1(np.concatenate((self.section0,self.section1,
                                            self.section3,self.section4,
                                            self.section5))).hexdigest()


    def attrs_by_section(self, sect: int, values: bool=False):
        """
        Provide a tuple of attribute names for the given GRIB2 section.

        Parameters
        ----------
        sect
            The GRIB2 section number.
        values
            Optional (default is `False`) argument to return attributes values.

        Returns
        -------
        attrs_by_section
            A list of attribute names or dict of name:value pairs if `values =
            True`.
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
        Pack GRIB2 section data into a binary message.

        It is the user's responsibility to populate the GRIB2 section
        information with appropriate metadata.
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
        self.section3[1] = self.nx * self.ny
        self._msg,self._pos = g2clib.grib2_addgrid(self._msg,self.gridDefinitionSection,
                                                   self.gridDefinitionTemplate,
                                                   self._deflist)
        self._sections.append(3)

        # Prepare data.
        if self._data is None:
            if self._ondiskarray is None:
                raise ValueError("Grib2Message object has no data, thus it cannot be packed.")
        field = np.copy(self.data)
        if self.scanModeFlags is not None:
            if self.scanModeFlags[3]:
                fieldsave = field.astype('f') # Casting makes a copy
                field[1::2,:] = fieldsave[1::2,::-1]
        fld = field.astype('f')

        # Prepare bitmap, if necessary
        bitmapflag = self.bitMapFlag.value
        if bitmapflag == 0:
            if self.bitmap is not None:
                bmap = np.ravel(self.bitmap).astype(DEFAULT_NUMPY_INT)
            else:
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
        if bitmapflag in {0,254}:
            fld = np.where(np.isnan(fld),0,fld)
        else:
            if np.isnan(fld).any():
                if hasattr(self,'priMissingValue'):
                    fld = np.where(np.isnan(fld),self.priMissingValue,fld)
            if hasattr(self,'_missvalmap'):
                if hasattr(self,'priMissingValue'):
                    fld = np.where(self._missvalmap==1,self.priMissingValue,fld)
                if hasattr(self,'secMissingValue'):
                    fld = np.where(self._missvalmap==2,self.secMissingValue,fld)

        # Add sections 4, 5, 6, and 7.
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
        self._sections.append(6)
        self._sections.append(7)

        # Finalize GRIB2 message with section 8.
        self._msg, self._pos = g2clib.grib2_end(self._msg)
        self._sections.append(8)
        self.section0[-1] = len(self._msg)


    @property
    def data(self) -> np.array:
        """Access the unpacked data values."""
        if self._data is None:
            if self._auto_nans != _AUTO_NANS:
                self._data = self._ondiskarray
            self._data = np.asarray(self._ondiskarray)
        return self._data


    @data.setter
    def data(self, data):
        if not isinstance(data, np.ndarray):
            raise ValueError('Grib2Message data only supports numpy arrays')
        self._data = data


    def flush_data(self):
        """
        Flush the unpacked data values from the Grib2Message object.

        Note: If the Grib2Message object was constructed from "scratch" (i.e.
        not read from file), this method will remove the data array from
        the object and it cannot be recovered.
        """
        self._data = None
        self.bitmap = None


    def __getitem__(self, item):
        return self.data[item]


    def __setitem__(self, item):
        raise NotImplementedError('assignment of data not supported via setitem')


    def latlons(self, *args, **kwrgs):
        """Alias for `grib2io.Grib2Message.grid` method."""
        return self.grid(*args, **kwrgs)


    def grid(self, unrotate: bool=True):
        """
        Return lats,lons (in degrees) of grid.

        Currently can handle reg. lat/lon,cglobal Gaussian, mercator,
        stereographic, lambert conformal, albers equal-area, space-view and
        azimuthal equidistant grids.

        Parameters
        ----------
        unrotate
            If `True` [DEFAULT], and grid is rotated lat/lon, then unrotate the
            grid, otherwise `False`, do not.

        Returns
        -------
        lats, lons : numpy.ndarray
            Returns two numpy.ndarrays with dtype=numpy.float32 of grid
            latitudes and longitudes in units of degrees.
        """
        if self._sha1_section3 in _latlon_datastore.keys():
            return (_latlon_datastore[self._sha1_section3]['latitude'],
                    _latlon_datastore[self._sha1_section3]['longitude'])
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
            from grib2io.utils.gauss_grid import gaussian_latitudes
            lon1, lat1 = self.longitudeFirstGridpoint, self.latitudeFirstGridpoint
            lon2, lat2 = self.longitudeLastGridpoint, self.latitudeLastGridpoint
            nlats = self.ny
            if not reggrid: # Reduced Gaussian grid.
                nlons = 2*nlats
                dlon = 360./nlons
            else:
                nlons = self.nx
                dlon = self.gridlengthXDirection
            lons = np.linspace(lon1,lon2,nlons)
            # Compute Gaussian lats (north to south)
            lats = gaussian_latitudes(nlats)
            if lat1 < lat2:  # reverse them if necessary
                lats = lats[::-1]
            lons,lats = np.meshgrid(lons,lats)
        elif gdtn in {10,20,30,31,110}:
            # Mercator, Lambert Conformal, Stereographic, Albers Equal Area,
            # Azimuthal Equidistant
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
            from grib2io.utils import arakawa_rotated_grid
            from grib2io.utils.rotated_grid import DEG2RAD
            di, dj = 0.0, 0.0
            do_180 = False
            idir = 1 if self.scanModeFlags[0] == 0 else -1
            jdir = -1 if self.scanModeFlags[1] == 0 else 1
            grid_oriented = 0 if self.resolutionAndComponentFlags[4] == 0 else 1
            do_rot = 1 if grid_oriented == 1 else 0
            la1 = self.latitudeFirstGridpoint
            lo1 = self.longitudeFirstGridpoint
            clon = self.longitudeCenterGridpoint
            clat = self.latitudeCenterGridpoint
            lasp = clat - 90.0
            losp = clon
            llat, llon = arakawa_rotated_grid.ll2rot(la1,lo1,lasp,losp)
            la2, lo2 = arakawa_rotated_grid.rot2ll(-llat,-llon,lasp,losp)
            rlat = -llat
            rlon = -llon
            if self.nx == 1:
                di = 0.0
            elif idir == 1:
                ti = rlon
                while ti < llon:
                    ti += 360.0
                di = (ti - llon)/float(self.nx-1)
            else:
                ti = llon
                while ti < rlon:
                    ti += 360.0
                di = (ti - rlon)/float(self.nx-1)
            if self.ny == 1:
               dj = 0.0
            else:
                dj = (rlat - llat)/float(self.ny-1)
                if dj < 0.0:
                    dj = -dj
            if idir == 1:
                if llon > rlon:
                    llon -= 360.0
                if llon < 0 and rlon > 0:
                    do_180 = True
            else:
                if rlon > llon:
                    rlon -= 360.0
                if rlon < 0 and llon > 0:
                    do_180 = True
            xlat1d = llat + (np.arange(self.ny)*jdir*dj)
            xlon1d = llon + (np.arange(self.nx)*idir*di)
            xlons, xlats = np.meshgrid(xlon1d,xlat1d)
            rot2ll_vectorized = np.vectorize(arakawa_rotated_grid.rot2ll)
            lats, lons = rot2ll_vectorized(xlats,xlons,lasp,losp)
            if do_180:
                lons = np.where(lons>180.0,lons-360.0,lons)
            vector_rotation_angles_vectorized = np.vectorize(arakawa_rotated_grid.vector_rotation_angles)
            rots = vector_rotation_angles_vectorized(lats, lons, clat, losp, xlats)
            del xlat1d, xlon1d, xlats, xlons
        else:
            raise ValueError('Unsupported grid')

        _latlon_datastore[self._sha1_section3] = dict(latitude=lats,longitude=lons)
        try:
            _latlon_datastore[self._sha1_section3]['vector_rotation_angles'] = rots
        except(NameError):
            pass

        return lats, lons


    def map_keys(self):
        """
        Unpack data grid replacing integer values with strings.

        These types of fields are categorical or classifications where data
        values do not represent an observable or predictable physical quantity.
        An example of such a field would be [Dominant Precipitation Type -
        DPTYPE](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-201.shtml)

        Returns
        -------
        map_keys
            numpy.ndarray of string values per element.
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


    def to_bytes(self, validate: bool=True):
        """
        Return packed GRIB2 message in bytes format.

        This will be useful for exporting data in non-file formats. For example,
        can be used to output grib data directly to S3 using the boto3 client
        without the need to write a temporary file to upload first.

        Parameters
        ----------
        validate: default=True
            If `True` (DEFAULT), validates first/last four bytes for proper
            formatting, else returns None. If `False`, message is output as is.

        Returns
        -------
        to_bytes
            Returns GRIB2 formatted message as bytes.
        """
        if hasattr(self,'_msg'):
            if validate:
                if self.validate():
                    return self._msg
                else:
                    return None
            else:
                return self._msg
        else:
            return None


    def interpolate(self, method, grid_def_out, method_options=None, drtn=None,
                    num_threads=1):
        """
        Grib2Message Interpolator

        Performs spatial interpolation via the [NCEPLIBS-ip
        library](https://github.com/NOAA-EMC/NCEPLIBS-ip). This interpolate
        method only supports scalar interpolation. If you need to perform
        vector interpolation, use the module-level `grib2io.interpolate`
        function.

        Parameters
        ----------
        method
            Interpolate method to use. This can either be an integer or string
            using the following mapping:

            | Interpolate Scheme | Integer Value |
            | :---:              | :---:         |
            | 'bilinear'         | 0             |
            | 'bicubic'          | 1             |
            | 'neighbor'         | 2             |
            | 'budget'           | 3             |
            | 'spectral'         | 4             |
            | 'neighbor-budget'  | 6             |

        grid_def_out : grib2io.Grib2GridDef
            Grib2GridDef object of the output grid.
        method_options : list of ints, optional
            Interpolation options. See the NCEPLIBS-ip documentation for
            more information on how these are used.
        drtn
            Data Representation Template to be used for the returned
            interpolated GRIB2 message. When `None`, the data representation
            template of the source GRIB2 message is used. Once again, it is the
            user's responsibility to properly set the Data Representation
            Template attributes.
        num_threads : int, optional
            Number of OpenMP threads to use for interpolation. The default
            value is 1. If grib2io_interp was not built with OpenMP, then
            this keyword argument and value will have no impact.

        Returns
        -------
        interpolate
            If interpolating to a grid, a new Grib2Message object is returned.
            The GRIB2 metadata of the new Grib2Message object is identical to
            the input except where required to be different because of the new
            grid specs and possibly a new data representation template.

            If interpolating to station points, the interpolated data values are
            returned as a numpy.ndarray.
        """
        section0 = self.section0
        section0[-1] = 0
        gds = [0, grid_def_out.npoints, 0, 255, grid_def_out.gdtn]
        section3 = np.concatenate((gds,grid_def_out.gdt))
        drtn = self.drtn if drtn is None else drtn

        msg = Grib2Message(section0,self.section1,self.section2,section3,
                           self.section4,None,self.bitMapFlag.value,drtn=drtn)

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
                                method_options=method_options,num_threads=num_threads).reshape(msg.ny,msg.nx)
        msg.section5[0] = grid_def_out.npoints
        return msg


    def validate(self):
        """
        Validate a complete GRIB2 message.

        The g2c library does its own internal validation when g2_gribend() is called, but
        we will check in grib2io also. The validation checks if the first 4 bytes in
        self._msg is 'GRIB' and '7777' as the last 4 bytes and that the message length in
        section 0 equals the length of the packed message.

        Returns
        -------
        `True` if the packed GRIB2 message is complete and well-formed, `False` otherwise.
        """
        valid = False
        if hasattr(self,'_msg'):
            if self._msg[0:4]+self._msg[-4:] == b'GRIB7777':
                if self.section0[-1] == len(self._msg):
                    valid = True
        return valid


@dataclass
class Grib2MessageOnDiskArray:
    shape: str
    ndim: str
    dtype: str
    filehandle: open
    msg: Grib2Message
    offset: int
    bitmap_offset: int
    data_offset: int

    def __array__(self, dtype=None):
        return np.asarray(_data(self.filehandle, self.msg, self.bitmap_offset, self.data_offset),dtype=dtype)


def _data(
    filehandle: open,
    msg: Grib2Message,
    bitmap_offset: Optional[int],
    data_offset: int,
)-> np.array:
    """
    Returns an unpacked data grid.

    Parameters
    ----------
    filehandle
        A filehandle object pointing to a GRIB2 message.
    msg
        A Grib2Message object.
    bitmap_offset
        The offset to the beginning of the bitmap section.
    data_offset
        The offset to the beginning of the data section.

    Returns
    -------
    numpy.ndarray
        A numpy.ndarray with shape (ny,nx). By default the array
        dtype=np.float32, but could be np.int32 if Grib2Message.typeOfValues is
        integer.
    """
    gds = msg.section3[0:5]
    gdt = msg.section3[5:]
    drt = msg._orig_section5[2:]
    nx, ny = msg.nx, msg.ny

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
    if bitmap_offset is not None:
        # Position file pointer to the beginning of bitmap section.
        filehandle.seek(bitmap_offset)
        bmap_size,num = struct.unpack('>IB',filehandle.read(5))
        filehandle.seek(filehandle.tell()-5)
        ipos = 0
        bmap,bmapflag = g2clib.unpack6(filehandle.read(bmap_size),msg.section3[1],ipos,np.empty)
        if bmap is not None:
            msg.bitmap = bmap.reshape((ny,nx)).astype(np.int8)

    if hasattr(msg,'scanModeFlags'):
        scanModeFlags = msg.scanModeFlags
        storageorder = 'F' if scanModeFlags[2] else 'C'

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


def set_auto_nans(value: bool):
    """
    Handle missing values in GRIB2 message data.

    Parameters
    ----------
    value
        If `True` [DEFAULT], missing values in GRIB2 message data will be set to
        `np.nan` and if `False`, missing values will present in the data array.
        If a bitmap is used, then `np.nan` will be used regardless of this
        setting.
    """
    global _AUTO_NANS
    if isinstance(value,bool):
        _AUTO_NANS = value
    else:
        raise TypeError(f"Argument must be bool")


def interpolate(a, method: Union[int, str], grid_def_in, grid_def_out,
                method_options=None, num_threads=1):
    """
    This is the module-level interpolation function.

    This interfaces with the grib2io_interp component package that interfaces to
    the [NCEPLIBS-ip library](https://github.com/NOAA-EMC/NCEPLIBS-ip).

    Parameters
    ----------
    a : numpy.ndarray or tuple
        Input data.  If `a` is a `numpy.ndarray`, scalar interpolation will be
        performed.  If `a` is a `tuple`, then vector interpolation will be
        performed with the assumption that u = a[0] and v = a[1] and are both
        `numpy.ndarray`.

        These data are expected to be in 2-dimensional form with shape (ny, nx)
        or 3-dimensional (:, ny, nx) where the 1st dimension represents another
        spatial, temporal, or classification (i.e. ensemble members) dimension.
        The function will properly flatten the (ny,nx) dimensions into (nx * ny)
        acceptable for input into the interpolation subroutines.
    method
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

    grid_def_in : grib2io.Grib2GridDef
        Grib2GridDef object for the input grid.
    grid_def_out : grib2io.Grib2GridDef
        Grib2GridDef object for the output grid or station points.
    method_options : list of ints, optional
        Interpolation options. See the NCEPLIBS-ip documentation for
        more information on how these are used.
    num_threads : int, optional
        Number of OpenMP threads to use for interpolation. The default
        value is 1. If grib2io_interp was not built with OpenMP, then
        this keyword argument and value will have no impact.

    Returns
    -------
    interpolate
        Returns a `numpy.ndarray` when scalar interpolation is performed or a
        `tuple` of `numpy.ndarray`s when vector interpolation is performed with
        the assumptions that 0-index is the interpolated u and 1-index is the
        interpolated v.
    """
    import grib2io_interp
    from grib2io_interp import interpolate

    prev_num_threads = 1
    try:
        import grib2io_interp
        if grib2io_interp.has_openmp_support:
            prev_num_threads = grib2io_interp.get_openmp_threads()
            grib2io_interp.set_openmp_threads(num_threads)
    except(AttributeError):
        pass

    if isinstance(method,int) and method not in _interp_schemes.values():
        raise ValueError('Invalid interpolation method.')
    elif isinstance(method,str):
        if method in _interp_schemes.keys():
            method = _interp_schemes[method]
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
        if np.any(np.isnan(a)):
            ibi = np.zeros((a.shape[0]),dtype=np.int32)+1
            li = np.where(np.isnan(a),0,1).astype(np.int8)
        else:
            ibi = np.zeros((a.shape[0]),dtype=np.int32)
            li = np.zeros(a.shape,dtype=np.int8)
        go = np.zeros((a.shape[0],no),dtype=np.float32)
        no,ibo,lo,iret = interpolate.interpolate_scalar(method,method_options,
                                                 grid_def_in.gdtn,grid_def_in.gdt,
                                                 grid_def_out.gdtn,grid_def_out.gdt,
                                                 ibi,li.T,a.T,go.T,rlat,rlon)
        lo = lo.T.reshape(newshp)
        out = go.reshape(newshp)
        out = np.where(lo==0,np.nan,out)
    elif isinstance(a,tuple):
        # Vector
        if np.any(np.isnan(a)):
            ibi = np.zeros((a.shape[0]),dtype=np.int32)+1
            li = np.where(np.isnan(a),0,1).astype(np.int8)
        else:
            ibi = np.zeros((a.shape[0]),dtype=np.int32)
            li = np.zeros(a.shape,dtype=np.int8)
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
        lo = lo[:,0].reshape(newshp)
        uo = uo.reshape(new)
        vo = vo.reshape(new)
        uo = np.where(lo==0,np.nan,uo)
        vo = np.where(lo==0,np.nan,vo)
        out = (uo,vo)

    del rlat
    del rlon

    try:
        if grib2io_interp.has_openmp_support:
            grib2io_interp.set_openmp_threads(prev_num_threads)
    except(AttributeError):
        pass

    return out


def interpolate_to_stations(a, method, grid_def_in, lats, lons,
                            method_options=None, num_threads=1):
    """
    Module-level interpolation function for interpolation to stations.

    Interfaces with the grib2io_interp component package that interfaces to the
    [NCEPLIBS-ip
    library](https://github.com/NOAA-EMC/NCEPLIBS-ip). It supports scalar and
    vector interpolation according to the type of object a.

    Parameters
    ----------
    a : numpy.ndarray or tuple
        Input data.  If `a` is a `numpy.ndarray`, scalar interpolation will be
        performed.  If `a` is a `tuple`, then vector interpolation will be
        performed with the assumption that u = a[0] and v = a[1] and are both
        `numpy.ndarray`.

        These data are expected to be in 2-dimensional form with shape (ny, nx)
        or 3-dimensional (:, ny, nx) where the 1st dimension represents another
        spatial, temporal, or classification (i.e. ensemble members) dimension.
        The function will properly flatten the (ny,nx) dimensions into (nx * ny)
        acceptable for input into the interpolation subroutines.
    method
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

    grid_def_in : grib2io.Grib2GridDef
        Grib2GridDef object for the input grid.
    lats : numpy.ndarray or list
        Latitudes for station points
    lons : numpy.ndarray or list
        Longitudes for station points
    method_options : list of ints, optional
        Interpolation options. See the NCEPLIBS-ip documentation for
        more information on how these are used.
    num_threads : int, optional
        Number of OpenMP threads to use for interpolation. The default
        value is 1. If grib2io_interp was not built with OpenMP, then
        this keyword argument and value will have no impact.

    Returns
    -------
    interpolate_to_stations
        Returns a `numpy.ndarray` when scalar interpolation is performed or a
        `tuple` of `numpy.ndarray`s when vector interpolation is performed with
        the assumptions that 0-index is the interpolated u and 1-index is the
        interpolated v.
    """
    import grib2io_interp
    from grib2io_interp import interpolate

    prev_num_threads = 1
    try:
        import grib2io_interp
        if grib2io_interp.has_openmp_support:
            prev_num_threads = grib2io_interp.get_openmp_threads()
            grib2io_interp.set_openmp_threads(num_threads)
    except(AttributeError):
        pass

    if isinstance(method,int) and method not in _interp_schemes.values():
        raise ValueError('Invalid interpolation method.')
    elif isinstance(method,str):
        if method in _interp_schemes.keys():
            method = _interp_schemes[method]
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

    try:
        if grib2io_interp.has_openmp_support:
            grib2io_interp.set_openmp_threads(prev_num_threads)
    except(AttributeError):
        pass

    return out


@dataclass
class Grib2GridDef:
    """
    Class for Grid Definition Template Number and Template as attributes.

    This allows for cleaner looking code when passing these metadata around.
    For example, the `grib2io._Grib2Message.interpolate` method and
    `grib2io.interpolate` function accepts these objects.
    """
    gdtn: int
    gdt: NDArray

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


def _adjust_array_shape_for_interp(a, grid_def_in, grid_def_out):
    """
    Adjust shape of input data array for interpolation to grids.

    Returned array will conform to the dimensionality used in the NCEPLIBS-ip
    interpolation subroutine arguments for grids.

    Parameters
    ----------
    a : numpy.ndarray or tuple
        Input data.  If `a` is a `numpy.ndarray`, scalar interpolation will be
        performed.  If `a` is a `tuple`, then vector interpolation will be
        performed with the assumption that u = a[0] and v = a[1] and are both
        `numpy.ndarray`.

        These data are expected to be in 2-dimensional form with shape (ny, nx)
        or 3-dimensional (:, ny, nx) where the 1st dimension represents another
        spatial, temporal, or classification (i.e. ensemble members) dimension.
        The function will properly flatten the (ny,nx) dimensions into (nx * ny)
        acceptable for input into the interpolation subroutines.
    grid_def_in : grib2io.Grib2GridDef
        Grib2GridDef object for the input grid.
    grid_def_out : grib2io.Grib2GridDef
        Grib2GridDef object for the output grid or station points.

    Returns
    -------
    _adjust_array_shape_for_interp
        Returns a `tuple` of the adjusted array and the new shape.
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
    Adjust shape of input data array for interpolation to stations.

    Returned array will conform to the dimensionality used in the NCEPLIBS-ip
    interpolation subroutine arguments for grids.

    Parameters
    ----------
    a : numpy.ndarray or tuple
        Input data.  If `a` is a `numpy.ndarray`, scalar interpolation will be
        performed.  If `a` is a `tuple`, then vector interpolation will be
        performed with the assumption that u = a[0] and v = a[1] and are both
        `numpy.ndarray`.

        These data are expected to be in 2-dimensional form with shape (ny, nx)
        or 3-dimensional (:, ny, nx) where the 1st dimension represents another
        spatial, temporal, or classification (i.e. ensemble members) dimension.
        The function will properly flatten the (ny,nx) dimensions into (nx * ny)
        acceptable for input into the interpolation subroutines.
    grid_def_in : grib2io.Grib2GridDef
        Grib2GridDef object for the input grid.
    grid_def_out : grib2io.Grib2GridDef
        Grib2GridDef object for the output grid or station points.

    Returns
    -------
    _adjust_array_shape_for_interp
        Returns a `tuple` of the adjusted array and the new shape.
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
