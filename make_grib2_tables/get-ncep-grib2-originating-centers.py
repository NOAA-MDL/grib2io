#!/usr/bin/env python

from urllib.request import urlopen
import pandas as pd

# ----------------------------------------------------------------------------------------
# Get NCEP GRIB2 tables version
# ----------------------------------------------------------------------------------------
url = 'https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/'
page = urlopen(url).read()
for n in range(len(page)):
    try:
        if page[n:n+7].decode('utf-8') == 'Version':
            version = page[n:n+40].decode('utf-8')
            break
    except(UnicodeDecodeError):
        pass
version = version.split('<')[0]
version_num = version.split('-')[0].replace('Version','').strip()
# FUTURE: version_date = version.split('-')[1].strip()
# FUTURE: datetime.datetime.strptime(version_date,'%B %d, %Y')
print(f"_ncep_grib2_table_version = \'{version_num}\'\n")

# ----------------------------------------------------------------------------------------
# Originating Center
# ----------------------------------------------------------------------------------------
#url = r'https://www.nco.ncep.noaa.gov/pmb/docs/on388/table0.html'
url = r'https://www.nco.ncep.noaa.gov/pmb/docs/on388/tablea.html'

tables = pd.read_html(url)

df = tables[0]

name = 'table_originating_centers'

print(name," = {")
for idx,row in df.iterrows():
    if "-" in str(row['VALUE']):
        value = str(row['VALUE'])
    else:
        value = str(row['VALUE']).lstrip('0')
    center = str(row['MODEL']).replace('\'','')
    line = "'%s':'%s'," % (value,center)
    line = line.replace('nan','unknown')
    line = line.replace('  ',' ')
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
    line = line.replace('  ',' ')
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
    line = line.replace('  ',' ')
    print(line)
print("}")
