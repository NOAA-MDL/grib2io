/* This is a test for the NCEPLIBS-g2c project. This test is for
 * gbits.c.
 *
 * Ed Hartnett 7/19/21
 */

#include <stdio.h>
#include "grib2.h"

#define G2C_ERROR 2

int
main()
{
    
    printf("Testing sbit.\n");
    printf("Testing simple sbit() call...");
    {
	unsigned char out[1] = {0x00};
	g2int in[1] = {0x01};
	
	sbit(out, in, 0, 8);
	if (out[0] != 1)
	    return G2C_ERROR;
    }
    printf("ok!\n");
    /* printf("Testing more sbit() calls..."); */
    /* { */
    /* 	unsigned char out; */
    /* 	g2int in = 1; */
    /* 	g2int expected_out[8] = {0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01}; */
    /* 	int i; */

    /* 	for (i = 0; i < 8; i++) */
    /* 	{ */
    /* 	    sbit(&out, &in, 0, i + 1); */
    /* 	    /\* printf("in 0x%02x out 0x%02x\n", in, out); *\/ */
    /* 	    if (out != expected_out[i]) */
    /* 		return G2C_ERROR; */
    /* 	} */
    /* } */
    /* printf("ok!\n"); */
    printf("SUCCESS!\n");
    return 0;
}
