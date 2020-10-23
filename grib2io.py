import builtins
import g2clib
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
        if 'r' in self.mode: self._build_index()


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
            self._filehandle.seek(beg)
            return [self.current_message(i+1) for i in range(beg,end,inc)]
        elif isinstance(key,int):
            if key == 0: return None
            self._filehandle.seek(key)
            return self.current_message(key)
        else:
            raise KeyError('Key must be an integer or slice')


    def _build_index(self):
        """
        Perform indexing of GRIB2 Messages.
        """
        # Initialize index dictionary
        self._index['offset'] = []
        self._index['discipline'] = []
        self._index['edition'] = []
        self._index['size'] = []
        # Set first item (0th index) to None.
        self._index['offset'].append(None)
        self._index['discipline'].append(None)
        self._index['edition'].append(None)
        self._index['size'].append(None)

        # Iterate
        while True:
            try:
                # Read first 4 bytes and decode...looking for "GRIB"
                pos = self._filehandle.tell()
                header = struct.unpack('>4s',self._filehandle.read(4))[0].decode()

                # Test header. Then get information from GRIB2 Section 0: the discipline
                # number, edition number (should always be 2), and GRIB2 message size.
                if header == 'GRIB':
                    self._filehandle.seek(self._filehandle.tell()+2)
                    discipline = int(struct.unpack('>B',self._filehandle.read(1))[0])
                    edition = int(struct.unpack('>B',self._filehandle.read(1))[0])
                    size = struct.unpack('>Q',self._filehandle.read(8))[0]
                    self._filehandle.seek((pos+size)-4)
                    trailer = struct.unpack('>4s',self._filehandle.read(4))[0].decode()
                    if trailer == '7777':
                        self._index['offset'].append(pos)
                        self._index['discipline'].append(discipline)
                        self._index['edition'].append(edition)
                        self._index['size'].append(size)
                        self.messages += 1

            except(struct.error):
                self._filehandle.seek(0)
                break

        self._hasindex = True
                    

    def close(self):
        """
        Close the file handle
        """
        self._filehandle.close()

    def read(self, num=0):
        """    
        Read num GRIB2 messages from the current position
        """
        msgs = []
        if self.tell() >= self.messages: return msgs
        if num > 0:
            msgrange = range(self.tell()+1,self.tell()+num+1)
            for n in msgrange:
                self._filehandle.seek(self._index['offset'][n+1])
                msgs.append(Grib2Message(self._filehandle.read(self._index['size'][n+1])))
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
    def __init__(self, msg):
        """
        """
        self._msg = msg
        self._pos = 0
        self._datapos = 0
        self._msgcount = 0
        
        # Section 0, Indicator Section
        self.indicator_section = []
        self.indicator_section.append(struct.unpack('>4s',self._msg[0:4])[0])
        self.indicator_section.append(struct.unpack('>H',self._msg[4:6])[0])
        self.indicator_section.append(self._msg[6])
        self.indicator_section.append(self._msg[7])
        self.indicator_section.append(struct.unpack('>Q',self._msg[8:16])[0])
        self._pos = 16
        
        # Section 1, Indentification Section.
        self.identification_section,self._pos = g2clib.unpack1(self._msg,self._pos,np.empty)
        self.identification_section = self.identification_section.tolist()

        # After Section 1, perform rest of GRIB2 Decoding inside while loop
        # to account for sub-messages.
        while 1:

            if self._msg[self._pos:self._pos+4].decode('ascii','ignore') == '7777': break
            if self._msgcount >= 1:
                print("GRIB2 Message has sub-messages")
                # We have sub-messages... need to convert to lists.

            lensect = struct.unpack('>i',self._msg[self._pos:self._pos+4])[0]
            sectnum = struct.unpack('>B',self._msg[self._pos+4:self._pos+5])[0]
            # Section 2, Local Use Section.
            if sectnum == 2:
                self.sect2 = self._msg[self._pos+5:self._pos+lensect]
                self._pos += lensect
            # Section 3, Grid Definition Section.
            elif sectnum == 3:
                self.sect3_gds,self.sect3_gdtempl,self.sect3_deflist,self._pos = g2clib.unpack3(self._msg,self._pos,np.empty)
            # Section 4, Product Definition Section.
            elif sectnum == 4:
                self.sect4_pdtempl,self.sect4_pdtn,self.sect4_coordlst,self._pos = g2clib.unpack4(self._msg,self._pos,np.empty)
            # Section 5, Data Representation Section.
            elif sectnum == 5:
                self.sect5_drtempl,self.sect5_drtn,self.sect5_npts,self._pos = g2clib.unpack5(self._msg,self._pos,np.empty)
            # Section 6, Bitmap Section.
            elif sectnum == 6:
                self.sect6_bmap,self.sect6_bmapflag = g2clib.unpack6(self._msg,self.sect3_gds[1],self._pos,np.empty)
                #bitmapflag = struct.unpack('>B',self._msg[pos+5])[0]
                #if bmapflag == 0:
                #    bitmaps.append(bmap.astype('b'))
                ## use last defined bitmap.
                #elif bmapflag == 254:
                #    bmapflag = 0
                #    for bmp in bitmaps[::-1]:
                #        if bmp is not None: bitmaps.append(bmp)
                #else:
                #    bitmaps.append(None)
                #bitmapflags.append(bmapflag)
                self._pos += lensect
            # Section 7, Data Section (data unpacked when getfld method is invoked).
            else:
                if sectnum != 7:
                   errmsg = 'Unknown section number = %i' % sectnum
                   raise ValueError(errmsg) 
                self._pos += lensect
                self._datapos = self._pos
                self._msgcount += 1
                

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
