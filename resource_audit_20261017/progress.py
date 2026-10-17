from audit import connect
from pathlib import Path
c=connect('10.157.197.181',10055);s=c.open_sftp();b='/home/user/wxd/9.19.2026';x=s.open(b+'/extract_progress_0040.py').read().decode().replace('progress_20261017_0040','progress_20261017_1535').replace('limit=100000000 if','limit=200000000 if').replace("if last<100000000:continue","if last<100000000:continue\n  if 'n350' in j['name']:last=min(last,100000000)").replace('stride=5000000 if','stride=10000000 if').replace('limit=200000000 if \'relax\' in campaign else 300000000','limit=(200000000 if last>=200000000 else 100000000)')
s.open(b+'/extract_progress_1535.py','w').write(x)
i,o,e=c.exec_command('OPENBLAS_NUM_THREADS=1 /home/user/anaconda3/bin/python '+b+'/extract_progress_1535.py',timeout=300);print(o.read().decode(),e.read().decode());s.get(b+'/progress_20261017_1535.zip','defect_focus_20261016/progress_20261017_1535.zip')
for port in [10006]:
 g=connect('10.157.197.181',port);i,o,e=g.exec_command("find /home/user/soft/lammps-22Jul2025 -maxdepth 3 -type f -executable -name 'lmp*'; command -v mpirun; ls /usr/local/bin/lmp* 2>/dev/null");print('GPU6',o.read().decode());g.close()
c.close()

