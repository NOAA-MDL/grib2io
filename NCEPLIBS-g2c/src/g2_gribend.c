/** @file
 * @brief Finalize a GRIB2 message after all grids and fields have
 * been added.
 * @author Stephen Gilbert @date 2002-10-31
 */
#include <stdio.h>
#include "grib2.h"

/**
 * This routine finalizes a GRIB2 message after all grids and fields
 * have been added. It adds the End Section ("7777") to the end of
 * the GRIB message and calculates the length and stores it in the
 * appropriate place in Section 0. This routine is used with routines
 * g2_create(), g2_addlocal(), g2_addgrid(), and g2_addfield() to
 * create a complete GRIB2 message. g2_create() must be called first to
 * initialize a new GRIB2 message.
 *
 * @param cgrib Char array containing all the data sections added be
 * previous calls to g2_create, g2_addlocal, g2_addgrid, and
 * g2_addfield. After function is called, contains the finalized GRIB2
 * message.
 *
 * @return
 * - > 0 = Length of the final GRIB2 message in bytes.
 * - -1 = GRIB message was not initialized. Need to call routine g2_create first.
 * - -2 = GRIB message already complete.
 * - -3 = Sum of Section byte counts doesn't add to total byte count
 * - -4 = Previous Section was not 7.
 *
 * @note This routine is intended for use with routines g2_create(),
 * g2_addlocal(), g2_addgrid(), and g2_addfield() to create a complete
 * GRIB2 message.
 *
 * @author Stephen Gilbert @date 2002-10-31
 */
g2int g2_gribend(unsigned char *cgrib)
{

    g2int iofst,lencurr,len,ilen,isecnum;
    g2int   ierr,lengrib;
    static unsigned char G=0x47;       // 'G'
    static unsigned char R=0x52;       // 'R'
    static unsigned char I=0x49;       // 'I'
    static unsigned char B=0x42;       // 'B'
    static unsigned char seven=0x37;   // '7'

    ierr=0;
//
//  Check to see if beginning of GRIB message exists
//
    if ( cgrib[0]!=G || cgrib[1]!=R || cgrib[2]!=I || cgrib[3]!=B ) {
        printf("g2_gribend: GRIB not found in given message.\n");
        ierr=-1;
        return (ierr);
    }
//
//  Get current length of GRIB message
//
    gbit(cgrib,&lencurr,96,32);
//
//  Loop through all current sections of the GRIB message to
//  find the last section number.
//
    len=16;    // Length of Section 0
    for (;;) {
        //    Get number and length of next section
        iofst=len*8;
        gbit(cgrib,&ilen,iofst,32);
        iofst=iofst+32;
        gbit(cgrib,&isecnum,iofst,8);
        len=len+ilen;
        //    Exit loop if last section reached
        if ( len == lencurr ) break;
        //    If byte count for each section doesn't match current
        //    total length, then there is a problem.
        if ( len > lencurr ) {
            printf("g2_gribend: Section byte counts don''t add to total.\n");
            printf("g2_gribend: Sum of section byte counts = %d\n",(int)len);
            printf("g2_gribend: Total byte count in Section 0 = %d\n",(int)lencurr);
            ierr=-3;
            return (ierr);
        }
    }
//
//  Can only add End Section (Section 8) after Section 7.
//
    if ( isecnum != 7 ) {
        printf("g2_gribend: Section 8 can only be added after Section 7.\n");
        printf("g2_gribend: Section %ld was the last found in given GRIB message.\n",isecnum);
        ierr=-4;
        return (ierr);
    }
//
//  Add Section 8  - End Section
//
    //cgrib(lencurr+1:lencurr+4)=c7777
    cgrib[lencurr]=seven;
    cgrib[lencurr+1]=seven;
    cgrib[lencurr+2]=seven;
    cgrib[lencurr+3]=seven;

//
//  Update current byte total of message in Section 0
//
    lengrib=lencurr+4;
    sbit(cgrib,&lengrib,96,32);

    return (lengrib);

}
