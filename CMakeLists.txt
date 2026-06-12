cmake_minimum_required(VERSION 3.18)
project(grib2io LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)

function(grib2io_env_bool ENV_NAME DEFAULT_VALUE OUT_VAR)
  if(DEFINED ENV{${ENV_NAME}})
    string(TOUPPER "$ENV{${ENV_NAME}}" _env_val)
    if(_env_val STREQUAL "1" OR _env_val STREQUAL "ON" OR _env_val STREQUAL "TRUE" OR _env_val STREQUAL "YES")
      set(_out ON)
    elseif(_env_val STREQUAL "0" OR _env_val STREQUAL "OFF" OR _env_val STREQUAL "FALSE" OR _env_val STREQUAL "NO")
      set(_out OFF)
    else()
      message(FATAL_ERROR "Environment variable ${ENV_NAME} must be a boolean (True/False, On/Off, 1/0)")
    endif()
  else()
    set(_out ${DEFAULT_VALUE})
  endif()
  set(${OUT_VAR} ${_out} PARENT_SCOPE)
endfunction()

function(grib2io_python_bool VALUE OUT_VAR)
  if(${VALUE})
    set(${OUT_VAR} "True" PARENT_SCOPE)
  else()
    set(${OUT_VAR} "False" PARENT_SCOPE)
  endif()
endfunction()

function(grib2io_find_library OUT_VAR)
  set(options REQUIRED STATIC)
  set(oneValueArgs)
  set(multiValueArgs NAMES HINTS)
  cmake_parse_arguments(PARSE_ARGV 1 ARG "${options}" "${oneValueArgs}" "${multiValueArgs}")

  if(ARG_STATIC)
    set(_saved_suffixes ${CMAKE_FIND_LIBRARY_SUFFIXES})
    set(CMAKE_FIND_LIBRARY_SUFFIXES ".a")
  endif()

  if(ARG_REQUIRED)
    find_library(_lib NAMES ${ARG_NAMES} HINTS ${ARG_HINTS} PATH_SUFFIXES lib lib64 REQUIRED)
  else()
    find_library(_lib NAMES ${ARG_NAMES} HINTS ${ARG_HINTS} PATH_SUFFIXES lib lib64)
  endif()

  if(ARG_STATIC)
    set(CMAKE_FIND_LIBRARY_SUFFIXES ${_saved_suffixes})
  endif()

  set(${OUT_VAR} ${_lib} PARENT_SCOPE)
endfunction()

function(grib2io_add_cython_module TARGET_NAME PYX_FILE)
  set(_generated_c "${CMAKE_CURRENT_BINARY_DIR}/${TARGET_NAME}.c")

  add_custom_command(
    OUTPUT ${_generated_c}
    COMMAND "${Python_EXECUTABLE}" -m cython -3 --fast-fail -o ${_generated_c} ${PYX_FILE}
    DEPENDS ${PYX_FILE}
    VERBATIM
  )

  Python_add_library(${TARGET_NAME} MODULE WITH_SOABI ${_generated_c})
  set_target_properties(${TARGET_NAME} PROPERTIES PREFIX "" OUTPUT_NAME "${TARGET_NAME}")

  target_include_directories(${TARGET_NAME} PRIVATE ${Python_INCLUDE_DIRS})
  target_compile_definitions(${TARGET_NAME} PRIVATE NPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION)

  install(TARGETS ${TARGET_NAME} LIBRARY DESTINATION grib2io)
endfunction()

execute_process(
  COMMAND "${Python_EXECUTABLE}" -c "import numpy; print(numpy.get_include())"
  OUTPUT_VARIABLE NUMPY_INCLUDE_DIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
)
if(NOT NUMPY_INCLUDE_DIR)
  message(FATAL_ERROR "Unable to determine NumPy include directory")
endif()

# -----------------------------------------------------------------------------
# Read version from VERSION file
# -----------------------------------------------------------------------------
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" GRIB2IO_VERSION)
string(STRIP "${GRIB2IO_VERSION}" GRIB2IO_VERSION)

# -----------------------------------------------------------------------------
# Build options (defaults can be overridden with env vars or cmake.define)
# -----------------------------------------------------------------------------
option(GRIB2IO_WITH_IP "Build with NCEPLIBS-ip interpolation support when available" ON)
grib2io_env_bool("G2C_STATIC" OFF GRIB2IO_G2C_STATIC)
grib2io_env_bool("IP_STATIC" OFF GRIB2IO_IP_STATIC)

set(_g2c_hints)
set(_conda_prefix_hints)

if(DEFINED ENV{CONDA_PREFIX})
  list(APPEND _conda_prefix_hints "$ENV{CONDA_PREFIX}")
endif()
if(DEFINED ENV{CONDA_ROOT})
  list(APPEND _conda_prefix_hints "$ENV{CONDA_ROOT}")
endif()
if(DEFINED ENV{MAMBA_ROOT_PREFIX})
  list(APPEND _conda_prefix_hints "$ENV{MAMBA_ROOT_PREFIX}")
endif()

if(DEFINED ENV{G2C_INCDIR})
  list(APPEND _g2c_include_hints "$ENV{G2C_INCDIR}")
endif()
if(DEFINED ENV{G2C_LIBDIR})
  list(APPEND _g2c_hints "$ENV{G2C_LIBDIR}")
endif()
if(DEFINED ENV{G2C_DIR})
  list(APPEND _g2c_include_hints "$ENV{G2C_DIR}" "$ENV{G2C_DIR}/include")
  list(APPEND _g2c_hints "$ENV{G2C_DIR}" "$ENV{G2C_DIR}/lib" "$ENV{G2C_DIR}/lib64")
endif()

foreach(_prefix IN LISTS _conda_prefix_hints)
  list(APPEND _g2c_include_hints "${_prefix}" "${_prefix}/include")
  list(APPEND _g2c_hints "${_prefix}" "${_prefix}/lib" "${_prefix}/lib64")
endforeach()

list(APPEND _g2c_include_hints /usr /usr/local /opt/homebrew /opt/local /opt)
list(APPEND _g2c_hints /usr /usr/local /opt/homebrew /opt/local /opt)

find_path(G2C_INCLUDE_DIR grib2.h HINTS ${_g2c_include_hints} PATH_SUFFIXES include REQUIRED)
if(GRIB2IO_G2C_STATIC)
  grib2io_find_library(G2C_LIBRARY REQUIRED STATIC NAMES g2c HINTS ${_g2c_hints})
else()
  grib2io_find_library(G2C_LIBRARY REQUIRED NAMES g2c HINTS ${_g2c_hints})
endif()
get_filename_component(G2C_LIBRARY_DIR "${G2C_LIBRARY}" DIRECTORY)

# -----------------------------------------------------------------------------
# g2clib extension module
# -----------------------------------------------------------------------------
grib2io_add_cython_module(g2clib "${CMAKE_CURRENT_SOURCE_DIR}/src/ext/g2clib.pyx")
target_include_directories(g2clib PRIVATE "${G2C_INCLUDE_DIR}" "${NUMPY_INCLUDE_DIR}")
target_link_libraries(g2clib PRIVATE "${G2C_LIBRARY}")
set_property(TARGET g2clib PROPERTY INSTALL_RPATH "${G2C_LIBRARY_DIR}")

# -----------------------------------------------------------------------------
# redtoreg extension module
# -----------------------------------------------------------------------------
grib2io_add_cython_module(redtoreg "${CMAKE_CURRENT_SOURCE_DIR}/src/ext/redtoreg.pyx")
target_include_directories(redtoreg PRIVATE "${NUMPY_INCLUDE_DIR}")

# -----------------------------------------------------------------------------
# Optional iplib extension module
# -----------------------------------------------------------------------------
set(GRIB2IO_HAS_INTERPOLATION OFF)
set(GRIB2IO_HAS_OPENMP OFF)

if(GRIB2IO_WITH_IP)
  set(_ip_hints)
  set(_ip_include_hints)

  if(DEFINED ENV{IP_INCDIR})
    list(APPEND _ip_include_hints "$ENV{IP_INCDIR}")
  endif()
  if(DEFINED ENV{IP_LIBDIR})
    list(APPEND _ip_hints "$ENV{IP_LIBDIR}")
  endif()
  if(DEFINED ENV{IP_DIR})
    list(APPEND _ip_include_hints "$ENV{IP_DIR}" "$ENV{IP_DIR}/include" "$ENV{IP_DIR}/include_d")
    list(APPEND _ip_hints "$ENV{IP_DIR}" "$ENV{IP_DIR}/lib" "$ENV{IP_DIR}/lib64")
  endif()

  foreach(_prefix IN LISTS _conda_prefix_hints)
    list(APPEND _ip_include_hints "${_prefix}" "${_prefix}/include" "${_prefix}/include_d")
    list(APPEND _ip_hints "${_prefix}" "${_prefix}/lib" "${_prefix}/lib64")
  endforeach()

  list(APPEND _ip_include_hints /usr /usr/local /opt/homebrew /opt/local /opt)
  list(APPEND _ip_hints /usr /usr/local /opt/homebrew /opt/local /opt)

  find_path(IP_INCLUDE_DIR iplib.h HINTS ${_ip_include_hints} PATH_SUFFIXES include_d include)

  if(GRIB2IO_IP_STATIC)
    grib2io_find_library(IP_LIBRARY STATIC NAMES ip_d ip HINTS ${_ip_hints})
  else()
    grib2io_find_library(IP_LIBRARY NAMES ip_d ip HINTS ${_ip_hints})
  endif()

  if(IP_INCLUDE_DIR AND IP_LIBRARY)
    set(GRIB2IO_HAS_INTERPOLATION ON)
    get_filename_component(IP_LIBRARY_DIR "${IP_LIBRARY}" DIRECTORY)

    grib2io_add_cython_module(iplib "${CMAKE_CURRENT_SOURCE_DIR}/src/ext/iplib.pyx")
    target_include_directories(iplib PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src/ext" "${IP_INCLUDE_DIR}" "${NUMPY_INCLUDE_DIR}")
    target_link_libraries(iplib PRIVATE "${IP_LIBRARY}")
    set_property(TARGET iplib PROPERTY INSTALL_RPATH "${IP_LIBRARY_DIR}")

    find_package(OpenMP)
    if(OpenMP_C_FOUND)
      set(GRIB2IO_HAS_OPENMP ON)
      target_link_libraries(iplib PRIVATE OpenMP::OpenMP_C)
      target_compile_definitions(iplib PRIVATE IPLIB_WITH_OPENMP)
    endif()
  else()
    message(WARNING "NCEPLIBS-ip not found. grib2io will build without interpolation support.")
  endif()
endif()

# -----------------------------------------------------------------------------
# Generate runtime build configuration module
# -----------------------------------------------------------------------------
set(GRIB2IO_EXTRA_OBJECTS "[]")
grib2io_python_bool(GRIB2IO_G2C_STATIC GRIB2IO_G2C_STATIC_PY)
grib2io_python_bool(GRIB2IO_HAS_INTERPOLATION GRIB2IO_HAS_INTERPOLATION_PY)
grib2io_python_bool(GRIB2IO_IP_STATIC GRIB2IO_IP_STATIC_PY)
grib2io_python_bool(GRIB2IO_HAS_OPENMP GRIB2IO_HAS_OPENMP_PY)

configure_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/grib2io_config.py.in"
  "${CMAKE_CURRENT_BINARY_DIR}/__config__.py"
  @ONLY
)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/__config__.py" DESTINATION grib2io)

message(STATUS "grib2io version: ${GRIB2IO_VERSION}")
message(STATUS "NCEPLIBS-g2c static: ${GRIB2IO_G2C_STATIC}")
message(STATUS "Interpolation support: ${GRIB2IO_HAS_INTERPOLATION}")
message(STATUS "NCEPLIBS-ip static: ${GRIB2IO_IP_STATIC}")
message(STATUS "OpenMP support: ${GRIB2IO_HAS_OPENMP}")
