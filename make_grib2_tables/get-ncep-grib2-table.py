#!/usr/bin/env python3

import pandas as pd
import sys

# ---------------------------------------------------------------------------------------- 
# Handle command line args
# ---------------------------------------------------------------------------------------- 
if len(sys.argv) != 2:
    print("Usage: ",sys.argv[0]," TABLE")
    print("")
    print("Arguments:")
    print("\tTABLE - Table number in X.Y format (e.g. 4.0)")
    exit(0)
tblin = sys.argv[1]
if "." in tblin:
    tblin_html = tblin.replace(".","-")

# ---------------------------------------------------------------------------------------- 
# Define URL and read HTML table
# ---------------------------------------------------------------------------------------- 
url = r'https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table'+tblin_html+'.shtml'
tables = pd.read_html(url)

# ---------------------------------------------------------------------------------------- 
# Some NCEP HTML pages have multiple tables with other info than the desired GRIB2 table.
# ---------------------------------------------------------------------------------------- 
tbl_idx = -1
for i,t in enumerate(tables):
    if len(t) > 1: tbl_idx = i
df = tables[tbl_idx]

# ---------------------------------------------------------------------------------------- 
# Table 4.5 has a units column with no column heading.
# ---------------------------------------------------------------------------------------- 
if tblin == '4.5':
    df.columns = df.iloc[0]
    df.rename(columns={df.columns[2]:"Units"},inplace=True)
    df = df.drop([0])

# ---------------------------------------------------------------------------------------- 
# Convert Pandas DataFrame table into Python dictionary syntax
# ---------------------------------------------------------------------------------------- 
name = 'table_'+tblin.replace(".","_")
print("%s = {"%(name))
for idx,row in df.iterrows():
    try:
        value = row['Code Figure']
    except(KeyError):
        value = row['Number']
    if not isinstance(row['Meaning'],str): continue
    center = row['Meaning'].replace('\'','')

    # For tables listed, remove parenthetical text.
    if tblin in ['0.0','1.6']:
        center = center.split('(')[0].strip()

    # For 4.5, format the dictionary key/value pair according to its contents.
    if tblin == '4.5':
        units = row['Units']
        line = "'%s':['%s','%s']," % (value,center,units)
    else:
        line = "'%s':'%s'," % (value,center)
    line = line.replace('nan','unknown')
    print(line)

    # For table 1.0, for some reason, I cannot figure out, a row is not present in the
    # pandas read_html, so manually add here.
    if tblin == '1.0' and value == '24':
        line = "'25':'Pre-operational to be implemented by next amendment',"
        print(line)
print("}")
print("")
