/**
 * @file
 * @brief Free up memory that was allocated for struct gribfield.
 * @author Stephen Gilbeert @date 2002-10-28
 */

#include <stdlib.h>
#include  "grib2.h"

/**
 * This routine frees up memory that was allocated for struct
 * gribfield.
 *
 * @param gfld pointer to gribfield structure (defined in include file
 * grib2.h) returned from routine g2_getfld().
 *
 * @note This routine must be called to free up memory used by the
 * decode routine, g2_getfld(), when user no longer needs to reference
 * this data.
 *
 * @author Stephen Gilbeert @date 2002-10-28
 */
void
g2_free(gribfield *gfld)
{
    if (gfld->idsect != 0 ) free(gfld->idsect);
    if (gfld->local != 0 ) free(gfld->local);
    if (gfld->list_opt != 0 ) free(gfld->list_opt);
    if (gfld->igdtmpl != 0 ) free(gfld->igdtmpl);
    if (gfld->ipdtmpl != 0 ) free(gfld->ipdtmpl);
    if (gfld->coord_list != 0 ) free(gfld->coord_list);
    if (gfld->idrtmpl != 0 ) free(gfld->idrtmpl);
    if (gfld->bmap != 0 ) free(gfld->bmap);
    if (gfld->fld != 0 ) free(gfld->fld);
    free(gfld);

    return;
}
