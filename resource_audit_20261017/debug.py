from audit import connect
c=connect('10.157.197.181',10053);i,o,e=c.exec_command('ps -eo pid,comm,pcpu,args | grep -E "lmp|hydra|mpirun" | head -15; ls -l /home/user/wxd/9.19.2026/sphere_distributed_20261017/bench; /home/user/wxd/9.19.2026/sphere_distributed_20261017/bench/lmp -h | head -5');print(o.read().decode(),e.read().decode());c.close()
