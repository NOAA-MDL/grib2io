from .section0 import *
from .section1 import *
from .section3 import *
from .section4 import *
from .section5 import *
from .originating_centers import *

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
        raise Exception('Use function get_varname_from_table() for GRIB2 Code Table 4.2')
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


def get_value_from_table(value, table):
    """
    Return the definition given a GRIB2 code table.

    Parameters
    ----------

    **`value`**: `int` or `str` code table value.

    **`table`**: `str` code table number.

    Returns
    -------

    Table value or `None` if not found.
    """
    try:
        tbl = get_table(table,expand=True)
        if isinstance(value,int): value = str(value)
        return tbl[value]
    except(KeyError):
        return None


def get_varinfo_from_table(discipline,parmcat,parmnum):
    """
    Return the GRIB2 variable information given values of `discipline`,
    `parmcat`, and `parmnum`. NOTE: This functions allows for all arguments
    to be converted to a string type if arguments are integer.

    Parameters
    ----------

    **`discipline`**: `int` or `str` of Discipline code value of a GRIB2 message.

    **`parmcat`**: `int` or `str` of Parameter Category value of a GRIB2 message.

    **`parmnum`**: `int` or `str` of Parameter Number value of a GRIB2 message.

    Returns
    -------

    **`list`**: containing variable information. "Unknown" is given for item of
    information if variable is not found.
    - list[0] = full name
    - list[1] = units
    - list[2] = short name (abbreviated name)
    """
    if isinstance(discipline,int): discipline = str(discipline)
    if isinstance(parmcat,int): parmcat = str(parmcat)
    if isinstance(parmnum,int): parmnum = str(parmnum)
    try:
        tblname = 'table_4_2_'+discipline+'_'+parmcat
        modname = '.section4_discipline'+discipline
        exec('from '+modname+' import *')
        return locals()[tblname][parmnum]
    except(ImportError,KeyError):
        return ['Unknown','Unknown','Unknown']
