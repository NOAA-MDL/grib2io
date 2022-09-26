from copy import copy
from dataclasses import dataclass, field

from . import tables
from . import utils
from . import _grib2io


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
        return _grib2io.Grib2Metadata(obj._section0[2],table='0.0')
    def __set__(self, obj, value):
        obj._section0[2] = value
        obj._varinfo = tables.get_varinfo_from_table(obj._section0[2],obj._productDefinitionTemplate[0],
                                                     obj._productDefinitionTemplate[1],isNDFD=obj.isNDFD)

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 1 metadata.
# ---------------------------------------------------------------------------------------- 
class OriginatingCenter:
    def __get__(self, obj, objtype=None):
        return _grib2io.Grib2Metadata(obj._section1[0],table='originating_centers')
    def __set__(self, obj, value):
        obj._section1[0] = value
class OriginatingSubCenter:
    def __get__(self, obj, objtype=None):
        return _grib2io.Grib2Metadata(obj._section1[1],table='originating_subcenters')
    def __set__(self, obj, value):
        obj._section1[1] = value
class MasterTableInfo:
    def __get__(self, obj, objtype=None):
        return _grib2io.Grib2Metadata(obj._section1[2],table='1.0')
    def __set__(self, obj, value):
        obj._section1[2] = value
class LocalTableInfo:
    def __get__(self, obj, objtype=None):
        return _grib2io.Grib2Metadata(obj._section1[3],table='1.1')
    def __set__(self, obj, value):
        obj._section1[3] = value
class SignificanceOfReferenceTime:
    def __get__(self, obj, objtype=None):
        return _grib2io.Grib2Metadata(obj._section1[4],table='1.2')
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
        return _grib2io.Grib2Metadata(obj.section1[11],table='1.3')
    def __set__(self, obj, value):
        obj._section1[11] = value
class TypeOfData:
    def __get__(self, obj, objtype=None):
        return _grib2io.Grib2Metadata(obj.section1[12],table='1.4')
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
        return _grib2io.Grib2Metadata(obj._gridDefinitionSection[4],table='3.1')
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
        return _grib2io.Grib2Metadata(obj._gridDefinitionTemplate[0],table='3.2')
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
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[4]
        if gdtn in {0,1,40,41,203,204,205,32768,32769}:
            return utils.int2bin(obj._gridDefinitionTemplate[18],output=list)[0:4]
        elif gdtn in {10,110}:
            return utils.int2bin(obj._gridDefinitionTemplate[15],output=list)[0:4]
        elif gdtn in {20,30,31}:
            return utils.int2bin(obj._gridDefinitionTemplate[17],output=list)[0:4]
        elif gdtn == 50:
            return [None, None, None, None]
        elif gdtn == 90:
            return utils.int2bin(obj._gridDefinitionTemplate[16],output=list)[0:4]
        else:
            raise ValueError
    def __set__(self, obj, value):
        pass

class ResolutionAndComponentFlags:
    def __get__(self, obj, objtype=None):
        gdtn = obj._gridDefinitionSection[4]
        if gdtn in {0,1,40,41,203,204,205,32768,32769}:
            return utils.int2bin(obj._gridDefinitionTemplate[13],output=list)
        elif gdtn in {10,110,20,30,31,90}:
            return utils.int2bin(obj._gridDefinitionTemplate[11],output=list)
        elif gdtn == 50:
            return [None for i in range(8)]
        else:
            raise ValueError
    def __set__(self, obj, value):
        pass

def add_grid_definition_template(cls,gdtn):
    """
    Adds a GRIB2 Grid Definition Template to the Grib2Message class.  The template added
    is a dataclass with class variables defined for that template.  Each class variable
    is a dataclass with a default value of a custom descriptor class for that particular
    attribute.
    """
    class LatitudeFirstGridpoint:
        def loc(self, gdtn):
            if gdtn in {0,1,40,41,203,204,205,32768,32769}:
                return  11
            elif gdtn in {10,110}:
                return 9
            elif gdtn in {20,30,31}:
                return 9
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class LongitudeFirstGridpoint:
        def loc(self, gdtn):
            if gdtn in {0,1,40,41,203,204,205,32768,32769}:
                return  12
            elif gdtn in {10,110}:
                return 10
            elif gdtn in {20,30,31}:
                return 10
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class LatitudeLastGridpoint:
        def loc(self, gdtn):
            if gdtn in {0,1,40,41,203,204,205,32768,32769}:
                return  14
            elif gdtn in {10}:
                return 13
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class LongitudeLastGridpoint:
        def loc(self, gdtn):
            if gdtn in {0,1,40,41,203,204,205,32768,32769}:
                return  15
            elif gdtn in {10}:
                return 14
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class GridLengthXDirection:
        def loc(self, gdtn):
            if gdtn in {0,1,40,41,203,204,205,32768,32769}:
                return  16
            elif gdtn in {10}:
                return 17
            elif gdtn in {20,30,31}:
                return 14
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._xydivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._xydivisor/obj._llscalefactor)

    class GridLengthYDirection:
        def loc(self, gdtn):
            if gdtn in {0,1,40,41,203,204,205,32768,32769}:
                return  17
            elif gdtn in {10,110}:
                return 18
            elif gdtn in {20,30,31}:
                return 15
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._xydivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._xydivisor/obj._llscalefactor)

    class LatitudeSouthernPole:
        def loc(self, gdtn):
            if gdtn in {1,41}:
                return  19
            elif gdtn in {30,31}:
                return 20
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class LongitudeSouthernPole:
        def loc(self, gdtn):
            if gdtn in {1,41}:
                return  20
            elif gdtn in {30,31}:
                return 21
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class AnglePoleRotation:
        def loc(self, gdtn):
            if gdtn in {1,41}:
                return  21
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._gridDefinitionTemplate[l]
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value)

    class LatitudeTrueScale:
        def loc(self, gdtn):
            if gdtn in {10,20,30,31}:
                return 12
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class GridOrientation:
        def loc(self, gdtn):
            if gdtn in {10}:
                return  16
            elif gdtn in {20,30,31}:
                return  13
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            if obj._gridDefinitionSection[-1] == 10 and (value < 0 or value > 90):
                raise ValueError("Grid orientation is limited to range of 0 to 90 degrees.")
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class ProjectionCenterFlag:
        def loc(self, gdtn):
            if gdtn in {20,30,31}:
                return  16
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return utils.int2bin(obj._gridDefinitionTemplate[l],output=list)[0]
        def __set__(self, obj, value):
            pass

    class StandardLatitude1:
        def loc(self, gdtn):
            if gdtn in {30,31}:
                return 18
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

    class StandardLatitude2:
        def loc(self, gdtn):
            if gdtn in {30,31}:
                return 18
        def __get__(self, obj, objtype=None):
            l = self.loc(obj._gridDefinitionSection[-1])
            return obj._llscalefactor*obj._gridDefinitionTemplate[l]/obj._lldivisor
        def __set__(self, obj, value):
            l = self.loc(obj._gridDefinitionSection[-1])
            obj._gridDefinitionTemplate[l] = int(value*obj._lldivisor/obj._llscalefactor)

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

    if gdtn == 0: 
        @dataclass(init=False)
        class GridDefinitionTemplate0(cls):
            latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
            longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
            latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
            longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
            gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
            gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
        return GridDefinitionTemplate0

    elif gdtn == 1:
        @dataclass(init=False)
        class GridDefinitionTemplate1(cls):
            latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
            longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
            latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
            longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
            gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
            gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
            latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
            longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
            anglePoleRotation: float = field(init=False, repr=True, default=AnglePoleRotation())
        return GridDefinitionTemplate1

    elif gdtn == 10:
        @dataclass(init=False)
        class GridDefinitionTemplate10(cls):
            latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
            longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
            latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
            latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
            longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
            gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
            gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
            gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
            projParameters: dict = field(init=False, repr=True, default=ProjParameters())
        return GridDefinitionTemplate10

    elif gdtn == 20:
        @dataclass(init=False)
        class GridDefinitionTemplate20(cls):
            latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
            longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
            latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
            gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
            gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
            gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
            projectionCenterFlag: list = field(init=False, repr=True, default=ProjectionCenterFlag())
            projParameters: dict = field(init=False, repr=True, default=ProjParameters())
        return GridDefinitionTemplate20

    elif gdtn == 30:
        @dataclass(init=False)
        class GridDefinitionTemplate30(cls):
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
        return GridDefinitionTemplate30

    elif gdtn == 31:
        @dataclass(init=False)
        class GridDefinitionTemplate31(cls):
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
        return GridDefinitionTemplate31

    elif gdtn == 40:
        @dataclass(init=False)
        class GridDefinitionTemplate40(cls):
            latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
            longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
            latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
            longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
            gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
            gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
        return GridDefinitionTemplate40

    elif gdtn == 41:
        @dataclass(init=False)
        class GridDefinitionTemplate41(cls):
            latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
            longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
            latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
            longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
            gridLengthXDirection: float = field(init=False, repr=True, default=GridLengthXDirection())
            gridLengthYDirection: float = field(init=False, repr=True, default=GridLengthYDirection())
            latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
            longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
            anglePoleRotation: float = field(init=False, repr=True, default=AnglePoleRotation())
        return GridDefinitionTemplate41

    elif gdtn == 50:
        @dataclass(init=False)
        class GridDefinitionTemplate50(cls):
            spectralFunctionParameters: list = field(init=False, repr=True, default=SpectralFunctionParameters())
        return GridDefinitionTemplate50

    else:
        errmsg = 'Unsupported Grid Definition Template Number - 3.%i' % (gdtn)
        raise ValueError(errmsg)

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 4 metadata.
# ---------------------------------------------------------------------------------------- 
class ProductDefinitionTemplateNumber:
    def __get__(self, obj, objtype=None):
        return _grib2io.Grib2Metadata(obj._productDefinitionTemplateNumber,table='4.0')
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
        return _grib2io.Grib2Metadata(obj._productDefinitionTemplate[9],table='4.5')
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
        return _grib2io.Grib2Metadata(obj._productDefinitionTemplate[12],table='4.5')
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

# ---------------------------------------------------------------------------------------- 
# Descriptor Classes for Section 5 metadata.
# ---------------------------------------------------------------------------------------- 
class TypeOfValues:
    def __get__(self, obj, objtype=None):
        if obj.dataRepresentationTemplateNumber == 0:
            # Template 5.0 - Simple Packing
            return _grib2io.Grib2Metadata(obj.dataRepresentationTemplate[3],table='5.1')
        else:
            return _grib2io.Grib2Metadata(obj.dataRepresentationTemplate[4],table='5.1')
