"""GRIB2 section templates classes and metadata descriptor classes."""
from dataclasses import dataclass, field
from collections import defaultdict
import datetime
from typing import Union

from numpy import timedelta64, datetime64

from . import tables
from . import utils

# This dict is used by grib2io.Grib2Message.attrs_by_section() method
# to get attr names that defined in the Grib2Message base class.
_section_attrs = {0:['discipline'],
                  1:['originatingCenter', 'originatingSubCenter', 'masterTableInfo', 'localTableInfo',
                     'significanceOfReferenceTime', 'year', 'month', 'day', 'hour', 'minute', 'second',
                     'refDate', 'productionStatus', 'typeOfData'],
                  2:[],
                  3:['sourceOfGridDefinition', 'numberOfDataPoints', 'interpretationOfListOfNumbers',
                     'gridDefinitionTemplateNumber', 'shapeOfEarth', 'earthRadius', 'earthMajorAxis',
                     'earthMinorAxis', 'resolutionAndComponentFlags', 'ny', 'nx', 'scanModeFlags'],
                  4:[],
                  5:['dataRepresentationTemplateNumber','numberOfPackedValues','typeOfValues'],
                  6:['bitMapFlag'],
                  7:[],
                  8:[],}


def _calculate_scale_factor(value: float):
    """
    Calculate the scale factor for a given value.

    Parameters
    ----------
    value : float
        Value for which to calculate the scale factor.

    Returns
    -------
    int
        Scale factor for the value.
    """
    return len(f"{value}".split(".")[1].rstrip("0"))


class Grib2Metadata:
    """
    Class to hold GRIB2 metadata.

    Stores both numeric code value as stored in GRIB2 and its plain language
    definition.

    Attributes
    ----------
    value : int
        GRIB2 metadata integer code value.
    table : str, optional
        GRIB2 table to lookup the `value`. Default is None.
    definition : str
        Plain language description of numeric metadata.
    """
    __slots__ = ('value','table')
    def __init__(self, value, table=None):
        self.value = value
        self.table = table
    def __call__(self):
        return self.value
    def __hash__(self):
        # AS- added hash() to self.value as pandas was raising error about some
        # non integer returns from hash method
        return hash(self.value)
    def __repr__(self):
        return f"{self.__class__.__name__}({self.value}, table = '{self.table}')"
    def __str__(self):
        return f'{self.value} - {self.definition}'
    def __eq__(self,other):
        return self.value == other or self.definition[0] == other
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
    def __hash__(self):
        return hash(self.value)
    def __index__(self):
        return int(self.value)
    @property
    def definition(self):
        return tables.get_value_from_table(self.value,self.table)
    def show_table(self):
        """Provide the table related to this metadata."""
        return tables.get_table(self.table)

# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 0 metadata.
# ----------------------------------------------------------------------------------------
class IndicatorSection:
    """
    [GRIB2 Indicator Section (0)](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_sect0.shtml)
    """
    def __get__(self, obj, objtype=None):
        return obj.section0
    def __set__(self, obj, value):
        obj.section0 = value

class Discipline:
    """[Discipline](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table0-0.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.indicatorSection[2],table='0.0')
    def __set__(self, obj, value):
        obj.section0[2] = value


# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 1 metadata.
# ----------------------------------------------------------------------------------------
class IdentificationSection:
    """
    GRIB2 Section 1, [Identification Section](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_sect1.shtml)
    """
    def __get__(self, obj, objtype=None):
        return obj.section1
    def __set__(self, obj, value):
        obj.section1 = value

class OriginatingCenter:
    """[Originating Center](https://www.nco.ncep.noaa.gov/pmb/docs/on388/table0.html)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[0],table='originating_centers')
    def __set__(self, obj, value):
        obj.section1[0] = value

class OriginatingSubCenter:
    """[Originating SubCenter](https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablec.html)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[1],table='originating_subcenters')
    def __set__(self, obj, value):
        obj.section1[1] = value

class MasterTableInfo:
    """[GRIB2 Master Table Version](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-0.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[2],table='1.0')
    def __set__(self, obj, value):
        obj.section1[2] = value

class LocalTableInfo:
    """[GRIB2 Local Tables Version Number](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-1.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[3],table='1.1')
    def __set__(self, obj, value):
        obj.section1[3] = value

class SignificanceOfReferenceTime:
    """[Significance of Reference Time](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-2.shtml)"""
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
    """Reference Date. NOTE: This is a `datetime.datetime` object."""
    def __get__(self, obj, objtype=None):
        return datetime.datetime(*obj.section1[5:11])
    def __set__(self, obj, value):
        if isinstance(value, datetime64):
            timestamp = (value - datetime64("1970-01-01T00:00:00")) / timedelta64(
                1, "s"
            )
            value = datetime.datetime.utcfromtimestamp(timestamp)
        if isinstance(value, datetime.datetime):
            obj.section1[5] = value.year
            obj.section1[6] = value.month
            obj.section1[7] = value.day
            obj.section1[8] = value.hour
            obj.section1[9] = value.minute
            obj.section1[10] = value.second
        else:
            msg = "Reference date must be a datetime.datetime or np.datetime64 object."
            raise TypeError(msg)

class ProductionStatus:
    """[Production Status of Processed Data](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-3.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section1[11],table='1.3')
    def __set__(self, obj, value):
        obj.section1[11] = value

class TypeOfData:
    """[Type of Processed Data in this GRIB message](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table1-4.shtml)"""
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
    """
    GRIB2 Section 3, [Grid Definition Section](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_sect3.shtml)
    """
    def __get__(self, obj, objtype=None):
        return obj.section3[0:5]
    def __set__(self, obj, value):
        raise RuntimeError

class SourceOfGridDefinition:
    """[Source of Grid Definition](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-0.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section3[0],table='3.0')
    def __set__(self, obj, value):
        raise RuntimeError

class NumberOfDataPoints:
    """Number of Data Points"""
    def __get__(self, obj, objtype=None):
        return obj.section3[1]
    def __set__(self, obj, value):
        raise RuntimeError

class InterpretationOfListOfNumbers:
    """Interpretation of List of Numbers"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section3[3],table='3.11')
    def __set__(self, obj, value):
        raise RuntimeError

class GridDefinitionTemplateNumber:
    """[Grid Definition Template Number](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-1.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section3[4],table='3.1')
    def __set__(self, obj, value):
        raise RuntimeError

class GridDefinitionTemplate:
    """Grid definition template"""
    def __get__(self, obj, objtype=None):
        return obj.section3[5:]
    def __set__(self, obj, value):
        raise RuntimeError

class EarthParams:
    """Metadata about the shape of the Earth"""
    def __get__(self, obj, objtype=None):
        if obj.section3[5] in {50,51,52,1200}:
            return None
        return tables.get_table('earth_params')[str(obj.section3[5])]
    def __set__(self, obj, value):
        raise RuntimeError

class DxSign:
    """Sign of Grid Length in X-Direction"""
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,203,205,32768,32769} and \
        obj.section3[17] > obj.section3[20]:
            return -1.0
        return 1.0
    def __set__(self, obj, value):
        raise RuntimeError

class DySign:
    """Sign of Grid Length in Y-Direction"""
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,203,205,32768,32769} and \
        obj.section3[16] > obj.section3[19]:
            return -1.0
        return 1.0
    def __set__(self, obj, value):
        raise RuntimeError

class LLScaleFactor:
    """Scale Factor for Lats/Lons"""
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,40,41,203,205,32768,32769}:
            llscalefactor = float(obj.section3[14])
            if llscalefactor == 0:
                return 1
            return llscalefactor
        return 1
    def __set__(self, obj, value):
        raise RuntimeError

class LLDivisor:
    """Divisor Value for scaling Lats/Lons"""
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,40,41,203,205,32768,32769}:
            lldivisor = float(obj.section3[15])
            if lldivisor <= 0:
                return 1.e6
            return lldivisor
        return 1.e6
    def __set__(self, obj, value):
        raise RuntimeError

class XYDivisor:
    """Divisor Value for scaling grid lengths"""
    def __get__(self, obj, objtype=None):
        if obj.section3[4] in {0,1,40,41,203,205,32768,32769}:
            return obj._lldivisor
        return 1.e3
    def __set__(self, obj, value):
        raise RuntimeError

class ShapeOfEarth:
    """[Shape of the Reference System](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-2.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section3[5],table='3.2')
    def __set__(self, obj, value):
        obj.section3[5] = value

class EarthShape:
    """Description of the shape of the Earth"""
    def __get__(self, obj, objtype=None):
        return obj._earthparams['shape']
    def __set__(self, obj, value):
        raise RuntimeError

class EarthRadius:
    """Radius of the Earth (Assumes "spherical")"""
    def __get__(self, obj, objtype=None):
        ep = obj._earthparams
        if ep['shape'] == 'spherical':
            if ep['radius'] is None:
                return obj.section3[7]/(10.**obj.section3[6])
            else:
                return ep['radius']
        elif ep['shape'] in {'ellipsoid','oblateSpheriod'}:
            return None
    def __set__(self, obj, value):
        raise RuntimeError

class EarthMajorAxis:
    """Major Axis of the Earth (Assumes "oblate spheroid" or "ellipsoid")"""
    def __get__(self, obj, objtype=None):
        ep = obj._earthparams
        if ep['shape'] == 'spherical':
            return None
        elif ep['shape'] in {'ellipsoid','oblateSpheriod'}:
            if ep['major_axis'] is None and ep['minor_axis'] is None:
                return obj.section3[9]/(10.**obj.section3[8])
            else:
                return ep['major_axis']
    def __set__(self, obj, value):
        raise RuntimeError

class EarthMinorAxis:
    """Minor Axis of the Earth (Assumes "oblate spheroid" or "ellipsoid")"""
    def __get__(self, obj, objtype=None):
        ep = obj._earthparams
        if ep['shape'] == 'spherical':
            return None
        if ep['shape'] in {'ellipsoid','oblateSpheriod'}:
            if ep['major_axis'] is None and ep['minor_axis'] is None:
                return obj.section3[11]/(10.**section3[10])
            else:
                return ep['minor_axis']
    def __set__(self, obj, value):
        raise RuntimeError

class Nx:
    """Number of grid points in the X-direction (generally East-West)"""
    def __get__(self, obj, objtype=None):
        return obj.section3[12]
    def __set__(self, obj, value):
        obj.section3[12] = value
        obj.section3[1] = value * obj.section3[13]

class Ny:
    """Number of grid points in the Y-direction (generally North-South)"""
    def __get__(self, obj, objtype=None):
        return obj.section3[13]
    def __set__(self, obj, value):
        obj.section3[13] = value
        obj.section3[1] = value * obj.section3[12]

class ScanModeFlags:
    """[Scanning Mode](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-4.shtml)"""
    _key = {0:18, 1:18, 10:15, 20:17, 30:17, 31:17, 40:18, 41:18, 90:16, 110:15, 203:18, 204:18, 205:18, 32768:18, 32769:18}
    def __get__(self, obj, objtype=None):
        if obj.gdtn == 50:
            return [None, None, None, None]
        else:
            return utils.int2bin(obj.section3[self._key[obj.gdtn]+5],output=list)[0:8]
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = value

class ResolutionAndComponentFlags:
    """[Resolution and Component Flags](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-3.shtml)"""
    _key = {0:13, 1:13, 10:11, 20:11, 30:11, 31:11, 40:13, 41:13, 90:11, 110:11, 203:13, 204:13, 205:13, 32768:13, 32769:13}
    def __get__(self, obj, objtype=None):
        if obj.gdtn == 50:
            return [None for i in range(8)]
        else:
            return utils.int2bin(obj.section3[self._key[obj.gdtn]+5],output=list)
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = value

class LatitudeFirstGridpoint:
    """Latitude of first gridpoint"""
    _key = {0:11, 1:11, 10:9, 20:9, 30:9, 31:9, 40:11, 41:11, 110:9, 203:11, 204:11, 205:11, 32768:11, 32769:11}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeFirstGridpoint:
    """Longitude of first gridpoint"""
    _key = {0:12, 1:12, 10:10, 20:10, 30:10, 31:10, 40:12, 41:12, 110:10, 203:12, 204:12, 205:12, 32768:12, 32769:12}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LatitudeLastGridpoint:
    """Latitude of last gridpoint"""
    _key = {0:14, 1:14, 10:13, 40:14, 41:14, 203:14, 204:14, 205:14, 32768:14, 32769:19}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeLastGridpoint:
    """Longitude of last gridpoint"""
    _key = {0:15, 1:15, 10:14, 40:15, 41:15, 203:15, 204:15, 205:15, 32768:15, 32769:20}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LatitudeCenterGridpoint:
    """Latitude of center gridpoint"""
    _key = {32768:14, 32769:14}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeCenterGridpoint:
    """Longitude of center gridpoint"""
    _key = {32768:15, 32769:15}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class GridlengthXDirection:
    """Grid lenth in the X-Direction"""
    _key = {0:16, 1:16, 10:17, 20:14, 30:14, 31:14, 40:16, 41:16, 203:16, 204:16, 205:16, 32768:16, 32769:16}
    def __get__(self, obj, objtype=None):
        return (obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._xydivisor)*obj._dxsign
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._xydivisor/obj._llscalefactor)

class GridlengthYDirection:
    """Grid lenth in the Y-Direction"""
    _key = {0:17, 1:17, 10:18, 20:15, 30:15, 31:15, 203:17, 204:17, 205:17, 32768:17, 32769:17}
    def __get__(self, obj, objtype=None):
        if obj.gdtn in {40, 41}:
            return obj.gridlengthXDirection
        else:
            return (obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._xydivisor)*obj._dysign
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._xydivisor/obj._llscalefactor)

class NumberOfParallels:
    """Number of parallels between a pole and the equator"""
    _key = {40:17, 41:17}
    def __get__(self, obj, objtype=None):
        return obj.section3[self._key[obj.gdtn]+5]
    def __set__(self, obj, value):
        raise RuntimeError

class LatitudeSouthernPole:
    """Latitude of the Southern Pole for a Rotated Lat/Lon Grid"""
    _key = {1:19, 30:20, 31:20, 41:19}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class LongitudeSouthernPole:
    """Longitude of the Southern Pole for a Rotated Lat/Lon Grid"""
    _key = {1:20, 30:21, 31:21, 41:20}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class AnglePoleRotation:
    """Angle of Pole Rotation for a Rotated Lat/Lon Grid"""
    _key = {1:21, 41:21}
    def __get__(self, obj, objtype=None):
        return obj.section3[self._key[obj.gdtn]+5]
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value)

class LatitudeTrueScale:
    """Latitude at which grid lengths are specified"""
    _key = {10:12, 20:12, 30:12, 31:12}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class GridOrientation:
    """Longitude at which the grid is oriented"""
    _key = {10:16, 20:13, 30:13, 31:13}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        if obj.gdtn == 10 and (value < 0 or value > 90):
            raise ValueError("Grid orientation is limited to range of 0 to 90 degrees.")
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class ProjectionCenterFlag:
    """[Projection Center](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table3-5.shtml)"""
    _key = {20:16, 30:16, 31:16}
    def __get__(self, obj, objtype=None):
        return utils.int2bin(obj.section3[self._key[obj.gdtn]+5],output=list)[0]
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = value

class StandardLatitude1:
    """First Standard Latitude (from the pole at which the secant cone cuts the sphere)"""
    _key = {30:18, 31:18}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class StandardLatitude2:
    """Second Standard Latitude (from the pole at which the secant cone cuts the sphere)"""
    _key = {30:19, 31:19}
    def __get__(self, obj, objtype=None):
        return obj._llscalefactor*obj.section3[self._key[obj.gdtn]+5]/obj._lldivisor
    def __set__(self, obj, value):
        obj.section3[self._key[obj.gdtn]+5] = int(value*obj._lldivisor/obj._llscalefactor)

class SpectralFunctionParameters:
    """Spectral Function Parameters"""
    def __get__(self, obj, objtype=None):
        return obj.section3[0:3]
    def __set__(self, obj, value):
        obj.section3[0:3] = value[0:3]

class ProjParameters:
    """PROJ Parameters to define the reference system"""
    def __get__(self, obj, objtype=None):
        projparams = {}
        projparams['a'] = 1.0
        projparams['b'] = 1.0
        if obj.earthRadius is not None:
            projparams['a'] = obj.earthRadius
            projparams['b'] = obj.earthRadius
        else:
            if obj.earthMajorAxis is not None: projparams['a'] = obj.earthMajorAxis
            if obj.earthMajorAxis is not None: projparams['b'] = obj.earthMinorAxis
        if obj.gdtn == 0:
            projparams['proj'] = 'longlat'
        elif obj.gdtn == 1:
            projparams['o_proj'] = 'longlat'
            projparams['proj'] = 'ob_tran'
            projparams['o_lat_p'] = -1.0*obj.latitudeSouthernPole
            projparams['o_lon_p'] = obj.anglePoleRotation
            projparams['lon_0'] = obj.longitudeSouthernPole
        elif obj.gdtn == 10:
            projparams['proj'] = 'merc'
            projparams['lat_ts'] = obj.latitudeTrueScale
            projparams['lon_0'] = 0.5*(obj.longitudeFirstGridpoint+obj.longitudeLastGridpoint)
        elif obj.gdtn == 20:
            if obj.projectionCenterFlag == 0:
                lat0 = 90.0
            elif obj.projectionCenterFlag == 1:
                lat0 = -90.0
            projparams['proj'] = 'stere'
            projparams['lat_ts'] = obj.latitudeTrueScale
            projparams['lat_0'] = lat0
            projparams['lon_0'] = obj.gridOrientation
        elif obj.gdtn == 30:
            projparams['proj'] = 'lcc'
            projparams['lat_1'] = obj.standardLatitude1
            projparams['lat_2'] = obj.standardLatitude2
            projparams['lat_0'] = obj.latitudeTrueScale
            projparams['lon_0'] = obj.gridOrientation
        elif obj.gdtn == 31:
            projparams['proj'] = 'aea'
            projparams['lat_1'] = obj.standardLatitude1
            projparams['lat_2'] = obj.standardLatitude2
            projparams['lat_0'] = obj.latitudeTrueScale
            projparams['lon_0'] = obj.gridOrientation
        elif obj.gdtn == 40:
            projparams['proj'] = 'eqc'
        elif obj.gdtn == 32769:
            projparams['proj'] = 'aeqd'
            projparams['lon_0'] = obj.longitudeCenterGridpoint
            projparams['lat_0'] = obj.latitudeCenterGridpoint
        return projparams
    def __set__(self, obj, value):
        raise RuntimeError

@dataclass(init=False)
class GridDefinitionTemplate0:
    """[Grid Definition Template 0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-0.shtml)"""
    _len = 19
    _num = 0
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=False, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=False, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate1:
    """[Grid Definition Template 1](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-1.shtml)"""
    _len = 22
    _num = 1
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=False, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=False, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    latitudeSouthernPole: float = field(init=False, repr=False, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=False, default=LongitudeSouthernPole())
    anglePoleRotation: float = field(init=False, repr=False, default=AnglePoleRotation())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate10:
    """[Grid Definition Template 10](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-10.shtml)"""
    _len = 19
    _num = 10
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=False, default=LatitudeTrueScale())
    latitudeLastGridpoint: float = field(init=False, repr=False, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=False, default=LongitudeLastGridpoint())
    gridOrientation: float = field(init=False, repr=False, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    projParameters: dict = field(init=False, repr=False, default=ProjParameters())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate20:
    """[Grid Definition Template 20](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-20.shtml)"""
    _len = 18
    _num = 20
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=False, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=False, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=False, default=ProjectionCenterFlag())
    projParameters: dict = field(init=False, repr=False, default=ProjParameters())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate30:
    """[Grid Definition Template 30](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-30.shtml)"""
    _len = 22
    _num = 30
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=False, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=False, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=False, default=ProjectionCenterFlag())
    standardLatitude1: float = field(init=False, repr=False, default=StandardLatitude1())
    standardLatitude2: float = field(init=False, repr=False, default=StandardLatitude2())
    latitudeSouthernPole: float = field(init=False, repr=False, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=False, default=LongitudeSouthernPole())
    projParameters: dict = field(init=False, repr=False, default=ProjParameters())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate31:
    """[Grid Definition Template 31](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-31.shtml)"""
    _len = 22
    _num = 31
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeTrueScale: float = field(init=False, repr=False, default=LatitudeTrueScale())
    gridOrientation: float = field(init=False, repr=False, default=GridOrientation())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    projectionCenterFlag: list = field(init=False, repr=False, default=ProjectionCenterFlag())
    standardLatitude1: float = field(init=False, repr=False, default=StandardLatitude1())
    standardLatitude2: float = field(init=False, repr=False, default=StandardLatitude2())
    latitudeSouthernPole: float = field(init=False, repr=False, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=False, default=LongitudeSouthernPole())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate40:
    """[Grid Definition Template 40](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-40.shtml)"""
    _len = 19
    _num = 40
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=False, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=False, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    numberOfParallels: int = field(init=False, repr=False, default=NumberOfParallels())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate41:
    """[Grid Definition Template 41](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-41.shtml)"""
    _len = 22
    _num = 41
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeLastGridpoint: float = field(init=False, repr=False, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=False, default=LongitudeLastGridpoint())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    numberOfParallels: int = field(init=False, repr=False, default=NumberOfParallels())
    latitudeSouthernPole: float = field(init=False, repr=False, default=LatitudeSouthernPole())
    longitudeSouthernPole: float = field(init=False, repr=False, default=LongitudeSouthernPole())
    anglePoleRotation: float = field(init=False, repr=False, default=AnglePoleRotation())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate50:
    """[Grid Definition Template 50](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-50.shtml)"""
    _len = 5
    _num = 50
    spectralFunctionParameters: list = field(init=False, repr=False, default=SpectralFunctionParameters())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate32768:
    """[Grid Definition Template 32768](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-32768.shtml)"""
    _len = 19
    _num = 32768
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeCenterGridpoint: float = field(init=False, repr=False, default=LatitudeCenterGridpoint())
    longitudeCenterGridpoint: float = field(init=False, repr=False, default=LongitudeCenterGridpoint())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class GridDefinitionTemplate32769:
    """[Grid Definition Template 32769](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp3-32769.shtml)"""
    _len = 19
    _num = 32769
    latitudeFirstGridpoint: float = field(init=False, repr=False, default=LatitudeFirstGridpoint())
    longitudeFirstGridpoint: float = field(init=False, repr=False, default=LongitudeFirstGridpoint())
    latitudeCenterGridpoint: float = field(init=False, repr=False, default=LatitudeCenterGridpoint())
    longitudeCenterGridpoint: float = field(init=False, repr=False, default=LongitudeCenterGridpoint())
    gridlengthXDirection: float = field(init=False, repr=False, default=GridlengthXDirection())
    gridlengthYDirection: float = field(init=False, repr=False, default=GridlengthYDirection())
    latitudeLastGridpoint: float = field(init=False, repr=False, default=LatitudeLastGridpoint())
    longitudeLastGridpoint: float = field(init=False, repr=False, default=LongitudeLastGridpoint())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

_gdt_by_gdtn = {0: GridDefinitionTemplate0,
    1: GridDefinitionTemplate1,
    10: GridDefinitionTemplate10,
    20: GridDefinitionTemplate20,
    30: GridDefinitionTemplate30,
    31: GridDefinitionTemplate31,
    40: GridDefinitionTemplate40,
    41: GridDefinitionTemplate41,
    50: GridDefinitionTemplate50,
    32768: GridDefinitionTemplate32768,
    32769: GridDefinitionTemplate32769,
    }

def gdt_class_by_gdtn(gdtn: int):
    """
    Provides a Grid Definition Template class via the template number

    Parameters
    ----------
    gdtn
        Grid definition template number.

    Returns
    -------
    gdt_class_by_gdtn
        Grid definition template class object (not an instance).
    """
    return _gdt_by_gdtn[gdtn]

# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 4 metadata.
# ----------------------------------------------------------------------------------------
class ProductDefinitionTemplateNumber:
    """[Product Definition Template Number](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-0.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[1],table='4.0')
    def __set__(self, obj, value):
        raise RuntimeError

#  since PDT begins at position 2 of section4, code written with +2 for added readability with grib2 documentation
class ProductDefinitionTemplate:
    """Product Definition Template"""
    def __get__(self, obj, objtype=None):
        return obj.section4[2:]
    def __set__(self, obj, value):
        raise RuntimeError

class ParameterCategory:
    """[Parameter Category](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-1.shtml)"""
    _key = defaultdict(lambda: 0)
    def __get__(self, obj, objtype=None):
        return obj.section4[0+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ParameterNumber:
    """[Parameter Number](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-2.shtml)"""
    _key = defaultdict(lambda: 1)
    def __get__(self, obj, objtype=None):
        return obj.section4[1+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class VarInfo:
    """
    Variable Information.

    These are the metadata returned for a specific variable according to
    discipline, parameter category, and parameter number.
    """
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)
    def __set__(self, obj, value):
        raise RuntimeError

class FullName:
    """Full name of the Variable."""
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)[0]
    def __set__(self, obj, value):
        raise RuntimeError

class Units:
    """Units of the Variable."""
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)[1]
    def __set__(self, obj, value):
        raise RuntimeError

class ShortName:
    """ Short name of the variable (i.e. the variable abbreviation)."""
    def __get__(self, obj, objtype=None):
        return tables.get_varinfo_from_table(obj.section0[2],*obj.section4[2:4],isNDFD=obj._isNDFD)[2]
    def __set__(self, obj, value):
        raise RuntimeError

class TypeOfGeneratingProcess:
    """[Type of Generating Process](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-3.shtml)"""
    _key = defaultdict(lambda: 2, {48:13})
    #_key = {0:2, 1:2, 2:2, 5:2, 6:2, 8:2, 9:2, 10:2, 11:2, 12:2, 15:2, 48:13}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='4.3')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class BackgroundGeneratingProcessIdentifier:
    """Background Generating Process Identifier"""
    _key = defaultdict(lambda: 3, {48:14})
    #_key = {0:3, 1:3, 2:3, 5:3, 6:3, 8:3, 9:3, 10:3, 11:3, 12:3, 15:3, 48:14}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class GeneratingProcess:
    """[Generating Process](https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablea.html)"""
    _key = defaultdict(lambda: 4, {48:15})
    #_key = {0:4, 1:4, 2:4, 5:4, 6:4, 8:4, 9:4, 10:4, 11:4, 12:4, 15:4, 48:15}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='generating_process')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class HoursAfterDataCutoff:
    """Hours of observational data cutoff after reference time."""
    _key = defaultdict(lambda: 5, {48:16})
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class MinutesAfterDataCutoff:
    """Minutes of observational data cutoff after reference time."""
    _key = defaultdict(lambda: 6, {48:17})
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class UnitOfForecastTime:
    """[Units of Forecast Time](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-4.shtml)"""
    _key = defaultdict(lambda: 7, {48:18})
    #_key = {0:7, 1:7, 2:7, 5:7, 6:7, 8:7, 9:7, 10:7, 11:7, 12:7, 15:7, 48:18}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='4.4')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ValueOfForecastTime:
    """Value of forecast time in units defined by `UnitofForecastTime`."""
    _key = defaultdict(lambda: 8, {48:19})
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class LeadTime:
    """Forecast Lead Time. NOTE: This is a `datetime.timedelta` object."""

    def __get__(self, obj, objtype=None):
        return utils.get_leadtime(obj.section1, obj.section4[1], obj.section4[2:])

    def __set__(self, obj, value):
        pdt = obj.section4[2:]

        # For the tables below, the key is the PDTN and the value is the slice
        # of the PDT that contains the end date of the accumulation.
        # This is only needed for PDTNs 8-12.
        _key = {
            8: slice(15, 21),
            9: slice(22, 28),
            10: slice(16, 22),
            11: slice(18, 24),
            12: slice(17, 23),
        }

        accumulation_offset = 0
        if obj.pdtn in _key:
            accumulation_end_date = _key[obj.pdtn]
            accumulation_key = accumulation_end_date.stop + 5
            accumulation_offset = int(
                timedelta64(pdt[accumulation_key], "h") / timedelta64(1, "h")
            )
            accumulation_offset = accumulation_offset / (
                tables.get_value_from_table(
                    pdt[accumulation_key - 1], "scale_time_hours"
                )
            )

            refdate = datetime.datetime(*obj.section1[5:11])
            pdt[_key[obj.pdtn]] = (
                datetime.timedelta(hours=accumulation_offset) + refdate
            ).timetuple()[:6]

        # All messages need the leadTime value set, but for PDTNs 8-12, the
        # leadTime value has to be set to the beginning of the accumulation
        # period which is done here by subtracting the already calculated
        # value accumulation_offset.
        lead_time_index = 8
        if obj.pdtn == 48:
            lead_time_index = 19

        ivalue = int(timedelta64(value, "h") / timedelta64(1, "h"))

        pdt[lead_time_index] = (
            ivalue
            / (
                tables.get_value_from_table(
                    pdt[lead_time_index - 1], "scale_time_hours"
                )
            )
            - accumulation_offset
        )

class FixedSfc1Info:
    """Information of the first fixed surface via [table 4.5](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-5.shtml)"""
    _key = defaultdict(lambda: 9, {48:20})
    #_key = {0:9, 1:9, 2:9, 5:9, 6:9, 8:9, 9:9, 10:9, 11:9, 12:9, 15:9, 48:20}
    def __get__(self, obj, objtype=None):
        if obj.section4[self._key[obj.pdtn]+2] == 255:
            return [None, None]
        return tables.get_value_from_table(obj.section4[self._key[obj.pdtn]+2],'4.5')
    def __set__(self, obj, value):
        raise NotImplementedError

class FixedSfc2Info:
    """Information of the second fixed surface via [table 4.5](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-5.shtml)"""
    _key = defaultdict(lambda: 12, {48:23})
    #_key = {0:12, 1:12, 2:12, 5:12, 6:12, 8:12, 9:12, 10:12, 11:12, 12:12, 15:12, 48:23}
    def __get__(self, obj, objtype=None):
        if obj.section4[self._key[obj.pdtn]+2] == 255:
            return [None, None]
        return tables.get_value_from_table(obj.section4[self._key[obj.pdtn]+2],'4.5')
    def __set__(self, obj, value):
        raise NotImplementedError

class TypeOfFirstFixedSurface:
    """[Type of First Fixed Surface](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-5.shtml)"""
    _key = defaultdict(lambda: 9, {48:20})
    #_key = {0:9, 1:9, 2:9, 5:9, 6:9, 8:9, 9:9, 10:9, 11:9, 12:9, 15:9, 48:20}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='4.5')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaleFactorOfFirstFixedSurface:
    """Scale Factor of First Fixed Surface"""
    _key = defaultdict(lambda: 10, {48:21})
    #_key = {0:10, 1:10, 2:10, 5:10, 6:10, 8:10, 9:10, 10:10, 11:10, 12:10, 15:10, 48:21}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaledValueOfFirstFixedSurface:
    """Scaled Value Of First Fixed Surface"""
    _key = defaultdict(lambda: 11, {48:22})
    #_key = {0:11, 1:11, 2:11, 5:11, 6:11, 8:11, 9:11, 10:11, 11:11, 12:11, 15:11, 48:22}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class UnitOfFirstFixedSurface:
    """Units of First Fixed Surface"""
    def __get__(self, obj, objtype=None):
        return obj._fixedsfc1info[1]
    def __set__(self, obj, value):
        pass

class ValueOfFirstFixedSurface:
    """Value of First Fixed Surface"""
    def __get__(self, obj, objtype=None):
        scale_factor = getattr(obj, "scaleFactorOfFirstFixedSurface")
        scaled_value = getattr(obj, "scaledValueOfFirstFixedSurface")
        return scaled_value / (10.**scale_factor)
    def __set__(self, obj, value):
        scale = _calculate_scale_factor(value)
        setattr(obj, "scaleFactorOfFirstFixedSurface", scale)
        setattr(obj, "scaledValueOfFirstFixedSurface", value * 10**scale)

class TypeOfSecondFixedSurface:
    """[Type of Second Fixed Surface](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-5.shtml)"""
    _key = defaultdict(lambda: 12, {48:23})
    #_key = {0:12, 1:12, 2:12, 5:12, 6:12, 8:12, 9:12, 10:12, 11:12, 12:12, 15:12, 48:23}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='4.5')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaleFactorOfSecondFixedSurface:
    """Scale Factor of Second Fixed Surface"""
    _key = defaultdict(lambda: 13, {48:24})
    #_key = {0:13, 1:13, 2:13, 5:13, 6:13, 8:13, 9:13, 10:13, 11:13, 12:13, 15:13, 48:24}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaledValueOfSecondFixedSurface:
    """Scaled Value Of Second Fixed Surface"""
    _key = defaultdict(lambda: 14, {48:25})
    #_key = {0:14, 1:14, 2:14, 5:14, 6:14, 8:14, 9:14, 10:14, 11:14, 12:14, 15:14, 48:25}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class UnitOfSecondFixedSurface:
    """Units of Second Fixed Surface"""
    def __get__(self, obj, objtype=None):
        return obj._fixedsfc2info[1]
    def __set__(self, obj, value):
        pass

class ValueOfSecondFixedSurface:
    """Value of Second Fixed Surface"""
    def __get__(self, obj, objtype=None):
        scale_factor = getattr(obj, "scaleFactorOfSecondFixedSurface")
        scaled_value = getattr(obj, "scaledValueOfSecondFixedSurface")
        return scaled_value / (10.**scale_factor)
    def __set__(self, obj, value):
        scale = _calculate_scale_factor(value)
        setattr(obj, "scaleFactorOfSecondFixedSurface", scale)
        setattr(obj, "scaledValueOfSecondFixedSurface", value * 10**scale)

class Level:
    """Level (same as provided by [wgrib2](https://github.com/NOAA-EMC/NCEPLIBS-wgrib2/blob/develop/wgrib2/Level.c))"""
    def __get__(self, obj, objtype=None):
        return tables.get_wgrib2_level_string(obj.pdtn,obj.section4[2:])
    def __set__(self, obj, value):
        pass

class TypeOfEnsembleForecast:
    """[Type of Ensemble Forecast](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-6.shtml)"""
    _key = {1:15, 11:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.6')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class PerturbationNumber:
    """Ensemble Perturbation Number"""
    _key = {1:16, 11:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class NumberOfEnsembleForecasts:
    """Total Number of Ensemble Forecasts"""
    _key = {1:17, 2:16, 11:17, 12:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfDerivedForecast:
    """[Type of Derived Forecast](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-7.shtml)"""
    _key = {2:15, 12:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.7')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ForecastProbabilityNumber:
    """Forecast Probability Number"""
    _key = {5:15, 9:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TotalNumberOfForecastProbabilities:
    """Total Number of Forecast Probabilities"""
    _key = {5:16, 9:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfProbability:
    """[Type of Probability](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-9.shtml)"""
    _key = {5:17, 9:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.9')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ScaleFactorOfThresholdLowerLimit:
    """Scale Factor of Threshold Lower Limit"""
    _key = {5:18, 9:18}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ScaledValueOfThresholdLowerLimit:
    """Scaled Value of Threshold Lower Limit"""
    _key = {5:19, 9:19}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ScaleFactorOfThresholdUpperLimit:
    """Scale Factor of Threshold Upper Limit"""
    _key = {5:20, 9:20}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ScaledValueOfThresholdUpperLimit:
    """Scaled Value of Threshold Upper Limit"""
    _key = {5:21, 9:21}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class ThresholdLowerLimit:
    """Threshold Lower Limit"""
    def __get__(self, obj, objtype=None):
        scale_factor = getattr(obj, "scaleFactorOfThresholdLowerLimit")
        scaled_value = getattr(obj, "scaledValueOfThresholdLowerLimit")
        if scale_factor == -127 and scaled_value == 255:
            return 0.0
        return scaled_value / (10.**scale_factor)
    def __set__(self, obj, value):
        scale = _calculate_scale_factor(value)
        setattr(obj, "scaleFactorOfThresholdLowerLimit", scale)
        setattr(obj, "scaledValueOfThresholdLowerLimit", value * 10**scale)

class ThresholdUpperLimit:
    """Threshold Upper Limit"""
    def __get__(self, obj, objtype=None):
        scale_factor = getattr(obj, "scaleFactorOfThresholdUpperLimit")
        scaled_value = getattr(obj, "scaledValueOfThresholdUpperLimit")
        if scale_factor == -127 and scaled_value == 255:
            return 0.0
        return scaled_value / (10.**scale_factor)
    def __set__(self, obj, value):
        scale = _calculate_scale_factor(value)
        setattr(obj, "scaleFactorOfThresholdUpperLimit", scale)
        setattr(obj, "scaledValueOfThresholdUpperLimit", value * 10**scale)

class Threshold:
    """Threshold string (same as [wgrib2](https://github.com/NOAA-EMC/NCEPLIBS-wgrib2/blob/develop/wgrib2/Prob.c))"""
    def __get__(self, obj, objtype=None):
        return utils.get_wgrib2_prob_string(*obj.section4[17+2:22+2])
    def __set__(self, obj, value):
        pass

class PercentileValue:
    """Percentile Value"""
    _key = {6:15, 10:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class YearOfEndOfTimePeriod:
    """Year of End of Forecast Time Period"""
    _key = {8:15, 9:22, 10:16, 11:18, 12:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class MonthOfEndOfTimePeriod:
    """Month Year of End of Forecast Time Period"""
    _key = {8:16, 9:23, 10:17, 11:19, 12:18}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class DayOfEndOfTimePeriod:
    """Day Year of End of Forecast Time Period"""
    _key = {8:17, 9:24, 10:18, 11:20, 12:19}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class HourOfEndOfTimePeriod:
    """Hour Year of End of Forecast Time Period"""
    _key = {8:18, 9:25, 10:19, 11:21, 12:20}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class MinuteOfEndOfTimePeriod:
    """Minute Year of End of Forecast Time Period"""
    _key = {8:19, 9:26, 10:20, 11:22, 12:21}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class SecondOfEndOfTimePeriod:
    """Second Year of End of Forecast Time Period"""
    _key = {8:20, 9:27, 10:21, 11:23, 12:22}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class Duration:
    """Duration of time period. NOTE: This is a `datetime.timedelta` object."""
    def __get__(self, obj, objtype=None):
        return utils.get_duration(obj.section4[1],obj.section4[2:])
    def __set__(self, obj, value):
        pass

class ValidDate:
    """Valid Date of the forecast. NOTE: This is a `datetime.datetime` object."""
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
    """Number of time ranges specifications describing the time intervals used to calculate the statistically-processed field"""
    _key = {8:21, 9:28, 10:22, 11:24, 12:23}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class NumberOfMissingValues:
    """Total number of data values missing in statistical process"""
    _key = {8:22, 9:29, 10:23, 11:25, 12:24}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class StatisticalProcess:
    """[Statistical Process](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-10.shtml)"""
    _key = {8:23, 9:30, 10:24, 11:26, 12:25, 15:15}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.10')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfTimeIncrementOfStatisticalProcess:
    """[Type of Time Increment of Statistical Process](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-11.shtml)"""
    _key = {8:24, 9:31, 10:25, 11:27, 12:26}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.11')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class UnitOfTimeRangeOfStatisticalProcess:
    """[Unit of Time Range of Statistical Process](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-11.shtml)"""
    _key = {8:25, 9:32, 10:26, 11:28, 12:27}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.4')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TimeRangeOfStatisticalProcess:
    """Time Range of Statistical Process"""
    _key = {8:26, 9:33, 10:27, 11:29, 12:28}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class UnitOfTimeRangeOfSuccessiveFields:
    """[Unit of Time Range of Successive Fields](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-4.shtml)"""
    _key = {8:27, 9:34, 10:28, 11:30, 12:29}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.4')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TimeIncrementOfSuccessiveFields:
    """Time Increment of Successive Fields"""
    _key = {8:28, 9:35, 10:29, 11:31, 12:30}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class TypeOfStatisticalProcessing:
    """[Type of Statistical Processing](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-15.shtml)"""
    _key = {15:16}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return Grib2Metadata(obj.section4[self._key[pdtn]+2],table='4.15')
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class NumberOfDataPointsForSpatialProcessing:
    """Number of Data Points for Spatial Processing"""
    _key = {15:17}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class NumberOfContributingSpectralBands:
    """Number of Contributing Spectral Bands (NB)"""
    _key = {32:9}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2]
    def __set__(self, obj, value):
        pdtn = obj.section4[1]
        obj.section4[self._key[pdtn]+2] = value

class SatelliteSeries:
    """Satellte Series of band nb, where nb=1,NB if NB > 0"""
    _key = {32:10}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2::5][:obj.section4[9+2]]
    def __set__(self, obj, value):
        pass

class SatelliteNumber:
    """Satellte Number of band nb, where nb=1,NB if NB > 0"""
    _key = {32:11}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2::5][:obj.section4[9+2]]
    def __set__(self, obj, value):
        pass

class InstrumentType:
    """Instrument Type of band nb, where nb=1,NB if NB > 0"""
    _key = {32:12}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2::5][:obj.section4[9+2]]
    def __set__(self, obj, value):
        pass

class ScaleFactorOfCentralWaveNumber:
    """Scale Factor Of Central WaveNumber of band nb, where nb=1,NB if NB > 0"""
    _key = {32:13}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2::5][:obj.section4[9+2]]
    def __set__(self, obj, value):
        pass

class ScaledValueOfCentralWaveNumber:
    """Scaled Value Of Central WaveNumber of band NB"""
    _key = {32:14}
    def __get__(self, obj, objtype=None):
        pdtn = obj.section4[1]
        return obj.section4[self._key[pdtn]+2::5][:obj.section4[9+2]]
    def __set__(self, obj, value):
        pass

class TypeOfAerosol:
    """[Type of Aerosol](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-233.shtml)"""
    _key = {48:2}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='4.233')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class TypeOfIntervalForAerosolSize:
    """[Type of Interval for Aerosol Size](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-91.shtml)"""
    _key = {48:3}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='4.91')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaleFactorOfFirstSize:
    """Scale Factor of First Size"""
    _key = {48:4}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaledValueOfFirstSize:
    """Scaled Value of First Size"""
    _key = {48:5}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaleFactorOfSecondSize:
    """Scale Factor of Second Size"""
    _key = {48:6}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaledValueOfSecondSize:
    """Scaled Value of Second Size"""
    _key = {48:7}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class TypeOfIntervalForAerosolWavelength:
    """[Type of Interval for Aerosol Wavelength](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-91.shtml)"""
    _key = {48:8}
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section4[self._key[obj.pdtn]+2],table='4.91')
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaleFactorOfFirstWavelength:
    """Scale Factor of First Wavelength"""
    _key = {48:9}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaledValueOfFirstWavelength:
    """Scaled Value of First Wavelength"""
    _key = {48:10}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaleFactorOfSecondWavelength:
    """Scale Factor of Second Wavelength"""
    _key = {48:11}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

class ScaledValueOfSecondWavelength:
    """Scaled Value of Second Wavelength"""
    _key = {48:12}
    def __get__(self, obj, objtype=None):
        return obj.section4[self._key[obj.pdtn]+2]
    def __set__(self, obj, value):
        obj.section4[self._key[obj.pdtn]+2] = value

"""
GRIB2 Section 4, Product Definition Template Classes
"""

@dataclass(init=False)
class ProductDefinitionTemplateBase:
    """Base attributes for Product Definition Templates"""
    _varinfo: list = field(init=False, repr=False, default=VarInfo())
    fullName: str = field(init=False, repr=False, default=FullName())
    units: str = field(init=False, repr=False, default=Units())
    shortName: str = field(init=False, repr=False, default=ShortName())
    leadTime: datetime.timedelta = field(init=False,repr=False,default=LeadTime())
    duration: datetime.timedelta = field(init=False,repr=False,default=Duration())
    validDate: datetime.datetime = field(init=False,repr=False,default=ValidDate())
    level: str = field(init=False, repr=False, default=Level())
    # Begin template here...
    parameterCategory: int = field(init=False,repr=False,default=ParameterCategory())
    parameterNumber: int = field(init=False,repr=False,default=ParameterNumber())
    typeOfGeneratingProcess: Grib2Metadata = field(init=False,repr=False,default=TypeOfGeneratingProcess())
    generatingProcess: Grib2Metadata = field(init=False, repr=False, default=GeneratingProcess())
    backgroundGeneratingProcessIdentifier: int = field(init=False,repr=False,default=BackgroundGeneratingProcessIdentifier())
    hoursAfterDataCutoff: int = field(init=False,repr=False,default=HoursAfterDataCutoff())
    minutesAfterDataCutoff: int = field(init=False,repr=False,default=MinutesAfterDataCutoff())
    unitOfForecastTime: Grib2Metadata = field(init=False,repr=False,default=UnitOfForecastTime())
    valueOfForecastTime: int = field(init=False,repr=False,default=ValueOfForecastTime())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplateSurface:
    """Surface attributes for Product Definition Templates"""
    _fixedsfc1info: list = field(init=False, repr=False, default=FixedSfc1Info())
    _fixedsfc2info: list = field(init=False, repr=False, default=FixedSfc2Info())
    typeOfFirstFixedSurface: Grib2Metadata = field(init=False,repr=False,default=TypeOfFirstFixedSurface())
    scaleFactorOfFirstFixedSurface: int = field(init=False,repr=False,default=ScaleFactorOfFirstFixedSurface())
    scaledValueOfFirstFixedSurface: int = field(init=False,repr=False,default=ScaledValueOfFirstFixedSurface())
    typeOfSecondFixedSurface: Grib2Metadata = field(init=False,repr=False,default=TypeOfSecondFixedSurface())
    scaleFactorOfSecondFixedSurface: int = field(init=False,repr=False,default=ScaleFactorOfSecondFixedSurface())
    scaledValueOfSecondFixedSurface: int = field(init=False,repr=False,default=ScaledValueOfSecondFixedSurface())
    unitOfFirstFixedSurface: str = field(init=False,repr=False,default=UnitOfFirstFixedSurface())
    valueOfFirstFixedSurface: int = field(init=False,repr=False,default=ValueOfFirstFixedSurface())
    unitOfSecondFixedSurface: str = field(init=False,repr=False,default=UnitOfSecondFixedSurface())
    valueOfSecondFixedSurface: int = field(init=False,repr=False,default=ValueOfSecondFixedSurface())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate0(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-0.shtml)"""
    _len = 15
    _num = 0
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate1(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 1](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-1.shtml)"""
    _len = 18
    _num = 1
    typeOfEnsembleForecast: Grib2Metadata = field(init=False, repr=False, default=TypeOfEnsembleForecast())
    perturbationNumber: int = field(init=False, repr=False, default=PerturbationNumber())
    numberOfEnsembleForecasts: int = field(init=False, repr=False, default=NumberOfEnsembleForecasts())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate2(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 2](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-2.shtml)"""
    _len = 17
    _num = 2
    typeOfDerivedForecast: Grib2Metadata = field(init=False, repr=False, default=TypeOfDerivedForecast())
    numberOfEnsembleForecasts: int = field(init=False, repr=False, default=NumberOfEnsembleForecasts())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate5(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 5](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-5.shtml)"""
    _len = 22
    _num = 5
    forecastProbabilityNumber: int = field(init=False, repr=False, default=ForecastProbabilityNumber())
    totalNumberOfForecastProbabilities: int = field(init=False, repr=False, default=TotalNumberOfForecastProbabilities())
    typeOfProbability: Grib2Metadata = field(init=False, repr=False, default=TypeOfProbability())
    scaleFactorOfThresholdLowerLimit: float = field(init=False, repr=False, default=ScaleFactorOfThresholdLowerLimit())
    scaledValueOfThresholdLowerLimit: float = field(init=False, repr=False, default=ScaledValueOfThresholdLowerLimit())
    scaleFactorOfThresholdUpperLimit: float = field(init=False, repr=False, default=ScaleFactorOfThresholdUpperLimit())
    scaledValueOfThresholdUpperLimit: float = field(init=False, repr=False, default=ScaledValueOfThresholdUpperLimit())
    thresholdLowerLimit: float = field(init=False, repr=False, default=ThresholdLowerLimit())
    thresholdUpperLimit: float = field(init=False, repr=False, default=ThresholdUpperLimit())
    threshold: str = field(init=False, repr=False, default=Threshold())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate6(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 6](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-6.shtml)"""
    _len = 16
    _num = 6
    percentileValue: int = field(init=False, repr=False, default=PercentileValue())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate8(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 8](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-8.shtml)"""
    _len = 29
    _num = 8
    yearOfEndOfTimePeriod: int = field(init=False, repr=False, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=False, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=False, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=False, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=False, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=False, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=False, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=False, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=False, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=False, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=False, default=TimeIncrementOfSuccessiveFields())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate9(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 9](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-9.shtml)"""
    _len = 36
    _num = 9
    forecastProbabilityNumber: int = field(init=False, repr=False, default=ForecastProbabilityNumber())
    totalNumberOfForecastProbabilities: int = field(init=False, repr=False, default=TotalNumberOfForecastProbabilities())
    typeOfProbability: Grib2Metadata = field(init=False, repr=False, default=TypeOfProbability())
    scaleFactorOfThresholdLowerLimit: float = field(init=False, repr=False, default=ScaleFactorOfThresholdLowerLimit())
    scaledValueOfThresholdLowerLimit: float = field(init=False, repr=False, default=ScaledValueOfThresholdLowerLimit())
    scaleFactorOfThresholdUpperLimit: float = field(init=False, repr=False, default=ScaleFactorOfThresholdUpperLimit())
    scaledValueOfThresholdUpperLimit: float = field(init=False, repr=False, default=ScaledValueOfThresholdUpperLimit())
    thresholdLowerLimit: float = field(init=False, repr=False, default=ThresholdLowerLimit())
    thresholdUpperLimit: float = field(init=False, repr=False, default=ThresholdUpperLimit())
    threshold: str = field(init=False, repr=False, default=Threshold())
    yearOfEndOfTimePeriod: int = field(init=False, repr=False, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=False, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=False, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=False, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=False, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=False, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=False, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=False, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=False, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=False, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=False, default=TimeIncrementOfSuccessiveFields())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate10(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 10](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-10.shtml)"""
    _len = 30
    _num = 10
    percentileValue: int = field(init=False, repr=False, default=PercentileValue())
    yearOfEndOfTimePeriod: int = field(init=False, repr=False, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=False, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=False, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=False, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=False, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=False, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=False, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=False, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=False, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=False, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=False, default=TimeIncrementOfSuccessiveFields())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate11(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 11](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-11.shtml)"""
    _len = 32
    _num = 11
    typeOfEnsembleForecast: Grib2Metadata = field(init=False, repr=False, default=TypeOfEnsembleForecast())
    perturbationNumber: int = field(init=False, repr=False, default=PerturbationNumber())
    numberOfEnsembleForecasts: int = field(init=False, repr=False, default=NumberOfEnsembleForecasts())
    yearOfEndOfTimePeriod: int = field(init=False, repr=False, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=False, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=False, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=False, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=False, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=False, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=False, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=False, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=False, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=False, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=False, default=TimeIncrementOfSuccessiveFields())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate12(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 12](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-12.shtml)"""
    _len = 31
    _num = 12
    typeOfDerivedForecast: Grib2Metadata = field(init=False, repr=False, default=TypeOfDerivedForecast())
    numberOfEnsembleForecasts: int = field(init=False, repr=False, default=NumberOfEnsembleForecasts())
    yearOfEndOfTimePeriod: int = field(init=False, repr=False, default=YearOfEndOfTimePeriod())
    monthOfEndOfTimePeriod: int = field(init=False, repr=False, default=MonthOfEndOfTimePeriod())
    dayOfEndOfTimePeriod: int = field(init=False, repr=False, default=DayOfEndOfTimePeriod())
    hourOfEndOfTimePeriod: int = field(init=False, repr=False, default=HourOfEndOfTimePeriod())
    minuteOfEndOfTimePeriod: int = field(init=False, repr=False, default=MinuteOfEndOfTimePeriod())
    secondOfEndOfTimePeriod: int = field(init=False, repr=False, default=SecondOfEndOfTimePeriod())
    numberOfTimeRanges: int = field(init=False, repr=False, default=NumberOfTimeRanges())
    numberOfMissingValues: int = field(init=False, repr=False, default=NumberOfMissingValues())
    statisticalProcess: Grib2Metadata = field(init=False, repr=False, default=StatisticalProcess())
    typeOfTimeIncrementOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=TypeOfTimeIncrementOfStatisticalProcess())
    unitOfTimeRangeOfStatisticalProcess: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfStatisticalProcess())
    timeRangeOfStatisticalProcess: int = field(init=False, repr=False, default=TimeRangeOfStatisticalProcess())
    unitOfTimeRangeOfSuccessiveFields: Grib2Metadata = field(init=False, repr=False, default=UnitOfTimeRangeOfSuccessiveFields())
    timeIncrementOfSuccessiveFields: int = field(init=False, repr=False, default=TimeIncrementOfSuccessiveFields())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate15(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 15](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-15.shtml)"""
    _len = 18
    _num = 15
    statisticalProcess: Grib2Metadata = field(init=False, repr=False, default=StatisticalProcess())
    typeOfStatisticalProcessing: Grib2Metadata = field(init=False, repr=False, default=TypeOfStatisticalProcessing())
    numberOfDataPointsForSpatialProcessing: int = field(init=False, repr=False, default=NumberOfDataPointsForSpatialProcessing())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate31:
    """[Product Definition Template 31](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-31.shtml)"""
    _len = 5
    _num = 31
    parameterCategory: int = field(init=False,repr=False,default=ParameterCategory())
    parameterNumber: int = field(init=False,repr=False,default=ParameterNumber())
    typeOfGeneratingProcess: Grib2Metadata = field(init=False,repr=False,default=TypeOfGeneratingProcess())
    generatingProcess: Grib2Metadata = field(init=False, repr=False, default=GeneratingProcess())
    numberOfContributingSpectralBands: int = field(init=False,repr=False,default=NumberOfContributingSpectralBands())
    satelliteSeries: list = field(init=False,repr=False,default=SatelliteSeries())
    satelliteNumber: list = field(init=False,repr=False,default=SatelliteNumber())
    instrumentType: list = field(init=False,repr=False,default=InstrumentType())
    scaleFactorOfCentralWaveNumber: list = field(init=False,repr=False,default=ScaleFactorOfCentralWaveNumber())
    scaledValueOfCentralWaveNumber: list = field(init=False,repr=False,default=ScaledValueOfCentralWaveNumber())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate32(ProductDefinitionTemplateBase):
    """[Product Definition Template 32](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-32.shtml)"""
    _len = 10
    _num = 32
    numberOfContributingSpectralBands: int = field(init=False,repr=False,default=NumberOfContributingSpectralBands())
    satelliteSeries: list = field(init=False,repr=False,default=SatelliteSeries())
    satelliteNumber: list = field(init=False,repr=False,default=SatelliteNumber())
    instrumentType: list = field(init=False,repr=False,default=InstrumentType())
    scaleFactorOfCentralWaveNumber: list = field(init=False,repr=False,default=ScaleFactorOfCentralWaveNumber())
    scaledValueOfCentralWaveNumber: list = field(init=False,repr=False,default=ScaledValueOfCentralWaveNumber())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

@dataclass(init=False)
class ProductDefinitionTemplate48(ProductDefinitionTemplateBase,ProductDefinitionTemplateSurface):
    """[Product Definition Template 48](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp4-48.shtml)"""
    _len = 26
    _num = 48
    typeOfAerosol: Grib2Metadata = field(init=False, repr=False, default=TypeOfAerosol())
    typeOfIntervalForAerosolSize: Grib2Metadata = field(init=False, repr=False, default=TypeOfIntervalForAerosolSize())
    scaleFactorOfFirstSize: int = field(init=False, repr=False, default=ScaleFactorOfFirstSize())
    scaledValueOfFirstSize: int = field(init=False, repr=False, default=ScaledValueOfFirstSize())
    scaleFactorOfSecondSize: int = field(init=False, repr=False, default=ScaleFactorOfSecondSize())
    scaledValueOfSecondSize: int = field(init=False, repr=False, default=ScaledValueOfSecondSize())
    typeOfIntervalForAerosolWavelength: Grib2Metadata = field(init=False, repr=False, default=TypeOfIntervalForAerosolWavelength())
    scaleFactorOfFirstWavelength: int = field(init=False, repr=False, default=ScaleFactorOfFirstWavelength())
    scaledValueOfFirstWavelength: int = field(init=False, repr=False, default=ScaledValueOfFirstWavelength())
    scaleFactorOfSecondWavelength: int = field(init=False, repr=False, default=ScaleFactorOfSecondWavelength())
    scaledValueOfSecondWavelength: int = field(init=False, repr=False, default=ScaledValueOfSecondWavelength())
    @classmethod
    @property
    def _attrs(cls):
        return [key for key in cls.__dataclass_fields__.keys() if not key.startswith('_')]

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
    31: ProductDefinitionTemplate31,
    32: ProductDefinitionTemplate32,
    48: ProductDefinitionTemplate48,
    }

def pdt_class_by_pdtn(pdtn: int):
    """
    Provide a Product Definition Template class via the template number.

    Parameters
    ----------
    pdtn
        Product definition template number.

    Returns
    -------
    pdt_class_by_pdtn
        Product definition template class object (not an instance).
    """
    return _pdt_by_pdtn[pdtn]

# ----------------------------------------------------------------------------------------
# Descriptor Classes for Section 5 metadata.
# ----------------------------------------------------------------------------------------
class NumberOfPackedValues:
    """Number of Packed Values"""
    def __get__(self, obj, objtype=None):
        return obj.section5[0]
    def __set__(self, obj, value):
        pass

class DataRepresentationTemplateNumber:
    """[Data Representation Template Number](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-0.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[1],table='5.0')
    def __set__(self, obj, value):
        pass

class DataRepresentationTemplate:
    """Data Representation Template"""
    def __get__(self, obj, objtype=None):
        return obj.section5[2:]
    def __set__(self, obj, value):
        raise NotImplementedError

class RefValue:
    """Reference Value (represented as an IEEE 32-bit floating point value)"""
    def __get__(self, obj, objtype=None):
        return utils.ieee_int_to_float(obj.section5[0+2])
    def __set__(self, obj, value):
        pass

class BinScaleFactor:
    """Binary Scale Factor"""
    def __get__(self, obj, objtype=None):
        return obj.section5[1+2]
    def __set__(self, obj, value):
        obj.section5[1+2] = value

class DecScaleFactor:
    """Decimal Scale Factor"""
    def __get__(self, obj, objtype=None):
        return obj.section5[2+2]
    def __set__(self, obj, value):
        obj.section5[2+2] = value

class NBitsPacking:
    """Minimum number of bits for packing"""
    def __get__(self, obj, objtype=None):
        return obj.section5[3+2]
    def __set__(self, obj, value):
        obj.section5[3+2] = value

class TypeOfValues:
    """[Type of Original Field Values](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-1.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[4+2],table='5.1')
    def __set__(self, obj, value):
        obj.section5[4+2] = value

class GroupSplittingMethod:
    """[Group Splitting Method](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-4.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[5+2],table='5.4')
    def __set__(self, obj, value):
        obj.section5[5+2] = value

class TypeOfMissingValueManagement:
    """[Type of Missing Value Management](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-5.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[6+2],table='5.5')
    def __set__(self, obj, value):
        obj.section5[6+2] = value

class PriMissingValue:
    """Primary Missing Value"""
    def __get__(self, obj, objtype=None):
        if obj.typeOfValues == 0:
            return utils.ieee_int_to_float(obj.section5[7+2]) if obj.section5[6+2] in {1,2} and obj.section5[7+2] != 255 else None
        elif obj.typeOfValues == 1:
            return obj.section5[7+2] if obj.section5[6+2] in [1,2] else None
    def __set__(self, obj, value):
        if obj.typeOfValues == 0:
            obj.section5[7+2] = utils.ieee_float_to_int(value)
        elif self.typeOfValues == 1:
            obj.section5[7+2] = int(value)
        obj.section5[6+2] = 1

class SecMissingValue:
    """Secondary Missing Value"""
    def __get__(self, obj, objtype=None):
        if obj.typeOfValues == 0:
            return utils.ieee_int_to_float(obj.section5[8+2]) if obj.section5[6+2] in {1,2} and obj.section5[8+2] != 255 else None
        elif obj.typeOfValues == 1:
            return obj.section5[8+2] if obj.section5[6+2] in {1,2} else None
    def __set__(self, obj, value):
        if obj.typeOfValues == 0:
            obj.section5[8+2] = utils.ieee_float_to_int(value)
        elif self.typeOfValues == 1:
            obj.section5[8+2] = int(value)
        obj.section5[6+2] = 2

class NGroups:
    """Number of Groups"""
    def __get__(self, obj, objtype=None):
        return obj.section5[9+2]
    def __set__(self, obj, value):
        pass

class RefGroupWidth:
    """Reference Group Width"""
    def __get__(self, obj, objtype=None):
        return obj.section5[10+2]
    def __set__(self, obj, value):
        pass

class NBitsGroupWidth:
    """Number of bits for Group Width"""
    def __get__(self, obj, objtype=None):
        return obj.section5[11+2]
    def __set__(self, obj, value):
        pass

class RefGroupLength:
    """Reference Group Length"""
    def __get__(self, obj, objtype=None):
        return obj.section5[12+2]
    def __set__(self, obj, value):
        pass

class GroupLengthIncrement:
    """Group Length Increment"""
    def __get__(self, obj, objtype=None):
        return obj.section5[13+2]
    def __set__(self, obj, value):
        pass

class LengthOfLastGroup:
    """Length of Last Group"""
    def __get__(self, obj, objtype=None):
        return obj.section5[14+2]
    def __set__(self, obj, value):
        pass

class NBitsScaledGroupLength:
    """Number of bits of Scaled Group Length"""
    def __get__(self, obj, objtype=None):
        return obj.section5[15+2]
    def __set__(self, obj, value):
        pass

class SpatialDifferenceOrder:
    """[Spatial Difference Order](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-6.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[16+2],table='5.6')
    def __set__(self, obj, value):
        obj.section5[16+2] = value

class NBytesSpatialDifference:
    """Number of bytes for Spatial Differencing"""
    def __get__(self, obj, objtype=None):
        return obj.section5[17+2]
    def __set__(self, obj, value):
        pass

class Precision:
    """[Precision for IEEE Floating Point Data](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-7.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[0+2],table='5.7')
    def __set__(self, obj, value):
        obj.section5[0+2] = value

class TypeOfCompression:
    """[Type of Compression](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table5-40.shtml)"""
    def __get__(self, obj, objtype=None):
        return Grib2Metadata(obj.section5[5+2],table='5.40')
    def __set__(self, obj, value):
        obj.section5[5+2] = value

class TargetCompressionRatio:
    """Target Compression Ratio"""
    def __get__(self, obj, objtype=None):
        return obj.section5[6+2]
    def __set__(self, obj, value):
        pass

class RealOfCoefficient:
    """Real of Coefficient"""
    def __get__(self, obj, objtype=None):
        return utils.ieee_int_to_float(obj.section5[4+2])
    def __set__(self, obj, value):
        obj.section5[4+2] = utils.ieee_float_to_int(float(value))

class CompressionOptionsMask:
    """Compression Options Mask for AEC/CCSDS"""
    def __get__(self, obj, objtype=None):
        return obj.section5[5+2]
    def __set__(self, obj, value):
        obj.section5[5+2] = value

class BlockSize:
    """Block Size for AEC/CCSDS"""
    def __get__(self, obj, objtype=None):
        return obj.section5[6+2]
    def __set__(self, obj, value):
        obj.section5[6+2] = value

class RefSampleInterval:
    """Reference Sample Interval for AEC/CCSDS"""
    def __get__(self, obj, objtype=None):
        return obj.section5[7+2]
    def __set__(self, obj, value):
        obj.section5[7+2] = value

@dataclass(init=False)
class DataRepresentationTemplate0:
    """[Data Representation Template 0](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-0.shtml)"""
    _len = 5
    _num = 0
    _packingScheme = 'simple'
    refValue: float = field(init=False, repr=False, default=RefValue())
    binScaleFactor: int = field(init=False, repr=False, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=False, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=False, default=NBitsPacking())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class DataRepresentationTemplate2:
    """[Data Representation Template 2](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-2.shtml)"""
    _len = 16
    _num = 2
    _packingScheme = 'complex'
    refValue: float = field(init=False, repr=False, default=RefValue())
    binScaleFactor: int = field(init=False, repr=False, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=False, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=False, default=NBitsPacking())
    groupSplittingMethod: Grib2Metadata = field(init=False, repr=False, default=GroupSplittingMethod())
    typeOfMissingValueManagement: Grib2Metadata = field(init=False, repr=False, default=TypeOfMissingValueManagement())
    priMissingValue: Union[float, int] = field(init=False, repr=False, default=PriMissingValue())
    secMissingValue: Union[float, int] = field(init=False, repr=False, default=SecMissingValue())
    nGroups: int = field(init=False, repr=False, default=NGroups())
    refGroupWidth: int = field(init=False, repr=False, default=RefGroupWidth())
    nBitsGroupWidth: int = field(init=False, repr=False, default=NBitsGroupWidth())
    refGroupLength: int = field(init=False, repr=False, default=RefGroupLength())
    groupLengthIncrement: int = field(init=False, repr=False, default=GroupLengthIncrement())
    lengthOfLastGroup: int = field(init=False, repr=False, default=LengthOfLastGroup())
    nBitsScaledGroupLength: int = field(init=False, repr=False, default=NBitsScaledGroupLength())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class DataRepresentationTemplate3:
    """[Data Representation Template 3](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-3.shtml)"""
    _len = 18
    _num = 3
    _packingScheme = 'complex-spdiff'
    refValue: float = field(init=False, repr=False, default=RefValue())
    binScaleFactor: int = field(init=False, repr=False, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=False, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=False, default=NBitsPacking())
    groupSplittingMethod: Grib2Metadata = field(init=False, repr=False, default=GroupSplittingMethod())
    typeOfMissingValueManagement: Grib2Metadata = field(init=False, repr=False, default=TypeOfMissingValueManagement())
    priMissingValue: Union[float, int] = field(init=False, repr=False, default=PriMissingValue())
    secMissingValue: Union[float, int] = field(init=False, repr=False, default=SecMissingValue())
    nGroups: int = field(init=False, repr=False, default=NGroups())
    refGroupWidth: int = field(init=False, repr=False, default=RefGroupWidth())
    nBitsGroupWidth: int = field(init=False, repr=False, default=NBitsGroupWidth())
    refGroupLength: int = field(init=False, repr=False, default=RefGroupLength())
    groupLengthIncrement: int = field(init=False, repr=False, default=GroupLengthIncrement())
    lengthOfLastGroup: int = field(init=False, repr=False, default=LengthOfLastGroup())
    nBitsScaledGroupLength: int = field(init=False, repr=False, default=NBitsScaledGroupLength())
    spatialDifferenceOrder: Grib2Metadata = field(init=False, repr=False, default=SpatialDifferenceOrder())
    nBytesSpatialDifference: int = field(init=False, repr=False, default=NBytesSpatialDifference())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class DataRepresentationTemplate4:
    """[Data Representation Template 4](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-4.shtml)"""
    _len = 1
    _num = 4
    _packingScheme = 'ieee-float'
    precision: Grib2Metadata = field(init=False, repr=False, default=Precision())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class DataRepresentationTemplate40:
    """[Data Representation Template 40](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-40.shtml)"""
    _len = 7
    _num = 40
    _packingScheme = 'jpeg'
    refValue: float = field(init=False, repr=False, default=RefValue())
    binScaleFactor: int = field(init=False, repr=False, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=False, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=False, default=NBitsPacking())
    typeOfCompression: Grib2Metadata = field(init=False, repr=False, default=TypeOfCompression())
    targetCompressionRatio: int = field(init=False, repr=False, default=TargetCompressionRatio())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class DataRepresentationTemplate41:
    """[Data Representation Template 41](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-41.shtml)"""
    _len = 5
    _num = 41
    _packingScheme = 'png'
    refValue: float = field(init=False, repr=False, default=RefValue())
    binScaleFactor: int = field(init=False, repr=False, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=False, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=False, default=NBitsPacking())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class DataRepresentationTemplate42:
    """[Data Representation Template 42](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-42.shtml)"""
    _len = 8
    _num = 42
    _packingScheme = 'aec'
    refValue: float = field(init=False, repr=False, default=RefValue())
    binScaleFactor: int = field(init=False, repr=False, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=False, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=False, default=NBitsPacking())
    compressionOptionsMask: int = field(init=False, repr=False, default=CompressionOptionsMask())
    blockSize: int = field(init=False, repr=False, default=BlockSize())
    refSampleInterval: int = field(init=False, repr=False, default=RefSampleInterval())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

@dataclass(init=False)
class DataRepresentationTemplate50:
    """[Data Representation Template 50](https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_temp5-50.shtml)"""
    _len = 5
    _num = 0
    _packingScheme = 'spectral-simple'
    refValue: float = field(init=False, repr=False, default=RefValue())
    binScaleFactor: int = field(init=False, repr=False, default=BinScaleFactor())
    decScaleFactor: int = field(init=False, repr=False, default=DecScaleFactor())
    nBitsPacking: int = field(init=False, repr=False, default=NBitsPacking())
    realOfCoefficient: float = field(init=False, repr=False, default=RealOfCoefficient())
    @classmethod
    @property
    def _attrs(cls):
        return list(cls.__dataclass_fields__.keys())

_drt_by_drtn = {
    0: DataRepresentationTemplate0,
    2: DataRepresentationTemplate2,
    3: DataRepresentationTemplate3,
    4: DataRepresentationTemplate4,
    40: DataRepresentationTemplate40,
    41: DataRepresentationTemplate41,
    42: DataRepresentationTemplate42,
    50: DataRepresentationTemplate50,
    }

def drt_class_by_drtn(drtn: int):
    """
    Provide a Data Representation Template class via the template number.

    Parameters
    ----------
    drtn
        Data Representation template number.

    Returns
    -------
    drt_class_by_drtn
        Data Representation template class object (not an instance).
    """
    return _drt_by_drtn[drtn]
