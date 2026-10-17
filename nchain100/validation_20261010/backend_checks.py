"""External backend force verification; requires a real MPI/CUDA-enabled build.
python backend_checks.py --exe /path/lmp --mpi mpiexec
python backend_checks.py --exe /path/lmp --kokkos
GPU support is NOT inferred from a directory name or this script's existence.
"""
from tests import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--exe',required=True);p.add_argument('--mpi');p.add_argument('--kokkos',action='store_true');a=p.parse_args()
x=np.loadtxt(W/'F_25_bd_cpu2/serial/initial.xyz',skiprows=2)[:,1:4]
ref=analytic(x);expected=sum(ref[k] for k in ['pair','bond','angle','wall','active'])
rows=[]
for ranks in ([1,2,4] if a.mpi else [1]):
 d=P/f'backend_{"kokkos" if a.kokkos else "cpu"}_{ranks}';d.mkdir(exist_ok=True);data(d,x)
 style='bd/sphere/kk' if a.kokkos else 'bd/sphere'
 text=base()+f'timestep 0.01\nfix bd all {style} 1000 0 25 123456 mchain 30\nrun 1\nwrite_dump all custom force.dump id x y z fx fy fz modify sort id format float %.16g\n'
 (d/'in.test').write_text(text)
 cmd=([a.mpi,'-n',str(ranks)] if a.mpi else [])+[a.exe]+(['-k','on','g','1'] if a.kokkos else [])+['-in','in.test']
 with (d/'console.log').open('w') as f:r=subprocess.run(cmd,cwd=d,stdout=f,stderr=subprocess.STDOUT,timeout=300)
 row={'command':cmd,'exit_code':r.returncode,'ranks':ranks}
 if r.returncode==0:row['max_force_error']=float(np.max(abs(dump_read(d/'force.dump')[:,4:7]-expected)));row['passed']=row['max_force_error']<1e-8
 rows.append(row)
(P/'backend_results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
