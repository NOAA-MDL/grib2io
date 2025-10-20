#!/usr/bin/env python3

import pandas as pd
import re
import sys

# ----------------------------------------------------------------------------------------
# Handle command line args
# ----------------------------------------------------------------------------------------
if len(sys.argv) != 3:
    print("usage: ",sys.argv[0]," DISCIPLINE PARMCAT")
    exit(1)
discipline = sys.argv[1]
parmcat = sys.argv[2]

# ----------------------------------------------------------------------------------------
# Define URL according to DISCIPLINE and PARMCAT (Parameter Category)
# ----------------------------------------------------------------------------------------
url = r'https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-2-'+discipline+'-'+parmcat+'.shtml'
tables = pd.read_html(url)

# ----------------------------------------------------------------------------------------
# Update table column names
# ----------------------------------------------------------------------------------------
df = tables[0]
df.columns = df.iloc[0]
df = df.drop([0])
df.rename(columns={df.columns[0]:"Number"},inplace=True)

# ----------------------------------------------------------------------------------------
# Write table as Python dictionary
# ----------------------------------------------------------------------------------------
name = 'table_4_2_'+discipline+'_'+parmcat
print(name," = {")
for idx,row in df.iterrows():
    parmnum = row['Number']
    parmname = str(row['Parameter']).replace('*','').replace('- Parameter deprecated','').strip()
    parmname = parmname.replace("\'",'')
    units = str(row['Units'])
    units = re.sub(r"\bnan\b", "unknown", units)
    abbrev = str(row['Abbrev'])
    abbrev = re.sub(r"\bnan\b", "unknown", abbrev)
    line = "'%s':['%s','%s','%s']," % (parmnum,parmname,units,abbrev)
    line = re.sub(r"\bnan\b", "unknown", line)
    line = line.replace('  ',' ')
    print(line)
print("}")
