#!/usr/bin/env python3

import pandas as pd
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
    parmname = row['Parameter'].strip()
    parmname = parmname.replace("\'",'')
    units = row['Units'] if row['Units'] != 'nan' else 'unknown'
    abbrev = row['Abbrev'] if row['Abbrev'] != 'nan' else 'unknown'
    line = "'%s':['%s','%s','%s']," % (parmnum,parmname,units,abbrev)
    line = line.replace('nan','unknown')
    print(line)
print("}")
