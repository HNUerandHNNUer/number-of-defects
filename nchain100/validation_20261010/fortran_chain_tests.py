from tests import *
d=P/'fortran_chain';d.mkdir(exist_ok=True)
mod=(P/'fortran/module.f90').read_text().replace('INTEGER :: i, n, clock','INTEGER :: i, n, clock\nCHARACTER(LEN=32) :: seed_arg').replace('clock = 123456',"call get_command_argument(2,seed_arg)\nread(seed_arg,*) clock")
(d/'module.f90').write_text(mod);shutil.copy2(P/'fortran/routines.f90',d/'routines.f90')
driver='''program passive
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
'''
(d/'driver.f90').write_text(driver)
r=subprocess.run([str(BIN/'gfortran.exe'),'-O2','-ffree-line-length-none','-fcheck=all','module.f90','routines.f90','driver.f90','-o','passive.exe'],cwd=d,env=ENV,capture_output=True)
(d/'compile.log').write_bytes(r.stdout+r.stderr)
if r.returncode:raise RuntimeError(r.stderr.decode())
rows=[]
for dt in [.01,.005,.0025]:
 for seed in [13579,24681,35791]:
  case=P/f'chain_sphere_fortran_{dt}_{seed}';case.mkdir(exist_ok=True)
  s=(np.arange(30)-14.5)*.965;x=np.column_stack([R*np.cos(s/R),R*np.sin(s/R),np.zeros(30)]);data(case,x)
  t=time.perf_counter();r=subprocess.run([str(d/'passive.exe'),str(dt),str(seed)],cwd=case,env=ENV,capture_output=True,timeout=300)
  (case/'console.log').write_bytes(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError(r.stderr.decode())
  a=np.loadtxt(case/'trajectory.txt').reshape(-1,30,3);b=np.diff(a,axis=1);bl=np.linalg.norm(b,axis=2);u=b/bl[:,:,None];co=np.sum(u[:,:-1]*u[:,1:],axis=2);rad=np.linalg.norm(a,axis=2)-R
  row=dict(geometry='sphere',method='fortran',dt=dt,seed=seed,physical_time=1000,mean_bond=float(bl[499:].mean()),mean_cos=float(co[499:].mean()),radial_rms=float(np.sqrt(np.mean(rad[499:]**2))),max_saved_bond=float(bl.max()),bad_saved_frames=int(np.count_nonzero(np.any(bl>=1.5,axis=1))),seconds=time.perf_counter()-t)
  rows.append(row);(P/'fortran_chain_results.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
