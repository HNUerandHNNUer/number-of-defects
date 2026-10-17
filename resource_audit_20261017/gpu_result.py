from audit import connect
from pathlib import Path
c=connect('10.157.197.181',10006);s=c.open_sftp();s.get('/home/user/soft/lammps-22Jul2025/src/fix_bd_sphere.cpp','resource_audit_20261017/gpu_base.cpp');i,o,e=c.exec_command('grep -E "Loop time|ERROR|Performance|WARNING" /home/user/wxd/9.19.2026/sphere_distributed_20261017/gpu_bench/log.gpu');print(o.read().decode());c.close()
