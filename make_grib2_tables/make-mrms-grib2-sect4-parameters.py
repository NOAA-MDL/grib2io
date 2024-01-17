#!/usr/bin/env python3

import pandas as pd

# ---------------------------------------------------------------------------------------- 
# Some variables.
# ---------------------------------------------------------------------------------------- 
startdict = '{'
enddict = '}\n'
discipline = 209

# ---------------------------------------------------------------------------------------- 
# Read the MRMS product table CSV file and remove "n/a" lines.
# ---------------------------------------------------------------------------------------- 
df = pd.read_csv('UserTable_MRMS_v12.2.csv')
df = df[df['Discipline']==str(discipline)]

# ---------------------------------------------------------------------------------------- 
# Create a list of unique parameter categories.
# ---------------------------------------------------------------------------------------- 
parmcats = [int(n) for n in set(list(df.Category.values))]

# ---------------------------------------------------------------------------------------- 
# Iterate over parameter categories, then rows matching, and create the dictionary entry.
# ---------------------------------------------------------------------------------------- 
for pc in parmcats:
    dictname = f'table_4_2_{discipline}_{pc} = {startdict}'
    print(dictname)
    df2 = df[df['Category']==float(pc)]
    for idx,row in df2.iterrows():
        parmcat = int(row['Category'])
        parmnum = int(row['Parameter'])
        name = row['Name']
        unit = row['Unit']
        description = row['Description']
        line = f'\'{str(parmnum)}\':[\'{description}\',\'{unit}\',\'{name}\'],'
        print(line)
    print(enddict)
