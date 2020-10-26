# *** manually set environments (for intel compiler) of g2c ***

 : ${USERMODE:=false}  # user mode (USERMODE) is closed by default
                       # set env var USERMODE to "true" to active it
 ${USERMODE} && {
    echo "Environment set by user"
# On theia/cray, user can load environment
    module load intel/18.0.1.163
 }

#  JASPER, PNG and Z LIB in default system include *
#  *** set nothing ***

#  WCOSS WCOSS WCOSS WCOSS WCOSS WCOSS WCOSS WCOSS *
#JPZlib=/nwprod2/lib
#JASPER_VER=v1.900.1
#PNG_VER=v1.2.44
#Z_VER=v1.2.6
#JASPER_INC=$JPZlib/jasper/v1.900.1/include
#PNG_INC=$JPZlib/png/v1.2.44/include
#Z_INC=$JPZlib/z/v1.2.6/include

#  THEIA THEIA THEIA THEIA THEIA THEIA THEIA THEIA *
#JPZlib=/scratch3/NCEPDEV/nwprod/lib
#JASPER_VER=v1.900.1
#PNG_VER=v1.2.44
#Z_VER=v1.2.6
#JASPER_INC=$JPZlib/jasper/v1.900.1/include
#PNG_INC=$JPZlib/png/v1.2.44/src/include
#Z_INC=$JPZlib/z/v1.2.6/include

 export CC=icc
 export FC=ifort
 export CPP=cpp
 export OMPCC="$CC -qopenmp"
 export OMPFC="$FC -qopenmp"
 export MPICC=mpiicc
 export MPIFC=mpiifort

 export DEBUG="-g -traceback -O0"
 export CFLAGS="-g -traceback -O3 -fPIC"
 export FFLAGS="-g -traceback -O3 -fPIC"
 export FPPCPP="-cpp"
 export FREEFORM="-free"
 export CPPFLAGS="-P -traditional-cpp"
 export MPICFLAGS="-g -traceback -O3 -fPIC"
 export MPIFFLAGS="-g -traceback -O3 -xHOST -fPIC"
 export MODPATH="-module "
 export I4R4="-integer-size 32 -real-size 32"
 export I4R8="-integer-size 32 -real-size 64"
 export I8R8="-integer-size 64 -real-size 64"

 export CPPDEFS=""
 [[ -z "${PNG_INC-}" ]] && { IPNG= ; } || { IPNG=-I$PNG_INC; }
 [[ -z "${JASPER_INC-}" ]] && { IJASPER= ; } || { IJASPER=-I$JASPER_INC; }
 [[ -z "${Z_INC-}" ]] && { IZ= ; } || { IZ=-I$Z_INC; }
 export CFLAGSDEFS="$IPNG $IJASPER $IZ -DUNDERSCORE -DLINUX -DUSE_JPEG2000 -DUSE_PNG -D__64BIT__"
 export FFLAGSDEFS=""

 export USECC="YES"
 export USEFC=""
 export DEPS="JASPER ${JASPER_VER-}, LIBPNG ${PNG_VER-}, ZLIB ${Z_VER-}"
