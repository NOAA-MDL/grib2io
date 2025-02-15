#ifndef IPLIB_H
#define IPLIB_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void ipolates_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni, 
                    int *igdtnumo, int *igdtmplo, int *igdtleno, 
                    int *mi, int *mo, int *km, int *ibi, bool *li, float *gi, 
                    int *no, float *rlat, float *rlon, int *ibo, bool *lo, float *go, int *iret);


void ipolatev_grib2(int *ip, int *ipopt, int *igdtnumi, int *igdtmpli, int *igdtleni,
                    int *igdtnumo, int *igdtmplo, int *igdtleno,
                    int *mi, int *mo, int *km, int *ibi, bool *li, float *ui, float *vi,
                    int *no, float *rlat, float *rlon, float *crot, float *srot, int *ibo, bool *lo,
                    float *uo, float *vo, int *iret);

#ifdef __cplusplus
}
#endif

#endif

