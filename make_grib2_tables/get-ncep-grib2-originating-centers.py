#!/usr/bin/env python3

import pandas as pd

# ---------------------------------------------------------------------------------------- 
# Originating Center
# ---------------------------------------------------------------------------------------- 
url = r'https://www.nco.ncep.noaa.gov/pmb/docs/on388/table0.html'

tables = pd.read_html(url)

df = tables[0]

name = 'table_originating_centers'

print(name," = {")
for idx,row in df.iterrows():
    value = row['VALUE'].lstrip('0') 
    center = row['CENTER'].replace('\'','') 
    line = "'%s':'%s'," % (value,center)
    line = line.replace('nan','unknown')
    print(line)
print("}")
print("")

# ---------------------------------------------------------------------------------------- 
# Originating Sub-Center
# ---------------------------------------------------------------------------------------- 
url = r'https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablec.html'

tables = pd.read_html(url)

df = tables[0]

name = 'table_originating_subcenters'

print(name," = {")
for idx,row in df.iterrows():
    value = row['VALUE']
    center = row['CENTER'].replace('\'','')
    line = "'%s':'%s'," % (value,center)
    line = line.replace('nan','unknown')
    print(line)
print("}")
print("")

# ---------------------------------------------------------------------------------------- 
# Generating Process
# ---------------------------------------------------------------------------------------- 
url = r'https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablea.html'

tables = pd.read_html(url)

df = tables[0]

name = 'table_generating_process'

print(name," = {")
for idx,row in df.iterrows():
    if pd.isnull(row['VALUE']): continue
    value = row['VALUE']
    if value == '00-01':
        value = '0-1'
    elif value == '07-09':
        value = '7-9'
    else:
        value = value.lstrip('0')
    center = row['MODEL'].replace('\'','')
    line = "'%s':'%s'," % (value,center)
    line = line.replace('nan','unknown')
    print(line)
print("}")
