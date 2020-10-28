__version__ = '0.1.0'

import g2clib

import builtins
import os
import struct
import numpy as np

ONE_MB = 1024 ** 3

class open():
    def __init__(self, filename, mode='r'):
        """
        Class Constructor

        Parameters
        ----------

        **`filename : str`**

        File name.

        **`mode : str, optional, default = 'r'`**

        File handle mode.  The default is open for reading ('r').
        """
        if mode == 'r' or mode == 'w':
            mode = mode+'b'
        elif mode == 'a':
            mode = 'wb'
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
            return self.read(1)[0]
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
            beg, end, inc = key.indices(self.messages)
            return [self[i] for i in range(beg,end,inc)]
        elif isinstance(key,int):
            if key == 0: return None
            self._filehandle.seek(self._index['offset'][key])
            return [Grib2Message(self._filehandle.read(self._index['size'][key]),ref=self)]
        else:
            raise KeyError('Key must be an integer or slice')


    def _build_index(self):
        """
        Perform indexing of GRIB2 Messages.
        """
        # Initialize index dictionary
        self._index['offset'] = [None]
        self._index['discipline'] = [None]
        self._index['edition'] = [None]
        self._index['size'] = [None]
        self._index['hasSubmessage'] = [None]
        self._index['numberOfSubmessages'] = [None]
        self._index['identificationSection'] = [None]
        self._index['productDefinitionTemplateNumber'] = [None]
        self._index['productDefinitionTemplate'] = [None]

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
                    _hassubmessage = False
                    _nmsg = 1

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
                    
                    secrange = range(2,8)
                    while 1:
                        for num in secrange:
                            secsize = struct.unpack('>i',self._filehandle.read(4))[0]
                            secnum = struct.unpack('>B',self._filehandle.read(1))[0]
                            if secnum == num:
                                if secnum == 4:
                                    self._filehandle.seek(self._filehandle.tell()-5) 
                                    _grbmsg = self._filehandle.read(secsize)
                                    _grbpos = 0
                                    # Unpack Section 4
                                    _pdt,_pdtnum,_coordlist,_grbpos = g2clib.unpack4(_grbmsg,_grbpos,np.empty)
                                    _pdt = _pdt.tolist()
                                else:
                                    self._filehandle.seek(self._filehandle.tell()+secsize-5)
                            else:
                                if num == 2 and secnum == 3:
                                    pass # Allow this.  Just means no Local Use Section.
                                else:
                                    _hassubmessage = True
                                self._filehandle.seek(self._filehandle.tell()-5)
                                continue
                        trailer = struct.unpack('>4s',self._filehandle.read(4))[0].decode()
                        if trailer == '7777':
                            self.messages += 1
                            self._index['offset'].append(pos)
                            self._index['discipline'].append(discipline)
                            self._index['edition'].append(edition)
                            self._index['size'].append(size)
                            self._index['hasSubmessage'].append(_hassubmessage)
                            self._index['numberOfSubmessages'].append(_nmsg)
                            self._index['identificationSection'].append(_grbsec1)
                            if _hassubmessage:
                                self._index['productDefinitionTemplateNumber'][self.messages-1].append(_pdtnum)
                                self._index['productDefinitionTemplate'][self.messages-1].append(_pdt)
                            else:
                                self._index['productDefinitionTemplateNumber'].append([_pdtnum])
                                self._index['productDefinitionTemplate'].append([_pdt])
                            break
                        else:
                            self._filehandle.seek(self._filehandle.tell()-4)
                            if _nmsg == 1:
                                self._index['productDefinitionTemplateNumber'].append([_pdtnum])
                                self._index['productDefinitionTemplate'].append([_pdt])
                            else:
                                self._index['productDefinitionTemplateNumber'][self.messages].append(_pdtnum)
                                self._index['productDefinitionTemplate'][self.messages].append(_pdt)
                            _nmsg += 1
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


    def read(self, num=0):
        """    
        Read num GRIB2 messages from the current position
        """
        msgs = []
        if self.tell() >= self.messages: return msgs
        if num > 0:
            beg = self.tell()+1
            end = self.tell()+1+num if self.tell()+1+num <= self.messages else self.messages
            msgrange = range(beg,end+1)
            for n in msgrange:
                self._filehandle.seek(self._index['offset'][n])
                msgs.append(Grib2Message(self._filehandle.read(self._index['size'][n]),ref=self))
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
        """
        return self.current_message



class Grib2Message:
    def __init__(self, msg, ref=None):
        """
        """
        self._msg = msg
        self._pos = 0
        self._ref = ref
        self._datapos = []
        self._msgcount = 0
        self._secnumlist = []
        
        # Section 0, Indicator Section
        self.indicatorSection = []
        self.indicatorSection.append(struct.unpack('>4s',self._msg[0:4])[0])
        self.indicatorSection.append(struct.unpack('>H',self._msg[4:6])[0])
        self.indicatorSection.append(self._msg[6])
        self.indicatorSection.append(self._msg[7])
        self.indicatorSection.append(struct.unpack('>Q',self._msg[8:16])[0])
        self._pos = 16
        self._secnumlist.append(0)
        
        # Section 1, Indentification Section.
        self.identificationSection,self._pos = g2clib.unpack1(self._msg,self._pos,np.empty)
        self.identificationSection = self.identificationSection.tolist()
        self._secnumlist.append(1)

        # After Section 1, perform rest of GRIB2 Decoding inside while loop
        # to account for sub-messages.
        while True:
            if self._msg[self._pos:self._pos+4].decode('ascii','ignore') == '7777': break
            if self._msgcount >= 1:
                pass #print("GRIB2 Message has sub-messages")
                # We have sub-messages... need to convert to lists.

            # Read the length and section number.
            sectlen = struct.unpack('>i',self._msg[self._pos:self._pos+4])[0]
            sectnum = struct.unpack('>B',self._msg[self._pos+4:self._pos+5])[0]
            self._secnumlist.append(sectnum)

            # Section 2, Local Use Section.
            if sectnum == 2:
                if self._msgcount == 0:
                    self.localUseSection = []
                _lus = self._msg[self._pos+5:self._pos+sectlen]
                self._pos += sectlen
                self.localUseSection.append(_lus)
            # Section 3, Grid Definition Section.
            elif sectnum == 3:
                if self._msgcount == 0:
                    self.gridDefinitionSection  = []
                    self.gridDefinitionTemplateNumber = []
                    self.gridDefinitionTemplate = []
                    self.defList = []
                _gds,_gdtn,_deflist,self._pos = g2clib.unpack3(self._msg,self._pos,np.empty)
                self.gridDefinitionSection.append(_gds.tolist())
                self.gridDefinitionTemplateNumber.append(_gds[4])
                self.gridDefinitionTemplate.append(_gdtn.tolist())
                self.defList.append(_deflist.tolist())
            # Section 4, Product Definition Section.
            elif sectnum == 4:
                if self._msgcount == 0:
                    self.productDefinitionTemplate = []
                    self.productDefinitionTemplateNumber = []
                    self.coordinateList = []
                _pdt,_pdtn,_coordlst,self._pos = g2clib.unpack4(self._msg,self._pos,np.empty)
                self.productDefinitionTemplate.append(_pdt.tolist())
                self.productDefinitionTemplateNumber.append(_pdtn)
                self.coordinateList.append(_coordlst.tolist())
            # Section 5, Data Representation Section.
            elif sectnum == 5:
                if self._msgcount == 0:
                    self.dataRepresentationTemplate = []
                    self.dataRepresentationTemplateNumber = []
                    self.numberOfDataPoints = []
                _drt,_drtn,_npts,self._pos = g2clib.unpack5(self._msg,self._pos,np.empty)
                self.dataRepresentationTemplate.append(_drt.tolist())
                self.dataRepresentationTemplateNumber.append(_drtn)
                self.numberOfDataPoints.append(_npts)
            # Section 6, Bitmap Section.
            elif sectnum == 6:
                if self._msgcount == 0:
                    self.bitMapFlag = []
                    self.bitMap = []
                _bmap,_bmapflag = g2clib.unpack6(self._msg,self.gridDefinitionSection[self._msgcount-1][1],self._pos,np.empty)
                self.bitMapFlag.append(_bmapflag)
                self.bitMap.append(_bmap)
                self._pos += sectlen # IMPORTANT: This is here because g2clib.unpack6() does not return updated position.
            # Section 7, Data Section (data unpacked when getfld method is invoked).
            elif sectnum == 7:
                self._datapos.append(self._pos)
                self._pos += sectlen # REMOVE WHEN UNPACKING DATA IS IMPLEMENTED
                self._msgcount += 1
            else:
                errmsg = 'Unknown section number = %i' % sectnum
                raise ValueError(errmsg) 


    def __repr__(self):
        """
        """
        strings = []
        keys = self.__dict__.keys()
        for k in keys:
            if not k.startswith('_'):
                strings.append('%s = %s\n'%(k,self.__dict__[k]))
        return ''.join(strings)
                

#    @property
#    def discipline(self):
#        return self.indicator_section[2]
#
#    @property
#    def edition(self):
#        return self.indicator_section[3]
#        
#    @property
#    def size(self):
#        return self.indicator_section[4]
