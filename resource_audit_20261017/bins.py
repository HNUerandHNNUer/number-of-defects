from audit import connect
from concurrent.futures import ThreadPoolExecutor

def f(port):
 c=connect('10.157.197.181',port);i,o,e=c.exec_command('ls -lh /home/user/soft/lammps-22Jul2025/build/lmp /home/user/wxd/9.19.2026/sphere_relaxation_20261016/bin/lmp 2>/dev/null; /home/user/soft/lammps-22Jul2025/build/lmp -h | grep bd/sphere');print(port,o.read().decode());c.close()
with ThreadPoolExecutor(max_workers=2) as p:list(p.map(f,[10053,10055]))
