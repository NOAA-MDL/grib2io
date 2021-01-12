from .. import tables
from .. import utils

"""
section1_template is a dictionary where keys are the grib2io's GRIB2 section 1 keys and the value
is a list.  The first element in the list is a function (or None).  The second element is another
list with args for said function.  The eval builtin is necessary for this template layout.

This template dictionary is used in by grib2io.templates.set_section1_keys().
"""
section1_template = {
'originatingCenter': [tables.get_value_from_table,["eval('a[0]')",'originating_centers']],
'originatingSubCenter': [tables.get_value_from_table,["eval('a[1]')",'originating_subcenters']],
'masterTableInfo': [tables.get_value_from_table,["eval('a[2]')",'1.0']],
'localTableInfo': [tables.get_value_from_table,["eval('a[3]')",'1.1']],
'significanceOfReferenceTime': [tables.get_value_from_table,["eval('a[4]')",'1.2']],
'year': [None,["eval('a[5]')"]],
'month': [None,["eval('a[6]')"]],
'day': [None,["eval('a[7]')"]],
'hour': [None,["eval('a[8]')"]],
'minute': [None,["eval('a[9]')"]],
'second': [None,["eval('a[10]')"]],
'intReferenceDate': [utils.getdate,["eval('a[slice(5,11)]')"]],
'dtReferenceDate': [None,[]],
'productionStatus': [tables.get_value_from_table,["eval('a[11]')",'1.3']],
'typeOfData': [tables.get_value_from_table,["eval('a[12]')",'1.4']],
}
