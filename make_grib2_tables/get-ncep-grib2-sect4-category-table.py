#!/usr/bin/env python3

import pandas as pd

# ---------------------------------------------------------------------------------------- 
# URL for GRIB2 Section 4 Table 4.1
# ---------------------------------------------------------------------------------------- 
url = r'https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-1.shtml'
tables = pd.read_html(url)

# ---------------------------------------------------------------------------------------- 
# Iterate over tables, looking for product discipline tables embedded in the other HTML
# table.
# ---------------------------------------------------------------------------------------- 
for df in tables:
    if "Product Discipline" not in df.iloc[0][0]: continue
    discipline = ''.join(i for i in df.iloc[0][0] if i.isdigit())
    df.drop(0,inplace=True)
    df.columns = df.iloc[0]
    df.drop(1,inplace=True)
    df.columns = ['Category','Description']

    name = 'table_4_1_'+discipline
    print(name,"= {")
    for idx,row in df.iterrows():
        category = row['Category']
        description = row['Description'].strip().split('(')[0].strip()
        line = "'%s':'%s'," % (category,description)
        print(line)
    print("}")
    print("")
