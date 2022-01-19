/** @file
 * @brief Searches a file for the next GRIB message.
 * @author Stephen Gilbert @date 2002-10-28
 */
#include <stdio.h>
#include <stdlib.h>
#include "grib2.h"

/**
 * This subprogram searches a file for the next GRIB Message. The
 * search is done starting at byte offset iseek of the file referenced
 * by lugb for mseek bytes at a time. If found, the starting position
 * and length of the message are returned in lskip and lgrib,
 * respectively. The search is terminated when an EOF or I/O error is
 * encountered.
 *
 * PROGRAM HISTORY LOG:
 * - 2002-10-28  GILBERT   Modified from Iredell's skgb subroutine
 * - 2009-01-16  VUONG     Changed  lskip to 4 instead of sizof(g2int)
 *
 * @param lugb FILE pointer for the file to search. File must be
 * opened before this routine is called.
 * @param iseek number of bytes in the file to skip before search.
 * @param mseek number of bytes to search at a time.
 * @param lskip number of bytes to skip from the beggining of the file
 * to where the GRIB message starts.
 * @param lgrib number of bytes in message (set to 0, if no message
 * found).
 *
 * @author Stephen Gilbert @date 2002-10-28
 */
void seekgb(FILE *lugb,g2int iseek,g2int mseek,g2int *lskip,g2int *lgrib)
{
    g2int  ret;
    g2int k,k4,ipos,nread,lim,start,vers,lengrib;
    int    end;
    unsigned char *cbuf;

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    *lgrib=0;
    cbuf=(unsigned char *)malloc(mseek);
    nread=mseek;
    ipos=iseek;

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
//  LOOP UNTIL GRIB MESSAGE IS FOUND

    while (*lgrib==0 && nread==mseek) {

//  READ PARTIAL SECTION

        ret=fseek(lugb,ipos,SEEK_SET);
        nread=fread(cbuf,sizeof(unsigned char),mseek,lugb);
        lim=nread-8;

//  LOOK FOR 'GRIB...' IN PARTIAL SECTION

        for (k=0;k<lim;k++) {
            gbit(cbuf,&start,(k+0)*8,4*8);
            gbit(cbuf,&vers,(k+7)*8,1*8);
            if (start==1196575042 && (vers==1 || vers==2)) {
//  LOOK FOR '7777' AT END OF GRIB MESSAGE
                if (vers == 1) gbit(cbuf,&lengrib,(k+4)*8,3*8);
                if (vers == 2) gbit(cbuf,&lengrib,(k+12)*8,4*8);
                ret=fseek(lugb,ipos+k+lengrib-4,SEEK_SET);
//          Hard code to 4 instead of sizeof(g2int)
                k4=fread(&end,4,1,lugb);
                if (k4 == 1 && end == 926365495) {      //GRIB message found
                    *lskip=ipos+k;
                    *lgrib=lengrib;
                    break;
                }
            }
        }
        ipos=ipos+lim;
    }

    free(cbuf);
}
