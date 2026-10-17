from audit import connect
from pathlib import Path
c=connect('10.157.197.181',10055)
cmd="cat /home/user/wxd/9.19.2026/sphere_relaxation_20261016/status.json; tail -5 /home/user/wxd/9.19.2026/sphere_relaxation_20261016/relax_n350_F0.3_r1/log.lammps; cat /home/user/wxd/9.19.2026/sphere_relaxation_20261016/relax_n350_F0_r3/in.production; ldd /home/user/wxd/9.19.2026/sphere_relaxation_20261016/bin/lmp; ls /home/user/anaconda3/bin/*mpi*; find /home/user -name fix_bd_sphere.cpp 2>/dev/null | head"
i,o,e=c.exec_command(cmd);s=o.read().decode();Path('resource_audit_20261017/cpu5_details.txt').write_text(s);print(s);c.close()
