# This is the cmake build file for the tests directory of the
# NCEPLIBS-g2c_UTILS project.
#
# Ed Hartnett, 7/11/21
# Dusan Jovic

function(g2c_test name)
  add_executable(${name} ${name}.c)
  add_dependencies(${name} g2c)
  target_link_libraries(${name} PRIVATE g2c)
  add_test(NAME ${name} COMMAND ${name})
endfunction()

g2c_test(tst_g2_create)
g2c_test(tst_decode)
g2c_test(tst_gbits)
