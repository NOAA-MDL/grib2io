#!/bin/bash

# This script documents the process of subsetting the GFS data to only include
# the message necessary for testing. This is done to reduce the size of the
# data and make it easier to work with.

# This script is only run once to subset the data.
#
# Take the "mandatory" pressure levels along with the 2m messages:
# 1000 mb, 925 mb, 850 mb, 700 mb, 500 mb, 300 mb, 250 mb, 200 mb, 150 mb, 2 m
# Also take the REFC message for radar reflectivity which is used in the
# testing.
#
# Remove the GRLE, O3MR, and RWMR messages which are not used in the testing.
#
# The output is saved to a temporary file then replaces the original.
for filename in *_subset; do
    wgrib2 "${filename}" | grep -e '1000 mb\|925 mb\|850 mb\|700 mb\|500 mb\|300 mb\|250 mb\|200 mb\|150 mb\|2 m \|:TMP:' -e REFC | grep -v 'GRLE\|O3MR\|RWMR' | wgrib2 -i "${filename}" -grib tmpfile
    mv tmpfile "${filename}"
done
