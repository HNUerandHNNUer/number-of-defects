from audit import connect
from pathlib import Path
import io
b='/home/user/wxd/9.19.2026/sphere_relaxation_20261016';d='/home/user/wxd/9.19.2026/sphere_distributed_20261017/gpu_bench'
a=connect('10.157.197.181',10055);s=a.open_sftp();g=connect('10.157.197.181',10006);i,o,e=g.exec_command('mkdir -p '+d);o.channel.recv_exit_status();f=g.open_sftp();s.get(b+'/relax_n350_F0.3_r3/polymer.data','resource_audit_20261017/gpu_polymer.data');f.put('resource_audit_20261017/gpu_polymer.data',d+'/polymer.data');x=s.open(b+'/relax_n350_F0.3_r3/in.production').read().decode();x=x[:x.index('dump traj')]+'run 100000\n';f.open(d+'/in.bench','w').write(x);i,o,e=g.exec_command('cd '+d+' && OMP_NUM_THREADS=1 /home/user/soft/lammps-22Jul2025/build/lmp -k on g 1 -sf kk -in in.bench -log log.gpu > screen.gpu 2>&1',timeout=300);print(o.read().decode(),e.read().decode());i,o,e=g.exec_command('tail -12 '+d+'/screen.gpu');print(o.read().decode());g.close();a.close()
