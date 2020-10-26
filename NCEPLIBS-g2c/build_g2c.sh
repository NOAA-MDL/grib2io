#!/bin/bash

 : ${THISDIR:=$(dirname $(readlink -f -n ${BASH_SOURCE[0]}))}
 CDIR=$PWD; cd $THISDIR

 source ./Conf/Analyse_args.sh
 source ./Conf/Collect_info.sh
 source ./Conf/Gen_cfunction.sh
 source ./Conf/Reset_version.sh

 if [[ ${sys} == "intel_general" ]]; then
   sys6=${sys:6}
   source ./Conf/G2c_${sys:0:5}_${sys6^}.sh
   rinst=false
 elif [[ ${sys} == "gnu_general" ]]; then
   sys4=${sys:4}
   source ./Conf/G2c_${sys:0:3}_${sys4^}.sh
   rinst=false
 else
   source ./Conf/G2c_intel_${sys^}.sh
 fi
 $CC --version &> /dev/null || {
   echo "??? G2C: compilers not set." >&2
   exit 1
 }
 [[ -z ${G2C_VER+x} || -z ${G2C_LIB4+x} ]] && {
   [[ -z ${libver+x} || -z ${libver} ]] && {
     echo "??? G2C: \"libver\" not set." >&2
     exit
   }
   G2C_LIB4=lib${libver}_4.a
   G2C_VER=v${libver##*_v}
 }

set -x
 g2cLib4=$(basename $G2C_LIB4)

#################
 cd src
#################

#-------------------------------------------------------------------
# Start building libraries
#
 echo
 echo "   ... build (i4/r4) g2c library ..."
 echo
   make clean LIB=$g2cLib4
   collect_info g2c 4 OneLine4 LibInfo4
   g2cInfo4=g2c_info_and_log4.txt
   $debg && make debug LIB=$g2cLib4 &> $g2cInfo4 \
         || make build LIB=$g2cLib4 &> $g2cInfo4
   make message MSGSRC="$(gen_cfunction $g2cInfo4 OneLine4 LibInfo4)" LIB=$g2cLib4

 $inst && {
#
#     Install libraries and source files
#
   $local && {
     instloc=..
     LIB_DIR=$instloc/lib
     [ -d $LIB_DIR ] || { mkdir -p $LIB_DIR; }
     LIB_DIR4=$LIB_DIR
     SRC_DIR=
   } || {
     $rinst && {
       LIB_DIR4=$(dirname ${G2C_LIB4})
       SRC_DIR=$G2C_SRC
     } || {
       LIB_DIR=$instloc/lib
       LIB_DIR4=$LIB_DIR
       SRC_DIR=$instloc/src/${libver}
       [[ $instloc == .. ]] && SRC_DIR=
     }
     [ -d $LIB_DIR4 ] || mkdir -p $LIB_DIR4
     [ -z $SRC_DIR ] || { [ -d $SRC_DIR ] || mkdir -p $SRC_DIR; }
   }

   make clean LIB=
   make install LIB=$g2cLib4 LIB_DIR=$LIB_DIR4 SRC_DIR=$SRC_DIR
 }
