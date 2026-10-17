from audit import connect
from pathlib import Path
c=connect('10.157.197.181',10052);s=c.open_sftp();script='''from pathlib import Path
import numpy as np,zipfile,json
b=Path('/home/user/wxd/9.19.2026/sphere_distributed_20261017');out=b/'progress_r3_first100m';out.mkdir(exist_ok=True);audit=[]
for d in sorted(b.glob('relax_n200*')):
 ss=[];xx=[]
 with (d/'trajectory.lammpstrj').open('rb') as f:
  while True:
   h=f.readline()
   if not h:break
   step=int(f.readline())
   if step>100000000:break
   f.readline();n=int(f.readline());f.readline();[f.readline() for _ in range(3)];f.readline();ls=[f.readline() for _ in range(n)]
   if not ls[-1].endswith(b'\\n'):break
   if step%10000000:continue
   a=np.fromstring(b''.join(ls).decode(),sep=' ').reshape(n,6);assert np.array_equal(a[:,0],np.arange(1,n+1));ss.append(step);xx.append(a[:,3:])
 assert len(ss)==11,(d.name,len(ss))
 np.savez_compressed(str(out/(d.name+'.npz')),steps=np.array(ss),xyz=np.array(xx));audit.append(dict(name=d.name,frames=len(ss),last=ss[-1]));print(d.name,len(ss),flush=True)
(out/'audit.json').write_text(json.dumps(audit,indent=2))
with zipfile.ZipFile(str(b/'progress_r3_first100m.zip'),'w') as z:
 for p in out.iterdir():z.write(str(p),p.name)
''';s.open('/home/user/wxd/9.19.2026/sphere_distributed_20261017/extract_r3.py','w').write(script);i,o,e=c.exec_command('/home/user/anaconda3/bin/python /home/user/wxd/9.19.2026/sphere_distributed_20261017/extract_r3.py',timeout=180);print(o.read().decode(),e.read().decode());s.get('/home/user/wxd/9.19.2026/sphere_distributed_20261017/progress_r3_first100m.zip','defect_focus_20261016/progress_r3_first100m.zip');c.close()
