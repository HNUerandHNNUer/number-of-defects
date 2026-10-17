from audit import connect
from pathlib import Path
import io,json
b='/home/user/wxd/9.19.2026/sphere_relaxation_20261016';dest='/home/user/wxd/9.19.2026/sphere_distributed_20261017'
s=connect('10.157.197.181',10055);sf=s.open_sftp();c=connect('10.157.197.181',10053);c.exec_command('mkdir -p '+dest+'/bench');f=c.open_sftp()
for src,name in [(b+'/bin/lmp','lmp'),(b+'/relax_n350_F0.3_r3/polymer.data','polymer.data')]:
 local='resource_audit_20261017/'+name;sf.get(src,local);f.put(local,dest+'/bench/'+name)
f.chmod(dest+'/bench/lmp',0o755)
x=sf.open(b+'/relax_n350_F0.3_r3/in.production').read().decode();x=x[:x.index('dump traj')]+'run 100000\n';f.open(dest+'/bench/in.bench','w').write(x)
i,o,e=c.exec_command('cd '+dest+'/bench && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /home/user/anaconda3/bin/mpirun -np 2 ./lmp -in in.bench -log log.2 > screen.2 2>&1; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /home/user/anaconda3/bin/mpirun -np 4 ./lmp -in in.bench -log log.4 > screen.4 2>&1',timeout=300)
print(o.read().decode(),e.read().decode());i,o,e=c.exec_command('grep -E "Loop time|ERROR|Performance" '+dest+'/bench/log.*');print(o.read().decode());c.close();s.close()


