import paramiko,json,concurrent.futures,time,os,getpass
from pathlib import Path
nodes=[('cpu%d'%i,'10.157.197.181',10050+i) for i in range(1,7)]+[('gpu%d'%i,'10.157.197.33' if i<5 else '10.157.197.181',10000+i) for i in range(1,7)]
def connect(host,port):
 c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect(host,port=port,username='user',password=os.environ.get('CPU_SSH_PASSWORD') or getpass.getpass('SSH password: '),timeout=12,auth_timeout=12);return c
cmd="hostname; nproc; uptime; free -m; df -h /home/user; ps -eo comm,pcpu --sort=-pcpu | head -16; command -v mpirun; command -v lmp; nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null; pgrep -af 'lmp|gmx|python.*train' | head -15"
def one(n):
 name,host,port=n
 try:
  c=connect(host,port);i,o,e=c.exec_command(cmd,timeout=25);r=dict(name=name,host=host,port=port,output=o.read().decode(),error=e.read().decode());c.close()
 except Exception as ex:r=dict(name=name,host=host,port=port,error=str(ex))
 print(name,r,flush=True);return r
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:r=list(pool.map(one,nodes))
 Path('resource_audit_20261017/inventory.json').write_text(json.dumps(r,indent=2))

