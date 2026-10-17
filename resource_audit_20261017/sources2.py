from audit import connect
c=connect('10.157.197.181',10006);i,o,e=c.exec_command("find /home/user/soft/lammps-22Jul2025/src -iname '*bd*sphere*'; /home/user/soft/lammps-22Jul2025/build/lmp -h | head -30");print(o.read().decode());c.close()
c=connect('10.157.197.181',10055);s=c.open_sftp();s.get('/home/user/soft/lammps-22Jul2025/src/fix_bd_sphere.cpp','resource_audit_20261017/fix_bd_sphere.cpp');c.close()
