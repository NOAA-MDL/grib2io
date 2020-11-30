from .section0 import *
from .section1 import *
from .section3 import *
from .section4 import *
from .section5 import *
from .originating_centers import *


def get_table(table,expand=False):
    """
    Return GRIB2 code table as a dictionary.

    Parameters
    ----------

    **`table : str`**

    Code table number.  Example: '1.0'

    **`expand : bool`**

    When **`True`**, expand output dictionary where keys are a range. Default is **`false`**

    Returns
    -------

    **`dict`**    
    """
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


def get_value_from_table(value,table):
    """
    Return the meaning/definition given a GRIB2 code table `value` and `table`.

    Parameters
    ----------

    **`value : str`**

    Code table value.  Function will convert integer to string.  Example: '5'

    **`table : str`**

    Code table number.  Example: '1.0'

    Returns
    -------

    **`str` or `list`**
    """
    try:
        tbl = get_table(table,expand=True)
        if isinstance(value,int): value = str(value)
        return tbl[value]
    except(KeyError):
        return None


def get_varname_from_table(discipline,parmcat,parmnum):
    """
    Return the GRIB2 variable name information given values of `discipline`,
    `parmcat`, and `parmnum`. NOTE: This functions allows for all arguments
    to be converted to a string type if arguments are integer.

    Parameters
    ----------

    **`discipline : str`**

    Discipline code value of a GRIB2 message.

    **`parmcat : str`**

    Parameter Category value of a GRIB2 message.

    **`parmnum : str`**

    Parameter Number value of a GRIB2 message.

    Returns
    -------
    """
    if isinstance(discipline,int): discipline = str(discipline)
    if isinstance(parmcat,int): parmcat = str(parmcat)
    if isinstance(parmnum,int): parmnum = str(parmnum)
    tblname = 'table_4_2_'+discipline+'_'+parmcat
    modname = '.section4_discipline'+discipline
    exec('from '+modname+' import *')
    return locals()[tblname][parmnum]
