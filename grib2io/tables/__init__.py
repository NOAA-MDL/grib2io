"""Functions for retrieving data from NCEP GRIB2 Tables."""

from functools import lru_cache

from typing import Optional, Union, List
from numpy.typing import ArrayLike

from .section0 import *
from .section1 import *
from .section3 import *
from .section4 import *
from .section5 import *
from .section6 import *
from .originating_centers import *

GRIB2_DISCIPLINES = [0, 1, 2, 3, 4, 10, 20]

def get_table(table: str, expand: bool=False) -> dict:
    """
    Return GRIB2 code table as a dictionary.

    Parameters
    ----------
    table
        Code table number (e.g. '1.0').

        NOTE: Code table '4.1' requires a 3rd value representing the product
        discipline (e.g. '4.1.0').
    expand
        If `True`, expand output dictionary wherever keys are a range.

    Returns
    -------
    get_table
        GRIB2 code table as a dictionary.
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


def get_value_from_table(
    value: Union[int, str],
    table: str,
    expand: bool = False,
) -> Optional[Union[float, int]]:
    """
    Return the definition given a GRIB2 code table.

    Parameters
    ----------
    value
        Code table value.
    table
        Code table number.
    expand
        If `True`, expand output dictionary where keys are a range.

    Returns
    -------
    get_value_from_table
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


def get_varinfo_from_table(
    discipline: Union[int, str],
    parmcat: Union[int, str],
    parmnum: Union[int, str],
    isNDFD: bool = False,
):
    """
    Return the GRIB2 variable information.

    NOTE: This functions allows for all arguments to be converted to a string
    type if arguments are integer.

    Parameters
    ----------
    discipline
        Discipline code value of a GRIB2 message.
    parmcat
        Parameter Category value of a GRIB2 message.
    parmnum
        Parameter Number value of a GRIB2 message.
    isNDFD: optional
        If `True`, signals function to try to get variable information from the
        supplemental NDFD tables.

    Returns
    -------
    full_name
        Full name of the GRIB2 variable. "Unknown" if variable is not found.
    units
        Units of the GRIB2 variable. "Unknown" if variable is not found.
    shortName
        Abbreviated name of the GRIB2 variable. "Unknown" if variable is not
        found.
    """
    if isNDFD:
        try:
            tblname = f'table_4_2_{discipline}_{parmcat}_ndfd'
            modname = f'.section4_discipline{discipline}'
            exec('from '+modname+' import *')
            return locals()[tblname][str(parmnum)]
        except(ImportError,KeyError):
            pass
    try:
        tblname = f'table_4_2_{discipline}_{parmcat}'
        modname = f'.section4_discipline{discipline}'
        exec('from '+modname+' import *')
        return locals()[tblname][str(parmnum)]
    except(ImportError,KeyError):
        return ['Unknown','Unknown','Unknown']


@lru_cache(maxsize=None)
def get_shortnames(
    discipline: Optional[Union[int, str]] = None,
    parmcat: Optional[Union[int, str]] = None,
    parmnum: Optional[Union[int, str]] = None,
    isNDFD: bool = False,
) -> List[str]:
    """
    Return a list of variable shortNames.

    If all 3 args are None, then shortNames from all disciplines, parameter
    categories, and numbers will be returned.

    Parameters
    ----------
    discipline
        GRIB2 discipline code value.
    parmcat
        GRIB2 parameter category value.
    parmnum
        Parameter Number value of a GRIB2 message.
    isNDFD: optional
        If `True`, signals function to try to get variable information from the
        supplemental NDFD tables.

    Returns
    -------
    get_shortnames
        list of GRIB2 shortNames.
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


@lru_cache(maxsize=None)
def get_metadata_from_shortname(shortname: str):
    """
    Provide GRIB2 variable metadata attributes given a GRIB2 shortName.

    Parameters
    ----------
    shortname
        GRIB2 variable shortName.

    Returns
    -------
    get_metadata_from_shortname
        list of dictionary items where each dictionary item contains the
        variable metadata key:value pairs.

        NOTE: Some variable shortNames will exist in multiple parameter
        category/number tables according to the GRIB2 discipline.
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


def get_wgrib2_level_string(pdtn: int, pdt: ArrayLike) -> str:
    """
    Return a string that describes the level or layer of the GRIB2 message.

    The format and language of the string is an exact replica of how wgrib2
    produces the level/layer string in its inventory output.

    Contents of wgrib2 source,
    [Level.c](https://github.com/NOAA-EMC/NCEPLIBS-wgrib2/blob/develop/wgrib2/Level.c),
    were converted into a Python dictionary and stored in grib2io as table
    'wgrib2_level_string'.

    Parameters
    ----------
    pdtn
        GRIB2 Product Definition Template Number
    pdt
        Sequence containing GRIB2 Product Definition Template (Section 4).

    Returns
    -------
    get_wgrib2_level_string
        wgrib2-formatted level/layer string.
    """
    lvlstr = ''
    if pdtn == 32:
        return 'no_level'
    elif pdtn == 48:
        idxs = slice(20,26)
    else:
        idxs = slice(9,15)
    type1, sfac1, sval1, type2, sfac2, sval2 = map(int,pdt[idxs])
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
