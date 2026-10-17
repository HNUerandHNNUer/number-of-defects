"""Produce complete OpenMP sources from the supplied, unchanged originals."""
from pathlib import Path
import re

here = Path(__file__).resolve().parent
parent = here.parent
def clean(path):
    result=[]
    for line in path.read_bytes().decode('utf-8',errors='replace').splitlines():
        quote=None
        for index,char in enumerate(line):
            if char in ("'", '"'):
                if quote==char: quote=None
                elif quote is None: quote=char
            elif char=='!' and quote is None:
                line=line[:index];break
        if line.strip():result.append(line.rstrip())
    return '\n'.join(result)+'\n'


mod = clean(parent/'module.f90')
src = clean(parent/'bd_read.f90')
mod += '''
! Buffers have one writer per interaction; gathering has one writer per atom.
MODULE Parallel_Work
  IMPLICIT NONE
  DOUBLE PRECISION, ALLOCATABLE :: pair_force(:,:), pair_energy(:), pair_virial(:)
  DOUBLE PRECISION, ALLOCATABLE :: bond_virial(:), random_draw(:,:)
  LOGICAL, ALLOCATABLE :: pair_active(:), pair_barrier(:)
  INTEGER, ALLOCATABLE :: incident_start(:), incident_list(:), pair_owner(:)
END MODULE Parallel_Work
'''
# Optional fixed seed, same serial generator and scalar draw ordering.
mod = mod.replace('INTEGER :: i, n, clock', '''INTEGER :: i, n, clock, status, ios
        CHARACTER(LEN=64) :: seed_text''')
mod = mod.replace('CALL SYSTEM_CLOCK(COUNT = clock)', '''CALL SYSTEM_CLOCK(COUNT = clock)
        CALL GET_ENVIRONMENT_VARIABLE('BD_SEED', seed_text, STATUS=status)
        IF (status == 0 .AND. LEN_TRIM(seed_text) > 0) THEN
            READ(seed_text, *, IOSTAT=ios) clock
            IF (ios /= 0) ERROR STOP 'Invalid BD_SEED'
            IF (clock < 0 .OR. clock > 2000000000) ERROR STOP 'BD_SEED must be 0..2000000000'
        END IF''')

src = src.replace('INTEGER :: i, k\n', '''INTEGER :: i, k, production_steps, env_status, ios
CHARACTER(LEN=64) :: env_value
''', 1)
src = src.replace('CALL Evolve_Sample(1000000000)', '''production_steps = 1000000000
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
CALL Evolve_Sample(production_steps)''')
src = src.replace("start_pos = INDEX(dummy_line, 'BoxSize:')", "start_pos = INDEX(dummy_line, 'BoxSize:')\nIF (start_pos == 0) ERROR STOP 'Missing BoxSize: in initial.xyz'")
src = src.replace('maxatomtype = 1\nCALL Allocate_Particles', "IF (N /= nchain*mchain) ERROR STOP 'N must equal nchain*mchain'\nIF (ANY(BoxSize <= 0.d0)) ERROR STOP 'Invalid box size'\nmaxatomtype = 1\nCALL Allocate_Particles",1)
src = src.replace('CLOSE(UNIT=10)', "CLOSE(UNIT=10)\nIF (ANY(ptype /= 1)) ERROR STOP 'This input supports atom type 1 only'",1)
# Original density was undefined in the read-from-file variant; used only for pressure.
src = src.replace('volume = BoxSize(1) * BoxSize(2) * BoxSize(3)', 'volume = BoxSize(1) * BoxSize(2) * BoxSize(3)\n! Number density for the legacy 3D pressure diagnostic only.\ndensity = N / volume')

def section(name):
    return re.search(r'(?im)^SUBROUTINE '+name+r'\b.*?^END SUBROUTINE '+name+r'\s*$',src,re.S|re.M)
def replace_section(name, text):
    global src
    match=section(name)
    assert match, name
    src=src[:match.start()]+text+'\n'+src[match.end():]

alloc=section('Allocate_Particles').group()
alloc=alloc.replace('implicit none','USE Parallel_Work\nimplicit none',1)
alloc=alloc.replace('END SUBROUTINE Allocate_Particles', '''allocate(bond_virial(BMaxListLength), random_draw(DIM,N))
END SUBROUTINE Allocate_Particles''')
replace_section('Allocate_Particles',alloc)

force=section('Compute_Forces').group()
local=force[force.index('    IF (i .le. N) THEN'):force.rindex('END DO')]
local=local.replace('(/ran(),ran(),ran()/)', 'random_draw(:,i)')
# Use a small atom-local routine so original local additions occur between
# the same incoming/outgoing pair contributions as in the serial source.
local_routine='''SUBROUTINE Add_Local_Forces(i)
USE Particles
USE Simulation_Control
USE Parallel_Work
IMPLICIT NONE
INTEGER, INTENT(IN) :: i
DOUBLE PRECISION :: Sext(DIM), direction(DIM), Rext, rm, DISi, dphi1
'''+local+'''END SUBROUTINE Add_Local_Forces
'''
pairbody=force[force.index('        j = List(L)'):force.index('    IF (i .le. N) THEN')]
pairbody=pairbody[:pairbody.rindex('    END DO')]
pairbody=pairbody.replace("                print *, 'barrier'",'                pair_barrier(L) = .TRUE.')
start=pairbody.index('            ene_pot(i)')
pairbody=pairbody[:start]+'''            pair_active(L) = .TRUE.
            pair_energy(L) = 0.5d0 * phi
            pair_force(:,L) = dphi * Sij
            pair_virial(L) = dphi * R * Rshift
        END IF
'''
newforce='''SUBROUTINE Compute_Forces
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
'''+pairbody+'''    END DO
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
'''+local_routine
replace_section('Compute_Forces',newforce)

b=section('Compute_Bonds').group()
b=b.replace('implicit none','USE Parallel_Work\nimplicit none',1).replace('integer :: i,j,k,L','integer :: i,j,k,L,chain')
b=b.replace('do i = 1,N','''!$omp parallel do default(shared) schedule(static) &
!$omp& private(chain,i,j,k,L,pti,ptj,Sij,Rsqij,R,Rshift,phi,dphi)
do chain=1,N/mchain
do i=(chain-1)*mchain+1,chain*mchain''',1)
b=b.replace('virial = virial - dphi*R*Rshift','bond_virial(L) = dphi*R*Rshift')
b=b.replace('END SUBROUTINE Compute_Bonds','''end do
!$omp end parallel do
do L=1,BListLength
    virial=virial-bond_virial(L)
end do
END SUBROUTINE Compute_Bonds''')
replace_section('Compute_Bonds',b)
a=section('Compute_Angle').group().replace('INTEGER :: i, j, k, L1','INTEGER :: i, j, k, L1, chain')
a=a.replace('do j = 1,N','''!$omp parallel do default(shared) schedule(static) &
!$omp& private(chain,i,j,k,L1,theta1,p,disi,disj,Sij,ei,ej,eij,eji,eiij,ejji)
do chain=1,N/mchain
do j=(chain-1)*mchain+1,chain*mchain''',1)
a=a.replace('END SUBROUTINE Compute_Angle','end do\n!$omp end parallel do\nEND SUBROUTINE Compute_Angle')
# Wrap legacy >132-character continuation while keeping operation order.
a=a.replace(' - K_Angle /disj * dsin(theta - theta1) &', ' - &\n                K_Angle /disj * dsin(theta - theta1) &')
replace_section('Compute_Angle',a)

u=section('Update_List').group()
u=u.replace("print *,'Update_List: FATAL: List too small'", "ERROR STOP 'Update_List: List too small'")
u=u.replace('ListLength = L - 1','ListLength = L - 1\nCALL Build_Incident_List')
replace_section('Update_List',u)
src+='''
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
'''
t=section('Terminate').group().replace('implicit none','USE Parallel_Work\nimplicit none',1)
t=t.replace('END SUBROUTINE Terminate','''IF (ALLOCATED(pair_owner)) THEN
    DEALLOCATE(pair_owner,pair_force,pair_energy,pair_virial,pair_active,pair_barrier,incident_list)
END IF
IF (ALLOCATED(incident_start)) DEALLOCATE(incident_start)
DEALLOCATE(bond_virial,random_draw)
IF (ALLOCATED(Head)) DEALLOCATE(Head)
END SUBROUTINE Terminate''')
replace_section('Terminate',t)
src=src.replace("'Atoms. Timestep: ', step", "'Atoms. Timestep: ', step")
src=src.replace("'(a,I9,a,3E23.15)'", "'(a,I10,a,3E23.15)'")
header='! OpenMP optimization: equations and original delayed update order retained.\n'
(here/'module.f90').write_text(header+mod,encoding='ascii')
(here/'bd_read.f90').write_text(header+src,encoding='ascii')
print('Generated complete module.f90 and bd_read.f90')
