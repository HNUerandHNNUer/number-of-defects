! OpenMP optimization: equations and original delayed update order retained.
MODULE Particles
    INTEGER, PARAMETER :: DIM = 3
    LOGICAL :: VelAcc = .FALSE.
    LOGICAL :: VideoSave = .FALSE.
    DOUBLE PRECISION :: hpdensity = 0.23d0
    INTEGER :: N
    INTEGER :: nchain
    INTEGER :: mchain = 9
    DOUBLE PRECISION :: density, pi=dacos(-1.d0), enlarge
    DOUBLE PRECISION, DIMENSION(3) :: BoxSize
    integer :: maxatomtype
    integer, dimension(:,:), allocatable :: im
    integer, dimension(:), allocatable :: ptype
    double precision, dimension(:,:), allocatable :: deltar
    double precision, dimension(:,:), allocatable :: pos
    double precision, dimension(:,:), allocatable :: vel
    double precision, dimension(:,:), allocatable :: acc
    double precision, dimension(:), allocatable :: ene_pot
    DOUBLE PRECISION, DIMENSION(:), ALLOCATABLE :: ene_pot_exbond
    double precision, dimension(:), allocatable :: ene_kin
    double precision :: volume
    double precision :: virial
    integer, parameter :: MaxBondsPerAtom = 3
    integer, dimension(:), allocatable :: BondMarker1,BondMarker2,BondList
    integer :: BMaxListLength,BListLength
    integer, parameter :: MaxAngleforcePerAtom = 3
    integer, dimension(:), allocatable :: AngleMarker1,AngleMarker2,AngleList
    integer :: AMaxListLength,AListLength
END MODULE Particles
module Simulation_Control
    character*80     :: title   = 'BROWNIAN DYNAMICS'
    CHARACTER*20     :: argum
    integer          :: iPrint  = 10000
    integer          :: iSave   = 100000
    double precision :: deltat  = 0.01d0
    double precision :: gamma   = 1d3
    double precision :: Fext
    double precision :: TRequested = 1.0d0
    double precision :: Skin = 0.5d0
    logical          :: lpps = .FALSE.
    logical          :: lppp = .TRUE.
    logical          :: sphere = .TRUE.
    double precision :: r_sphere = 1.4d1
    logical          :: cylinder = .FALSE.
    double precision :: r_cylinder = 3.5d1
    integer          :: step = 0
end module Simulation_Control
module Potential
    double precision, dimension(:,:), allocatable :: epsil
    double precision, dimension(:,:), allocatable :: Rcutoffsq
    double precision, dimension(:,:), allocatable :: phicutoff
    DOUBLE PRECISION, DIMENSION(:,:), ALLOCATABLE :: PotShift
    double precision, parameter :: FENE_K = 30.d0
    double precision, parameter :: FENE_Rmax = 1.5d0
    DOUBLE PRECISION, PARAMETER :: K_Angle = 30.d0
    DOUBLE PRECISION, PARAMETER :: theta = dacos(-1.d0)
end module Potential
module Statistics
    DOUBLE PRECISION :: ene_kin_aver, ene_pot_aver, ene_tot_aver, ene_pot_aver_exbond
    DOUBLE PRECISION :: temperature, pressure
    double precision :: temperature_sum = 0.d0
    double precision :: ene_kin_sum     = 0.d0
    double precision :: ene_pot_sum     = 0.d0
    double precision :: pressure_sum    = 0.d0
end module Statistics
module Neighbor_List
    integer, parameter :: MaxPairsPerAtom = 500
    integer, dimension(:), allocatable :: Advance, Marker1, Marker2, List
    integer :: MaxListLength, ListLength
    double precision, dimension(:,:), allocatable :: DisplaceList
    integer :: nPart
    integer, dimension(3) :: iCell
    integer, dimension(:,:,:), allocatable :: Head
    integer, dimension(:), allocatable :: CellList
end module Neighbor_List
MODULE ran_mod
CONTAINS
    FUNCTION ran()
        IMPLICIT NONE
        INTEGER,SAVE :: flag = 0
        DOUBLE PRECISION :: ran
        IF (flag == 0) THEN
            CALL init_random_seed(); flag = 1
        END IF
        CALL random_number(ran)
        RETURN
    END FUNCTION ran
    FUNCTION normal()
        IMPLICIT NONE
        INTEGER, SAVE :: flag = 0
        DOUBLE PRECISION :: normal
        DOUBLE PRECISION :: fac, gsave, rsq, r1, r2
        SAVE gsave
        IF (flag.eq.0) THEN
            rsq = 2.0d0
            DO WHILE (rsq.ge.1.0d0.or.rsq.eq.0.0d0)
                r1 = 2.0d0 * ran() - 1.0d0
                r2 = 2.0d0 * ran() - 1.0d0
                rsq = r1 * r1 + r2 * r2
            END DO
            fac = sqrt(-2.0d0*log(rsq)/rsq)
            gsave = r1 * fac
            normal = r2 * fac
            flag = 1
        ELSE
            normal = gsave
            flag = 0
        ENDIF
        RETURN
    END FUNCTION normal
    SUBROUTINE init_random_seed()
        INTEGER :: i, n, clock, status, ios
        CHARACTER(LEN=64) :: seed_text
        INTEGER, DIMENSION(:), ALLOCATABLE :: seed
        CALL RANDOM_SEED(size = n)
        ALLOCATE(seed(n))
        CALL SYSTEM_CLOCK(COUNT = clock)
        CALL GET_ENVIRONMENT_VARIABLE('BD_SEED', seed_text, STATUS=status)
        IF (status == 0 .AND. LEN_TRIM(seed_text) > 0) THEN
            READ(seed_text, *, IOSTAT=ios) clock
            IF (ios /= 0) ERROR STOP 'Invalid BD_SEED'
            IF (clock < 0 .OR. clock > 2000000000) ERROR STOP 'BD_SEED must be 0..2000000000'
        END IF
        seed = clock + 37 * (/ (i - 1, i = 1, n) /)
        CALL RANDOM_SEED(PUT = seed)
        DEALLOCATE(seed)
    END SUBROUTINE
END MODULE ran_mod

! Buffers have one writer per interaction; gathering has one writer per atom.
MODULE Parallel_Work
  IMPLICIT NONE
  DOUBLE PRECISION, ALLOCATABLE :: pair_force(:,:), pair_energy(:), pair_virial(:)
  DOUBLE PRECISION, ALLOCATABLE :: bond_virial(:), random_draw(:,:)
  LOGICAL, ALLOCATABLE :: pair_active(:), pair_barrier(:)
  INTEGER, ALLOCATABLE :: incident_start(:), incident_list(:), pair_owner(:)
END MODULE Parallel_Work
