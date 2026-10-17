from audit import connect
from concurrent.futures import ThreadPoolExecutor

def f(port):
 c=connect('10.157.197.181',port);i,o,e=c.exec_command("ls /home/user/anaconda3/bin/mpirun /home/user/anaconda3/lib/libmpi.so.12; find /home/user/soft -maxdepth 4 -type f -name 'lmp*' 2>/dev/null | head; lscpu | head -18; df -h /home/user");print(port,o.read().decode());c.close()
with ThreadPoolExecutor(max_workers=3) as p:list(p.map(f,[10052,10053,10006]))
