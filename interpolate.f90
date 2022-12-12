subroutine interpolate(ip,ipopt,igdtnumi,igdtmpli,igdtleni, &
                       igdtnumo,igdtmplo,igdtleno, &
                       mi,mo,km,ibi,li,gi, &
                       no,ibo,lo,go,iret)
use ipolates_mod
implicit none

! ---------------------------------------------------------------------------------------- 
! Input/Output Variables
! ---------------------------------------------------------------------------------------- 
integer, intent(in) :: ip
integer, intent(in), dimension(20) :: ipopt
integer, intent(in) :: igdtnumi
integer, intent(in), dimension(igdtleni) :: igdtmpli
integer, intent(in) :: igdtleni
integer, intent(in) :: igdtnumo
integer, intent(in), dimension(igdtleno) :: igdtmplo
integer, intent(in) :: igdtleno
integer, intent(in) :: mi
integer, intent(in) :: mo
integer, intent(in) :: km
integer, intent(in), dimension(km) :: ibi
logical(kind=1), intent(in), dimension(mi,km) :: li
real, intent(in), dimension(mi,km) :: gi
integer, intent(out) :: no 
integer, intent(out), dimension(km) :: ibo
logical(kind=1), intent(out), dimension(mo,km) :: lo
real, intent(out), dimension(mo,km) :: go
integer, intent(out) :: iret 

! ---------------------------------------------------------------------------------------- 
! Local variables
! ---------------------------------------------------------------------------------------- 
real, allocatable, dimension(:) :: rlat
real, allocatable, dimension(:) :: rlon

! ---------------------------------------------------------------------------------------- 
! Initialize
! ---------------------------------------------------------------------------------------- 
iret=0
no=0

! ---------------------------------------------------------------------------------------- 
! Allocate lat lon arrays.
! ---------------------------------------------------------------------------------------- 
if(allocated(rlat))deallocate(rlat)
allocate(rlat(mo))
if(allocated(rlon))deallocate(rlon)
allocate(rlon(mo))

! ---------------------------------------------------------------------------------------- 
! Call NCEPLIBS-ip subroutine, ipolates_grib2 to perform interpolation of scalar fields
! using GRIB2 metadata.
! ---------------------------------------------------------------------------------------- 
call ipolates_grib2(ip,ipopt,igdtnumi,igdtmpli,igdtleni,igdtnumo,igdtmplo,igdtleno, &
                    mi,mo,km,ibi,li,gi,no,rlat,rlon,ibo,lo,go,iret)

! ---------------------------------------------------------------------------------------- 
! Deallocate lat lon arrays.
! ---------------------------------------------------------------------------------------- 
if(allocated(rlat))deallocate(rlat)
if(allocated(rlon))deallocate(rlon)

return
end subroutine interpolate
