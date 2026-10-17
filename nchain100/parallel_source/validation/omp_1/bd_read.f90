! OpenMP optimization: equations and original delayed update order retained.
PROGRAM bd
USE Particles
USE Simulation_Control
USE Potential
IMPLICIT NONE
DOUBLE PRECISION :: ReqTRequested, StepTRequested, rescale2
DOUBLE PRECISION, DIMENSION(3) :: ReqBoxSize, StepBoxSize, rescale
INTEGER :: i, k, production_steps, env_status, ios
CHARACTER(LEN=64) :: env_value
step = 0
TRequested = 1.d0
CALL New_Sample
CALL Initial_Printout
CALL Pair(1, 1, 1.d0, 2.d0**(1.d0/6.d0))
Fext = 25.d0
r_sphere = BoxSize(1)/2.d0-2.5d0
CALL Write_Sample
VideoSave = .TRUE.
production_steps = 1000000000
CALL GET_ENVIRONMENT_VARIABLE('BD_STEPS', env_value, STATUS=env_status)
IF (env_status == 0 .AND. LEN_TRIM(env_value) > 0) THEN
    READ(env_value, *, IOSTAT=ios) production_steps
    IF (ios /= 0) ERROR STOP 'Invalid BD_STEPS'
    IF (production_steps < 0) ERROR STOP 'BD_STEPS must be nonnegative'
END IF
CALL GET_ENVIRONMENT_VARIABLE('BD_SAVE', env_value, STATUS=env_status)
IF (env_status == 0 .AND. LEN_TRIM(env_value) > 0) THEN
    READ(env_value, *, IOSTAT=ios) iSave
    IF (ios /= 0) ERROR STOP 'Invalid BD_SAVE'
    IF (iSave < 1) ERROR STOP 'BD_SAVE must be positive'
END IF
CALL Evolve_Sample(production_steps)
CALL Terminate
END PROGRAM bd
SUBROUTINE New_Sample
USE Particles
USE Simulation_Control
USE Potential
IMPLICIT NONE
INTEGER :: i, j, k, L, L1
CHARACTER(LEN=120) :: dummy_line
INTEGER :: start_pos
nchain = 100
mchain = 30
OPEN(UNIT=10, FILE='initial.xyz', STATUS='OLD', ACTION='READ')
READ(10, *) N
READ(10, '(A)') dummy_line
start_pos = INDEX(dummy_line, 'BoxSize:')
IF (start_pos == 0) ERROR STOP 'Missing BoxSize: in initial.xyz'
READ(dummy_line(start_pos + 8 :), *) BoxSize(1), BoxSize(2), BoxSize(3)
IF (N /= nchain*mchain) ERROR STOP 'N must equal nchain*mchain'
IF (ANY(BoxSize <= 0.d0)) ERROR STOP 'Invalid box size'
maxatomtype = 1
CALL Allocate_Particles
DO i = 1, N
    READ(10,*) ptype(i), pos(1,i), pos(2,i), pos(3,i)
END DO
CLOSE(UNIT=10)
IF (ANY(ptype /= 1)) ERROR STOP 'This input supports atom type 1 only'
volume = BoxSize(1) * BoxSize(2) * BoxSize(3)
! Number density for the legacy 3D pressure diagnostic only.
density = N / volume
PotShift = 0.d0
L = 1
L1 = 1
DO i = 1, N, mchain
    DO j = 0, mchain-2
        BondMarker1(i+j) = L
        BondList(L) = i+j+1
        L=L+1
        BondMarker2(i+j)= L-1
    END DO
    BondMarker1(i+mchain-1) = L
    BondMarker2(i+mchain-1) = L-1
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
SUBROUTINE Allocate_Particles
use Particles
USE Potential
use Neighbor_List
USE Statistics
USE Parallel_Work
implicit none
allocate( ptype(N) );          ptype = 0
allocate( deltar(DIM,N) );     deltar = 0.d0
allocate( pos(DIM,N) );        pos = 0.d0
allocate( vel(DIM,N) );        vel = 0.d0
allocate( acc(DIM,N) );        acc = 0.d0
allocate( ene_pot(N) );        ene_pot = 0.d0
ALLOCATE( ene_pot_exbond(N) ); ene_pot_exbond = 0.d0
allocate( ene_kin(N) );        ene_kin = 0.d0
BMaxListLength = MaxBondsPerAtom*N
allocate( BondList(BMaxListLength) )
allocate( BondMarker1(N) )
allocate( BondMarker2(N) )
AMaxListLength = MaxAngleforcePerAtom*N
allocate( AngleList(AMaxListLength) )
allocate( AngleMarker1(N) )
allocate( AngleMarker2(N) )
MaxListLength = MaxPairsPerAtom*N
allocate( List(MaxListLength) )
allocate( Marker1(N) )
allocate( Marker2(N) )
allocate( Advance(N) )
allocate( DisplaceList(DIM,N) )
allocate( CellList(N) )
ALLOCATE(epsil(maxatomtype,maxatomtype))
ALLOCATE(Rcutoffsq(maxatomtype,maxatomtype))
ALLOCATE(phicutoff(maxatomtype,maxatomtype))
ALLOCATE(PotShift(maxatomtype,maxatomtype)); PotShift = 0.d0
allocate(bond_virial(BMaxListLength), random_draw(DIM,N))
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
SUBROUTINE Evolve_Sample(runsteps)
USE Particles
USE Neighbor_List
USE Simulation_Control
USE Statistics
IMPLICIT NONE
INTEGER :: currentstep, runsteps
LOGICAL, EXTERNAL :: MovedTooMuch
LOGICAL :: ListUpdateRequested
INTEGER :: i
ListUpdateRequested = .TRUE.
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
USE Particles
USE Simulation_Control
USE Potential
USE Neighbor_List
USE ran_mod
USE Parallel_Work
IMPLICIT NONE
INTEGER :: i, j, L, pti, ptj, slot
DOUBLE PRECISION :: Sij(DIM), Rsqij, R, Rshift, rm2, rm6, rm12, phi, dphi
LOGICAL :: local_done
ene_pot = 0.d0
ene_pot_exbond = 0.d0
acc = 0.d0
virial = 0.d0
CALL Compute_Bonds
CALL Compute_Angle
! Never invoke the stateful RNG from worker threads.
DO i=1,N
    random_draw(:,i) = (/ran(),ran(),ran()/)
END DO
!$omp parallel default(shared) private(i,j,L,pti,ptj,slot,Sij,Rsqij,R,Rshift, &
!$omp& rm2,rm6,rm12,phi,dphi,local_done)
!$omp do schedule(static)
DO i=1,N
    pti=ptype(i)
    DO L=Marker1(i),Marker2(i)
        pair_active(L)=.FALSE.
        pair_barrier(L)=.FALSE.
        j = List(L)
        ptj = ptype(j)
        Sij = pos(:,i) - pos(:,j)
        WHERE ( abs(Sij) > 0.5d0 * BoxSize )
            Sij = Sij - SIGN(BoxSize, Sij)
        END WHERE
        Rsqij = dot_product(Sij,Sij)
        IF ( Rsqij .lt. Rcutoffsq(pti,ptj) ) THEN
            R = SQRT(Rsqij)
            Rshift = R - PotShift(pti,ptj)
            IF ( Rshift < 0 ) THEN
                pair_barrier(L) = .TRUE.
            END IF
            rm2  = 1.d0/(Rshift**2)
            rm6  = rm2**3
            rm12 = rm6**2
            phi  =  4.d0 * epsil(pti,ptj) * (rm12 - rm6) - phicutoff(pti,ptj)
            dphi = 24.d0 * epsil(pti,ptj) * (2.d0 * rm12 - rm6) / Rshift / R
            pair_active(L) = .TRUE.
            pair_energy(L) = 0.5d0 * phi
            pair_force(:,L) = dphi * Sij
            pair_virial(L) = dphi * R * Rshift
        END IF
    END DO
END DO
!$omp end do
! Each atom gathers its interactions in original global list order.
! The local force is inserted at precisely the original point in that order.
!$omp do schedule(static)
DO i=1,N
    local_done=.FALSE.
    DO slot=incident_start(i),incident_start(i+1)-1
        L=incident_list(slot)
        IF (.NOT. local_done .AND. L > Marker2(i)) THEN
            CALL Add_Local_Forces(i)
            local_done=.TRUE.
        END IF
        IF (.NOT. pair_active(L)) CYCLE
        ene_pot(i)=ene_pot(i)+pair_energy(L)
        ene_pot_exbond(i)=ene_pot_exbond(i)+pair_energy(L)
        IF (pair_owner(L) == i) THEN
            acc(:,i)=acc(:,i)+pair_force(:,L)
        ELSE
            acc(:,i)=acc(:,i)-pair_force(:,L)
        END IF
    END DO
    IF (.NOT. local_done) CALL Add_Local_Forces(i)
END DO
!$omp end do
!$omp end parallel
! Preserve the scalar summation order too (no unordered reduction).
DO L=1,ListLength
    IF (pair_barrier(L)) PRINT *, 'barrier'
    IF (pair_active(L)) virial=virial-pair_virial(L)
END DO
virial=-virial/DIM
END SUBROUTINE Compute_Forces
SUBROUTINE Add_Local_Forces(i)
USE Particles
USE Simulation_Control
USE Parallel_Work
IMPLICIT NONE
INTEGER, INTENT(IN) :: i
DOUBLE PRECISION :: Sext(DIM), direction(DIM), Rext, rm, DISi, dphi1
    IF (i .le. N) THEN
        acc(:,i) = acc(:,i) + ( random_draw(:,i) - 0.5d0 ) * &
                    SQRT(24.d0*TRequested*gamma/deltat)
    END IF
    IF (i .le. N .and. mod(i,mchain)>1) THEN
        Sext =  pos(:,i+1) - pos(:,i-1)
        WHERE ( abs(Sext) > 0.5d0 * BoxSize )
            Sext = Sext - SIGN(BoxSize, Sext)
        END WHERE
        Rext = SQRT(dot_product(Sext,Sext))
        acc(:,i) = acc(:,i) + Fext*Sext/Rext
    END IF
    DISi=(r_sphere+2.d0**(1.d0/6.d0))-sqrt(dot_product(pos(:,i),pos(:,i)))
	if (DISi .le. 2.d0**(1.d0/6.d0)) then
		rm = 1.d0/(DISi**2)
		dphi1 = 100*24.d0 * (2.d0 * rm**6 - rm**3) / DISi**2
		direction = pos(:,i) / sqrt(dot_product(pos(:,i),pos(:,i)))
		acc(:,i) = acc(:,i) - dphi1 * DISi * direction
	end if
	DISi=sqrt(dot_product(pos(:,i),pos(:,i)))-(r_sphere-2.d0**(1.d0/6.d0))
	if (DISi .le. 2.d0**(1.d0/6.d0)) then
		rm = 1.d0/(DISi**2)
		dphi1 = 100*24.d0 * (2.d0 * rm**6 - rm**3) / DISi**2
		direction = -pos(:,i) / sqrt(dot_product(pos(:,i),pos(:,i)))
		acc(:,i) = acc(:,i) - dphi1 * DISi * direction
	end if
END SUBROUTINE Add_Local_Forces


SUBROUTINE Compute_Bonds
use Particles
use Potential
USE Parallel_Work
implicit none
double precision, dimension(DIM) :: Sij
double precision :: Rsqij, R, Rshift, phi,dphi
INTEGER :: pti, ptj
integer :: i,j,k,L,chain
!$omp parallel do default(shared) schedule(static) &
!$omp& private(chain,i,j,k,L,pti,ptj,Sij,Rsqij,R,Rshift,phi,dphi)
do chain=1,N/mchain
do i=(chain-1)*mchain+1,chain*mchain
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
        bond_virial(L) = dphi*R*Rshift
        acc(:,i) = acc(:,i) + dphi*Sij
        acc(:,j) = acc(:,j) - dphi*Sij
    end do
end do
end do
!$omp end parallel do
do L=1,BListLength
    virial=virial-bond_virial(L)
end do
END SUBROUTINE Compute_Bonds

SUBROUTINE Compute_Angle
USE Particles
USE Potential
IMPLICIT NONE
INTEGER :: i, j, k, L1, chain
DOUBLE PRECISION :: theta1, p, disi, disj
DOUBLE PRECISION, DIMENSION(DIM) :: Sij, ei, ej, eij, eji, eiij, ejji
!$omp parallel do default(shared) schedule(static) &
!$omp& private(chain,i,j,k,L1,theta1,p,disi,disj,Sij,ei,ej,eij,eji,eiij,ejji)
do chain=1,N/mchain
do j=(chain-1)*mchain+1,chain*mchain
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
            acc(:,i) = acc(:,i) - K_Angle /disi * dsin(theta - theta1) * eiij - &
                K_Angle /disj * dsin(theta - theta1) &
            * ejji
        end if
    end do
end do
end do
!$omp end parallel do
END SUBROUTINE Compute_Angle

SUBROUTINE Compute_Temperature(ene_kin_aver,temperature)
use Particles
implicit none
double precision :: ene_kin_aver, temperature
integer :: i
do i=1,N
    ene_kin(i) = 0.5d0*dot_product(vel(:,i),vel(:,i))
end do
ene_kin_aver = sum( ene_kin ) / N
temperature = 2.d0*ene_kin_aver/DIM
END SUBROUTINE Compute_Temperature
SUBROUTINE Update_List
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
        if ( all(m == iCell) ) then
            j = CellList(i)
        else
            where (m > nPart) m = m - nPart
            where (m <= 0) m = m + nPart
            j = Head(m(1),m(2),m(3))
        end if
        do while (j .ne. 0)
            Sij = pos(:,i) - pos(:,j)
            where ( abs(Sij) > 0.5d0 * BoxSize )
                Sij = Sij - sign(BoxSize,Sij)
            end where
            Rsqij = dot_product(Sij,Sij)
            if ( Rsqij < Rrangesq(pti,ptype(j)) ) then
                if ( L > MaxListLength ) then
                    ERROR STOP 'Update_List: List too small'
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
CALL Build_Incident_List
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
    if (Displ >= Displ1) then
        Displ2 = Displ1
        Displ1 = Displ
    else if (Displ >= Displ2) then
        Displ2 = Displ
    end if
end do
MovedTooMuch = ( Displ1 + Displ2 > Skin )
END FUNCTION MovedTooMuch
SUBROUTINE Print_Statistics
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
use Particles
use Simulation_Control
implicit none
integer :: i
character(LEN=10) :: strStep
CHARACTER(LEN=4) :: form
WRITE(strStep, '(I10.10)') step
OPEN(unit=2, file='out-'//strStep//'.xyz', status='replace')
WRITE(form,'(a,I1,a)') '(I', INT(LOG10(10.*N)), ')'
WRITE(2,form) N
WRITE(2,'(a,I10,a,3E23.15)') 'Atoms. Timestep: ', step, ', BoxSize: ', BoxSize
DO i = 1, N
    WRITE(2,'(I1,1X,3E23.15)') ptype(i), pos(:,i)
END DO
CLOSE(UNIT=2)
CLOSE(UNIT=2)
END SUBROUTINE Write_Sample
SUBROUTINE Terminate
use Particles
USE Potential
use Neighbor_List
USE Statistics
USE Parallel_Work
implicit none
deallocate( ptype )
deallocate( deltar )
deallocate( pos )
deallocate( vel )
deallocate( acc )
deallocate( ene_pot )
DEALLOCATE( ene_pot_exbond )
deallocate( ene_kin )
deallocate( BondList )
deallocate( BondMarker1 )
deallocate( BondMarker2 )
deallocate( AngleList )
deallocate( AngleMarker1 )
deallocate( AngleMarker2 )
deallocate( List )
deallocate( Marker1 )
deallocate( Marker2 )
deallocate( Advance )
deallocate( DisplaceList )
deallocate( CellList )
DEALLOCATE( epsil )
DEALLOCATE( Rcutoffsq )
DEALLOCATE( phicutoff )
DEALLOCATE( PotShift )
IF (ALLOCATED(pair_owner)) THEN
    DEALLOCATE(pair_owner,pair_force,pair_energy,pair_virial,pair_active,pair_barrier,incident_list)
END IF
IF (ALLOCATED(incident_start)) DEALLOCATE(incident_start)
DEALLOCATE(bond_virial,random_draw)
IF (ALLOCATED(Head)) DEALLOCATE(Head)
END SUBROUTINE Terminate


SUBROUTINE Build_Incident_List
USE Particles
USE Neighbor_List
USE Parallel_Work
IMPLICIT NONE
INTEGER :: counts(N), cursor(N), i,j,L, capacity
! Reuse allocations between neighbor rebuilds; grow only when needed.
capacity=0
IF (ALLOCATED(pair_owner)) capacity=SIZE(pair_owner)
IF (capacity < ListLength .OR. .NOT. ALLOCATED(pair_owner)) THEN
    IF (ALLOCATED(pair_owner)) THEN
        DEALLOCATE(pair_owner,pair_force,pair_energy,pair_virial,pair_active,pair_barrier,incident_list)
    END IF
    capacity=MAX(1,ListLength+ListLength/4)
    ALLOCATE(pair_owner(capacity),pair_force(DIM,capacity),pair_energy(capacity))
    ALLOCATE(pair_virial(capacity),pair_active(capacity),pair_barrier(capacity))
    ALLOCATE(incident_list(2*capacity))
END IF
IF (.NOT. ALLOCATED(incident_start)) ALLOCATE(incident_start(N+1))
counts=0
DO i=1,N
    DO L=Marker1(i),Marker2(i)
        j=List(L)
        IF (i == j) ERROR STOP 'Unexpected self-pair in neighbor list'
        pair_owner(L)=i
        counts(i)=counts(i)+1
        counts(j)=counts(j)+1
    END DO
END DO
incident_start(1)=1
DO i=1,N
    incident_start(i+1)=incident_start(i)+counts(i)
END DO
cursor=incident_start(1:N)
DO L=1,ListLength
    i=pair_owner(L)
    j=List(L)
    incident_list(cursor(i))=L
    incident_list(cursor(j))=L
    cursor(i)=cursor(i)+1
    cursor(j)=cursor(j)+1
END DO
END SUBROUTINE Build_Incident_List
