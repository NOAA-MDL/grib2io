"""
Introduction
============

grib2io is a Python package that provides an interface to the [NCEP GRIB2 C (g2c)](https://github.com/NOAA-EMC/NCEPLIBS-g2c) 
library for the purpose of reading and writing GRIB2 Messages.  WMO GRIdded Binary, Edition 2 (GRIB2) files store 2-D meteorological
data. A physical file can contain one or more GRIB2 messages.  File IO is handled in Python returning
a binary string of the GRIB2 message which is then passed to the g2c library for decoding of GRIB2 metadata
and unpacking of data values.
"""
__version__ = '0.9.1'

import g2clib
import builtins
import collections
import copy
import datetime
import os
#import pdb
import re
import struct
import math
import warnings

from numpy import ma
import numpy as np
import pyproj

from . import tables
from . import utils


DEFAULT_FILL_VALUE = 9.9692099683868690e+36
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
    """
    def __init__(self, filename, mode='r'):
        """
        Class Constructor

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
        self.decode = True
        if 'r' in self.mode: self._build_index()
        # FIX: Cannot perform reads on mode='a'
        #if 'a' in self.mode and self.size > 0: self._build_index()
        if self._hasindex:
            self.variables = tuple(sorted(set(filter(None,self._index['shortName']))))


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
        keys = self.__dict__.keys()
        for k in keys:
            if not k.startswith('_'):
                strings.append('%s = %s\n'%(k,self.__dict__[k]))
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
            if key == 0: return None
            self._filehandle.seek(self._index['offset'][key])
            return [Grib2Message(msg=self._filehandle.read(self._index['size'][key]),
                                 source=self,
                                 num=self._index['messageNumber'][key],
                                 decode=self.decode)]
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
        self._index['discipline'] = [None]
        self._index['edition'] = [None]
        self._index['size'] = [None]
        self._index['submessageOffset'] = [None]
        self._index['submessageBeginSection'] = [None]
        self._index['isSubmessage'] = [None]
        self._index['messageNumber'] = [None]
        self._index['identificationSection'] = [None]
        self._index['refDate'] = [None]
        self._index['productDefinitionTemplateNumber'] = [None]
        self._index['productDefinitionTemplate'] = [None]
        self._index['leadTime'] = [None]
        self._index['duration'] = [None]
        self._index['shortName'] = [None]
        self._index['bitMap'] = [None]

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
                    _refdate = utils.getdate(_grbsec1[5],_grbsec1[6],_grbsec1[7],_grbsec1[8])
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
                                    _gds,_gdtn,_deflist,_grbpos = g2clib.unpack3(_grbmsg,_grbpos,np.empty)
                                elif secnum == 4:
                                    self._filehandle.seek(self._filehandle.tell()-5)
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 4
                                    _pdt,_pdtnum,_coordlist,_grbpos = g2clib.unpack4(_grbmsg,_grbpos,np.empty)
                                    _pdt = _pdt.tolist()
                                    _varinfo = tables.get_varinfo_from_table(discipline,_pdt[0],_pdt[1])
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
                            self._index['discipline'].append(discipline)
                            self._index['edition'].append(edition)
                            self._index['size'].append(size)
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            self._index['identificationSection'].append(_grbsec1)
                            self._index['refDate'].append(_refdate)
                            self._index['productDefinitionTemplateNumber'].append(_pdtnum)
                            self._index['productDefinitionTemplate'].append(_pdt)
                            self._index['leadTime'].append(utils.getleadtime(_grbsec1,_pdtnum,_pdt))
                            self._index['duration'].append(utils.getduration(_pdtnum,_pdt))
                            self._index['shortName'].append(_varinfo[2])
                            self._index['bitMap'].append(_bmap)
                            if _issubmessage:
                                self._index['submessageOffset'].append(_submsgoffset)
                                self._index['submessageBeginSection'].append(_submsgbegin)
                            else:
                                self._index['submessageOffset'].append(0)
                                self._index['submessageBeginSection'].append(_submsgbegin)
                            break
                        else:
                            self._filehandle.seek(self._filehandle.tell()-4)
                            self.messages += 1
                            self._index['offset'].append(pos)
                            self._index['discipline'].append(discipline)
                            self._index['edition'].append(edition)
                            self._index['size'].append(size)
                            self._index['messageNumber'].append(self.messages)
                            self._index['isSubmessage'].append(_issubmessage)
                            self._index['identificationSection'].append(_grbsec1)
                            self._index['refDate'].append(_refdate)
                            self._index['productDefinitionTemplateNumber'].append(_pdtnum)
                            self._index['productDefinitionTemplate'].append(_pdt)
                            self._index['leadTime'].append(utils.getleadtime(_grbsec1,_pdtnum,_pdt))
                            self._index['duration'].append(utils.getduration(_pdtnum,_pdt))
                            self._index['shortName'].append(_varinfo[2])
                            self._index['bitMap'].append(_bmap)
                            self._index['submessageOffset'].append(_submsgoffset)
                            self._index['submessageBeginSection'].append(_submsgbegin)
                            continue

                #print(len(self._index['offset']),self.messages)

            except(struct.error):
                self._filehandle.seek(0)
                break

        self._hasindex = True


    def _find_level(self,level):
        """
        """
        # Determine level or layer....TBD
        #
        # IMPORTANT: Set idx_count to the number of searches.
        if any(re.findall(r'ground|surface|sfc', level, re.IGNORECASE)):
            # Ground/Surface - GRIB ID = 1
            sfctypeid = 1
            idx_type = np.where(np.asarray([i[9] if i is not None else None for i in self._index['productDefinitionTemplate']])==sfctypeid)[0]
            idxs = idx_type
            idx_count = 1
        elif any(re.findall(r'mb|pa|hpa', level, re.IGNORECASE)):
            # Isobaric Surface (i.e. pressure level) - GRIB ID = 100
            sfctypeid = 100
            idx_type = np.where(np.asarray([i[9] if i is not None else None for i in self._index['productDefinitionTemplate']])==sfctypeid)[0]
            val = float(re.sub("[^\d\.]", "",level))
            if any(re.findall(r'mb|hpa', level, re.IGNORECASE)): val *= 100
            idx_val = np.where(np.asarray([i[11] if i is not None else None for i in self._index['productDefinitionTemplate']])==val)[0]
            idxs = np.concatenate((idx_type,idx_val))
            idx_count = 2
        elif any(re.findall(r'sig|sigma', level, re.IGNORECASE)):
            # Sigma Level - GRIB ID = 104
            sfctypeid = 104
            idx_type = np.where(np.asarray([i[9] if i is not None else None for i in self._index['productDefinitionTemplate']])==sfctypeid)[0]
            val = float(re.sub("[^\d\.]", "",level))
            idx_val = np.where(np.asarray([i[11]/(10**i[10]) if i is not None else None for i in self._index['productDefinitionTemplate']])==val)[0]
            idxs = np.concatenate((idx_type,idx_val))
            idx_count = 2
        elif any(re.findall(r'm|meter', level, re.IGNORECASE)):
            # Specified Height Level Above (GRIB ID = 103) or Below Ground (GRIB ID = 106) Level
            sfctypeid = 103
            if any(re.findall(r'above ground|agl', level, re.IGNORECASE)):
                sfctypeid = 103
            if any(re.findall(r'below ground|bgl', level, re.IGNORECASE)):
                sfcid = 106
            idx_type = np.where(np.asarray([i[9] if i is not None else None for i in self._index['productDefinitionTemplate']])==sfctypeid)[0]
            val = float(re.sub("[^\d\.]", "",level))
            idx_val = np.where(np.asarray([i[11] if i is not None else None for i in self._index['productDefinitionTemplate']])==val)[0]
            idxs = np.concatenate((idx_type,idx_val))
            idx_count = 2
        return [i[0] for i in collections.Counter(idxs).most_common() if i[1] == idx_count]


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
                msgs.append(Grib2Message(msg=self._filehandle.read(self._index['size'][n]),
                                         source=self,
                                         num=self._index['messageNumber'][n],
                                         decode=self.decode))
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

        **`leadTime : int`** specifying ending lead time (in units of hours) of a GRIB2 Message.

        **`level : str`** string of value and units of the level of interest. For pressure level, use either:
        `mb`, `pa`, or `hpa`.  For sigma levels, use `sig` or `sigma`.  For geometric height level, use `m` or `meter`
        with optional `above ground` or `agl` [DEFAULT] or `below ground" or `bgl`.

        **`refDate : int`** specifying the reference date in `YYYYMMDDHH[MMSS]` format.

        **`shortName : str`** the GRIB2 `shortName`.  This is the abbreviation name found in the NCEP GRIB2 tables.
        """
        kwargs_allowed = ['duration','leadTime','level','refDate','shortName']
        idxs = {}
        for k,v in kwargs.items():
            if k not in kwargs_allowed: continue
            if k == 'duration':
                idxs[k] = np.where(np.asarray([i if i is not None else None for i in self._index['duration']])==v)[0]
            elif k == 'leadTime':
                idxs[k] = np.where(np.asarray([i if i is not None else None for i in self._index['leadTime']])==v)[0]
            elif k == 'level':
                idxs[k] = self._find_level(v)
            elif k == 'refDate':
                idxs[k] = np.where(np.asarray(self._index['refDate'])==v)[0]
            elif k == 'shortName':
                idxs[k] = np.where(np.array(self._index['shortName'])==v)[0]
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
        self._filehandle.write(msg._msg)
        self.size = os.path.getsize(self.name)
        self.messages += 1
        self.current_message += 1

class Grib2Message:
    def __init__(self, msg=None, source=None, num=-1, decode=True, discipline=None, idsect=None):
        """
        Class Constructor

        Usage
        -----

        The instantiation of this class can handle a GRIB2 message from an existing file or the
        creation of new GRIB2 message.

        To create a new GRIB2 message, provide the appropriate values to the arguments
        `discipline` and `idsect`.  When these 2 arguments are not `None`, then a new GRIB2 message is
        created. NOTE: All other keyword arguments are ignored when a new message is created.

        ...

        Parameters
        ----------

        **`msg`**: Binary string representing the GRIB2 Message read from file.

        **`source`**: Source of where where this GRIB2 message originated 
        from (i.e. the input file). This allow for interaction with the 
        instance of `grib2io.open`. Default is None.

        **`num`**: integer GRIB2 Message number from `grib2io.open`. Default value is -1.

        **`decode`**: If True [DEFAULT], decode GRIB2 section lists into metadata 
        instance variables.

        **`discipline`**: integer GRIB2 Discipline [GRIB2 Table 0.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table0-0.shtml)

        **`idsect`**: Sequence containing GRIB1 Identification Section values (Section 1).
        - idsect[0] = Id of orginating centre - [ON388 - Table 0](https://www.nco.ncep.noaa.gov/pmb/docs/on388/table0.html)
        - idsect[1] = Id of orginating sub-centre - [ON388 - Table C](https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablec.html)
        - idsect[2] = GRIB Master Tables Version Number - [Code Table 1.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-0.shtml)
        - idsect[3] = GRIB Local Tables Version Number - [Code Table 1.1](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-1.shtml)
        - idsect[4] = Significance of Reference Time - [Code Table 1.2](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-2.shtml)
        - idsect[5] = Reference Time - Year (4 digits)
        - idsect[6] = Reference Time - Month
        - idsect[7] = Reference Time - Day
        - idsect[8] = Reference Time - Hour
        - idsect[9] = Reference Time - Minute
        - idsect[10] = Reference Time - Second
        - idsect[11] = Production status of data - [Code Table 1.3](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-3.shtml)
        - idsect[12]= Type of processed data - [Code Table 1.4](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-4.shtml)
        """
        self._source = source
        self._msgnum = num
        self._decode = decode
        self._pos = 0
        self._datapos = 0
        self._sections = []
        self.hasLocalUseSection = False
        self.isNDFD = False
        if discipline is not None and idsect is not None:
            # New message
            self._msg,self._pos = g2clib.grib2_create(np.array([discipline,GRIB2_EDITION_NUMBER],np.int32),
                                                      np.array(idsect,np.int32))
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
        #self.md5[0] = _getmd5str(self.indicatorSection)

        # Section 1 - Identification Section via g2clib.unpack1()
        self.identificationSection,self._pos = g2clib.unpack1(self._msg,self._pos,np.empty)
        self.identificationSection = self.identificationSection.tolist()
        self._sections.append(1)
        if self.identificationSection[0:2] == [8,65535]: self.isNDFD = True

        # After Section 1, perform rest of GRIB2 Decoding inside while loop
        # to account for sub-messages.
        sectnum = 1
        while True:
            if self._msg[self._pos:self._pos+4].decode('ascii','ignore') == '7777':
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
                self.gridDefinitionSection = _gds.tolist()
                self.gridDefinitionTemplateNumber = Grib2Metadata(int(_gds[4]),table='3.1')
                self.gridDefinitionTemplate = _gdt.tolist()
                self.defList = _deflist.tolist()
                self._sections.append(3)
                #self.md5[3] = _getmd5str([self.gridDefinitionTemplateNumber]+self.gridDefinitionTemplate)

            # Section 4 - Product Definition Section.
            elif sectnum == 4:
                _pdt,_pdtn,_coordlst,self._pos = g2clib.unpack4(self._msg,self._pos,np.empty)
                self.productDefinitionTemplate = _pdt.tolist()
                self.productDefinitionTemplateNumber = Grib2Metadata(int(_pdtn),table='4.0')
                self.coordinateList = _coordlst.tolist()
                self._sections.append(4)
                #self.md5[4] = _getmd5str([self.productDefinitionTemplateNumber]+self.productDefinitionTemplate)

            # Section 5 - Data Representation Section.
            elif sectnum == 5:
                _drt,_drtn,_npts,self._pos = g2clib.unpack5(self._msg,self._pos,np.empty)
                self.dataRepresentationTemplate = _drt.tolist()
                self.dataRepresentationTemplateNumber = Grib2Metadata(int(_drtn),table='5.0')
                self.numberOfDataPoints = _npts
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

        if self._decode: self.decode()

    def decode(self):
        """
        Decode the unpacked GRIB2 integer-coded metadata in human-readable form and linked to GRIB2 tables.
        """

        # Section 0 - Indictator Section
        self.discipline = Grib2Metadata(self.indicatorSection[2],table='0.0')

        # Section 1 - Indentification Section.
        self.originatingCenter = Grib2Metadata(self.identificationSection[0],table='originating_centers')
        self.originatingSubCenter = Grib2Metadata(self.identificationSection[1],table='originating_subcenters')
        self.masterTableInfo = Grib2Metadata(self.identificationSection[2],table='1.0')
        self.localTableInfo = Grib2Metadata(self.identificationSection[3],table='1.1')
        self.significanceOfReferenceTime = Grib2Metadata(self.identificationSection[4],table='1.2')
        self.year = self.identificationSection[5]
        self.month = self.identificationSection[6]
        self.day = self.identificationSection[7]
        self.hour = self.identificationSection[8]
        self.minute = self.identificationSection[9]
        self.second = self.identificationSection[10]
        self.refDate = (self.year*1000000)+(self.month*10000)+(self.day*100)+self.hour
        self.dtReferenceDate = datetime.datetime(self.year,self.month,self.day,
                                                 hour=self.hour,minute=self.minute,
                                                 second=self.second)
        self.productionStatus = Grib2Metadata(self.identificationSection[11],table='1.3')
        self.typeOfData = Grib2Metadata(self.identificationSection[12],table='1.4')

        # ----------------------------
        # Section 3 -- Grid Definition
        # ----------------------------

        # Set shape of the Earth parameters
        if self.gridDefinitionTemplateNumber.value in [50,51,52,1200]:
            earthparams = None
        else:
            earthparams = tables.earth_params[str(self.gridDefinitionTemplate[0])]
        if earthparams['shape'] == 'spherical':
            if earthparams['radius'] is None:
                self.earthRadius = self.gridDefinitionTemplate[2]/(10.**self.gridDefinitionTemplate[1])
                self.earthMajorAxis = None
                self.earthMinorAxis = None
            else:
                self.earthRadius = earthparams['radius']
                self.earthMajorAxis = None
                self.earthMinorAxis = None
        elif earthparams['shape'] == 'oblateSpheroid':
            if earthparams['radius'] is None and earthparams['major_axis'] is None and earthparams['minor_axis'] is None:
                self.earthRadius = self.gridDefinitionTemplate[2]/(10.**self.gridDefinitionTemplate[1])
                self.earthMajorAxis = self.gridDefinitionTemplate[4]/(10.**self.gridDefinitionTemplate[3])
                self.earthMinorAxis = self.gridDefinitionTemplate[6]/(10.**self.gridDefinitionTemplate[5])
            else:
                self.earthRadius = earthparams['radius']
                self.earthMajorAxis = earthparams['major_axis']
                self.earthMinorAxis = earthparams['minor_axis']

        reggrid = self.gridDefinitionSection[2] == 0 # self.gridDefinitionSection[2]=0 means regular 2-d grid
        if reggrid and self.gridDefinitionTemplateNumber.value not in [50,51,52,53,100,120,1000,1200]:
            self.nx = self.gridDefinitionTemplate[7]
            self.ny = self.gridDefinitionTemplate[8]
        if not reggrid and self.gridDefinitionTemplateNumber == 40:
            # Reduced Gaussian Grid
            self.ny = self.gridDefinitionTemplate[8]
        if self.gridDefinitionTemplateNumber.value in [0,1,203,205,32768,32769]:
            # Regular or Rotated Lat/Lon Grid
            scalefact = float(self.gridDefinitionTemplate[9])
            divisor = float(self.gridDefinitionTemplate[10])
            if scalefact == 0: scalefact = 1.
            if divisor <= 0: divisor = 1.e6
            self.latitudeFirstGridpoint = scalefact*self.gridDefinitionTemplate[11]/divisor
            self.longitudeFirstGridpoint = scalefact*self.gridDefinitionTemplate[12]/divisor
            self.latitudeLastGridpoint = scalefact*self.gridDefinitionTemplate[14]/divisor
            self.longitudeLastGridpoint = scalefact*self.gridDefinitionTemplate[15]/divisor
            self.gridlengthXDirection = scalefact*self.gridDefinitionTemplate[16]/divisor
            self.gridlengthYDirection = scalefact*self.gridDefinitionTemplate[17]/divisor
            if self.latitudeFirstGridpoint > self.latitudeLastGridpoint:
                self.gridlengthYDirection = -self.gridlengthYDirection
            if self.longitudeFirstGridpoint > self.longitudeLastGridpoint:
                self.gridlengthXDirection = -self.gridlengthXDirection
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[18],output=list)[0:4]
            if self.gridDefinitionTemplateNumber == 1:
                self.latitudeSouthernPole = scalefact*self.gridDefinitionTemplate[19]/divisor
                self.longitudeSouthernPole = scalefact*self.gridDefinitionTemplate[20]/divisor
                self.anglePoleRotation = self.gridDefinitionTemplate[21]
        elif self.gridDefinitionTemplateNumber == 10:
            # Mercator
            self.latitudeFirstGridpoint = self.gridDefinitionTemplate[9]/1.e6
            self.longitudeFirstGridpoint = self.gridDefinitionTemplate[10]/1.e6
            self.latitudeLastGridpoint = self.gridDefinitionTemplate[13]/1.e6
            self.longitudeLastGridpoint = self.gridDefinitionTemplate[14]/1.e6
            self.gridlengthXDirection = self.gridDefinitionTemplate[17]/1.e3
            self.gridlengthYDirection= self.gridDefinitionTemplate[18]/1.e3
            self.proj4_lat_ts = self.gridDefinitionTemplate[12]/1.e6
            self.proj4_lon_0 = 0.5*(self.longitudeFirstGridpoint+self.longitudeLastGridpoint)
            self.proj4_proj = 'merc'
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[15],output=list)[0:4]
        elif self.gridDefinitionTemplateNumber == 20:
            # Stereographic
            projflag = utils.int2bin(self.gridDefinitionTemplate[16],output=list)[0]
            self.latitudeFirstGridpoint = self.gridDefinitionTemplate[9]/1.e6
            self.longitudeFirstGridpoint = self.gridDefinitionTemplate[10]/1.e6
            self.proj4_lat_ts = self.gridDefinitionTemplate[12]/1.e6
            if projflag == 0:
                self.proj4_lat_0 = 90
            elif projflag == 1:
                self.proj4_lat_0 = -90
            else:
                raise ValueError('Invalid projection center flag = %s'%projflag)
            self.proj4_lon_0 = self.gridDefinitionTemplate[13]/1.e6
            self.gridlengthXDirection = self.gridDefinitionTemplate[14]/1000.
            self.gridlengthYDirection = self.gridDefinitionTemplate[15]/1000.
            self.proj4_proj = 'stere'
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[17],output=list)[0:4]
        elif self.gridDefinitionTemplateNumber == 30:
            # Lambert Conformal
            self.latitudeFirstGridpoint = self.gridDefinitionTemplate[9]/1.e6
            self.longitudeFirstGridpoint = self.gridDefinitionTemplate[10]/1.e6
            self.gridlengthXDirection = self.gridDefinitionTemplate[14]/1000.
            self.gridlengthYDirection = self.gridDefinitionTemplate[15]/1000.
            self.proj4_lat_1 = self.gridDefinitionTemplate[18]/1.e6
            self.proj4_lat_2 = self.gridDefinitionTemplate[19]/1.e6
            self.proj4_lat_0 = self.gridDefinitionTemplate[12]/1.e6
            self.proj4_lon_0 = self.gridDefinitionTemplate[13]/1.e6
            self.proj4_proj = 'lcc'
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[17],output=list)[0:4]
        elif self.gridDefinitionTemplateNumber == 31:
            # Albers Equal Area
            self.latitudeFirstGridpoint = self.gridDefinitionTemplate[9]/1.e6
            self.longitudeFirstGridpoint = self.gridDefinitionTemplate[10]/1.e6
            self.gridlengthXDirection = self.gridDefinitionTemplate[14]/1000.
            self.gridlengthYDirection = self.gridDefinitionTemplate[15]/1000.
            self.proj4_lat_1 = self.gridDefinitionTemplate[18]/1.e6
            self.proj4_lat_2 = self.gridDefinitionTemplate[19]/1.e6
            self.proj4_lat_0 = self.gridDefinitionTemplate[12]/1.e6
            self.proj4_lon_0 = self.gridDefinitionTemplate[13]/1.e6
            self.proj4_proj = 'aea'
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[17],output=list)[0:4]
        elif self.gridDefinitionTemplateNumber == 40 or self.gridDefinitionTemplateNumber == 41:
            # Gaussian Grid
            scalefact = float(self.gridDefinitionTemplate[9])
            divisor = float(self.gridDefinitionTemplate[10])
            if scalefact == 0: scalefact = 1.
            if divisor <= 0: divisor = 1.e6
            self.pointsBetweenPoleAndEquator = self.gridDefinitionTemplate[17]
            self.latitudeFirstGridpoint = scalefact*self.gridDefinitionTemplate[11]/divisor
            self.longitudeFirstGridpoint = scalefact*self.gridDefinitionTemplate[12]/divisor
            self.latitudeLastGridpoint = scalefact*self.gridDefinitionTemplate[14]/divisor
            self.longitudeLastGridpoint = scalefact*self.gridDefinitionTemplate[15]/divisor
            if reggrid:
                self.gridlengthXDirection = scalefact*self.gridDefinitionTemplate[16]/divisor
                if self.longitudeFirstGridpoint > self.longitudeLastGridpoint:
                    self.gridlengthXDirection = -self.gridlengthXDirection
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[18],output=list)[0:4]
            if self.gridDefinitionTemplateNumber == 41:
                self.latitudeSouthernPole = scalefact*self.gridDefinitionTemplate[19]/divisor
                self.longitudeSouthernPole = scalefact*self.gridDefinitionTemplate[20]/divisor
                self.anglePoleRotation = self.gridDefinitionTemplate[21]
        elif self.gridDefinitionTemplateNumber == 50:
            # Spectral Coefficients
            self.spectralFunctionParameters = (self.gridDefinitionTemplate[0],self.gridDefinitionTemplate[1],self.gridDefinitionTemplate[2])
            self.scanModeFlags = [None,None,None,None]
        elif self.gridDefinitionTemplateNumber == 90:
            # Near-sided Vertical Perspective Satellite Projection
            self.proj4_lat_0 = self.gridDefinitionTemplate[9]/1.e6
            self.proj4_lon_0 = self.gridDefinitionTemplate[10]/1.e6
            self.proj4_h = self.earthMajorAxis * (self.gridDefinitionTemplate[18]/1.e6)
            dx = self.gridDefinitionTemplate[12]
            dy = self.gridDefinitionTemplate[13]
            # if lat_0 is equator, it's a geostationary view.
            if self.proj4_lat_0 == 0.: # if lat_0 is equator, it's a
                self.proj4_proj = 'geos'
            # general case of 'near-side perspective projection' (untested)
            else:
                self.proj4_proj = 'nsper'
                msg = 'Only geostationary perspective is supported. Lat/Lon values returned by grid method may be incorrect.'
                warnings.warn(msg)
            # latitude of horizon on central meridian
            lonmax = 90.-(180./np.pi)*np.arcsin(self.earthMajorAxis/self.proj4_h)
            # longitude of horizon on equator
            latmax = 90.-(180./np.pi)*np.arcsin(self.earthMinorAxis/self.proj4_h)
            # truncate to nearest thousandth of a degree (to make sure
            # they aren't slightly over the horizon)
            latmax = int(1000*latmax)/1000.
            lonmax = int(1000*lonmax)/1000.
            # h is measured from surface of earth at equator.
            self.proj4_h = self.proj4_h - self.earthMajorAxis
            # width and height of visible projection
            P = pyproj.Proj(proj=self.proj4_proj,\
                            a=self.earthMajorAxis,b=self.earthMinorAxis,\
                            lat_0=0,lon_0=0,h=self.proj4_h)
            x1,y1 = P(0.,latmax)
            x2,y2 = P(lonmax,0.)
            width = 2*x2
            height = 2*y1
            self.gridlengthXDirection = width/dx
            self.gridlengthYDirection = height/dy
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[16],output=list)[0:4]
        elif self.gridDefinitionTemplateNumber == 110:
            # Azimuthal Equidistant
            self.proj4_lat_0 = self.gridDefinitionTemplate[9]/1.e6
            self.proj4_lon_0 = self.gridDefinitionTemplate[10]/1.e6
            self.gridlengthXDirection = self.gridDefinitionTemplate[12]/1000.
            self.gridlengthYDirection = self.gridDefinitionTemplate[13]/1000.
            self.proj4_proj = 'aeqd'
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[15],output=list)[0:4]
        elif self.gridDefinitionTemplateNumber == 204:
            # Curvilinear Orthogonal
            self.scanModeFlags = utils.int2bin(self.gridDefinitionTemplate[18],output=list)[0:4]
        else:
            errmsg = 'Unsupported Grid Definition Template Number - 3.%i' % self.gridDefinitionTemplateNumber.value
            raise ValueError(errmsg)

        # -------------------------------
        # Section 4 -- Product Definition
        # -------------------------------
      
        # Template 4.0 - NOTE: That is these attributes apply to other templates.
        self.parameterCategory = self.productDefinitionTemplate[0]
        self.parameterNumber = self.productDefinitionTemplate[1]
        self.fullName,self.units,self.shortName = tables.get_varinfo_from_table(self.discipline.value,
                                                                                self.parameterCategory,
                                                                                self.parameterNumber)
        self.typeOfGeneratingProcess = Grib2Metadata(self.productDefinitionTemplate[2],table='4.3')
        self.backgroundGeneratingProcessIdentifier = self.productDefinitionTemplate[3]
        self.generatingProcess = Grib2Metadata(self.productDefinitionTemplate[4],table='generating_process')
        self.unitOfTimeRange = Grib2Metadata(self.productDefinitionTemplate[7],table='4.4')
        self.leadTime = self.productDefinitionTemplate[8]
        self.typeOfFirstFixedSurface = Grib2Metadata(self.productDefinitionTemplate[9],table='4.5')
        self.scaleFactorOfFirstFixedSurface = self.productDefinitionTemplate[10]
        self.unitOfFirstFixedSurface = self.typeOfFirstFixedSurface.definition[1]
        self.scaledValueOfFirstFixedSurface = self.productDefinitionTemplate[11]
        self.valueOfFirstFixedSurface = self.scaledValueOfFirstFixedSurface/(10.**self.scaleFactorOfFirstFixedSurface)
        temp = tables.get_value_from_table(self.productDefinitionTemplate[12],'4.5')
        if temp[0] == 'Missing' and temp[1] == 'unknown':
            self.typeOfSecondFixedSurface = None
            self.scaleFactorOfSecondFixedSurface = None
            self.unitOfSecondFixedSurface = None
            self.valueOfSecondFixedSurface = None
        else:
            self.typeOfSecondFixedSurface = Grib2Metadata(self.productDefinitionTemplate[12],table='4.5')
            self.scaleFactorOfSecondFixedSurface = self.productDefinitionTemplate[13]
            self.unitOfSecondFixedSurface = self.typeOfSecondFixedSurface.definition[1]
            self.scaledValueOfSecondFixedSurface = self.productDefinitionTemplate[14]
            self.valueOfSecondFixedSurface = self.scaledValueOfSecondFixedSurface/(10.**self.scaleFactorOfSecondFixedSurface)

        # Template 4.1 -
        if self.productDefinitionTemplateNumber == 1:
            self.typeOfEnsembleForecast = Grib2Metadata(self.productDefinitionTemplate[15],table='4.6')
            self.perturbationNumber = self.productDefinitionTemplate[16]
            self.numberOfEnsembleForecasts = self.productDefinitionTemplate[17]

        # Template 4.2 -
        elif self.productDefinitionTemplateNumber == 2:
            self.typeOfDerivedForecast = Grib2Metadata(self.productDefinitionTemplate[15],table='4.7')
            self.numberOfEnsembleForecasts = self.productDefinitionTemplate[16]

        # Template 4.5 -
        elif self.productDefinitionTemplateNumber == 5:
            self.forecastProbabilityNumber = self.productDefinitionTemplate[15]
            self.totalNumberOfForecastProbabilities = self.productDefinitionTemplate[16]
            self.typeOfProbability = Grib2Metadata(self.productDefinitionTemplate[16],table='4.9')
            self.thresholdLowerLimit = self.productDefinitionTemplate[18]/(10.**self.productDefinitionTemplate[17])
            self.thresholdUpperLimit = self.productDefinitionTemplate[20]/(10.**self.productDefinitionTemplate[19])

        # Template 4.6 -
        elif self.productDefinitionTemplateNumber == 6:
            self.percentileValue = self.productDefinitionTemplate[15]

        # Template 4.8 -
        elif self.productDefinitionTemplateNumber == 8:
            self.yearOfEndOfTimePeriod = self.productDefinitionTemplate[15]
            self.monthOfEndOfTimePeriod = self.productDefinitionTemplate[16]
            self.dayOfEndOfTimePeriod = self.productDefinitionTemplate[17]
            self.hourOfEndOfTimePeriod = self.productDefinitionTemplate[18]
            self.minuteOfEndOfTimePeriod = self.productDefinitionTemplate[19]
            self.secondOfEndOfTimePeriod = self.productDefinitionTemplate[20]
            self.numberOfTimeRanges = self.productDefinitionTemplate[21]
            self.numberOfMissingValues = self.productDefinitionTemplate[22]
            self.statisticalProcess = Grib2Metadata(self.productDefinitionTemplate[23],table='4.10')
            self.typeOfTimeIncrementOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[24],table='4.11')
            self.unitOfTimeRangeOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[25],table='4.4')
            self.timeRangeOfStatisticalProcess = self.productDefinitionTemplate[26]
            self.unitOfTimeRangeOfSuccessiveFields = Grib2Metadata(self.productDefinitionTemplate[27],table='4.4')
            self.timeIncrementOfSuccessiveFields = self.productDefinitionTemplate[28]

        # Template 4.9 -
        elif self.productDefinitionTemplateNumber == 9:
            self.forecastProbabilityNumber = self.productDefinitionTemplate[15]
            self.totalNumberOfForecastProbabilities = self.productDefinitionTemplate[16]
            self.typeOfProbability = Grib2Metadata(self.productDefinitionTemplate[17],table='4.9')
            self.thresholdLowerLimit = 0.0 if self.productDefinitionTemplate[19] == 255 else \
                                       self.productDefinitionTemplate[19]/(10.**self.productDefinitionTemplate[18])
            self.thresholdUpperLimit = 0.0 if self.productDefinitionTemplate[21] == 255 else \
                                       self.productDefinitionTemplate[21]/(10.**self.productDefinitionTemplate[20])
            self.yearOfEndOfTimePeriod = self.productDefinitionTemplate[22]
            self.monthOfEndOfTimePeriod = self.productDefinitionTemplate[23]
            self.dayOfEndOfTimePeriod = self.productDefinitionTemplate[24]
            self.hourOfEndOfTimePeriod = self.productDefinitionTemplate[25]
            self.minuteOfEndOfTimePeriod = self.productDefinitionTemplate[26]
            self.secondOfEndOfTimePeriod = self.productDefinitionTemplate[27]
            self.numberOfTimeRanges = self.productDefinitionTemplate[28]
            self.numberOfMissingValues = self.productDefinitionTemplate[29]
            self.statisticalProcess = Grib2Metadata(self.productDefinitionTemplate[30],table='4.10')
            self.typeOfTimeIncrementOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[31],table='4.11')
            self.unitOfTimeRangeOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[32],table='4.4')
            self.timeRangeOfStatisticalProcess = self.productDefinitionTemplate[33]
            self.unitOfTimeRangeOfSuccessiveFields = Grib2Metadata(self.productDefinitionTemplate[34],table='4.4')
            self.timeIncrementOfSuccessiveFields = self.productDefinitionTemplate[35]

        # Template 4.10 -
        elif self.productDefinitionTemplateNumber == 10:
            self.percentileValue = self.productDefinitionTemplate[15]
            self.yearOfEndOfTimePeriod = self.productDefinitionTemplate[16]
            self.monthOfEndOfTimePeriod = self.productDefinitionTemplate[17]
            self.dayOfEndOfTimePeriod = self.productDefinitionTemplate[18]
            self.hourOfEndOfTimePeriod = self.productDefinitionTemplate[19]
            self.minuteOfEndOfTimePeriod = self.productDefinitionTemplate[20]
            self.secondOfEndOfTimePeriod = self.productDefinitionTemplate[21]
            self.numberOfTimeRanges = self.productDefinitionTemplate[22]
            self.numberOfMissingValues = self.productDefinitionTemplate[23]
            self.statisticalProcess = Grib2Metadata(self.productDefinitionTemplate[24],table='4.10')
            self.typeOfTimeIncrementOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[25],table='4.11')
            self.unitOfTimeRangeOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[26],table='4.4')
            self.timeRangeOfStatisticalProcess = self.productDefinitionTemplate[27]
            self.unitOfTimeRangeOfSuccessiveFields = Grib2Metadata(self.productDefinitionTemplate[28],table='4.4')
            self.timeIncrementOfSuccessiveFields = self.productDefinitionTemplate[29]

        # Template 4.11 -
        elif self.productDefinitionTemplateNumber == 11:
            self.typeOfEnsembleForecast = Grib2Metadata(self.productDefinitionTemplate[15],table='4.6')
            self.perturbationNumber = self.productDefinitionTemplate[16]
            self.numberOfEnsembleForecasts = self.productDefinitionTemplate[17]
            self.yearOfEndOfTimePeriod = self.productDefinitionTemplate[18]
            self.monthOfEndOfTimePeriod = self.productDefinitionTemplate[19]
            self.dayOfEndOfTimePeriod = self.productDefinitionTemplate[20]
            self.hourOfEndOfTimePeriod = self.productDefinitionTemplate[21]
            self.minuteOfEndOfTimePeriod = self.productDefinitionTemplate[22]
            self.secondOfEndOfTimePeriod = self.productDefinitionTemplate[23]
            self.numberOfTimeRanges = self.productDefinitionTemplate[24]
            self.numberOfMissingValues = self.productDefinitionTemplate[25]
            self.statisticalProcess = Grib2Metadata(self.productDefinitionTemplate[26],table='4.10')
            self.typeOfTimeIncrementOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[27],table='4.11')
            self.unitOfTimeRangeOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[28],table='4.4')
            self.timeRangeOfStatisticalProcess = self.productDefinitionTemplate[29]
            self.unitOfTimeRangeOfSuccessiveFields = tables.get_value_from_table(self.productDefinitionTemplate[30],table='4.4')
            self.timeIncrementOfSuccessiveFields = self.productDefinitionTemplate[31]

        # Template 4.12 -
        elif self.productDefinitionTemplateNumber == 12:
            self.typeOfDerivedForecast = Grib2Metadata(self.productDefinitionTemplate[15],table='4.7')
            self.numberOfEnsembleForecasts = self.productDefinitionTemplate[16]
            self.yearOfEndOfTimePeriod = self.productDefinitionTemplate[17]
            self.monthOfEndOfTimePeriod = self.productDefinitionTemplate[18]
            self.dayOfEndOfTimePeriod = self.productDefinitionTemplate[19]
            self.hourOfEndOfTimePeriod = self.productDefinitionTemplate[20]
            self.minuteOfEndOfTimePeriod = self.productDefinitionTemplate[21]
            self.secondOfEndOfTimePeriod = self.productDefinitionTemplate[22]
            self.numberOfTimeRanges = self.productDefinitionTemplate[23]
            self.numberOfMissingValues = self.productDefinitionTemplate[24]
            self.statisticalProcess = Grib2Metadata(self.productDefinitionTemplate[25],table='4.10')
            self.typeOfTimeIncrementOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[26],table='4.11')
            self.unitOfTimeRangeOfStatisticalProcess = Grib2Metadata(self.productDefinitionTemplate[27],table='4.4')
            self.timeRangeOfStatisticalProcess = self.productDefinitionTemplate[28]
            self.unitOfTimeRangeOfSuccessiveFields = Grib2Metadata(self.productDefinitionTemplate[29],table='4.4')
            self.timeIncrementOfSuccessiveFields = self.productDefinitionTemplate[30]

        else:
            if self.productDefinitionTemplateNumber != 0:
                errmsg = 'Unsupported Product Definition Template Number - 4.%i' % self.productDefinitionTemplateNumber.value
                raise ValueError(errmsg)


        self.leadTime = utils.getleadtime(self.identificationSection,
                                          self.productDefinitionTemplateNumber.value,
                                          self.productDefinitionTemplate)

        if self.productDefinitionTemplateNumber.value in [8,9,10,11,12]:
            self.dtEndOfTimePeriod = datetime.datetime(self.yearOfEndOfTimePeriod,self.monthOfEndOfTimePeriod,
                                     self.dayOfEndOfTimePeriod,hour=self.hourOfEndOfTimePeriod,
                                     minute=self.minuteOfEndOfTimePeriod,
                                     second=self.secondOfEndOfTimePeriod)

        # --------------------------------
        # Section 5 -- Data Representation
        # --------------------------------

        # Template 5.0 - Simple Packing
        if self.dataRepresentationTemplateNumber == 0:
            self.refValue = utils.getieeeint(self.dataRepresentationTemplate[0])
            self.binScaleFactor = self.dataRepresentationTemplate[1]
            self.decScaleFactor = self.dataRepresentationTemplate[2]
            self.nBitsPacking = self.dataRepresentationTemplate[3]
            self.typeOfValues = Grib2Metadata(self.dataRepresentationTemplate[3],table='5.1')

        # Template 5.2 - Complex Packing
        elif self.dataRepresentationTemplateNumber == 2:
            self.refValue = utils.getieeeint(self.dataRepresentationTemplate[0])
            self.binScaleFactor = self.dataRepresentationTemplate[1]
            self.decScaleFactor = self.dataRepresentationTemplate[2]
            self.nBitsPacking = self.dataRepresentationTemplate[3]
            self.typeOfValues = Grib2Metadata(self.dataRepresentationTemplate[4],table='5.1')
            self.groupSplitMethod = Grib2Metadata(self.dataRepresentationTemplate[5],table='5.4')
            self.typeOfMissingValue = Grib2Metadata(self.dataRepresentationTemplate[6],table='5.5')
            self.priMissingValue = utils.getieeeint(self.dataRepresentationTemplate[7]) if self.dataRepresentationTemplate[6] in [1,2] else None
            self.secMissingValue = utils.getieeeint(self.dataRepresentationTemplate[8]) if self.dataRepresentationTemplate[6] == 2 else None
            self.nGroups = self.dataRepresentationTemplate[9]
            self.refGroupWidth = self.dataRepresentationTemplate[10]
            self.nBitsGroupWidth = self.dataRepresentationTemplate[11]
            self.refGroupLength = self.dataRepresentationTemplate[12]
            self.groupLengthIncrement = self.dataRepresentationTemplate[13]
            self.lengthOfLastGroup = self.dataRepresentationTemplate[14]
            self.nBitsScaledGroupLength = self.dataRepresentationTemplate[15]

        # Template 5.3 - Complex Packing and Spatial Differencing
        elif self.dataRepresentationTemplateNumber == 3:
            self.refValue = utils.getieeeint(self.dataRepresentationTemplate[0])
            self.binScaleFactor = self.dataRepresentationTemplate[1]
            self.decScaleFactor = self.dataRepresentationTemplate[2]
            self.nBitsPacking = self.dataRepresentationTemplate[3]
            self.typeOfValues = Grib2Metadata(self.dataRepresentationTemplate[4],table='5.1')
            self.groupSplitMethod = Grib2Metadata(self.dataRepresentationTemplate[5],table='5.4')
            self.typeOfMissingValue = Grib2Metadata(self.dataRepresentationTemplate[6],table='5.5')
            self.priMissingValue = utils.getieeeint(self.dataRepresentationTemplate[7]) if self.dataRepresentationTemplate[6] in [1,2] else None
            self.secMissingValue = utils.getieeeint(self.dataRepresentationTemplate[8]) if self.dataRepresentationTemplate[6] == 2 else None
            self.nGroups = self.dataRepresentationTemplate[9]
            self.refGroupWidth = self.dataRepresentationTemplate[10]
            self.nBitsGroupWidth = self.dataRepresentationTemplate[11]
            self.refGroupLength = self.dataRepresentationTemplate[12]
            self.groupLengthIncrement = self.dataRepresentationTemplate[13]
            self.lengthOfLastGroup = self.dataRepresentationTemplate[14]
            self.nBitsScaledGroupLength = self.dataRepresentationTemplate[15]
            self.spatialDifferenceOrder = Grib2Metadata(self.dataRepresentationTemplate[16],table='5.6')
            self.nBytesSpatialDifference = self.dataRepresentationTemplate[17]

        # Template 5.4 - IEEE Floating Point Data
        elif self.dataRepresentationTemplateNumber == 4:
            self.precision = Grib2Metadata(self.dataRepresentationTemplate[0],table='5.7')

        # Template 5.40 - JPEG2000 Compression
        elif self.dataRepresentationTemplateNumber == 40:
            self.refValue = utils.getieeeint(self.dataRepresentationTemplate[0])
            self.binScaleFactor = self.dataRepresentationTemplate[1]
            self.decScaleFactor = self.dataRepresentationTemplate[2]
            self.nBitsPacking = self.dataRepresentationTemplate[3]
            self.typeOfValues = Grib2Metadata(self.dataRepresentationTemplate[4],table='5.1')
            self.typeOfCompression = Grib2Metadata(self.dataRepresentationTemplate[5],table='5.40')
            self.targetCompressionRatio = self.dataRepresentationTemplate[6]

        # Template 5.41 - PNG Compression
        elif self.dataRepresentationTemplateNumber == 41:
            self.refValue = utils.getieeeint(self.dataRepresentationTemplate[0])
            self.binScaleFactor = self.dataRepresentationTemplate[1]
            self.decScaleFactor = self.dataRepresentationTemplate[2]
            self.nBitsPacking = self.dataRepresentationTemplate[3]
            self.typeOfValues = Grib2Metadata(self.dataRepresentationTemplate[4],table='5.1')

        else:
            errmsg = 'Unsupported Data Representation Definition Template Number - 5.%i' % self.dataRepresentationTemplateNumber.value
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

        **`expand`**: If `True` [DEFAULT], ECMWF 'reduced' gaussian grids are expanded to regular 
        gaussian grids.

        **`order`**: If 0 [DEFAULT], nearest neighbor interpolation is used if grid has missing 
        or bitmapped values. If 1, linear interpolation is used for expanding reduced gaussian grids.

        **`map_keys`**: If `True`, data values will be mapped to the string-based keys that are stored
        in the Local Use Section (section 2) of the GRIB2 Message or in a code table as specified in the
        units (i.e. "See Table 4.xxx").

        Returns
        -------

        **`numpy.ndarray`**: A numpy.ndarray with shape (ny,nx). By default the array dtype=np.float32, 
        but could be np.int32 if Grib2Message.typeOfValues is integer.  The array dtype will be 
        string-based if map_keys=True.
        """
        if not hasattr(self,'scanModeFlags'):
            raise ValueError('Unsupported grid definition template number %s'%self.gridDefinitionTemplateNumber)
        else:
            if self.scanModeFlags[2]:
                storageorder='F'
            else:
                storageorder='C'
        if order is None:
            if (self.dataRepresentationTemplateNumber in [2,3] and
                self.dataRepresentationTemplate[6] != 0) or self.bitMapFlag == 0:
                order = 0
            else:
                order = 1
        drtnum = self.dataRepresentationTemplateNumber.value
        drtmpl = np.asarray(self.dataRepresentationTemplate,dtype=np.int32)
        gdtnum = self.gridDefinitionTemplateNumber.value
        gdtmpl = np.asarray(self.gridDefinitionTemplate,dtype=np.int32)
        ndpts = self.numberOfDataPoints
        gds = self.gridDefinitionSection
        ngrdpts = gds[1]
        ipos = self._datapos
        fld1 = g2clib.unpack7(self._msg,gdtnum,gdtmpl,drtnum,drtmpl,ndpts,ipos,np.empty,storageorder=storageorder)
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
            if gds[2] and gdtnum == 40: # ECMWF 'reduced' global gaussian grid.
                if expand:
                    from redtoreg import _redtoreg
                    self.nx = 2*self.ny
                    lonsperlat = self.defList
                    if ma.isMA(fld):
                        fld = ma.filled(fld)
                        fld = _redtoreg(self.nx,lonsperlat.astype(np.long),\
                                fld.astype(np.double),fill_value)
                        fld = ma.masked_values(fld,fill_value)
                    else:
                        fld = _redtoreg(self.nx,lonsperlat.astype(np.long),\
                                fld.astype(np.double),fill_value)
        # Check scan modes for rect grids.
        if self.nx is not None and self.ny is not None:
            if self.scanModeFlags[3]:
                fldsave = fld.astype('f') # casting makes a copy
                fld[1::2,:] = fldsave[1::2,::-1]

        # Set data to integer according to GRIB metadata
        if self.typeOfValues == "Integer": fld = fld.astype(np.int32)

        # Map the data values to their respective definitions.
        if map_keys:
            fld = fld.astype(np.int32).astype(str)
            if self.identificationSection[0] == 7 and \
               self.identificationSection[1] == 14 and \
               self.shortName == 'PWTHER':
                # MDL Predominant Weather Grid
                keys = utils.decode_mdl_wx_strings(self._lus)
                for n,k in enumerate(keys):
                    fld = np.where(fld==str(n+1),k,fld)
            elif self.identificationSection[0] == 8 and \
                 self.identificationSection[1] == 65535 and \
                 self.shortName == 'CRAIN':
                # NDFD Predominant Weather Grid
                keys = utils.decode_ndfd_wx_strings(self._lus)
                for n,k in enumerate(keys):
                    fld = np.where(fld==str(n+1),k,fld)
            else:
                # For data whose units are defined in a code table
                tbl = re.findall(r'\d\.\d+',self.units,re.IGNORECASE)[0]
                for k,v in tables.get_table(tbl).items():
                    fld = np.where(fld==k,v,fld)
        return fld


    def latlons(self):
        """Alias for `grib2io.Grib2Message.grid` method"""
        return self.grid()


    def grid(self):
        """
        Return lats,lons (in degrees) of grid. Currently can handle reg. lat/lon, 
        global gaussian, mercator, stereographic, lambert conformal, albers equal-area, 
        space-view and azimuthal equidistant grids.

        Returns
        -------

        **`lats, lons : numpy.ndarray`**

        Returns two numpy.ndarrays with dtype=numpy.float32 of grid latitudes and
        longitudes in units of degrees.
        """
        gdtnum = self.gridDefinitionTemplateNumber
        gdtmpl = self.gridDefinitionTemplate
        reggrid = self.gridDefinitionSection[2] == 0 # This means regular 2-d grid
        self.projparams = {}
        if self.earthMajorAxis is not None: self.projparams['a']=self.earthMajorAxis
        if self.earthMajorAxis is not None: self.projparams['b']=self.earthMinorAxis
        if gdtnum == 0:
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
            self.projparams['proj'] = 'cyl'
            lons,lats = np.meshgrid(lons,lats) # make 2-d arrays.
        elif gdtnum == 40: # gaussian grid (only works for global!)
            try:
                from pygrib import gaulats
            except:
                raise ImportError("pygrib required to compute Gaussian latitude")
            lon1, lat1 = self.longitudeFirstGridpoint, self.latitudeFirstGridpoint
            lon2, lat2 = self.longitudeLastGridpoint, self.latitudeLastGridpoint
            nlats = self.ny
            if not reggrid: # ECMWF 'reduced' gaussian grid.
                nlons = 2*nlats
                dlon = 360./nlons
            else:
                nlons = self.nx
                dlon = self.gridlengthXDirection
            lons = np.arange(lon1,lon2+dlon,dlon)
            # Compute gaussian lats (north to south)
            lats = gaulats(nlats)
            if lat1 < lat2:  # reverse them if necessary
                lats = lats[::-1]
            # flip if scan mode says to.
            #if self.scanModeFlags[0]:
            #    lons = lons[::-1]
            #if not self.scanModeFlags[1]:
            #    lats = lats[::-1]
            self.projparams['proj'] = 'cyl'
            lons,lats = np.meshgrid(lons,lats) # make 2-d arrays
        elif gdtnum in [10,20,30,31,110]:
            # Mercator, Lambert Conformal, Stereographic, Albers Equal Area, Azimuthal Equidistant
            dx,dy = self.gridlengthXDirection, self.gridlengthYDirection
            lon1,lat1 = self.longitudeFirstGridpoint, self.latitudeFirstGridpoint
            if gdtnum == 10: # Mercator.
                self.projparams['lat_ts']=self.proj4_lat_ts
                self.projparams['proj']=self.proj4_proj
                self.projparams['lon_0']=self.proj4_lon_0
                pj = pyproj.Proj(self.projparams)
                llcrnrx, llcrnry = pj(lon1,lat1)
                x = llcrnrx+dx*np.arange(self.nx)
                y = llcrnry+dy*np.arange(self.ny)
                x,y = np.meshgrid(x, y)
                lons,lats = pj(x, y, inverse=True)
            elif gdtnum == 20:  # Stereographic
                self.projparams['lat_ts']=self.proj4_lat_ts
                self.projparams['proj']=self.proj4_proj
                self.projparams['lat_0']=self.proj4_lat_0
                self.projparams['lon_0']=self.proj4_lon_0
                pj = pyproj.Proj(self.projparams)
                llcrnrx, llcrnry = pj(lon1,lat1)
                x = llcrnrx+dx*np.arange(self.nx)
                y = llcrnry+dy*np.arange(self.ny)
                x,y = np.meshgrid(x, y)
                lons,lats = pj(x, y, inverse=True)
            elif gdtnum in [30,31]: # Lambert, Albers
                self.projparams['lat_1']=self.proj4_lat_1
                self.projparams['lat_2']=self.proj4_lat_2
                self.projparams['proj']=self.proj4_proj
                self.projparams['lon_0']=self.proj4_lon_0
                pj = pyproj.Proj(self.projparams)
                llcrnrx, llcrnry = pj(lon1,lat1)
                x = llcrnrx+dx*np.arange(self.nx)
                y = llcrnry+dy*np.arange(self.ny)
                x,y = np.meshgrid(x, y)
                lons,lats = pj(x, y, inverse=True)
            elif gdtnum == 110: # Azimuthal Equidistant
                self.projparams['proj']=self.proj4_proj
                self.projparams['lat_0']=self.proj4_lat_0
                self.projparams['lon_0']=self.proj4_lon_0
                pj = pyproj.Proj(self.projparams)
                llcrnrx, llcrnry = pj(lon1,lat1)
                x = llcrnrx+dx*np.arange(self.nx)
                y = llcrnry+dy*np.arange(self.ny)
                x,y = np.meshgrid(x, y)
                lons,lats = pj(x, y, inverse=True)
        elif gdtnum == 90:
            # Satellite Projection
            dx = self.gridlengthXDirection
            dy = self.gridlengthYDirection
            self.projparams['proj']=self.proj4_proj
            self.projparams['lon_0']=self.proj4_lon_0
            self.projparams['lat_0']=self.proj4_lat_0
            self.projparams['h']=self.proj4_h
            pj = pyproj.Proj(self.projparams)
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
        - gdsinfo[0] = Source of grid definition - [Code Table 3.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-0.shtml)
        - gdsinfo[1] = Number of data points
        - gdsinfo[2] = Number of octets for optional list of numbers defining number of points
        - gdsinfo[3] = Interpetation of list of numbers defining number of points - [Code Table 3.11](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-11.shtml)
        - gdsinfo[4] = Grid Definition Template Number - [Code Table 3.1](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-1.shtml)

        **`gdtmpl`**: Sequence of values for the specified Grid Definition Template. Each 
        element of this integer array contains an entry (in the order specified) of Grid
        Definition Template 3.NN

        **`deflist`**: Sequence containing the number of grid points contained in each 
        row (or column) of a non-regular grid.  Used if gdsinfo[2] != 0.
        """
        if 3 in self._sections:
            raise ValueError('GRIB2 Message already contains Grid Definition Section.')
        if deflist is not None:
            _deflist = np.array(deflist,dtype=np.int32)
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
                                                   np.array(gdsinfo,dtype=np.int32),
                                                   np.array(gdtmpl,dtype=np.int32),
                                                   _deflist)
        self._sections.append(3)


    def addfield(self, pdtnum, pdtmpl, drtnum, drtmpl, field, coordlist=None):
        """
        Add a Product Definition, Data Representation, Bitmap, and Data Sections 
        to `Grib2Message` instance (i.e. Sections 4-7).  Must be called after the grid 
        definition section has been added (`addfield`).

        Parameters
        ----------

        **`pdtnum`**: integer Product Definition Template Number - [Code Table 4.0](http://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-0.shtml)

        **`pdtmpl`**: Sequence with the data values for the specified Product Definition 
        Template (N=pdtnum).  Each element of this integer array contains an entry (in 
        the order specified) of Product Definition Template 4.N.

        **`drtnum`**: integer Data Representation Template Number - [Code Table 5.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-0.shtml)

        **`drtmpl`**: Sequence with the data values for the specified Data Representation
        Template (N=drtnum).  Each element of this integer array contains an entry (in 
        the order specified) of Data Representation Template 5.N.  Note that some values 
        in this template (eg. reference values, number of bits, etc...) may be changed by the
        data packing algorithms.  Use this to specify scaling factors and order of spatial 
        differencing, if desired.

        **`field`**: Numpy array of data points to pack.  If field is a masked array, then 
        a bitmap is created from the mask.

        **`coordlist`**: Sequence containing floating point values intended to document the 
        vertical discretization with model data on hybrid coordinate vertical levels. Default is `None`.
        """
        if not hasattr(self,'scanModeFlags'):
            raise ValueError('addgrid() must be called before addfield()')
        if self.scanModeFlags is not None:
            if self.scanModeFlags[3]:
                fieldsave = field.astype('f') # Casting makes a copy
                field[1::2,:] = fieldsave[1::2,::-1]
        fld = field.astype('f')
        if ma.isMA(field):
            bmap = 1-np.ravel(field.mask.astype('i'))
            bitmapflag = 0
        else:
            bitmapflag = 255
            bmap = None
        if coordlist is not None:
            crdlist = np.array(coordlist,'f')
        else:
            crdlist = None
        _pdtnum = pdtnum.value if isinstance(pdtnum,Grib2Metadata) else pdtnum
        _drtnum = drtnum.value if isinstance(drtnum,Grib2Metadata) else drtnum
        self._msg,self._pos = g2clib.grib2_addfield(self._msg,
                                                    _pdtnum,
                                                    np.array(pdtmpl,dtype=np.int32),
                                                    crdlist,
                                                    _drtnum,
                                                    np.array(drtmpl,dtype=np.int32),
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


class Grib2Metadata():
    """
    Class to hold GRIB2 metadata both as numeric code value as stored in
    GRIB2 and its plain langauge definition.

    **`value : int`**

    GRIB2 metadata integer code value.

    **`table : str, optional`**

    GRIB2 table to lookup the `value`. Default is None.
    """
    def __init__(self, value, table=None):
        self.value = value
        self.table = table
        if self.table is None:
            self.definition = None
        else:
            self.definition = tables.get_value_from_table(self.value,self.table)
    def __call__(self):
        return self.value
    def __repr__(self):
        return '%s(%d, table = %s)' % (self.__class__.__name__,self.value,self.table)
    def __str__(self):
        return '%d - %s' % (self.value,self.definition)
    def __eq__(self,other):
        return self.value == other
    def __gt__(self,other):
        return self.value > other
    def __ge__(self,other):
        return self.value >= other
    def __lt__(self,other):
        return self.value < other
    def __le__(self,other):
        return self.value <= other
    def __contains__(self,other):
        return other in self.definition
