/** @file
 * @brief Unpack Section 6 (Bit-Map Section) as defined in GRIB Edition 2.
 * @author Stephen Gilbert @date 2002-10-31
 */
#include <stdio.h>
#include <stdlib.h>
#include "grib2.h"

/**
 * This subroutine unpacks Section 6 (Bit-Map Section) as defined in
 * GRIB Edition 2.
 *
 * @param cgrib char array containing Section 6 of the GRIB2 message.
 * @param iofst Bit offset of the beginning of Section 6 in cgrib.
 * @param ngpts Number of grid points specified in the bit-map
 * @param ibmap Bitmap indicator (see Code Table 6.0)
 * - 0 bitmap applies and is included in Section 6.
 * - 1-253 Predefined bitmap applies
 * - 254 Previously defined bitmap applies to this field
 * - 255 Bit map does not apply to this product.
 * @param bmap Pointer to an integer array containing decoded
 * bitmap. (if ibmap=0)
 *
 * @return
 * - 0 no error
 * - 2 Not Section 6
 * - 4 Unrecognized pre-defined bit-map.
 * - 6 memory allocation error
 *
 * @author Stephen Gilbert @date 2002-10-31
 */
g2int
g2_unpack6(unsigned char *cgrib, g2int *iofst, g2int ngpts, g2int *ibmap,
           g2int **bmap)
{
    g2int j,ierr,isecnum;
    g2int *lbmap=0;
    g2int *intbmap;

    ierr=0;
    *bmap=0;    /* NULL */

    *iofst=*iofst+32;    /* skip Length of Section */
    gbit(cgrib,&isecnum,*iofst,8);         /* Get Section Number */
    *iofst=*iofst+8;

    if ( isecnum != 6 ) {
        ierr=2;
        fprintf(stderr,"g2_unpack6: Not Section 6 data.\n");
        return(ierr);
    }

    gbit(cgrib,ibmap,*iofst,8);    /* Get bit-map indicator */
    *iofst=*iofst+8;

    if (*ibmap == 0) {               /* Unpack bitmap */
        if (ngpts > 0) lbmap=(g2int *)calloc(ngpts,sizeof(g2int));
        if (lbmap == 0) {
            ierr=6;
            return(ierr);
        }
        else {
            *bmap=lbmap;
        }
        intbmap=(g2int *)calloc(ngpts,sizeof(g2int));
        gbits(cgrib,intbmap,*iofst,1,0,ngpts);
        *iofst=*iofst+ngpts;
        for (j=0;j<ngpts;j++) {
            lbmap[j]=(g2int)intbmap[j];
        }
        free(intbmap);
        /*
          else if (*ibmap.eq.254)               ! Use previous bitmap
          return(ierr);
          else if (*ibmap.eq.255)               ! No bitmap in message
          bmap(1:ngpts)=.true.
          else {
          print *,'gf_unpack6: Predefined bitmap ',*ibmap,' not recognized.'
          ierr=4;
        */
    }

    return(ierr);    /* End of Section 6 processing */

}
