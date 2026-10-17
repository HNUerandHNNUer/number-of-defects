program audit
use Particles
use Simulation_Control
use Potential
implicit none
integer i
call New_Sample
call Pair(1,1,1.d0,2.d0**(1.d0/6.d0))
r_sphere=BoxSize(1)/2.d0-2.5d0
TRequested=0.d0
Fext=25.d0
lppp=.false.
call Update_List
acc=0.d0
call Compute_Bonds
open(31,file='bond.txt')
do i=1,N
write(31,'(3ES25.16)') acc(:,i)
end do
close(31)
acc=0.d0
call Compute_Angle
open(31,file='angle.txt')
do i=1,N
write(31,'(3ES25.16)') acc(:,i)
end do
close(31)
call Compute_Forces
open(31,file='force.txt')
do i=1,N
write(31,'(3ES25.16)') acc(:,i)
end do
close(31)
acc=0.d0
vel=0.d0
call Evolve_Sample(2)
open(31,file='after2.txt')
do i=1,N
write(31,'(3ES25.16)') pos(:,i)
end do
close(31)
end program audit
