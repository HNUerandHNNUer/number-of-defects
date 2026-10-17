from audit import connect
for port,cmd in [(10053,'tail -4 /home/user/wxd/9.19.2026/sphere_distributed_20261017/bench/screen.2; tail -4 /home/user/wxd/9.19.2026/sphere_distributed_20261017/bench/screen.4'),(10006,'/home/user/soft/lammps-22Jul2025/build/lmp -h')]:
 c=connect('10.157.197.181',port);i,o,e=c.exec_command(cmd);x=o.read().decode();print(port,x if port==10053 else '\n'.join(l for l in x.splitlines() if any(k in l for k in ['GPU','KOKKOS','bd/sphere','lj/cut/gpu'])));c.close()
