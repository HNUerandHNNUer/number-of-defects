program passive
use Particles
use Simulation_Control
use Potential
implicit none
integer j,k
character(len=32) arg
call New_Sample
call Pair(1,1,1.d0,2.d0**(1.d0/6.d0))
r_sphere=BoxSize(1)/2.d0-2.5d0
TRequested=1.d0
Fext=0.d0
lppp=.false.
call get_command_argument(1,arg)
read(arg,*) deltat
open(31,file='trajectory.txt')
do j=1,1000
call Evolve_Sample(nint(1.d0/deltat))
do k=1,N
write(31,'(3ES25.16)')pos(:,k)
end do
end do
close(31)
end program passive
