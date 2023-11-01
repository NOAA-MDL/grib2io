"""
Functions for retreiving data from NCEP GRIB2 Tables.
"""
#from functools import cache # USE WHEN Python 3.9+ only
from functools import lru_cache

from .section0 import *
from .section1 import *
from .section3 import *
from .section4 import *
from .section5 import *
from .section6 import *
from .originating_centers import *

GRIB2_DISCIPLINES = [0, 1, 2, 3, 4, 10, 20]

def get_table(table, expand=False):
    """
    Return GRIB2 code table as a dictionary.

    Parameters
    ----------
    **`table`**: Code table number (e.g. '1.0'). NOTE: Code table '4.1' requires a 3rd value
    representing the product discipline (e.g. '4.1.0').

    **`expand`**: If `True`, expand output dictionary where keys are a range.

    Returns
    -------
    **`dict`**
    """
    if len(table) == 3 and table == '4.1':
        raise Exception('GRIB2 Code Table 4.1 requires a 3rd value representing the discipline.')
    if len(table) == 3 and table.startswith('4.2'):
        raise Exception('Use function get_varinfo_from_table() for GRIB2 Code Table 4.2')
    try:
        tbl = globals()['table_'+table.replace('.','_')]
        if expand:
            _tbl = {}
            for k,v in tbl.items():
                if '-' in k:
                    irng = [int(i) for i in k.split('-')]
                    for i in range(irng[0],irng[1]+1):
                        _tbl[str(i)] = v
                else:
                    _tbl[k] = v
            tbl = _tbl
        return tbl
    except(KeyError):
        return {}


def get_value_from_table(value, table, expand=False):
    """
    Return the definition given a GRIB2 code table.

    Parameters
    ----------
    **`value`**: `int` or `str` code table value.

    **`table`**: `str` code table number.

    **`expand`**: If `True`, expand output dictionary where keys are a range.

    Returns
    -------
    Table value or `None` if not found.
    """
    try:
        tbl = get_table(table,expand=expand)
        value = str(value)
        return tbl[value]
    except(KeyError):
        for k in tbl.keys():
            if '-' in k:
                bounds = k.split('-')
                if value >= bounds[0] and value <= bounds[1]:
                    return tbl[k]
        return None


def get_varinfo_from_table(discipline,parmcat,parmnum,isNDFD=False):
    """
    Return the GRIB2 variable information given values of `discipline`,
    `parmcat`, and `parmnum`. NOTE: This functions allows for all arguments
    to be converted to a string type if arguments are integer.

    Parameters
    ----------
    **`discipline`**: `int` or `str` of Discipline code value of a GRIB2 message.

    **`parmcat`**: `int` or `str` of Parameter Category value of a GRIB2 message.

    **`parmnum`**: `int` or `str` of Parameter Number value of a GRIB2 message.

    **`isNDFD`**: If `True`, signals function to try to get variable information
    from the supplemental NDFD tables.

    Returns
    -------
    **`list`**: containing variable information. "Unknown" is given for item of
    information if variable is not found.
    - list[0] = full name
    - list[1] = units
    - list[2] = short name (abbreviated name)
    """
    if isNDFD:
        try:
            tblname = f'table_4_2_{discipline}_{parmcat}_ndfd'
            modname = f'.section4_discipline{discipline}'
            exec('from '+modname+' import *')
            return locals()[tblname][str(parmnum)]
        except(ImportError,KeyError):
            pass
            #return ['Unknown','Unknown','Unknown']
    try:
        tblname = f'table_4_2_{discipline}_{parmcat}'
        modname = f'.section4_discipline{discipline}'
        exec('from '+modname+' import *')
        return locals()[tblname][str(parmnum)]
    except(ImportError,KeyError):
        return ['Unknown','Unknown','Unknown']


#@cache# USE WHEN Python 3.9+ only
@lru_cache(maxsize=None)
def get_shortnames(discipline=None, parmcat=None, parmnum=None, isNDFD=False):
    """
    Returns a list of variable shortNames given GRIB2 discipline, parameter
    category, and parameter number.  If all 3 args are None, then shortNames
    from all disciplines, parameter categories, and numbers will be returned.

    Parameters
    ----------
    **`discipline : int`** GRIB2 discipline code value.

    **`parmcat : int`** GRIB2 parameter category value.

    **`parmnum`**: `int` or `str` of Parameter Number value of a GRIB2 message.

    Returns
    -------
    **`list`** of GRIB2 shortNames.
    """
    shortnames = list()
    if discipline is None:
        discipline = GRIB2_DISCIPLINES
    else:
        discipline = [discipline]
    if parmcat is None:
        parmcat = list()
        for d in discipline:
            parmcat += list(get_table(f'4.1.{d}').keys())
    else:
        parmcat = [parmcat]
    if parmnum is None:
        parmnum = list(range(256))
    else:
        parmnum = [parmnum]
    for d in discipline:

        for pc in parmcat:
            for pn in parmnum:
                shortnames.append(get_varinfo_from_table(d,pc,pn,isNDFD)[2])

    shortnames = sorted(set(shortnames))
    try:
        shortnames.remove('unknown')
        shortnames.remove('Unknown')
    except(ValueError):
        pass
    return shortnames


#@cache# USE WHEN Python 3.9+ only
@lru_cache(maxsize=None)
def get_metadata_from_shortname(shortname):
    """
    Provide GRIB2 variable metadata attributes given a GRIB2 shortName.

    Parameters
    ----------
    **`shortname : str`** GRIB2 variable shortName.

    Returns
    -------
    **`list`** of dictionary items where each dictionary items contains the variable
    metadata key:value pairs. **NOTE:** Some variable shortNames will exist in multiple
    parameter category/number tables according to the GRIB2 discipline.
    """
    metadata = []
    for d in GRIB2_DISCIPLINES:
        parmcat = list(get_table(f'4.1.{d}').keys())
        for pc in parmcat:
            for pn in range(256):
                varinfo = get_varinfo_from_table(d,pc,pn,False)
                if shortname == varinfo[2]:
                    metadata.append(dict(discipline=d,parameterCategory=pc,parameterNumber=pn,
                                         fullName=varinfo[0],units=varinfo[1]))
    return metadata


def get_wgrib2_level_string(pdtn,pdt):
    """
    Return a string that describes the level or layer of the GRIB2 message. The
    format and language of the string is an exact replica of how wgrib2 produces
    the level/layer string in its inventory output.

    Contents of wgrib2 source, [Level.c](https://github.com/NOAA-EMC/NCEPLIBS-wgrib2/blob/develop/wgrib2/Level.c),
    were converted into a Python dictionary and stored in grib2io as table
    'wgrib2_level_string'.

    Parameters
    ----------
    **`pdtn`**: GRIB2 Product Definition Template Number

    **`pdt`**: sequence containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------
    **`str`**: wgrib2-formatted level/layer string.
    """
    if pdtn == 48:
        idxs = slice(20,26)
    else:
        idxs = slice(9,15)
    type1, sfac1, sval1, type2, sfac2, sval2 = map(int,pdt[idxs])
    lvlstr = ''
    val1 = sval1/10**sfac1
    if type1 in [100,108]: val1 *= 0.01
    if type2 != 255:
        # Layer
        #assert type2 == type1, "Surface types are not equal: %g - %g" % (type1,type2)
        val2 = sval2/10**sfac2
        if type2 in [100,108]: val2 *= 0.01
        lvlstr = get_value_from_table(type1,table='wgrib2_level_string')[1]
        vals = (val1,val2)
    else:
        # Level
        lvlstr = get_value_from_table(type1,table='wgrib2_level_string')[0]
        vals = (val1)
    if '%g' in lvlstr: lvlstr %= vals
    return lvlstr
