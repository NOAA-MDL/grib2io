#ifndef IPLIB_H
#define IPLIB_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void gdswzd(int igdtnum, int *igdtmpl, int igdtlen, int iopt, int npts, double fill,
            double *xpts, double *ypts, double *rlon, double *rlat, int *nret, double *crot,
            double *srot, double *xlon, double *xlat, double *ylon, double *ylat, double *area);

void ipolates_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni,
                    int *igdtnumo, int *igdtmplo, int *igdtleno,
                    int *mi, int *mo, int *km, int *ibi, bool *li, double *gi,
                    int *no, double *rlat, double *rlon, int *ibo, bool *lo, double *go, int *iret);


void ipolatev_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni,
                    int *igdtnumo, int *igdtmplo, int *igdtleno,
                    int *mi, int *mo, int *km, int *ibi, bool *li, double *ui, double *vi,
                    int *no, double *rlat, double *rlon, double *crot, double *srot, int *ibo, bool *lo,
                    double *uo, double *vo, int *iret);

void use_ncep_post_arakawa();

void unuse_ncep_post_arakawa();

#ifdef __cplusplus
}
#endif

#endif

