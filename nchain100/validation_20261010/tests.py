"""Actual compiled CPU fix / Fortran force checks and diagnostic Brownian tests.
Original production inputs are never edited. Run with Anaconda Python (numpy/scipy).
"""
from pathlib import Path
import os,subprocess,json,hashlib,re,shutil,time
import numpy as np
P=Path(__file__).resolve().parent;W=P.parent
BIN=W/'parallel_source/validation/toolchain/w64devkit/bin'
ENV=os.environ.copy();ENV['PATH']=str(BIN)+os.pathsep+ENV['PATH'];ENV['OMP_NUM_THREADS']='1'
EXE=P/'build/lmp.exe';RC=2**(1/6);R=16.366342;BOX=2*R+5
RESULT={}
def save():
 (P/'results.json').write_text(json.dumps(RESULT,indent=2),encoding='utf8')
def run_lmp(d,text):
 d.mkdir(parents=True,exist_ok=True);(d/'in.test').write_text(text,encoding='ascii')
 t=time.perf_counter()
 with (d/'console.log').open('w') as f:r=subprocess.run([str(EXE),'-in','in.test'],cwd=d,env=ENV,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 if r.returncode:raise RuntimeError(str(d)+' failed: '+(d/'console.log').read_text(errors='replace')[-1800:])
 return time.perf_counter()-t
def data(d,x,m=30,box=BOX):
 n=len(x);nb=n-n//m;na=n-2*(n//m)
 lines=['audit coordinates','',f'{n} atoms',f'{nb} bonds',f'{na} angles','','1 atom types','1 bond types','1 angle types','']
 lines += [f'{-box/2:.16g} {box/2:.16g} {s}lo {s}hi' for s in 'xyz']
 lines += ['','Masses','','1 1','','Atoms # molecular','']
 lines += [f'{i+1} {i//m+1} 1 '+' '.join('%.16g'%z for z in a) for i,a in enumerate(x)]
 lines += ['','Bonds',''];b=0
 for i in range(n):
  if i%m<m-1:b+=1;lines.append(f'{b} 1 {i+1} {i+2}')
 lines+=['','Angles',''];b=0
 for i in range(n):
  if i%m<m-2:b+=1;lines.append(f'{b} 1 {i+1} {i+2} {i+3}')
 (d/'sample.data').write_text('\n'.join(lines)+'\n')
 (d/'initial.xyz').write_text(str(n)+'\nBoxSize: '+('%.16g '%box)*3+'\n'+'\n'.join('1 '+' '.join('%.16g'%z for z in a) for a in x)+'\n')
def base():
 return '''units lj
atom_style molecular
atom_modify map array
boundary p p p
read_data sample.data
comm_modify cutoff 3.0
neighbor 0.5 bin
neigh_modify every 1 delay 0 check yes
special_bonds fene
pair_style lj/cut 1.122462048309373
pair_coeff 1 1 1 1
pair_modify shift yes
bond_style fene
bond_coeff 1 30 1.5 1 1
angle_style cosine
angle_coeff 1 30
thermo 100000
thermo_style custom step pe
'''
def dump_read(p):
 a=p.read_text().splitlines();return np.array([[float(v) for v in z.split()] for z in a[9:]])
def analytic(x,m=30):
 n=len(x);pair=np.zeros_like(x);bond=pair.copy();angle=pair.copy();gated=pair.copy();active=pair.copy();wall=pair.copy();gate=0
 for i in range(n):
  dr=x[i]-x[i+1:];dr-=BOX*np.rint(dr/BOX);r=np.linalg.norm(dr,axis=1)
  good=r<RC
  if np.any(good):
   j=np.where(good)[0]+i+1;rr=r[good];v=24*(2/rr**12-1/rr**6)/rr**2;f=v[:,None]*dr[good]
   pair[i]+=f.sum(axis=0);pair[j]-=f
  if i%m<m-1:
   dr=x[i]-x[i+1];dr-=BOX*np.rint(dr/BOX);rr=np.dot(dr,dr)
   f=-30/(1-rr/2.25)*dr;bond[i]+=f;bond[i+1]-=f
  if i%m<m-2:
   a=x[i]-x[i+1];b=x[i+2]-x[i+1];a-=BOX*np.rint(a/BOX);b-=BOX*np.rint(b/BOX)
   l=np.linalg.norm(a);h=np.linalg.norm(b);u=a/l;v=b/h;p=np.dot(u,v)
   f=30/l*(p*u-v);g=30/h*(p*v-u)
   angle[i]+=f;angle[i+2]+=g;angle[i+1]-=f+g
   if abs(p)<.99:gated[i]+=f;gated[i+2]+=g;gated[i+1]-=f+g
   else:gate+=1
  if 0<i%m<m-1:
   d=x[i+1]-x[i-1];d-=BOX*np.rint(d/BOX);active[i]=25*d/np.linalg.norm(d)
 rad=np.linalg.norm(x,axis=1)
 for dist,sign in [(R+RC-rad,-1),(rad-R+RC,1)]:
  good=dist<=RC;d=dist[good]
  wall[good]+=sign*(2400*(2/d**13-1/d**7))[:,None]*x[good]/rad[good,None]
 return dict(pair=pair,bond=bond,angle=angle,gated=gated,active=active,wall=wall,gate_count=gate)
def compile_fortran():
 d=P/'fortran';d.mkdir(exist_ok=True)
 source=W/'F_25_bd_cpu2/serial'
 def clean(s):
  out=[]
  for z in s.splitlines():
   quote=None
   for k,c in enumerate(z):
    if c in ['"',"'"]:
     if quote==c:quote=None
     elif quote is None:quote=c
    elif c=='!' and quote is None:z=z[:k];break
   out.append(z)
  return '\n'.join(out)+'\n'
 mod=clean((source/'module.f90').read_text(errors='replace')).replace('CALL SYSTEM_CLOCK(COUNT = clock)','clock = 123456')
 body=clean((source/'bd_read.f90').read_text(errors='replace'));body=body[body.upper().index('SUBROUTINE NEW_SAMPLE'):]
 driver='''program audit
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
'''
 (d/'module.f90').write_text(mod);(d/'routines.f90').write_text(body);(d/'driver.f90').write_text(driver)
 cmd=[str(BIN/'gfortran.exe'),'-O2','-ffree-line-length-none','-fcheck=all','-fbacktrace','module.f90','routines.f90','driver.f90','-o','audit.exe']
 r=subprocess.run(cmd,cwd=d,env=ENV,capture_output=True);(d/'compile.log').write_bytes(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
 return d/'audit.exe'
def force_tests():
 fexe=compile_fortran();x=np.loadtxt(W/'F_25_bd_cpu2/serial/initial.xyz',skiprows=2)[:,1:4]
 d=P/'forces';d.mkdir(exist_ok=True);data(d,x);a=analytic(x)
 r=subprocess.run([str(fexe)],cwd=d,env=ENV,capture_output=True);(d/'fortran.log').write_bytes(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
 run_lmp(d,base()+'''timestep 0.01
fix bd all bd/sphere 1000 0 25 123456 mchain 30
run 1
write_dump all custom forces.dump id x y z fx fy fz modify sort id format float %.16g
run 1
write_dump all custom after2.dump id x y z modify sort id format float %.16g
''')
 l=dump_read(d/'forces.dump');ff=np.loadtxt(d/'force.txt');fa=np.loadtxt(d/'angle.txt');fb=np.loadtxt(d/'bond.txt')
 total=a['pair']+a['bond']+a['angle']+a['active']+a['wall'];ftotal=total-a['angle']+a['gated']
 RESULT['force_comparison']={
  'N':len(x),'angles_cut_off':a['gate_count'],'angles_total':2800,
  'fortran_bond_max_error':float(np.max(abs(fb-a['bond']))),
  'fortran_angle_gated_max_error':float(np.max(abs(fa-a['gated']))),
  'fortran_total_max_error':float(np.max(abs(ff-ftotal))),
  'lammps_total_max_error':float(np.max(abs(l[:,4:7]-total))),
  'lammps_fortran_force_max_difference':float(np.max(abs(l[:,4:7]-ff))),
  'difference_after_accounting_angle_gate':float(np.max(abs((l[:,4:7]-ff)-(a['angle']-a['gated'])))),
  'lammps_step1_max_displacement':float(np.max(abs(l[:,1:4]-x))),
  'fortran_step2_max_displacement':float(np.max(abs(np.loadtxt(d/'after2.txt')-x))),
  'lammps_step2_error_expected_drift':float(np.max(abs(dump_read(d/'after2.dump')[:,1:4]-x-.01/1000*total))) }
 save();print('force tests',RESULT['force_comparison'],flush=True)
def diffusion_tests():
 out=[]
 # 6000 independent particles, one final endpoint per particle; no interactions.
 for style in ['bd/audit/free','brownian']:
  for dt in [.01,.005,.0025]:
   d=P/('diffusion_'+style.replace('/','_')+'_'+str(dt));n=6000;t=10;steps=round(t/dt)
   fix=(f'fix bd all {style} 1000 1 0 246813 mchain 30' if style!='brownian' else 'fix bd all brownian 1 246813 gamma_t 1000 rng uniform')
   text=f'''units lj
atom_style atomic
atom_modify map array
region b block -50 50 -50 50 -50 50
create_box 1 b
create_atoms 1 random {n} 314159 b
mass 1 1
pair_style zero 2.0
pair_coeff * *
neighbor 0.5 bin
neigh_modify every 1 delay 0 check yes
timestep {dt}
thermo {steps}
write_dump all custom start.dump id xu yu zu modify sort id format float %.16g
{fix}
run {steps}
write_dump all custom end.dump id xu yu zu modify sort id format float %.16g
'''
   sec=run_lmp(d,text);dx=dump_read(d/'end.dump')[:,1:]-dump_read(d/'start.dump')[:,1:]
   # independent-particle uncertainty; not time-frame pseudoreplication
   di=np.sum(dx*dx,axis=1)/(6*t);estimate=di.mean();se=di.std(ddof=1)/np.sqrt(n)
   row=dict(style=style,dt=dt,particles=n,time=t,D=float(estimate),SE=float(se),z=float((estimate-.001)/se),pass_4SE=bool(abs(estimate-.001)<=4*se),seconds=sec)
   out.append(row);RESULT['diffusion']=out;save();print('diffusion',row,flush=True)
if __name__=='__main__':
 force_tests();diffusion_tests()
