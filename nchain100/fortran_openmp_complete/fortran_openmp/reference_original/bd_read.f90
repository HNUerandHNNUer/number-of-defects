!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  CODE STARTS
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  HERE


PROGRAM bd
!
! This is the main driver for the brownian dynamics program.
!
USE Particles
USE Simulation_Control
USE Potential
IMPLICIT NONE
DOUBLE PRECISION :: ReqTRequested, StepTRequested, rescale2
DOUBLE PRECISION, DIMENSION(3) :: ReqBoxSize, StepBoxSize, rescale
INTEGER :: i, k

step = 0
TRequested = 1.d0


CALL New_Sample

CALL Initial_Printout

CALL Pair(1, 1, 1.d0, 2.d0**(1.d0/6.d0))

Fext = 25.d0
!ReqBoxSize = BoxSize
!BoxSize = enlarge * BoxSize
!StepBoxSize = BoxSize - ReqBoxSize
!r_sphere = BoxSize(1)/2.d0-2.5d0
!CALL Write_Sample
!CALL Evolve_Sample(30000000)
!DO i = 1, 1000
!    rescale = (BoxSize - 0.001d0 * StepBoxSize) / BoxSize
!    DO k = 1, DIM
!        BoxSize(k) = BoxSize(k) * rescale(k)
!        pos(k,:) = pos(k,:) * rescale(k)
!    END DO
!	r_sphere = BoxSize(1)/2.d0-2.5d0
!	CALL Evolve_Sample(1000)
!END DO
!BoxSize = ReqBoxSize
r_sphere = BoxSize(1)/2.d0-2.5d0
!CALL Evolve_Sample(10000000)
!step = 0
CALL Write_Sample
!Fext = 3.d-1
VideoSave = .TRUE.
CALL Evolve_Sample(1000000000)

! ReqTRequested = 0.25d0
! StepTRequested = TRequested - ReqTRequested
! DO i =1, 1000
!     rescale2 = (TRequested - 0.001d0 * StepTRequested) / TRequested
!     TRequested = TRequested * rescale2
!     CALL Evolve_Sample(100000)
! END DO

CALL Terminate
END PROGRAM bd


!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  INITIALIZATION 
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!     ROUTINES

SUBROUTINE New_Sample
!
!  Set up a new sample by reading from an existing .xyz file
!
USE Particles
USE Simulation_Control
USE Potential
IMPLICIT NONE
INTEGER :: i, j, k, L, L1
CHARACTER(LEN=120) :: dummy_line  ! String to hold the header line
INTEGER :: start_pos             ! To store the starting position of "BoxSize:"

! --- Define polymer topology ---
nchain = 100
mchain = 30

! --- Open the coordinate file ---
OPEN(UNIT=10, FILE='initial.xyz', STATUS='OLD', ACTION='READ')

! --- Read header information ---
READ(10, *) N                ! Read the total number of particles
READ(10, '(A)') dummy_line   ! Read the entire second line into a string

! --- ROBUST FIX: Find the keyword "BoxSize:" and read from there ---
! Find the starting character position of "BoxSize:"
start_pos = INDEX(dummy_line, 'BoxSize:')

! Read the 3 numbers from the substring that starts right after "BoxSize:"
READ(dummy_line(start_pos + 8 :), *) BoxSize(1), BoxSize(2), BoxSize(3)

! --- Allocate memory based on N ---
maxatomtype = 1
CALL Allocate_Particles

! --- Read particle coordinates and types ---
DO i = 1, N
    READ(10,*) ptype(i), pos(1,i), pos(2,i), pos(3,i)
END DO

CLOSE(UNIT=10) ! Close the file after reading

! --- System parameters derived from file data ---
volume = BoxSize(1) * BoxSize(2) * BoxSize(3)

! --- Potential setup (can be kept if particle types are consistent) ---
PotShift = 0.d0 ! Assuming PotShift is zero as in the original code for diameter 1.0

! --- Recreate the Bond and Angle lists based on the known chain topology ---
L = 1
L1 = 1
DO i = 1, N, mchain
    ! Create Bond List for each chain
    DO j = 0, mchain-2
        BondMarker1(i+j) = L
        BondList(L) = i+j+1
        L=L+1
        BondMarker2(i+j)= L-1
    END DO
    BondMarker1(i+mchain-1) = L
    BondMarker2(i+mchain-1) = L-1

    ! Create Angle List for each chain
    DO j = 0, mchain-3
        AngleMarker1(i+j) = L1
        AngleList(L1) = i+j+2
        L1=L1+1
        AngleMarker2(i+j)= L1-1
    END DO
    AngleMarker1(i+mchain-2) = L1
    AngleMarker2(i+mchain-2) = L1-1
    AngleMarker1(i+mchain-1) = L1
    AngleMarker2(i+mchain-1) = L1-1
END DO

BListLength = L-1
AListLength = L1-1

END SUBROUTINE New_Sample
!SUBROUTINE New_Sample
!!
!!  Set up a new sample
!!
!USE Particles
!USE Simulation_Control
!USE Potential
!use ran_mod
!IMPLICIT NONE
!DOUBLE PRECISION :: diameter1, diameter2, shift1, shift2, thetapos, phipos, u1, u2
!DOUBLE PRECISION, DIMENSION(DIM)::ori, PosObstacle, temp, boundary, a1, a2, a3
!INTEGER :: i, j, k, L, M, Count, L1,test,N1,q1,q2,q3
!
!
!nchain = 100
!mchain = 30
!N = nchain*mchain
!density = 0.75d0
!r_sphere = (nchain*mchain/16.d0/density)**0.5d0
!enlarge = 10.d0
!
!maxatomtype = 1
!CALL Allocate_Particles
!
!BoxSize = 2.d0 * r_sphere + 5.d0
!volume = BoxSize(1)*BoxSize(2)*BoxSize(3)
!
!diameter1 = 1.d0
!shift1 = (diameter1 - 1.d0) / 2.d0
!PotShift = RESHAPE((/ 2.d0 * shift1 /), &
!                   (/ maxatomtype, maxatomtype /) )
!
!L = 1
!L1 = 1
!
!DO i = 1, N, mchain
!	k = (i-1) / mchain
!	u1 = int(k/int(nchain**0.5d0))
!	u2 = k-u1*int(nchain**0.5d0)
!	thetapos = 1.d0*pi*(u1+2.5d0)/(int(nchain**0.5d0)+4.d0)
!	phipos = 2.d0*pi*(u2+0.5)/int(nchain**0.5d0)
!	ori = (/ sin(thetapos)*cos(phipos), sin(thetapos)*sin(phipos), cos(thetapos) /)*(enlarge*BoxSize(1)-5.d0)/2.d0
!	u1 = ran()-0.5d0
!	u2 = ran()-0.5d0
!	if ( abs(ori(1)) .ge. abs(ori(2)) ) then
!		if ( abs(ori(1)) .ge. abs(ori(3)) ) then
!			temp = (/ (u1*ori(2)+u2*ori(3))/ori(1), -u1, -u2 /)
!		else
!			temp = (/ -u1, -u2, (u1*ori(1)+u2*ori(2))/ori(3) /)
!		end if
!	else
!		if ( abs(ori(2)) .ge. abs(ori(3)) ) then
!			temp = (/ -u1, (u1*ori(1)+u2*ori(3))/ori(2), -u2 /)
!		else
!			temp = (/ -u1, -u2, (u1*ori(1)+u2*ori(2))/ori(3) /)
!		end if
!	end if
!	temp = temp/sqrt(dot_product(temp,temp))
!	Do j = 0, mchain-1
!		pos(:,i+j) = ori+temp*(j-mchain/2)
!		pos(:,i+j) = pos(:,i+j)/sqrt(dot_product(pos(:,i+j),pos(:,i+j)))*(enlarge*BoxSize(1)-5.d0)/2.d0
!		ptype(i+j) = 1
!	End do
!    DO j = 0, mchain-2
!       BondMarker1(i+j) = L; BondList(L) = i+j+1; L=L+1; BondMarker2(i+j)= L-1
!    END DO
!    BondMarker1(i+mchain-1) = L; BondMarker2(i+mchain-1) = L-1
!    DO j = 0, mchain-3
!       AngleMarker1(i+j) = L1; AngleList(L1) = i+j+2; L1=L1+1; AngleMarker2(i+j)= L1-1
!    END DO 
!    AngleMarker1(i+mchain-2) = L1; AngleMarker2(i+mchain-2) = L1-1
!    AngleMarker1(i+mchain-1) = L1; AngleMarker2(i+mchain-1) = L1-1
!END DO
!BListLength = L-1
!AListLength = L1-1
!
!END SUBROUTINE New_Sample


SUBROUTINE Allocate_Particles
!
!   Allocate the arrays containing atomic information
!
use Particles
USE Potential
use Neighbor_List
USE Statistics
implicit none
allocate( ptype(N) );          ptype = 0
allocate( deltar(DIM,N) );     deltar = 0.d0  !!3×120
allocate( pos(DIM,N) );        pos = 0.d0
allocate( vel(DIM,N) );        vel = 0.d0
allocate( acc(DIM,N) );        acc = 0.d0
allocate( ene_pot(N) );        ene_pot = 0.d0
ALLOCATE( ene_pot_exbond(N) ); ene_pot_exbond = 0.d0
allocate( ene_kin(N) );        ene_kin = 0.d0
! bond list
BMaxListLength = MaxBondsPerAtom*N  !!3×120=360
allocate( BondList(BMaxListLength) )
allocate( BondMarker1(N) )
allocate( BondMarker2(N) )
! angleforce list
AMaxListLength = MaxAngleforcePerAtom*N  !!3×120=360
allocate( AngleList(AMaxListLength) )
allocate( AngleMarker1(N) )
allocate( AngleMarker2(N) )
! also those related to the neighbor list:
MaxListLength = MaxPairsPerAtom*N  !!200×120
allocate( List(MaxListLength) )
allocate( Marker1(N) )
allocate( Marker2(N) )
allocate( Advance(N) )
allocate( DisplaceList(DIM,N) )
! cell list
allocate( CellList(N) )
! potential
ALLOCATE(epsil(maxatomtype,maxatomtype))  !!1×1
ALLOCATE(Rcutoffsq(maxatomtype,maxatomtype))
ALLOCATE(phicutoff(maxatomtype,maxatomtype))
ALLOCATE(PotShift(maxatomtype,maxatomtype)); PotShift = 0.d0
END SUBROUTINE Allocate_Particles


SUBROUTINE Pair(i, j, ep, rc)
USE Particles
USE Potential
IMPLICIT NONE
INTEGER :: i, j
DOUBLE PRECISION :: ep, rc

IF ( i .eq. 0 .or. j .eq. 0 ) THEN
    epsil     = ep
    Rcutoffsq = (rc+PotShift)**2
    phicutoff = 4.d0 * ep * (1.d0 / rc**12 - 1.d0 / rc**6)
ELSE
    epsil(i,j)     = ep
    Rcutoffsq(i,j) = (rc+PotShift(i,j))**2
    phicutoff(i,j) = 4.d0 * ep * (1.d0 / rc**12 - 1.d0 / rc**6)
    IF ( i .ne. j ) THEN
            epsil(j,i) =     epsil(i,j)
        Rcutoffsq(j,i) = Rcutoffsq(i,j)
        phicutoff(j,i) = phicutoff(i,j)
    END IF
END IF
END SUBROUTINE 


SUBROUTINE Initial_Printout
!
!   Prints information on the run parameters on the standard output
!   Leading # are to directly use the output as a gunplot input.
!
use Particles
use Neighbor_List
use Simulation_Control
implicit none
print '(a,/,a,/,a)','#','# Brownian: a minimal molecular dynamics program','#'
print '(2a)','# ',title(1:len_trim(title))
print '(a)','#                                                              (new model)'
print '(2a)','# Output sample: out-step'
print '(a,f7.4)', '# Time step:',deltat
print '(a,i6)','# Number of atoms:',N
print '(a,3f12.6,a,f15.3)', &
      '# Box size:',BoxSize,', Volume:',volume
print '(a,f12.6)','# Constant T run with T = ',TRequested
print '(a,f8.4,a,i9)', &
      '# Skin:',skin,' , maximum neighbor list length:',MaxListLength

print '(a,/,a,/,a)', '#', &
'#     Step   Temperature     Kinetic      Potential   Total Energy    Pressure',&
'# --------  ------------  ------------  ------------  ------------  ------------'
END SUBROUTINE Initial_Printout


!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  TIME EVOLUTION
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!     ROUTINES


SUBROUTINE Evolve_Sample(runsteps)
!
!   This is the main subroutine, controlling the time evolution of the system.
!
USE Particles
USE Neighbor_List
USE Simulation_Control
USE Statistics
IMPLICIT NONE
INTEGER :: currentstep, runsteps
LOGICAL, EXTERNAL :: MovedTooMuch
LOGICAL :: ListUpdateRequested
INTEGER :: i

ListUpdateRequested = .TRUE. ! always need an update when starting

currentstep = 0
DO WHILE (currentstep .lt. runsteps)

	currentstep = currentstep + 1
    step = step + 1
    
    deltar = deltat * vel
    pos = pos + deltar
    vel = acc/gamma
    
    IF (ListUpdateRequested) THEN
        CALL Update_List
        ListUpdateRequested = .FALSE.
    END IF
    
    CALL Compute_Forces

    DisplaceList = DisplaceList + deltar
    ListUpdateRequested = MovedTooMuch(Skin)
    
    IF ( lppp .or. lpps ) THEN
        CALL Print_Statistics
    END IF
    
    IF (VideoSave) THEN
      IF ( MOD(step, iSave) .eq. 0 ) THEN
          CALL Write_Sample
      END IF 
    End IF  
	
END DO

END SUBROUTINE Evolve_Sample


SUBROUTINE Compute_Forces
!
!  Compute forces on atoms from the position, this version makes use of
!  an existing neighbor list, and runs in O(N) time.
!
use Particles
use Simulation_Control
USE Potential
use Neighbor_List
use ran_mod
implicit none
DOUBLE PRECISION, DIMENSION(DIM) :: Sij, Sext,direction
DOUBLE PRECISION :: Rsqij, R, Rshift, rm2, rm6, rm12, phi, dphi, Rext, rm,DISi,dphi1
INTEGER :: i, j, L, pti, ptj

ene_pot = 0.d0
ene_pot_exbond = 0.d0
acc = 0.d0
virial = 0.d0

CALL Compute_Bonds

CALL Compute_Angle

DO i = 1,N
    pti = ptype(i)  !!1
    DO L = Marker1(i),Marker2(i)
        j = List(L)
        ptj = ptype(j) !!1
        Sij = pos(:,i) - pos(:,j)
        WHERE ( abs(Sij) > 0.5d0 * BoxSize )
            Sij = Sij - SIGN(BoxSize, Sij)
        END WHERE
        Rsqij = dot_product(Sij,Sij)
        IF ( Rsqij .lt. Rcutoffsq(pti,ptj) ) THEN
            R = SQRT(Rsqij)
            Rshift = R - PotShift(pti,ptj)
            IF ( Rshift < 0 ) THEN
                print *, 'barrier'
            END IF
            rm2  = 1.d0/(Rshift**2)
            rm6  = rm2**3
            rm12 = rm6**2
            phi  =  4.d0 * epsil(pti,ptj) * (rm12 - rm6) - phicutoff(pti,ptj)
            dphi = 24.d0 * epsil(pti,ptj) * (2.d0 * rm12 - rm6) / Rshift / R         
            ene_pot(i) = ene_pot(i) + 0.5d0 * phi
            ene_pot_exbond(i) = ene_pot_exbond(i) + 0.5d0 * phi
            acc(:,i) = acc(:,i) + dphi * Sij
            ene_pot(j) = ene_pot(j) + 0.5d0 * phi
            ene_pot_exbond(j) = ene_pot_exbond(j) + 0.5d0 * phi
            virial = virial - dphi * R * Rshift
            acc(:,j) = acc(:,j) - dphi * Sij
        END IF
    END DO
    ! frictional forces and random forces
    IF (i .le. N) THEN  
!         acc(:,i) = acc(:,i) - gamma * vel(:,i)
        acc(:,i) = acc(:,i) + ( (/ran(),ran(),ran()/) - 0.5d0 ) * &
                    SQRT(24.d0*TRequested*gamma/deltat)
    END IF
    ! external acitve forces
    IF (i .le. N .and. mod(i,mchain)>1) THEN
        Sext =  pos(:,i+1) - pos(:,i-1)
        WHERE ( abs(Sext) > 0.5d0 * BoxSize )
            Sext = Sext - SIGN(BoxSize, Sext)
        END WHERE
        Rext = SQRT(dot_product(Sext,Sext))
        acc(:,i) = acc(:,i) + Fext*Sext/Rext
    END IF
	! wall1
    DISi=(r_sphere+2.d0**(1.d0/6.d0))-sqrt(dot_product(pos(:,i),pos(:,i)))
	if (DISi .le. 2.d0**(1.d0/6.d0)) then
		rm = 1.d0/(DISi**2)
		dphi1 = 100*24.d0 * (2.d0 * rm**6 - rm**3) / DISi**2 
		direction = pos(:,i) / sqrt(dot_product(pos(:,i),pos(:,i)))
		acc(:,i) = acc(:,i) - dphi1 * DISi * direction
	end if
	! wall2
	DISi=sqrt(dot_product(pos(:,i),pos(:,i)))-(r_sphere-2.d0**(1.d0/6.d0))
	if (DISi .le. 2.d0**(1.d0/6.d0)) then
		rm = 1.d0/(DISi**2)
		dphi1 = 100*24.d0 * (2.d0 * rm**6 - rm**3) / DISi**2 
		direction = -pos(:,i) / sqrt(dot_product(pos(:,i),pos(:,i)))
		acc(:,i) = acc(:,i) - dphi1 * DISi * direction
	end if
	
END DO

virial = - virial/DIM
END SUBROUTINE Compute_Forces


SUBROUTINE Compute_Bonds
!
!   Spring force
!
use Particles
use Potential
implicit none
double precision, dimension(DIM) :: Sij
double precision :: Rsqij, R, Rshift, phi,dphi
INTEGER :: pti, ptj
integer :: i,j,k,L
do i = 1,N
    pti = ptype(i)
    do L = BondMarker1(i),BondMarker2(i)
        j = BondList(L)
        ptj = ptype(j)
        Sij = pos(:,i) - pos(:,j)
        where ( abs(Sij) > 0.5d0 * BoxSize )
            Sij = Sij - sign(BoxSize,Sij)
        end where
        Rsqij = dot_product(Sij,Sij)
        R = SQRT(Rsqij)
        Rshift = R - PotShift(pti,ptj)
        Rsqij = Rshift**2
        phi  = -0.5d0 * FENE_K * (FENE_Rmax**2) * log(1 - Rsqij/(FENE_Rmax**2))
        dphi = -FENE_K * Rshift / R / (1 - Rsqij/(FENE_Rmax**2))
        ene_pot(i) = ene_pot(i) + 0.5d0*phi
        ene_pot(j) = ene_pot(j) + 0.5d0*phi
        virial = virial - dphi*R*Rshift
        acc(:,i) = acc(:,i) + dphi*Sij
        acc(:,j) = acc(:,j) - dphi*Sij                                         
    end do
end do
END SUBROUTINE Compute_Bonds


SUBROUTINE Compute_Angle
!
!   Angle force
!
USE Particles
USE Potential
IMPLICIT NONE
INTEGER :: i, j, k, L1
DOUBLE PRECISION :: theta1, p, disi, disj
DOUBLE PRECISION, DIMENSION(DIM) :: Sij, ei, ej, eij, eji, eiij, ejji
do j = 1,N    !!change from Harmonic angle potential to Cosine angle potential
    do L1 = AngleMarker1(j),AngleMarker2(j)
        i = AngleList(L1)-1
        k = AngleList(L1)
        ei = pos(:,j) - pos(:,i)
        WHERE ( ABS(ei) > 0.5d0 * BoxSize )
            ei = ei - SIGN(BoxSize, ei)
        END WHERE
        disi = sqrt( dot_product(ei,ei) )
        ei = ei / disi
        ej = pos(:,k) - pos(:,i)
        WHERE ( ABS(ej) > 0.5d0 * BoxSize )
            ej = ej - SIGN(BoxSize, ej)
        END WHERE
        disj = sqrt( dot_product(ej,ej) )
        ej = ej / disj
        p = dot_product(ei,ej) 
        if ( (p.lt.0.99d0) .and.(p.gt.-0.99d0) ) then
            theta1 = dacos(p)
            eij(1) = ei(2)*ej(3) - ei(3)*ej(2)
            eij(2) = ei(3)*ej(1) - ei(1)*ej(3)
            eij(3) = ei(1)*ej(2) - ei(2)*ej(1)
            eij = eij / sqrt( dot_product(eij,eij) )
            eji = -eij
            eiij(1) = ei(2)*eij(3) - ei(3)*eij(2)
            eiij(2) = ei(3)*eij(1) - ei(1)*eij(3)
            eiij(3) = ei(1)*eij(2) - ei(2)*eij(1)
            ejji(1) = ej(2)*eji(3) - ej(3)*eji(2)
            ejji(2) = ej(3)*eji(1) - ej(1)*eji(3)
            ejji(3) = ej(1)*eji(2) - ej(2)*eji(1)
            eiij = eiij / sqrt( dot_product(eiij,eiij) )
            ejji = ejji / sqrt( dot_product(ejji,ejji) )
            acc(:,j) = acc(:,j) + K_Angle /disi * dsin(theta - theta1) * eiij
            acc(:,k) = acc(:,k) + K_Angle /disj * dsin(theta - theta1) * ejji
            acc(:,i) = acc(:,i) - K_Angle /disi * dsin(theta - theta1) * eiij - K_Angle /disj * dsin(theta - theta1) &  !!!由（theta - theta1)改为sin(theta - theta1)s
            * ejji
        end if
    end do
end do
END SUBROUTINE Compute_Angle


SUBROUTINE Compute_Temperature(ene_kin_aver,temperature)
use Particles
implicit none
double precision :: ene_kin_aver, temperature
integer :: i
do i=1,N
    ene_kin(i) = 0.5d0*dot_product(vel(:,i),vel(:,i))   ! kin en of each atom
end do
ene_kin_aver = sum( ene_kin ) / N
temperature = 2.d0*ene_kin_aver/DIM
END SUBROUTINE Compute_Temperature


SUBROUTINE Update_List
!
!  Update the neighbor list, including all atom pairs that are within a
!  distance Range to each other.
!
use Particles
use Simulation_Control
use Potential
use Neighbor_List
implicit none
double precision, dimension(maxatomtype,maxatomtype) :: Rrange, Rrangesq
double precision, dimension(DIM) :: Sij
double precision :: Rsqij
INTEGER :: pti, ptj
integer :: i,j,k,L,m(3)

do i = 1,maxatomtype
    do j = 1, maxatomtype
        Rrange(i,j) = SQRT(Rcutoffsq(i,j)) + Skin
    end do
end do

Rrangesq = Rrange**2
call new_clist(maxval(Rrange))

L = 1
do i = 1,N
    pti = ptype(i)
    Marker1(i) = L
    iCell = 1 + int( (pos(:,i) / BoxSize + 0.5d0) * nPart )
    where(iCell .gt. nPart) iCell = nPart

    do k=0,13
        select case(k)
            case(0)
                m = iCell
            case(1)
                m = iCell + (/ 1,0,0 /)
            case(2:4)
                m = iCell + (/k-3,1,0/)
            case(5:7)
                m = iCell + (/k-6,-1,1/)
            case(8:10)
                m = iCell + (/k-9,0,1/)
            case(11:13)
                m = iCell + (/k-12,1,1/)
        end select
        ! PBC
        if ( all(m == iCell) ) then
            j = CellList(i)
        else
            where (m > nPart) m = m - nPart
            where (m <= 0) m = m + nPart
            j = Head(m(1),m(2),m(3))
        end if
        ! Linked list
        do while (j .ne. 0)
            Sij = pos(:,i) - pos(:,j)
            where ( abs(Sij) > 0.5d0 * BoxSize )
                Sij = Sij - sign(BoxSize,Sij)
            end where
            Rsqij = dot_product(Sij,Sij)
            if ( Rsqij < Rrangesq(pti,ptype(j)) ) then
                if ( L > MaxListLength ) then
                    print *,'Update_List: FATAL: List too small'
                    !stop
                end if
                List(L) = j
                L = L + 1
            end if
            j = CellList(j)       
        end do
    end do
    Marker2(i) = L - 1
end do
ListLength = L - 1
DisplaceList = 0.d0
END SUBROUTINE Update_List


SUBROUTINE new_clist(Range)
use Particles
use Neighbor_List
use Simulation_Control
implicit none
double precision :: Range
integer :: i

nPart = minval(int(BoxSize / Range))
if ( nPart .lt. 3 ) then
    print *,'Range is too large!'
    stop
end if
IF (ALLOCATED(Head)) THEN
    IF (ANY(SHAPE(Head) /= nPart)) THEN
        DEALLOCATE(Head)
        ALLOCATE(Head(nPart, nPart, nPart))
    END IF
ELSE
    ALLOCATE(Head(nPart, nPart, nPart))
END IF
Head = 0
DO i = 1,N
    iCell = 1 + int( (pos(:,i) / BoxSize + 0.5d0) * nPart)
    where(iCell .gt. nPart) iCell = nPart
    CellList(i) = Head(iCell(1),iCell(2),iCell(3))
    Head(iCell(1),iCell(2),iCell(3)) = i
END DO
END SUBROUTINE new_clist


LOGICAL FUNCTION MovedTooMuch(Skin)
!
!   Scans the DisplaceList vector, containing the displacement vectors of
!   particles since the last time the list was updated.  It looks for the
!   magnitude of the two largest displacements in the system.   These are
!   summed together. If the sum is larger than Skin, the function returns
!   .TRUE., otherwise .FALSE.
!
use Particles
use Neighbor_List
implicit none
double precision :: Skin
double precision :: Displ,Displ1,Displ2
integer :: i
Displ1 = 0.d0
Displ2 = 0.d0
do i=1,N
    Displ = sqrt( dot_product(DisplaceList(:,i),DisplaceList(:,i)) )
    if (Displ >= Displ1) then       ! 1st position taken
        Displ2 = Displ1             ! push current 1st into 2nd place
        Displ1 = Displ              ! and put this one into current 1st
    else if (Displ >= Displ2) then  ! 2nd position taken
        Displ2 = Displ
    end if
end do
MovedTooMuch = ( Displ1 + Displ2 > Skin )
END FUNCTION MovedTooMuch


SUBROUTINE Print_Statistics
!
!   Print the mean value, averaged during the run, of the statistical
!   quantities which have been accumulated
!
USE Particles
USE Simulation_Control
USE Statistics
IMPLICIT NONE

IF ( iPrint <= 0 ) RETURN

CALL Compute_Temperature(ene_kin_aver,temperature)

ene_pot_aver = SUM( ene_pot ) / N
ene_pot_aver_exbond = SUM( ene_pot_exbond ) / N
ene_tot_aver = ene_kin_aver + ene_pot_aver
pressure = density*temperature + virial/volume

IF (lpps) THEN
    PRINT '(1x,i10,5f14.6)',step,temperature, &
                       ene_kin_aver,ene_pot_aver,ene_tot_aver,pressure
END IF

IF (lppp) THEN
    temperature_sum = temperature_sum + temperature
    ene_kin_sum     = ene_kin_sum     + ene_kin_aver
    ene_pot_sum     = ene_pot_sum     + ene_pot_aver
    pressure_sum    = pressure_sum    + pressure
    IF ( MOD(step,iPrint).eq.0 ) THEN
        PRINT '(1x,i10,5f14.6)',step, &
                            temperature_sum / iPrint , &
                            ene_kin_sum / iPrint , &
                            ene_pot_sum / iPrint , &
                            ( ene_kin_sum + ene_pot_sum ) / iPrint , &
                            pressure_sum / iPrint
        temperature_sum = 0
        ene_kin_sum = 0
        ene_pot_sum = 0
        pressure_sum = 0
    END IF
END IF
END SUBROUTINE Print_Statistics


SUBROUTINE Write_Sample
!
!  Writes the final sample to file unit 2
!
use Particles
use Simulation_Control
implicit none
integer :: i
character(LEN=10) :: strStep
CHARACTER(LEN=4) :: form
WRITE(strStep, '(I10.10)') step !!初始step=0

OPEN(unit=2, file='out-'//strStep//'.xyz', status='replace')  !!file=....out-0000000000.xyz?，字符串的合并
WRITE(form,'(a,I1,a)') '(I', INT(LOG10(10.*N)), ')'  !!form的值为多少:(I3)
WRITE(2,form) N !!以I3格式在打出120
WRITE(2,'(a,I9,a,3E23.15)') 'Atoms. Timestep: ', step, ', BoxSize: ', BoxSize !!step=0
DO i = 1, N
    WRITE(2,'(I1,1X,3E23.15)') ptype(i), pos(:,i) !!中间为输出位置向右移动1个位置
END DO
CLOSE(UNIT=2)!!不再进行读写操作，默认保留这个文件

! OPEN(UNIT=2, FILE='vi-'//strStep, STATUS='REPLACE')!!再次打开unit=2？？
! DO i = 1, N
    ! WRITE(2,'(3E23.15)') vel(:,i)!!1i,2i,3i
! END DO

CLOSE(UNIT=2)

END SUBROUTINE Write_Sample


!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  TERMINATION
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!    ROUTINES


SUBROUTINE Terminate
!
!   Termination procedure
!
use Particles
USE Potential
use Neighbor_List
USE Statistics
implicit none

deallocate( ptype )
deallocate( deltar )
deallocate( pos )
deallocate( vel )
deallocate( acc )
deallocate( ene_pot )
DEALLOCATE( ene_pot_exbond )
deallocate( ene_kin )
!
deallocate( BondList )
deallocate( BondMarker1 )
deallocate( BondMarker2 )
!
deallocate( AngleList )
deallocate( AngleMarker1 )
deallocate( AngleMarker2 )
!
deallocate( List )
deallocate( Marker1 )
deallocate( Marker2 )
deallocate( Advance )
deallocate( DisplaceList )
!
deallocate( CellList )
!
DEALLOCATE( epsil )
DEALLOCATE( Rcutoffsq )
DEALLOCATE( phicutoff )
DEALLOCATE( PotShift )
END SUBROUTINE Terminate
