from dataclasses import dataclass, field

import datetime

from . import tables
from . import utils

_section_attrs = {0:['discipline'],
                  1:['originatingCenter', 'originatingSubCenter', 'masterTableInfo', 'localTableInfo',
                     'significanceOfReferenceTime', 'year', 'month', 'day', 'hour', 'minute', 'second',
                     'refDate', 'validDate', 'productionStatus', 'typeOfData'],
                  2:[],
                  3:['shapeOfEarth', 'earthRadius', 'earthMajorAxis', 'earthMinorAxis',
                     'resolutionAndComponentFlags', 'ny', 'nx', 'scanModeFlags'],
                  4:['parameterCategory', 'parameterNumber', 'fullName', 'units', 'shortName',
                     'typeOfGeneratingProcess', 'backgroundGeneratingProcessIdentifier', 'generatingProcess',
                     'unitOfTimeRange', 'leadTime', 'typeOfFirstFixedSurface', 'scaleFactorOfFirstFixedSurface',
                     'unitOfFirstFixedSurface', 'scaledValueOfFirstFixedSurface', 'valueOfFirstFixedSurface',
                     'typeOfSecondFixedSurface', 'scaleFactorOfSecondFixedSurface', 'unitOfSecondFixedSurface',
                     'scaledValueOfSecondFixedSurface', 'valueOfSecondFixedSurface'],
                  5:[],
                  6:[],
                  7:[],
                  8:[],}

def _get_template_class_attrs(items):
    attrs = []
    for i in items:
        if not i.startswith('_') and i != 'attrs':
            attrs.append(i)
    return attrs

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
    def __hash__(self):
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

# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 0 metadata.
# ----------------------------------------------------------------------------------------
class IndicatorSection:
    """
    """
    def __get__(self, obj, objtype=None):
        return obj.section0
    def __set__(self, obj, value):
        obj.section0 = value

class Discipline:
    """Discipline [From Table 0.0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table0-0.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.indicatorSection[2],table='0.0')
    def __set__(self, obj, value):
        obj.section0[2] = value


# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 1 metadata.
# ----------------------------------------------------------------------------------------
class IdentificationSection:
    """
    """
    def __get__(self, obj, objtype=None):
        return obj.section1
    def __set__(self, obj, value):
        obj.section1 = value

class OriginatingCenter:
    """Identification of originating/generating center
    [(See Table 0)](https://www.nco.ncep.noaa.gov/pmb/docs/on388/table0.html)
    """
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[0],table='originating_centers')
    def __set__(self, obj, value):
        obj.section1[0] = value

class OriginatingSubCenter:
    """Identification of originating/generating subcenter
    [(See Table C)](https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablec.html)
    """
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[1],table='originating_subcenters')
    def __set__(self, obj, value):
        obj.section1[1] = value

class MasterTableInfo:
    """GRIB master tables version number (currently 2)
    [(See Table 1.0)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-0.shtml)
    """
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[2],table='1.0')
    def __set__(self, obj, value):
        obj.section1[2] = value

class LocalTableInfo:
    """Version number of GRIB local tables used to augment Master Tables
    [(See Table 1.1)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-1.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[3],table='1.1')
    def __set__(self, obj, value):
        obj.section1[3] = value

class SignificanceOfReferenceTime:
    """Significance of reference time [(See Table 1.2)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-2.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[4],table='1.2')
    def __set__(self, obj, value):
        obj.section1[4] = value

class Year:
    """Year of reference time"""
    def __get__(self, obj, objtype=None):
        return obj.section1[5]
    def __set__(self, obj, value):
        obj.section1[5] = value

class Month:
    """Month of reference time"""
    def __get__(self, obj, objtype=None):
        return obj.section1[6]
    def __set__(self, obj, value):
        obj.section1[6] = value

class Day:
    """Day of reference time"""
    def __get__(self, obj, objtype=None):
        return obj.section1[7]
    def __set__(self, obj, value):
        obj.section1[7] = value

class Hour:
    """Hour of reference time"""
    def __get__(self, obj, objtype=None):
        return obj.section1[8]
    def __set__(self, obj, value):
        obj.section1[8] = value

class Minute:
    """Minute of reference time"""
    def __get__(self, obj, objtype=None):
        return obj.section1[9]
    def __set__(self, obj, value):
        obj.section1[9] = value

class Second:
    """Second of reference time"""
    def __get__(self, obj, objtype=None):
        return obj.section1[10]
    def __set__(self, obj, value):
        obj.section1[10] = value

class RefDate:
    """Reference date as a `datetime.datetime` object"""
    def __get__(self, obj, objtype=None):
        return datetime.datetime(*obj.section1[5:11])
    def __set__(self, obj, value):
        if isinstance(value,datetime.datetime):
            obj.section1[5] = value.year
            obj.section1[6] = value.month
            obj.section1[7] = value.day
            obj.section1[8] = value.hour
            obj.section1[9] = value.minute
            obj.section1[10] = value.second
        else:
            msg = 'Reference date must be a datetime.datetime object.'
            raise TypeError(msg)

class ProductionStatus:
    """Production Status of Processed data in the GRIB message
    [(See Table 1.3)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-3.shtml)
    """
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[11],table='1.3')
    def __set__(self, obj, value):
        obj.section1[11] = value

class TypeOfData:
    """Type of processed data in this GRIB message
    [(See Table 1.4)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-4.shtml)
    """
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[12],table='1.4')
    def __set__(self, obj, value):
        obj.section1[12] = value

# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 2 metadata.
# ----------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 3 metadata.
# ----------------------------------------------------------------------------------------
class GridDefinitionSection:
    def __get__(self, obj, objtype=None):
        return obj.section3[0:5]
    def __set__(self, obj, value):
        raise NotImplementedError

class GridDefinitionTemplateNumber:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section3[4],table='3.1')
    def __set__(self, obj, value):
        raise NotImplementedError

class GridDefinitionTemplate:
    """
    """
    def __get__(self, obj, objtype=None):
        return obj.section3[5:]
    def __set__(self, obj, value):
        raise NotImplementedError

class EarthParams:
    def __get__(self, obj, objtype=None):
        if obj.gridDefinitionSection[4] in {50,51,52,1200}:
            return None
        return tables.earth_params[str(obj.section3[5])]

class DxSign:
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,203,205,32768,32769} and \
        obj.section3[17] > obj.section3[20]:
            return -1.0
        return 1.0

class DySign:
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,203,205,32768,32769} and \
        obj.section3[16] > obj.section3[19]:
            return -1.0
        return 1.0

class LLScaleFactor:
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,203,205,32768,32769}:
            llscalefactor = float(obj.section3[14])
            if llscalefactor == 0:
                return 1
            return llscalefactor
        return 1

class LLDivisor:
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,203,205,32768,32769}:
            lldivisor = float(obj.section3[15])
            if lldivisor <= 0:
                return 1.e6
            return lldivisor
        return 1.e6

class XYDivisor:
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,203,205,32768,32769}:
            return obj._lldivisor
        return 1.e3

class ShapeOfEarth:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section3[5],table='3.2')
    def __set__(self, obj, value):
        obj.section3[5] = value

class EarthRadius:
    def __get__(self, obj, objtype=None):
        earthparams = obj._earthparams
        if earthparams['shape'] == 'spherical':
            if earthparams['radius'] is None:
                return obj.section3[7]/(10.**obj.section3[6])
            else:
                return earthparams['radius']
        if earthparams['shape'] == 'oblateSpheriod':
            if earthparams['radius'] is None and earthparams['major_axis'] is None and earthparams['minor_axis'] is None:
                return obj.section3[7]/(10.**obj.section3[6])
            else:
                return earthparams['radius']

class EarthMajorAxis:
    def __get__(self, obj, objtype=None):
        earthparams = obj._earthparams
        if earthparams['shape'] == 'spherical':
            return None
        if earthparams['shape'] == 'oblateSpheriod':
            if earthparams['radius'] is None and earthparams['major_axis'] is None and earthparams['minor_axis'] is None:
                return obj.section3[9]/(10.**obj.section3[8])
            else:
                return earthparams['major_axis']

class EarthMinorAxis:
    def __get__(self, obj, objtype=None):
        earthparams = obj._earthparams
        if earthparams['shape'] == 'spherical':
            return None
        if earthparams['shape'] == 'oblateSpheriod':
            if earthparams['radius'] is None and earthparams['major_axis'] is None and earthparams['minor_axis'] is None:
                return obj.section3[11]/(10.**section3[10])
            else:
                return earthparams['minor_axis']

class Nx:
    def __get__(self, obj, objtype=None):
        return obj.section3[12]
    def __set__(self, obj, value):
        pass

class Ny:
    def __get__(self, obj, objtype=None):
        return obj.section3[13]
    def __set__(self, obj, value):
        pass

class ScanModeFlags:
    _key = {0:18, 1:18, 10:15, 20:17, 30:17, 31:17, 40:18, 41:18, 90:16, 110:15, 203:18, 204:18, 205:18, 32768:18, 32769:18}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        if gdtn == 50:
            return [None, None, None, None]
        else:
            return utils.int2bin(obj.section3[self._key[gdtn]+5],output=list)[0:4]
    def __set__(self, obj, value):
        pass

class ResolutionAndComponentFlags:
    _key = {0:13, 1:13, 10:11, 20:11, 30:11, 31:11, 40:13, 41:13, 90:11, 110:11, 203:13, 204:13, 205:13, 32768:13, 32769:13}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        if gdtn == 50:
            return [None for i in range(8)]
        else:
            return utils.int2bin(obj.section3[self._key[gdtn]+5],output=list)
    def __set__(self, obj, value):
        pass

class LatitudeFirstGridpoint:
    _key = {0:11, 1:11, 10:9, 20:9, 30:9, 31:9, 40:11, 41:11, 110:9, 203:11, 204:11, 205:11, 32768:11, 32769:11}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeFirstGridpoint:
    _key = {0:12, 1:12, 10:10, 20:10, 30:10, 31:10, 40:12, 41:12, 110:10, 203:12, 204:12, 205:12, 32768:12, 32769:12}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LatitudeLastGridpoint:
    _key = {0:14, 1:14, 10:13, 40:14, 41:14, 203:14, 204:14, 205:14, 32768:14, 32769:14}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeLastGridpoint:
    _key = {0:15, 1:15, 10:14, 40:15, 41:15, 203:15, 204:15, 205:15, 32768:15, 32769:15}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class GridlengthXDirection:
    _key = {0:16, 1:16, 10:17, 20:14, 30:14, 31:14, 40:16, 41:16, 203:16, 204:16, 205:16, 32768:16, 32769:16}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return (obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._xydivisor)*obj._dxsign
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._xydivisor/obj._llscalefactor)

class GridlengthYDirection:
    _key = {0:17, 1:17, 10:18, 20:15, 30:15, 31:15, 40:17, 41:17, 203:17, 204:17, 205:17, 32768:17, 32769:17}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return (obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._xydivisor)*obj._dysign
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._xydivisor/obj._llscalefactor)

class LatitudeSouthernPole:
    _key = {1:19, 30:20, 31:20, 41:19}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeSouthernPole:
    _key = {1:20, 30:21, 31:21, 41:20}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class AnglePoleRotation:
    _key = {1:21, 41:21}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj.section3[self._key[gdtn]+5]
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value)

class LatitudeTrueScale:
    _key = {10:12, 20:12, 30:12, 31:12}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class GridOrientation:
    _key = {10:16, 20:13, 30:13, 31:13}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        if gdtn == 10 and (value < 0 or value > 90):
            raise ValueError("Grid orientation is limited to range of 0 to 90 degrees.")
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class ProjectionCenterFlag:
    _key = {20:16, 30:16, 31:16}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return utils.int2bin(obj.section3[self._key[gdtn]+5],output=list)[0]
    def __set__(self, obj, value):
        pass

class StandardLatitude1:
    _key = {30:18, 31:18}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class StandardLatitude2:
    _key = {30:19, 31:19}
    def __get__(self, obj, objtype=None):
        gdtn = obj.section3[4]
        return obj._llscalefactor*obj.section3[self._key[gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        gdtn = obj.section3[4]
        obj.section3[self._key[gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class SpectralFunctionParameters:
    def __get__(self, obj, objtype=None):
        return obj.section3[0:3]
    def __set__(self, obj, value):
        obj.section3[0:3] = value[0:3]

class ProjParameters:
    def __get__(self, obj, objtype=None):
        a = 1.0
        b = 1.0
        if obj.earthRadius is not None:
            a = obj.earthRadius
            b = obj.earthRadius
        else:
            if obj.earthMajorAxis is not None: a = obj.earthMajorAxis
            if obj.earthMajorAxis is not None: b = obj.earthMinorAxis
        gdtn = obj.section3[4]
        if gdtn == 0:
            return {'proj':'eqc','a':a,'b':b}
        if gdtn == 10:
            return {'proj':'merc','lat_ts':obj.latitudeTrueScale,
                    'lon_0':0.5*(obj.longitudeFirstGridpoint+obj.longitudeLastGridpoint),'a':a,'b':b}
        elif gdtn == 20:
            if obj.projectionCenterFlag == 0:
                lat0 = 90.0
            elif obj.projectionCenterFlag == 1:
                lat0 = -90.0
            return {'proj':'stere','lat_ts':obj.latitudeTrueScale,
                    'lat_0':lat0,'lon_0':obj.gridOrientation,'a':a,'b':b}
        elif gdtn == 30:
            return {'proj':'lcc','lat_1':obj.standardLatitude1,'lat_2':obj.standardLatitude2,
                    'lat_0':obj.latitudeTrueScale,'lon_0':obj.gridOrientation,'a':a,'b':b}
        elif gdtn == 31:
            return {'proj':'aea','lat_1':obj.standardLatitude1,'lat_2':obj.standardLatitude2,
                    'lat_0':obj.latitudeTrueScale,'lon_0':obj.gridOrientation,'a':a,'b':b}
        elif gdtn == 40:
            return {'proj':'eqc','a':a,'b':b}
    def __set__(self, obj, value):
        pass

@dataclass(init=False)
class GridDefinitionTemplate0():
    _len = 19
    _num = 0
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate1():
    _len = 22
    _num = 1
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
    anglePoleRotation: float = field(init=False, repr=True, default=AnglePoleRotation())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate10():
    _len = 19
    _num = 10
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    projParameters: dict = field(init=False, repr=True, default=ProjParameters())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate20():
    _len = 18
    _num = 20
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=True, default=ProjectionCenterFlag())
    projParameters: dict = field(init=False, repr=True, default=ProjParameters())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate30():
    _len = 22
    _num = 30
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=True, default=ProjectionCenterFlag())
    standardLatitude1: float = field(init=False, repr=True, default=StandardLatitude1())
    standardLatitude2: float = field(init=False, repr=True, default=StandardLatitude2())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
    projParameters: dict = field(init=False, repr=True, default=ProjParameters())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate31():
    _len = 22
    _num = 31
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=True, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=True, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=True, default=ProjectionCenterFlag())
    standardLatitude1: float = field(init=False, repr=True, default=StandardLatitude1())
    standardLatitude2: float = field(init=False, repr=True, default=StandardLatitude2())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate40():
    _len = 19
    _num = 40
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate41():
    _len = 22
    _num = 41
    latitudeFirstGridpoint: float = field(init=False, repr=True, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=True, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=True, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=True, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=True, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=True, default=GridlengthYDirection())
    latitudeSouthernPole: float = field(init=False, repr=True, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=True, default=LongitudeSouthernPole())
    anglePoleRotation: float = field(init=False, repr=True, default=AnglePoleRotation())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class GridDefinitionTemplate50():
    _len = 5
    _num = 50
    spectralFunctionParameters: list = field(init=False, repr=True, default=SpectralFunctionParameters())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

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
        return Grib2Metadata(obj.section4[1],table='4.0')
    def __set__(self, obj, value):
        pass

class ProductDefinitionTemplate:
    def __get__(self, obj, objtype=None):
        return obj.section4[2:]
    def __set__(self, obj, value):
        pass

class ParameterCategory:
    def __get__(self, obj, objtype=None):
        return obj.section4[2]
    def __set__(self, obj, value):
        obj.section4[2] = value

class ParameterNumber:
    def __get__(self, obj, objtype=None):
        return obj.section4[3]
    def __set__(self, obj, value):
        obj.section4[3] = value

class VarInfo:
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)
    def __set__(self, obj, value):
        raise NotImplementedError

class FullName:
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)[0]
    def __set__(self, obj, value):
        raise NotImplementedError

class Units:
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)[1]
    def __set__(self, obj, value):
        raise NotImplementedError

class ShortName:
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)[2]
    def __set__(self, obj, value):
        raise NotImplementedError

class TypeOfGeneratingProcess:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[4],table='4.3')
    def __set__(self, obj, value):
        obj.section4[4] = value

class BackgroundGeneratingProcessIdentifier:
    def __get__(self, obj, objtype=None):
        return obj.section4[5]
    def __set__(self, obj, value):
        obj.section4[5] = value

class GeneratingProcess:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[6],table='generating_process')
    def __set__(self, obj, value):
        obj.section4[6] = value

class UnitOfTimeRange:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[9],table='4.4')
    def __set__(self, obj, value):
        obj.section4[9] = value

class LeadTime:
    def __get__(self, obj, objtype=None):
        return utils.getleadtime(obj.section1,obj.section4[2],
                obj.section4[2:])
    def __set__(self, obj, value):
        raise NotImplementedError

class FixedSfc1Info:
    def __get__(self, obj, objtype=None):
        if obj.section4[11] == 255:
            return [None, None]
        return tables.get_value_from_table(obj.section4[11],'4.5')
    def __set__(self, obj, value):
        raise NotImplementedError

class FixedSfc2Info:
    def __get__(self, obj, objtype=None):
        if obj.section4[14] == 255:
            return [None, None]
        return tables.get_value_from_table(obj.section4[14],'4.5')
    def __set__(self, obj, value):
        raise NotImplementedError

class TypeOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[11],table='4.5')
    def __set__(self, obj, value):
        obj.section4[11] = value

class ScaleFactorOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj.section4[12]
    def __set__(self, obj, value):
        obj.section4[12] = value

class ScaledValueOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj.section4[13]
    def __set__(self, obj, value):
        obj.section4[13] = value

class UnitOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._fixedsfc1info[1]
    def __set__(self, obj, value):
        pass

class ValueOfFirstFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj.section4[13]/(10.**obj.section4[12])
    def __set__(self, obj, value):
        pass

class TypeOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[14],table='4.5')
    def __set__(self, obj, value):
        obj.section4[14] = value

class ScaleFactorOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj.section4[15]
    def __set__(self, obj, value):
        obj.section4[15] = value

class ScaledValueOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj.section4[16]
    def __set__(self, obj, value):
        obj.section4[16] = value

class UnitOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj._fixedsfc2info[1]
    def __set__(self, obj, value):
        pass

class ValueOfSecondFixedSurface:
    def __get__(self, obj, objtype=None):
        return obj.section4[16]/(10.**obj.section4[15])
    def __set__(self, obj, value):
        pass

class Level:
    def __get__(self, obj, objtype=None):
        return tables.get_wgrib2_level_string(*obj.section4[11:17])
    def __set__(self, obj, value):
        pass

class TypeOfEnsembleForecast:
    _key = {1:15, 11:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.6')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class PerturbationNumber:
    _key = {1:16, 11:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class NumberOfEnsembleForecasts:
    _key = {1:17, 2:16, 11:17, 12:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfDerivedForecast:
    _key = {2:15, 12:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.7')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ForecastProbabilityNumber:
    _key = {5:15, 9:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TotalNumberOfForecastProbabilities:
    _key = {5:16, 9:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfProbability:
    _key = {5:17, 9:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.9')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ScaleFactorOfThresholdLowerLimit:
    _key = {5:18, 9:18}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ScaledValueOfThresholdLowerLimit:
    _key = {5:19, 9:19}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ThresholdLowerLimit:
    def __get__(self, obj, objtype=None):
        if obj.section4[18] == -127 and \
           obj.section4[19] == 255:
            return 0.0
        else:
            return obj.section4[19]/(10.**obj.section4[18])
    def __set__(self, obj, value):
        pass

class ThresholdUpperLimit:
    def __get__(self, obj, objtype=None):
        if obj.section4[20] == -127 and \
           obj.section4[21] == 255:
            return 0.0
        else:
            return obj.section4[21]/(10.**obj.section4[20])
    def __set__(self, obj, value):
        pass

class Threshold:
    def __get__(self, obj, objtype=None):
        return utils.get_wgrib2_prob_string(*obj.section4[17:22])
    def __set__(self, obj, value):
        pass

class PercentileValue:
    _key = {6:15, 10:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class YearOfEndOfTimePeriod:
    _key = {8:15, 9:22, 10:16, 11:18, 12:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class MonthOfEndOfTimePeriod:
    _key = {8:16, 9:23, 10:17, 11:19, 12:18}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class DayOfEndOfTimePeriod:
    _key = {8:17, 9:24, 10:18, 11:20, 12:19}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class HourOfEndOfTimePeriod:
    _key = {8:18, 9:25, 10:19, 11:21, 12:20}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class MinuteOfEndOfTimePeriod:
    _key = {8:19, 9:26, 10:20, 11:22, 12:21}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class SecondOfEndOfTimePeriod:
    _key = {8:20, 9:27, 10:21, 11:23, 12:22}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class Duration:
    def __get__(self, obj, objtype=None):
        return utils.getduration(obj.section4[1],obj.section4[2:])
    def __set__(self, obj, value):
        pass

class ValidDate:
    _key = {8:slice(15,21), 9:slice(22,28), 10:slice(16,22), 11:slice(18,24), 12:slice(17,23)}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        try:
            s = slice(self._key[pdtn].start+2,self._key[pdtn].stop+2)
            return datetime.datetime(*obj.section4[s])
        except(KeyError):
            return obj.refDate + obj.leadTime
    def __set__(self, obj, value):
        pass

class NumberOfTimeRanges:
    _key = {8:21, 9:28, 11:24, 12:23}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class NumberOfMissingValues:
    _key = {8:22, 9:29, 11:25, 12:24}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class StatisticalProcess:
    _key = {8:23, 9:30, 11:26, 12:25, 15:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.10')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfTimeIncrementOfStatisticalProcess:
    _key = {8:24, 9:31, 11:27, 12:26}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.11')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class UnitOfTimeRangeOfStatisticalProcess:
    _key = {8:25, 9:32, 11:28, 12:27}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.4')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TimeRangeOfStatisticalProcess:
    _key = {8:26, 9:33, 11:29, 12:28}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class UnitOfTimeRangeOfSuccessiveFields:
    _key = {8:27, 9:34, 11:30, 12:29}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.4')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TimeIncrementOfSuccessiveFields:
    _key = {8:28, 9:35, 11:31, 12:30}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfStatisticalProcessing:
    _key = {15:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.15')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class NumberOfDataPointsForSpatialProcessing:
    _key = {15:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

@dataclass(init=False)
class ProductDefinitionTemplate0():
    _len = 15
    _num = 0
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate1():
    _len = 18
    _num = 1
    typeOfEnsembleForecast: Grib2Metadata = field(init=False, repr=True, default=TypeOfEnsembleForecast())
    perturbationNumber: int = field(init=False, repr=True, default=PerturbationNumber())
    numberOfEnsembleForecasts: int = field(init=False, repr=True, default=NumberOfEnsembleForecasts())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate2():
    _len = 17
    _num = 2
    typeOfDerivedForecast: Grib2Metadata = field(init=False, repr=True, default=TypeOfDerivedForecast())
    numberOfEnsembleForecasts: int = field(init=False, repr=True, default=NumberOfEnsembleForecasts())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate5():
    _len = 22
    _num = 5
    forecastProbabilityNumber: int = field(init=False, repr=True, default=ForecastProbabilityNumber())
    totalNumberOfForecastProbabilities: int = field(init=False, repr=True, default=TotalNumberOfForecastProbabilities())
    typeOfProbability: Grib2Metadata = field(init=False, repr=True, default=TypeOfProbability())
    thesholdLowerLimit: float = field(init=False, repr=True, default=ThresholdLowerLimit())
    thesholdUpperLimit: float = field(init=False, repr=True, default=ThresholdUpperLimit())
    threshold: str = field(init=False, repr=True, default=Threshold())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate6():
    _len = 16
    _num = 6
    percentileValue: int = field(init=False, repr=True, default=PercentileValue())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate8():
    _len = 29
    _num = 8
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
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate9():
    _len = 36
    _num = 9
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
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate10():
    _len = 30
    _num = 10
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
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate11():
    _len = 32
    _num = 11
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
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate12():
    _len = 31
    _num = 12
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
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class ProductDefinitionTemplate15():
    _len = 18
    _num = 15
    statisticalProcess: Grib2Metadata = field(init=False, repr=True, default=StatisticalProcess())
    typeOfStatisticalProcessing: Grib2Metadata = field(init=False, repr=True, default=TypeOfStatisticalProcessing())
    numberOfDataPointsForSpatialProcessing: int = field(init=False, repr=True, default=NumberOfDataPointsForSpatialProcessing())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

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
class NumberOfDataPoints:
    def __get__(self, obj, objtype=None):
        return obj.section5[0]
    def __set__(self, obj, value):
        pass

class DataRepresentationTemplateNumber:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[1],table='5.0')
    def __set__(self, obj, value):
        pass

class DataRepresentationTemplate:
    def __get__(self, obj, objtype=None):
        return obj.section5[2:]
    def __set__(self, obj, value):
        raise NotImplementedError

class RefValue:
    def __get__(self, obj, objtype=None):
        return utils.ieee_int_to_float(obj.section5[0+2])
    def __set__(self, obj, value):
        pass

class BinScaleFactor:
    def __get__(self, obj, objtype=None):
        return obj.section5[1+2]
    def __set__(self, obj, value):
        obj.section5[1+2] = value

class DecScaleFactor:
    def __get__(self, obj, objtype=None):
        return obj.section5[2+2]
    def __set__(self, obj, value):
        obj.section5[2+2] = value

class NBitsPacking:
    def __get__(self, obj, objtype=None):
        return obj.section5[3+2]
    def __set__(self, obj, value):
        obj.section5[3+2] = value

class TypeOfValues:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[4+2],table='5.1')
    def __set__(self, obj, value):
        obj.section5[4+2] = value

class GroupSplitMethod:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[5+2],table='5.4')
    def __set__(self, obj, value):
        obj.section5[5+2] = value

class TypeOfMissingValue:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[6+2],table='5.5')
    def __set__(self, obj, value):
        obj.section5[5+2] = value

class PriMissingValue:
    def __get__(self, obj, objtype=None):
        if obj.typeOfValues == 0:
            return utils.ieee_int_to_float(obj.section5[7+2]) if obj.section5[6+2] in {1,2} else None
        elif obj.typeOfValues == 1:
            return obj.section5[7+2] if obj.section5[6+2] in [1,2] else None
    def __set__(self, obj, value):
        if obj.typeOfValues == 0:
            obj.section5[7+2] = utils.ieee_float_to_int(value)
        elif self.typeOfValues == 1:
            obj.section5[7+2] = int(value)
        obj.section5[6+2] = 1

class SecMissingValue:
    def __get__(self, obj, objtype=None):
        if obj.typeOfValues == 0:
            return utils.ieee_int_to_float(obj.section5[8+2]) if obj.section5[6+2] in {1,2} else None
        elif obj.typeOfValues == 1:
            return obj.section5[8+2] if obj.section5[6+2] in {1,2} else None
    def __set__(self, obj, value):
        if obj.typeOfValues == 0:
            obj.section5[8+2] = utils.ieee_float_to_int(value)
        elif self.typeOfValues == 1:
            obj.section5[8+2] = int(value)
        obj.section5[6+2] = 2

class NGroups:
    def __get__(self, obj, objtype=None):
        return obj.section5[9+2]
    def __set__(self, obj, value):
        pass

class RefGroupWidth:
    def __get__(self, obj, objtype=None):
        return obj.section5[10+2]
    def __set__(self, obj, value):
        pass

class NBitsGroupWidth:
    def __get__(self, obj, objtype=None):
        return obj.section5[11+2]
    def __set__(self, obj, value):
        pass

class RefGroupLength:
    def __get__(self, obj, objtype=None):
        return obj.section5[12+2]
    def __set__(self, obj, value):
        pass

class GroupLengthIncrement:
    def __get__(self, obj, objtype=None):
        return obj.section5[13+2]
    def __set__(self, obj, value):
        pass

class LengthOfLastGroup:
    def __get__(self, obj, objtype=None):
        return obj.section5[14+2]
    def __set__(self, obj, value):
        pass

class NBitsScaledGroupLength:
    def __get__(self, obj, objtype=None):
        return obj.section5[15+2]
    def __set__(self, obj, value):
        pass

class SpatialDifferenceOrder:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[16+2],table='5.6')
    def __set__(self, obj, value):
        obj.section5[16+2] = value

class NBytesSpatialDifference:
    def __get__(self, obj, objtype=None):
        return obj.section5[17+2]
    def __set__(self, obj, value):
        pass

class Precision:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[0+2],table='5.7')
    def __set__(self, obj, value):
        obj.section5[0+2] = value

class TypeOfCompression:
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[5+2],table='5.40')
    def __set__(self, obj, value):
        obj.section5[5+2] = value

class TargetCompressionRatio:
    def __get__(self, obj, objtype=None):
        return obj.section5[6+2]
    def __set__(self, obj, value):
        pass

class RealOfCoefficient:
    def __get__(self, obj, objtype=None):
        return utils.ieee_int_to_float(obj.section5[4+2])
    def __set__(self, obj, value):
        obj.section5[4+2] = utils.ieee_float_to_int(float(value))

@dataclass(init=False)
class DataRepresentationTemplate0():
    _len = 5
    _num = 0
    _packingScheme = 'simple'
    refValue: float = field(init=False, repr=True, default=RefValue())
    binScaleFactor: int = field(init=False, repr=True, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=True, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=True, default=NBitsPacking())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class DataRepresentationTemplate2():
    _len = 16
    _num = 2
    _packingScheme = 'complex'
    refValue: float = field(init=False, repr=True, default=RefValue())
    binScaleFactor: int = field(init=False, repr=True, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=True, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=True, default=NBitsPacking())
    typeOfMissingValue: Grib2Metadata = field(init=False, repr=True, default=TypeOfMissingValue())
    priMissingValue: [float, int] = field(init=False, repr=True, default=PriMissingValue())
    secMissingValue: [float, int] = field(init=False, repr=True, default=SecMissingValue())
    nGroups: int = field(init=False, repr=True, default=NGroups())
    refGroupWidth: int = field(init=False, repr=True, default=RefGroupWidth())
    nBitsGroupWidth: int = field(init=False, repr=True, default=NBitsGroupWidth())
    refGroupLength: int = field(init=False, repr=True, default=RefGroupLength())
    groupLengthIncrement: int = field(init=False, repr=True, default=GroupLengthIncrement())
    lengthOfLastGroup: int = field(init=False, repr=True, default=LengthOfLastGroup())
    nBitsScaledGroupLength: int = field(init=False, repr=True, default=NBitsScaledGroupLength())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class DataRepresentationTemplate3():
    _len = 18
    _num = 3
    _packingScheme = 'complex-spdiff'
    refValue: float = field(init=False, repr=True, default=RefValue())
    binScaleFactor: int = field(init=False, repr=True, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=True, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=True, default=NBitsPacking())
    typeOfMissingValue: Grib2Metadata = field(init=False, repr=True, default=TypeOfMissingValue())
    priMissingValue: [float, int] = field(init=False, repr=True, default=PriMissingValue())
    secMissingValue: [float, int] = field(init=False, repr=True, default=SecMissingValue())
    nGroups: int = field(init=False, repr=True, default=NGroups())
    refGroupWidth: int = field(init=False, repr=True, default=RefGroupWidth())
    nBitsGroupWidth: int = field(init=False, repr=True, default=NBitsGroupWidth())
    refGroupLength: int = field(init=False, repr=True, default=RefGroupLength())
    groupLengthIncrement: int = field(init=False, repr=True, default=GroupLengthIncrement())
    lengthOfLastGroup: int = field(init=False, repr=True, default=LengthOfLastGroup())
    nBitsScaledGroupLength: int = field(init=False, repr=True, default=NBitsScaledGroupLength())
    spatialDifferenceOrder: Grib2Metadata = field(init=False, repr=True, default=SpatialDifferenceOrder())
    nBytesSpatialDifference: int = field(init=False, repr=True, default=NBytesSpatialDifference())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class DataRepresentationTemplate4():
    _len = 1
    _num = 4
    _packingScheme = 'ieee-float'
    precision: Grib2Metadata = field(init=False, repr=True, default=Precision())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class DataRepresentationTemplate40():
    _len = 7
    _num = 40
    _packingScheme = 'jpeg'
    refValue: float = field(init=False, repr=True, default=RefValue())
    binScaleFactor: int = field(init=False, repr=True, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=True, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=True, default=NBitsPacking())
    typeOfCompression: Grib2Metadata = field(init=False, repr=True, default=TypeOfCompression())
    targetCompressionRatio: int = field(init=False, repr=True, default=TargetCompressionRatio())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class DataRepresentationTemplate41():
    _len = 5
    _num = 41
    _packingScheme = 'png'
    refValue: float = field(init=False, repr=True, default=RefValue())
    binScaleFactor: int = field(init=False, repr=True, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=True, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=True, default=NBitsPacking())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

@dataclass(init=False)
class DataRepresentationTemplate50():
    _len = 5
    _num = 0
    _packingScheme = 'spectral-simple'
    refValue: float = field(init=False, repr=True, default=RefValue())
    binScaleFactor: int = field(init=False, repr=True, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=True, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=True, default=NBitsPacking())
    realOfCoefficient: float = field(init=False, repr=True, default=RealOfCoefficient())
    @classmethod
    @property
    def attrs(cls):
        return _get_template_class_attrs(cls.__dict__.keys())

_drt_by_drtn = {
    0: DataRepresentationTemplate0,
    2: DataRepresentationTemplate2,
    3: DataRepresentationTemplate3,
    4: DataRepresentationTemplate4,
    40: DataRepresentationTemplate40,
    41: DataRepresentationTemplate41,
    50: DataRepresentationTemplate50,
    }

def drt_class_by_drtn(drtn):
    return _drt_by_drtn[drtn]
