#!/bin/sh

# ----------------------------------------------------------------------------------------
# Originating Centers
# ----------------------------------------------------------------------------------------
echo " -- Making originating_centers.py"
./get-ncep-grib2-originating-centers.py > originating_centers.py

# ----------------------------------------------------------------------------------------
# Generate Section 0
# ----------------------------------------------------------------------------------------
echo " -- Making section0.py"
if [ -f section0.py ]; then rm -f section0.py; fi
for table in 0.0
do
   echo "\t - Table $table"
   ./get-ncep-grib2-table.py $table > section0.py
done

# ----------------------------------------------------------------------------------------
# Generate Section 1
# ----------------------------------------------------------------------------------------
echo " -- Making section1.py"
if [ -f section1.py ]; then rm -f section1.py; fi
for table in 1.0 1.1 1.2 1.3 1.4 1.5 1.6
do
   echo "\t - Table $table"
   ./get-ncep-grib2-table.py $table >> section1.py
done

# ----------------------------------------------------------------------------------------
# Generate Section 3
# ----------------------------------------------------------------------------------------
echo " -- Making section3.py"
if [ -f section3.py ]; then rm -f section3.py; fi
for table in 3.0 3.1 3.2 3.11
do
   echo "\t - Table $table"
   ./get-ncep-grib2-table.py $table >> section3.py
done
sed 's/Unstructublack/Unstructured/g' section3.py > junk
mv -v junk section3.py

# Store the Earth params table here.  This is custom to grib2io.
echo "\t - Earth params table"
cat << EOF >> section3.py
table_earth_params = {
'0':{'shape':'spherical','radius':6367470.0},
'1':{'shape':'spherical','radius':None},
'2':{'shape':'oblateSpheriod','major_axis':6378160.0,'minor_axis':6356775.0,'flattening':1.0/297.0},
'3':{'shape':'oblateSpheriod','major_axis':None,'minor_axis':None,'flattening':None},
'4':{'shape':'oblateSpheriod','major_axis':6378137.0,'minor_axis':6356752.314,'flattening':1.0/298.257222101},
'5':{'shape':'ellipsoid','major_axis':6378137.0,'minor_axis':6356752.3142,'flattening':1.0/298.257222101},
'6':{'shape':'spherical','radius':6371229.0},
'7':{'shape':'oblateSpheriod','major_axis':None,'minor_axis':None,'flattening':None},
'8':{'shape':'spherical','radius':6371200.0},
}
for i in range(9,256):
    table_earth_params[str(i)] = {'shape':'unknown','radius':None}
EOF

# ----------------------------------------------------------------------------------------
# Generate Section 4 Tables for parameter categories and parameter tables unique for each
# discipline.
#
# NOTE: Table 4.225 references a PDF file.
# ----------------------------------------------------------------------------------------
echo " -- Making section4.py"
if [ -f section4.py ]; then rm -f section4.py; fi
echo "\t - Parameter category tables"
./get-ncep-grib2-sect4-category-table.py > section4.py
for table in $(cat list_section4_tables.txt)
do
   echo "\t - Table $table"
   ./get-ncep-grib2-table.py $table >> section4.py
done
echo "\t - GRIB2 Time to Hours Table"
cat << EOF >> section4.py
table_scale_time_seconds = {
'0': 60.,
'1': 3600.,
'2': float(3600. * 24.),
'3': float(3600. * 24. * 30.),
'4': float(3600. * 24. * 365.),
'5': float(3600. * 24. * 365. * 10.),
'6': float(3600. * 24. * 365. * 30.),
'7': float(3600. * 24. * 365. * 100.),
'8': 1.,
'9': 1.,
'10': float(3600. * 3.),
'11': float(3600. * 6.),
'12': float(3600. * 12.),
'13': 1.,
'14-255': 1.}
EOF
echo "\t - wgrib2 Level/Layer String Table"
cat table_wgrib2_level_string.txt >> section4.py
echo "\t - Aerosols Tables"
cat table_aerosols.txt >> section4.py
echo "\t - grib2io custom level names"
cat table_grib2io_custom_level_names.txt >> section4.py

# Discipline 0
echo " -- Making section4_discipline0.py"
if [ -f section4_discipline0.py ]; then rm -f section4_discipline0.py; fi
for table in $(seq 0 7 && seq 13 20 && seq 190 192)
do
   ./get-ncep-grib2-sect4-parameters-table.py 0 $table >> section4_discipline0.py
done
sed 's/Pblackomiunknownt/Predominant/g' section4_discipline0.py > junk
mv -v junk section4_discipline0.py

# NDFD Elements for Discipline 0
cat section4_discipline0.py table_ndfd_parameters_definitions.txt > junk
mv -v junk section4_discipline0.py

# Discipline 1
echo " -- Making section4_discipline1.py"
if [ -f section4_discipline1.py ]; then rm -f section4_discipline1.py; fi
for table in $(seq 0 2)
do
   ./get-ncep-grib2-sect4-parameters-table.py 1 $table >> section4_discipline1.py
done

# Discipline 2
echo " -- Making section4_discipline2.py"
if [ -f section4_discipline2.py ]; then rm -f section4_discipline2.py; fi
for table in 0 1 3 4 5
do
   ./get-ncep-grib2-sect4-parameters-table.py 2 $table >> section4_discipline2.py
done

# Discipline 3
echo " -- Making section4_discipline3.py"
if [ -f section4_discipline3.py ]; then rm -f section4_discipline3.py; fi
for table in 0 1 2 3 4 5 6 192
do
   ./get-ncep-grib2-sect4-parameters-table.py 3 $table >> section4_discipline3.py
done

# Discipline 4
echo " -- Making section4_discipline4.py"
if [ -f section4_discipline4.py ]; then rm -f section4_discipline4.py; fi
for table in $(seq 0 9)
do
   ./get-ncep-grib2-sect4-parameters-table.py 4 $table >> section4_discipline4.py
done

# Discipline 10
echo " -- Making section4_discipline10.py"
if [ -f section4_discipline10.py ]; then rm -f section4_discipline10.py; fi
for table in 0 1 2 3 4 191
do
   ./get-ncep-grib2-sect4-parameters-table.py 10 $table >> section4_discipline10.py
done

# Discipline 20
echo " -- Making section4_discipline20.py"
if [ -f section4_discipline20.py ]; then rm -f section4_discipline20.py; fi
for table in 0 1 2
do
   ./get-ncep-grib2-sect4-parameters-table.py 20 $table >> section4_discipline20.py
done

# Discipline 209 - MRMS GRIB2 Products
echo " -- Making section4_discipline209.py"
if [ -f section4_discipline209.py ]; then rm -f section4_discipline209.py; fi
./make-mrms-grib2-sect4-parameters.py >> section4_discipline209.py

# ----------------------------------------------------------------------------------------
# Remove "See Note" strings from section 4 discipline files.
# ----------------------------------------------------------------------------------------
for f in $(grep -l '([Ss]ee [Nn]ote [1-9]*)' section*.py)
do
   sed 's/ ([Ss]ee [Nn]ote [1-9]*)//g' $f > junk
   mv -v junk $f
done

# ----------------------------------------------------------------------------------------
# Generate Section 5
# ----------------------------------------------------------------------------------------
echo " -- Making section5.py"
if [ -f section5.py ]; then rm -f section5.py; fi
for table in 5.0 5.1 5.2 5.3 5.4 5.5 5.6 5.7 5.40
do
   echo "\t - Table $table"
   ./get-ncep-grib2-table.py $table >> section5.py
done
sed "s/:'201-49151',/:'Reserved',/g" section5.py > junk
mv -v junk section5.py

# ----------------------------------------------------------------------------------------
# Generate Section 6
# ----------------------------------------------------------------------------------------
echo " -- Making section6.py"
if [ -f section6.py ]; then rm -f section6.py; fi
for table in 6.0
do
   echo "\t - Table $table"
   ./get-ncep-grib2-table.py $table >> section6.py
done

# ----------------------------------------------------------------------------------------
# NDFD Keys
# ----------------------------------------------------------------------------------------
echo " -- Making ndfd_additionals.py"
cat table_ndfd_additionals.txt >> ndfd_additionals.py

# ----------------------------------------------------------------------------------------
# CF Tables
# ----------------------------------------------------------------------------------------
echo " -- Making cf.py"
cat table_cf.txt >> cf.py
