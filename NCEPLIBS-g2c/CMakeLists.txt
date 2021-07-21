# This is the main CMake file for NCEPLIBS-ip.
#
# Mark Potts, Kyle Gerheiser
cmake_minimum_required(VERSION 3.15)

file(STRINGS "VERSION" pVersion)

project(
  g2c
  VERSION ${pVersion}
  LANGUAGES C)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake/")

# Handle user options.
option(ENABLE_DOCS "Enable generation of doxygen-based documentation." OFF)
option(USE_PNG      "Use PNG library"      ON)
option(USE_Jasper   "Use Jasper library"   ON)
option(USE_OpenJPEG "Use OpenJPEG library" OFF)

if(NOT CMAKE_BUILD_TYPE MATCHES "^(Debug|Release|RelWithDebInfo|MinSizeRel)$")
  message(STATUS "Setting build type to 'Release' as none was specified.")
  set(CMAKE_BUILD_TYPE
      "Release"
      CACHE STRING "Choose the type of build." FORCE)
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release"
                                               "MinSizeRel" "RelWithDebInfo")
endif()

if(USE_PNG)
  find_package(ZLIB REQUIRED)
  find_package(PNG REQUIRED)
else()
  message(STATUS "Will not build PNG support")
endif()

if(USE_Jasper)
  find_package(Jasper REQUIRED)
else()
  message(STATUS "Will not build Jasper support")
endif()

if(USE_OpenJPEG)
  find_package(OpenJPEG REQUIRED)
else()
  message(STATUS "Will not build OpenJPEG support")
endif()

if(CMAKE_C_COMPILER_ID MATCHES "^(Intel)$")
  set(CMAKE_C_FLAGS "-g -traceback")
  set(CMAKE_C_FLAGS_RELEASE "-O3")
  set(CMAKE_C_FLAGS_DEBUG "-O0")
elseif(CMAKE_C_COMPILER_ID MATCHES "^(GNU|Clang|AppleClang)$")
  set(CMAKE_C_FLAGS "-g")
  set(CMAKE_C_FLAGS_RELEASE "-O3")
  set(CMAKE_C_FLAGS_DEBUG "-O0 -ggdb -Wall")
endif()

add_subdirectory(src)

set(lib_name ${PROJECT_NAME})

add_library(${lib_name} STATIC ${c_src})

target_compile_definitions(${lib_name} PUBLIC __64BIT__)

set(private_includes "")

if(PNG_FOUND)
  message(STATUS "Found PNG:")
  message(STATUS "      PNG include directories ${PNG_INCLUDE_DIR}")
  message(STATUS "      PNG libraries ${PNG_LIBRARIES}")
  target_compile_definitions(${lib_name} PRIVATE USE_PNG)
  target_link_libraries(${lib_name} INTERFACE ${PNG_LIBRARIES})
  list(APPEND private_includes "${PNG_INCLUDE_DIRS}")
endif()

if(JASPER_FOUND)
  message(STATUS "Found JASPER:")
  message(STATUS "      JASPER include directories ${JASPER_INCLUDE_DIR}")
  message(STATUS "      JASPER libraries ${JASPER_LIBRARIES}")
  target_compile_definitions(${lib_name} PRIVATE USE_JPEG2000)
  target_link_libraries(${lib_name} INTERFACE ${JASPER_LIBRARIES})
  list(APPEND private_includes "${JASPER_INCLUDE_DIR}")
endif()

if(OPENJPEG_FOUND)
  message(STATUS "Found OpenJPEG:")
  message(STATUS "      OpenJPEG include directories ${OpenJPEG_INCLUDE_DIRS}")
  message(STATUS "      OpenJPEG libraries ${OpenJPEG_LIBRARIES}")
  target_compile_definitions(${lib_name} PRIVATE USE_OPENJPEG)
  target_link_libraries(${lib_name} INTERFACE ${OpenJPEG_LIBRARIES})
  list(APPEND private_includes "${OpenJPEG_INCLUDE_DIRS}")
endif()

target_link_libraries(${lib_name} INTERFACE m)

set_target_properties(${lib_name} PROPERTIES PUBLIC_HEADER "src/grib2.h")

target_include_directories(
  ${lib_name}
  PRIVATE ${private_includes}
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
         $<INSTALL_INTERFACE:${CMAKE_INSTALL_PREFIX}/include>
)

### Install g2c library
install(
  TARGETS ${lib_name}
  EXPORT ${PROJECT_NAME}Exports
  RUNTIME DESTINATION bin
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
  PUBLIC_HEADER DESTINATION include)

### Package config
include(CMakePackageConfigHelpers)
set(CONFIG_INSTALL_DESTINATION lib/cmake/${PROJECT_NAME})

export(EXPORT ${PROJECT_NAME}Exports
  NAMESPACE ${PROJECT_NAME}::
  FILE ${PROJECT_NAME}-targets.cmake)

# g2c-config.cmake
configure_package_config_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/PackageConfig.cmake.in ${CMAKE_BINARY_DIR}/${PROJECT_NAME}-config.cmake
  INSTALL_DESTINATION ${CONFIG_INSTALL_DESTINATION})
install(FILES ${CMAKE_BINARY_DIR}/${PROJECT_NAME}-config.cmake
  DESTINATION ${CONFIG_INSTALL_DESTINATION})

# g2c-config-version.cmake
write_basic_package_version_file(
  ${CMAKE_BINARY_DIR}/${PROJECT_NAME}-config-version.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY AnyNewerVersion)
install(FILES ${CMAKE_BINARY_DIR}/${PROJECT_NAME}-config-version.cmake
  DESTINATION ${CONFIG_INSTALL_DESTINATION})

# g2c-targets.cmake and g2c-targets-<build-type>.cmake
install(EXPORT ${PROJECT_NAME}Exports
  NAMESPACE ${PROJECT_NAME}::
  FILE ${PROJECT_NAME}-targets.cmake
  DESTINATION ${CONFIG_INSTALL_DESTINATION})

# Determine whether or not to generate documentation.
if(ENABLE_DOCS)
  find_package(Doxygen REQUIRED)
endif()
add_subdirectory(docs)  
