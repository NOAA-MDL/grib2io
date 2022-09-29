from copy import copy
from dataclasses import dataclass, field

from . import tables
from . import utils

class Grib2Metadata():
    """
    Class to hold GRIB2 metadata both as numeric code value as stored in
    GRIB2 and its plain langauge definition.

    **`value : int`**

    GRIB2 metadata integer code value.

    **`table : str, optional`**

    GRIB2 table to lookup the `value`. Default is None.
    """
    __slots__ = ('definition','table','value')
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

class Grib2Section:
    """Generic descriptor class for a GRIB2 section."""
    def __set_name__(self, owner, name):
        self.private_name = f'_{name}'
        
    def public_name(self):
        """Can be used by subclass with super().get_name() to discover
           the private name without _ ; helpfull for raising informative errors"""
        return self.private_name.strip('_')
        
    def __get__(self, obj, objtype=None):
        # Returning a copy prevents changes occuring to obj
        return copy(getattr(obj, self.private_name))
    
    def __set__(self, obj, value):
        # Logic for managing set
        print(f'setitem called on self.{self.public_name()}; rebuild Grib2msg Object')
        setattr(obj, self.private_name, value)


# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 0 metadata.
# ---------------------------------------------------------------------------------------- 
class Discipline:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._section0[2],table='0.0')
    def __set__(self, obj, value):
        obj._section0[2] = value
        obj._varinfo = tables.get_varinfo_from_table(obj._section0[2],obj._productDefinitionTemplate[0],
                                                     obj._productDefinitionTemplate[1],isNDFD=obj.isNDFD)

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 1 metadata.
# ---------------------------------------------------------------------------------------- 
class OriginatingCenter:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._section1[0],table='originating_centers')
    def __set__(self, obj, value):
        obj._section1[0] = value

class OriginatingSubCenter:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._section1[1],table='originating_subcenters')
    def __set__(self, obj, value):
        obj._section1[1] = value

class MasterTableInfo:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._section1[2],table='1.0')
    def __set__(self, obj, value):
        obj._section1[2] = value

class LocalTableInfo:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._section1[3],table='1.1')
    def __set__(self, obj, value):
        obj._section1[3] = value

class SignificanceOfReferenceTime:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._section1[4],table='1.2')
    def __set__(self, obj, value):
        obj._section1[4] = value

class Year:
    def __get__(self, obj, objtype=None):
        return obj._section1[5]
    def __set__(self, obj, value):
        obj._section1[5] = value

class Month:
    def __get__(self, obj, objtype=None):
        return obj._section1[6]
    def __set__(self, obj, value):
        obj._section1[6] = value

class Day:
    def __get__(self, obj, objtype=None):
        return obj._section1[7]
    def __set__(self, obj, value):
        obj._section1[7] = value

class Hour:
    def __get__(self, obj, objtype=None):
        return obj._section1[8]
    def __set__(self, obj, value):
        obj._section1[8] = value

class Minute:
    def __get__(self, obj, objtype=None):
        return obj._section1[9]
    def __set__(self, obj, value):
        obj._section1[9] = value

class Second:
    def __get__(self, obj, objtype=None):
        return obj._section1[10]
    def __set__(self, obj, value):
        obj._section1[10] = value

class RefDate:
    def __get__(self, obj, objtype=None):
        return (obj.year*1000000)+(obj.month*10000)+(obj.day*100)+obj.hour
    def __set__(self, obj, value):
        d = str(value)
        obj._section1[5] = int(d[0:4])
        obj._section1[6] = int(d[4:6])
        obj._section1[7] = int(d[6:8])
        obj._section1[8] = int(d[8:10])
        del d

class ProductionStatus:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[11],table='1.3')
    def __set__(self, obj, value):
        obj._section1[11] = value

class TypeOfData:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[12],table='1.4')
    def __set__(self, obj, value):
        obj._section1[12] = value

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 2 metadata.
# ---------------------------------------------------------------------------------------- 

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 3 metadata.
# ---------------------------------------------------------------------------------------- 
class GridDefinitionTemplateNumber:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._gridDefinitionSection[4],table='3.1')
    def __set__(self, obj, value):
        #obj._gridDefinitionSection[4] = value
        pass

class GridDefinitionTemplate:
    """ This has __get__ and __set__ and therefore implements the descriptor protocol """ 
    def __set_name__(self, owner, name):
        self.private_name = f'_{name}'   
    def __get__(self, obj, objtype=None):
        return getattr(obj, self.private_name)
    def __set__(self, obj, value):
        setattr(obj, self.private_name, value)

class ShapeOfEarth:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._gridDefinitionTemplate[0],table='3.2')
    def __set__(self, obj, value):
        obj._gridDefinitionTemplate[0] = value

class EarthRadius:
    def __get__(self, obj, objtype=None):
        if obj._earthparams['shape'] == 'spherical':
            if obj._earthparams['radius'] is None:
                return obj._gridDefinitionTemplate[2]/(10.**obj._gridDefinitionTemplate[1])
            else:
                return obj._earthparams['radius']
        if obj._earthparams['shape'] == 'oblateSpheriod':
            if obj._earthparams['radius'] is None and obj._earthparams['major_axis'] is None and obj._earthparams['minor_axis'] is None:
                return obj._gridDefinitionTemplate[2]/(10.**obj._gridDefinitionTemplate[1])
            else:
                return earthparams['radius']

class EarthMajorAxis:
    def __get__(self, obj, objtype=None):
        if obj._earthparams['shape'] == 'spherical':
            return None
        if obj._earthparams['shape'] == 'oblateSpheriod':
            if obj._earthparams['radius'] is None and obj._earthparams['major_axis'] is None and obj._earthparams['minor_axis'] is None:
                return obj._gridDefinitionTemplate[4]/(10.**obj._gridDefinitionTemplate[3])
            else:
                return earthparams['major_axis']

class EarthMinorAxis:
    def __get__(self, obj, objtype=None):
        if obj._earthparams['shape'] == 'spherical':
            return None
        if obj._earthparams['shape'] == 'oblateSpheriod':
            if obj._earthparams['radius'] is None and obj._earthparams['major_axis'] is None and obj._earthparams['minor_axis'] is None:
                return obj._gridDefinitionTemplate[6]/(10.**obj._gridDefinitionTemplate[5])
            else:
                return earthparams['minor_axis']

class Nx:
    def __get__(self, obj, objtype=None):
        return obj._gridDefinitionTemplate[7]
    def __set__(self, obj, value):
        pass

class Ny:
    def __get__(self, obj, objtype=None):
        return obj._gridDefinitionTemplate[8]
    def __set__(self, obj, value):
        pass

class ScanModeFlags:
    _key = {0:18, 1:18, 10:15, 20:17, 30:17, 31:17, 40:18, 41:18, 90:16, 110:15, 203:18, 204:18, 205:18, 32768:18, 32769:18}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        if gdtn == 50:
            return [None, None, None, None]
        else:
            return utils.int2bin(obj._gridDefinitionTemplate[self._key[gdtn]],output=list)[0:4]
    def __set__(self, obj, value):
        pass

class ResolutionAndComponentFlags:
    _key = {0:13, 1:13, 10:11, 20:11, 30:11, 31:11, 40:13, 41:13, 90:11, 110:11, 203:13, 204:13, 205:13, 32768:13, 32769:13}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        if gdtn == 50:
            return [None for i in range(8)]
        else:
            return utils.int2bin(obj._gridDefinitionTemplate[self._key[gdtn]],output=list)
    def __set__(self, obj, value):
        pass

class LatitudeFirstGridpoint:
    _key = {0:11, 1:11, 10:9, 20:9, 30:9, 31:9, 40:11, 41:11, 110:9, 203:11, 204:11, 205:11, 32768:11, 32769:11}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeFirstGridpoint:
    _key = {0:12, 1:12, 10:10, 20:10, 30:10, 31:10, 40:12, 41:12, 110:10, 203:12, 204:12, 205:12, 32768:12, 32769:12}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._lldivisor/obj._llscalefactor)

class LatitudeLastGridpoint:
    _key = {0:14, 1:14, 10:13, 40:14, 41:14, 203:14, 204:14, 205:14, 32768:14, 32769:14}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeLastGridpoint:
    _key = {0:15, 1:15, 10:14, 40:15, 41:15, 203:15, 204:15, 205:15, 32768:15, 32769:15}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

class GridLengthXDirection:
    _key = {0:16, 1:16, 10:17, 20:14, 30:14, 31:14, 40:16, 41:16, 203:16, 204:16, 205:16, 32768:16, 32769:16}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._xydivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._xydivisor/obj._llscalefactor)

class GridLengthYDirection:
    _key = {0:17, 1:17, 10:18, 20:15, 30:15, 31:15, 40:17, 41:17, 203:17, 204:17, 205:17, 32768:17, 32769:17}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._xydivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._xydivisor/obj._llscalefactor)

class LatitudeSouthernPole:
    _key = {1:19, 30:20, 31:20, 41:19}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeSouthernPole:
    _key = {1:20, 30:21, 31:21, 41:20}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

class AnglePoleRotation:
    _key = {1:21, 41:21}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._gridDefinitionTemplate[self._key[gdtn]]
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value)

class LatitudeTrueScale:
    _key = {10:12, 20:12, 30:12, 31:12}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._lldivisor/obj._llscalefactor)

class GridOrientation:
    _key = {10:16, 20:13, 30:13, 31:13}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        if gdtn == 10 and (value < 0 or value > 90):
            raise ValueError("Grid orientation is limited to range of 0 to 90 degrees.")
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._lldivisor/obj._llscalefactor)

class ProjectionCenterFlag:
    _key = {20:16, 30:16, 31:16}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return utils.int2bin(obj._gridDefinitionTemplate[self._key[gdtn]],output=list)[0]
    def __set__(self, obj, value):
        pass

class StandardLatitude1:
    _key = {30:18, 31:18}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._lldivisor/obj._llscalefactor)

class StandardLatitude2:
    _key = {30:19, 31:19}
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        return obj._llscalefactor*obj._gridDefinitionTemplate[self._key[gdtn]]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj._gridDefinitionSection[-1]
        obj._gridDefinitionTemplate[self._key[gdtn]] = int(value*obj._lldivisor/obj._llscalefactor)

class SpectralFunctionParameters:
    def __get__(self, obj, objtype=None):
        return obj._gridDefinitionTemplate[0:3]
    def __set__(self, obj, value):
        obj._gridDefinitionTemplate[0:3] = value[0:3]

class ProjParameters:
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[-1]
        if gdtn == 10:
            return dict({'proj':'merc','lat_ts':obj.latitudeTrueScale,
                         'lon_0':0.5*(obj.longitudeFirstGridpoint+obj.longitudeLastGridpoint)})
        elif gdtn == 20:
            if obj.projectionCenterFlag == 0:
                lat0 = 90.0
            elif obj.projectionCenterFlag == 1:
                lat0 = -90.0
            return dict({'proj':'stere','lat_ts':obj.latitudeTrueScale,
                         'lat_0':lat0,'lon_0':obj.gridOrientation})
        elif gdtn == 30:
            return dict({'proj':'lcc','lat_1':obj.standardLatitude1,'lat_2':obj.standardLatitude2,
                         'lat_0':obj.latitudeTrueScale,'lon_0':gridOrientation})
        elif gdtn == 31:
            return dict({'proj':'aea','lat_1':obj.standardLatitude1,'lat_2':obj.standardLatitude2,
                         'lat_0':obj.latitudeTrueScale,'lon_0':gridOrientation})
    def __set__(self, obj, value):
        pass

@dataclass(init=False)
class GridDefinitionTemplate0():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())

@dataclass(init=False)
class GridDefinitionTemplate1():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
    anglePoleRotation: float = field(init=False, repr=True, default=AnglePoleRotation())

@dataclass(init=False)
class GridDefinitionTemplate10():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
    projParameters: dict = field(init=False, repr=True, default=ProjParameters())

@dataclass(init=False)
class GridDefinitionTemplate20():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=True, default=ProjectionCenterFlag())
    projParameters: dict = field(init=False, repr=True, default=ProjParameters())

@dataclass(init=False)
class GridDefinitionTemplate30():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=True, default=ProjectionCenterFlag())
    standardLatitude1: float = field(init=False, repr=True, default=StandardLatitude1())
    standardLatitude2: float = field(init=False, repr=True, default=StandardLatitude2())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
    projParameters: dict = field(init=False, repr=True, default=ProjParameters())

@dataclass(init=False)
class GridDefinitionTemplate31():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=True, default=ProjectionCenterFlag())
    standardLatitude1: float = field(init=False, repr=True, default=StandardLatitude1())
    standardLatitude2: float = field(init=False, repr=True, default=StandardLatitude2())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())

@dataclass(init=False)
class GridDefinitionTemplate40():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())

@dataclass(init=False)
class GridDefinitionTemplate41():
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
    gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
    anglePoleRotation: float = field(init=False, repr=True, default=AnglePoleRotation())

@dataclass(init=False)
class GridDefinitionTemplate50():
    spectralFunctionParameters: list = field(init=False, repr=True, default=SpectralFunctionParameters())

_gdt_by_gdtn = {0: GridDefinitionTemplate0,
    1: GridDefinitionTemplate1,
    10: GridDefinitionTemplate10,
    20: GridDefinitionTemplate20,
    30: GridDefinitionTemplate30,
    31: GridDefinitionTemplate31,
    40: GridDefinitionTemplate40,
    41: GridDefinitionTemplate41,
    50: GridDefinitionTemplate50,
    }

def gdt_class_by_gdtn(gdtn):
    return _gdt_by_gdtn[gdtn]

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 4 metadata.
# ---------------------------------------------------------------------------------------- 
class ProductDefinitionTemplateNumber:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._productDefinitionTemplateNumber,table='4.0')
    def __set__(self, obj, value):
        #obj._productDefinitionTemplateNumber = value
        pass

class ProductDefinitionTemplate:
    """ This has __get__ and __set__ and therefore implements the descriptor protocol """
    def __set_name__(self, owner, name):
        self.private_name = f'_{name}'
    def __get__(self, obj, objtype=None):
        return getattr(obj, self.private_name)
    def __set__(self, obj, value):
        setattr(obj, self.private_name, value)

class ParameterCategory:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[0]
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[0] = value
        obj._varinfo = tables.get_varinfo_from_table(obj._section0[2],obj._productDefinitionTemplate[0],
                                                     obj._productDefinitionTemplate[1],isNDFD=self.isNDFD)

class ParameterNumber:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[1]
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[1] = value
        obj._varinfo = tables.get_varinfo_from_table(obj._section0[2],obj._productDefinitionTemplate[0],
                                                     obj._productDefinitionTemplate[1],isNDFD=self.isNDFD)

class FullName:
    def __get__(self, obj, objtype=None):
        return obj._varinfo[0]
    def __set__(self, obj, value):
        #obj._varinfo[0] = value
        pass

class Units:
    def __get__(self, obj, objtype=None):
        return obj._varinfo[1]
    def __set__(self, obj, value):
        #obj._varinfo[1] = value
        pass

class ShortName:
    def __get__(self, obj, objtype=None):
        return obj._varinfo[2]
    def __set__(self, obj, value):
        #obj._varinfo[2] = value
        pass

class TypeOfGeneratingProcess:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._productDefinitionTemplate[2],table='4.3')
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[2] = value
        
class BackgroundGeneratingProcessIdentifier:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[3]
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[3] = value

class GeneratingProcess:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._productDefinitionTemplate[4],table='generating_process')
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[4] = value

class UnitOfTimeRange:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._productDefinitionTemplate[7],table='4.4')
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[7] = value

class LeadTime:
    def __get__(self, obj, objtype=None):
        return utils.getleadtime(obj._section1,obj._productDefinitionTemplateNumber,
                                 obj._productDefinitionTemplate)
    def __set__(self, obj, value):
        pass

class TypeOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._productDefinitionTemplate[9],table='4.5')
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[9] = value

class ScaleFactorOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[10]
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[10] = value

class ScaledValueOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[11]
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[11] = value

class UnitOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._fixedsfc1info[1]
    def __set__(self, obj, value):
        pass

class ValueOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[11]/(10.**obj._productDefinitionTemplate[10])
    def __set__(self, obj, value):
        pass

class TypeOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj._productDefinitionTemplate[12],table='4.5')
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[12] = value

class ScaleFactorOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[13]
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[13] = value

class ScaledValueOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[14]
    def __set__(self, obj, value):
        obj._productDefinitionTemplate[14] = value

class UnitOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._fixedsfc2info[1]
    def __set__(self, obj, value):
        pass

class ValueOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._productDefinitionTemplate[14]/(10.**obj._productDefinitionTemplate[13])
    def __set__(self, obj, value):
        pass

class Level:
    def __get__(self, obj, objtype=None):
        return tables.get_wgrib2_level_string(*obj._productDefinitionTemplate[9:15])
    def __set__(self, obj, value):
        pass

class TypeOfEnsembleForecast:
    _key = {1:15, 11:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.6')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class PerturbationNumber:
    _key = {1:16, 11:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class NumberOfEnsembleForecasts:
    _key = {1:17, 2:16, 11:17, 12:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class TypeOfDerivedForecast:
    _key = {2:15, 12:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.7')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class ForecastProbabilityNumber:
    _key = {5:15, 9:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class TotalNumberOfForecastProbabilities:
    _key = {5:16, 9:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class TypeOfProbability:
    _key = {5:17, 9:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.9')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class ScaleFactorOfThresholdLowerLimit:
    _key = {5:18, 9:18}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value
        
class ScaledValueOfThresholdLowerLimit:
    _key = {5:19, 9:19}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class ThresholdLowerLimit:
    def __get__(self, obj, objtype=None):
        if obj._productDefinitionTemplate[18] == -127 and \
           obj._productDefinitionTemplate[19] == 255:
            return 0.0
        else:
            return obj._productDefinitionTemplate[19]/(10.**obj._productDefinitionTemplate[18])
    def __set__(self, obj, value):
        pass

class ThresholdUpperLimit:
    def __get__(self, obj, objtype=None):
        if obj._productDefinitionTemplate[20] == -127 and \
           obj._productDefinitionTemplate[21] == 255:
            return 0.0
        else:
            return obj._productDefinitionTemplate[21]/(10.**obj._productDefinitionTemplate[20])
    def __set__(self, obj, value):
        pass

class Threshold:
    def __get__(self, obj, objtype=None):
        return utils.get_wgrib2_prob_string(*obj._productDefinitionTemplate[17:22])
    def __set__(self, obj, value):
        pass

class PercentileValue:
    _key = {6:15, 10:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class YearOfEndOfTimePeriod:
    _key = {8:15, 9:22, 10:16, 11:18, 12:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class MonthOfEndOfTimePeriod:
    _key = {8:16, 9:23, 10:17, 11:19, 12:18}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class DayOfEndOfTimePeriod:
    _key = {8:17, 9:24, 10:18, 11:20, 12:19}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class HourOfEndOfTimePeriod:
    _key = {8:18, 9:25, 10:19, 11:21, 12:20}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class MinuteOfEndOfTimePeriod:
    _key = {8:19, 9:26, 10:20, 11:22, 12:21}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class SecondOfEndOfTimePeriod:
    _key = {8:20, 9:27, 10:21, 11:23, 12:22}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class NumberOfTimeRanges:
    _key = {8:21, 9:28, 11:24, 12:23}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class NumberOfMissingValues:
    _key = {8:22, 9:29, 11:25, 12:24}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class StatisticalProcess:
    _key = {8:23, 9:30, 11:26, 12:25, 15:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.10')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class TypeOfTimeIncrementOfStatisticalProcess:
    _key = {8:24, 9:31, 11:27, 12:26}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.11')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class UnitOfTimeRangeOfStatisticalProcess:
    _key = {8:25, 9:32, 11:28, 12:27}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.4')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class TimeRangeOfStatisticalProcess:
    _key = {8:26, 9:33, 11:29, 12:28}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class UnitOfTimeRangeOfSuccessiveFields:
    _key = {8:27, 9:34, 11:30, 12:29}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.4')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class TimeIncrementOfSuccessiveFields:
    _key = {8:28, 9:35, 11:31, 12:30}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class TypeOfStatisticalProcessing:
    _key = {15:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return Grib2Metadata(obj._productDefinitionTemplate[self._key[pdtn]],table='4.15')
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value

class NumberOfDataPointsForSpatialProcessing:
    _key = {15:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj._productDefinitionTemplateNumber
        return obj._productDefinitionTemplate[self._key[pdtn]]
    def __set__(self, obj, value):
        pdtn = obj._productDefinitionTemplateNumber
        obj._productDefinitionTemplate[self._key[pdtn]] = value
    
@dataclass(init=False)
class ProductDefinitionTemplate0():
    pass

@dataclass(init=False)
class ProductDefinitionTemplate1():
    typeOfEnsembleForecast: Grib2Metadata = field(init=False, repr=True, default=TypeOfEnsembleForecast())
    perturbationNumber: int = field(init=False, repr=True, default=PerturbationNumber())
    numberOfEnsembleForecasts: int = field(init=False, repr=True, default=NumberOfEnsembleForecasts())

@dataclass(init=False)
class ProductDefinitionTemplate2():
    typeOfDerivedForecast: Grib2Metadata = field(init=False, repr=True, default=TypeOfDerivedForecast())
    numberOfEnsembleForecasts: int = field(init=False, repr=True, default=NumberOfEnsembleForecasts())

@dataclass(init=False)
class ProductDefinitionTemplate5():
    forecastProbabilityNumber: int = field(init=False, repr=True, default=ForecastProbabilityNumber())
    totalNumberOfForecastProbabilities: int = field(init=False, repr=True, default=TotalNumberOfForecastProbabilities())
    typeOfProbability: Grib2Metadata = field(init=False, repr=True, default=TypeOfProbability())
    thesholdLowerLimit: float = field(init=False, repr=True, default=ThresholdLowerLimit())
    thesholdUpperLimit: float = field(init=False, repr=True, default=ThresholdUpperLimit())
    threshold: str = field(init=False, repr=True, default=Threshold())

@dataclass(init=False)
class ProductDefinitionTemplate6():
    percentileValue: int = field(init=False, repr=True, default=PercentileValue())

@dataclass(init=False)
class ProductDefinitionTemplate8():
    yearOfEndOfTimePeriod: int = field(init=False, repr=True, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=True, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=True, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=True, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=True, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=True, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=True, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=True, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=True, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=True, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=True, default=TimeIncrementOfSuccessiveFields())

@dataclass(init=False)
class ProductDefinitionTemplate9():
    forecastProbabilityNumber: int = field(init=False, repr=True, default=ForecastProbabilityNumber())
    totalNumberOfForecastProbabilities: int = field(init=False, repr=True, default=TotalNumberOfForecastProbabilities())
    typeOfProbability: Grib2Metadata = field(init=False, repr=True, default=TypeOfProbability())
    thesholdLowerLimit: float = field(init=False, repr=True, default=ThresholdLowerLimit())
    thesholdUpperLimit: float = field(init=False, repr=True, default=ThresholdUpperLimit())
    threshold: str = field(init=False, repr=True, default=Threshold())
    yearOfEndOfTimePeriod: int = field(init=False, repr=True, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=True, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=True, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=True, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=True, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=True, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=True, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=True, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=True, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=True, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=True, default=TimeIncrementOfSuccessiveFields())

@dataclass(init=False)
class ProductDefinitionTemplate10():
    percentileValue: int = field(init=False, repr=True, default=PercentileValue())
    yearOfEndOfTimePeriod: int = field(init=False, repr=True, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=True, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=True, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=True, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=True, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=True, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=True, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=True, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=True, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=True, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=True, default=TimeIncrementOfSuccessiveFields())

@dataclass(init=False)
class ProductDefinitionTemplate11():
    typeOfEnsembleForecast: Grib2Metadata = field(init=False, repr=True, default=TypeOfEnsembleForecast())
    perturbationNumber: int = field(init=False, repr=True, default=PerturbationNumber())
    numberOfEnsembleForecasts: int = field(init=False, repr=True, default=NumberOfEnsembleForecasts())
    yearOfEndOfTimePeriod: int = field(init=False, repr=True, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=True, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=True, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=True, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=True, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=True, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=True, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=True, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=True, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=True, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=True, default=TimeIncrementOfSuccessiveFields())

@dataclass(init=False)
class ProductDefinitionTemplate12():
    typeOfDerivedForecast: Grib2Metadata = field(init=False, repr=True, default=TypeOfDerivedForecast())
    numberOfEnsembleForecasts: int = field(init=False, repr=True, default=NumberOfEnsembleForecasts())
    yearOfEndOfTimePeriod: int = field(init=False, repr=True, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=True, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=True, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=True, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=True, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=True, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=True, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=True, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=True, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=True, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=True, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=True, default=TimeIncrementOfSuccessiveFields())

@dataclass(init=False)
class ProductDefinitionTemplate15():
    statisticalProcess: Grib2Metadata = field(init=False, repr=True, default=StatisticalProcess())
    typeOfStatisticalProcessing: Grib2Metadata = field(init=False, repr=True, default=TypeOfStatisticalProcessing())
    numberOfDataPointsForSpatialProcessing: int = field(init=False, repr=True, default=NumberOfDataPointsForSpatialProcessing())

_pdt_by_pdtn = {
    0: ProductDefinitionTemplate0,
    1: ProductDefinitionTemplate1,
    2: ProductDefinitionTemplate2,
    5: ProductDefinitionTemplate5,
    6: ProductDefinitionTemplate6,
    8: ProductDefinitionTemplate8,
    9: ProductDefinitionTemplate9,
    10: ProductDefinitionTemplate10,
    11: ProductDefinitionTemplate11,
    12: ProductDefinitionTemplate12,
    15: ProductDefinitionTemplate15,
    }
        
def pdt_class_by_pdtn(pdtn):
    return _pdt_by_pdtn[pdtn]

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 5 metadata.
# ---------------------------------------------------------------------------------------- 
class TypeOfValues:
    def __get__(self, obj, objtype=None):
        if obj.dataRepresentationTemplateNumber == 0:
            # Template 5.0 - Simple Packing
            return Grib2Metadata(obj.dataRepresentationTemplate[3],table='5.1')
        else:
            return Grib2Metadata(obj.dataRepresentationTemplate[4],table='5.1')
