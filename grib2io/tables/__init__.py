from .section0 import *
from .section1 import *
from .section3 import *
from .section4 import *

from .originating_centers import *


def get_table(table,expand=False):
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
    """
    try:
        tbl = get_table(table,expand=True)
        if isinstance(value,int): value = str(value)
        return tbl[value]
    except(KeyError):
        return None


def get_varname_from_table(discipline,parmcat,parmnum):
    """
    """
    if isinstance(discipline,int): discipline = str(discipline)
    if isinstance(parmcat,int): parmcat = str(parmcat)
    if isinstance(parmnum,int): parmnum = str(parmnum)
    tblname = 'table_4_2_'+discipline+'_'+parmcat
    modname = '.section4_discipline'+discipline
    exec('from '+modname+' import *')
    return locals()[tblname][parmnum]
