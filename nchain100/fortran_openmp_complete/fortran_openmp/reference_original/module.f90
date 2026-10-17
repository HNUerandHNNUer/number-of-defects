MODULE Particles
!
!   Contains all the data structures containing informations
!   about atom properties
!
    INTEGER, PARAMETER :: DIM = 3   ! change DIM to switch between 2D and 3D !
    LOGICAL :: VelAcc = .FALSE.     ! velocities and accelerations in file?s
    LOGICAL :: VideoSave = .FALSE.
    DOUBLE PRECISION :: hpdensity = 0.23d0
    INTEGER :: N
    INTEGER :: nchain 
    INTEGER :: mchain = 9
    DOUBLE PRECISION :: density, pi=dacos(-1.d0), enlarge
    DOUBLE PRECISION, DIMENSION(3) :: BoxSize  
!       the following arrays are allocated at run time
!       when the number of atoms N is known
    integer :: maxatomtype
    integer, dimension(:,:), allocatable :: im                  ! images
    integer, dimension(:), allocatable :: ptype                 ! particle type
    double precision, dimension(:,:), allocatable :: deltar     ! displacement
    double precision, dimension(:,:), allocatable :: pos        ! positions
    double precision, dimension(:,:), allocatable :: vel        ! velocities
    double precision, dimension(:,:), allocatable :: acc        ! accelerations
    double precision, dimension(:), allocatable :: ene_pot      ! potential energies
    DOUBLE PRECISION, DIMENSION(:), ALLOCATABLE :: ene_pot_exbond ! potential energies exclude bond potential
    double precision, dimension(:), allocatable :: ene_kin      ! kinetic energies
!       scalars derived from the above quantities
    double precision :: volume                                  ! these are constants
    double precision :: virial                                  ! virial term, used to compute the presure 
!       bond list
    integer, parameter :: MaxBondsPerAtom = 3
    integer, dimension(:), allocatable :: BondMarker1,BondMarker2,BondList
    integer :: BMaxListLength,BListLength
!       angleforce list 
    integer, parameter :: MaxAngleforcePerAtom = 3
    integer, dimension(:), allocatable :: AngleMarker1,AngleMarker2,AngleList
    integer :: AMaxListLength,AListLength
END MODULE Particles


module Simulation_Control
!
!   Contains the parameters controlling the simulation, which will be
!   supplied as input by the user.
!
    character*80     :: title   = 'BROWNIAN DYNAMICS'   ! Arbitrary 'title' string
    CHARACTER*20     :: argum
    integer          :: iPrint  = 10000                 ! Number of time setps to print information
    integer          :: iSave   = 100000                ! Number of time steps to save sample
    double precision :: deltat  = 0.01d0                ! Time steps (reduced units)
    double precision :: gamma   = 1d3                   ! Friction coefficient
    double precision :: Fext                     ! external active force
    double precision :: TRequested = 1.0d0              ! Desired temperature
    double precision :: Skin = 0.5d0                    ! extra range for neighbor list
    logical          :: lpps = .FALSE.                  ! print per step
    logical          :: lppp = .TRUE.                   ! print per 
    ! Bounce back control
    logical          :: sphere = .TRUE.                 ! sphere-like boundry condition
    double precision :: r_sphere = 1.4d1                ! radius of the sphere
    logical          :: cylinder = .FALSE.              ! cylinder-like boundry condition
    double precision :: r_cylinder = 3.5d1              ! radius of the cylinder
    ! global variables
    integer          :: step = 0
end module Simulation_Control


module Potential
    ! pairwise interactions (LJ and WCA)
    double precision, dimension(:,:), allocatable :: epsil
    double precision, dimension(:,:), allocatable :: Rcutoffsq
    double precision, dimension(:,:), allocatable :: phicutoff
    DOUBLE PRECISION, DIMENSION(:,:), ALLOCATABLE :: PotShift
    ! bond interactions (FENE)
    double precision, parameter :: FENE_K = 30.d0
    double precision, parameter :: FENE_Rmax = 1.5d0
    DOUBLE PRECISION, PARAMETER :: K_Angle = 30.d0
    DOUBLE PRECISION, PARAMETER :: theta = dacos(-1.d0)
end module Potential


module Statistics
!
!   Contains statistical quantities accumulated during the run.
!   All quantities are resetted to zero.
!
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
!   cell list
    integer :: nPart
    integer, dimension(3) :: iCell
    ! 将Head声明为可分配数组，而不是固定大小
    integer, dimension(:,:,:), allocatable :: Head
    integer, dimension(:), allocatable :: CellList
end module Neighbor_List


MODULE ran_mod
! module contains two FUNCTIONs
! ran RETURN a uniform random number between 0-1
! normal RETURN a normal distribution
CONTAINS
    FUNCTION ran()                                  ! RETURN random number between 0-1
        IMPLICIT NONE
        INTEGER,SAVE :: flag = 0
        DOUBLE PRECISION :: ran
        
        IF (flag == 0) THEN
            CALL init_random_seed(); flag = 1
        END IF
        CALL random_number(ran)                     ! built in fortran 90 random number FUNCTION
        RETURN
    END FUNCTION ran
    
    FUNCTION normal()                               ! RETURNs a normal distribution
        IMPLICIT NONE
        INTEGER, SAVE :: flag = 0
        DOUBLE PRECISION :: normal
        DOUBLE PRECISION :: fac, gsave, rsq, r1, r2
        SAVE gsave
        
        IF (flag.eq.0) THEN
            rsq = 2.0d0
            DO WHILE (rsq.ge.1.0d0.or.rsq.eq.0.0d0) ! new from for do
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
        INTEGER :: i, n, clock
        INTEGER, DIMENSION(:), ALLOCATABLE :: seed
        CALL RANDOM_SEED(size = n)
        ALLOCATE(seed(n))
        CALL SYSTEM_CLOCK(COUNT = clock)
        seed = clock + 37 * (/ (i - 1, i = 1, n) /)
        CALL RANDOM_SEED(PUT = seed)
        DEALLOCATE(seed)
    END SUBROUTINE    
END MODULE ran_mod
