from audit import connect
from pathlib import Path
c=connect('10.157.197.181',10006);s=c.open_sftp();s.get('/home/user/soft/lammps-22Jul2025/src/fix_bd_sphere_kokkos.cpp','resource_audit_20261017/fix_bd_sphere_kokkos.cpp');c.close()
c=connect('10.157.197.181',10055);s=c.open_sftp();s.get('/home/user/soft/lammps-22Jul2025/src/fix_bd_sphere.cpp','resource_audit_20261017/fix_bd_sphere.cpp');c.close()

