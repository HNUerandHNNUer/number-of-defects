from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import json,time,zipfile,re
root=Path.cwd();out=root/'final_analysis_cpu5';out.mkdir(exist_ok=True)
jobs=json.load(open(root/'manifest.json'));status=json.load(open(root/'status.json'));assert len(status)==24 and all(j['state']=='completed' for j in status)
def read_dump(path,stride):
 steps=[];xyz=[];total=0;last=-1
 with path.open('rb') as f:
  while True:
   head=f.readline()
   if not head:break
   assert head.strip()==b'ITEM: TIMESTEP';step=int(f.readline());assert f.readline().strip()==b'ITEM: NUMBER OF ATOMS';n=int(f.readline());assert f.readline().startswith(b'ITEM: BOX BOUNDS')
   for _ in range(3):f.readline()
   assert f.readline().strip()==b'ITEM: ATOMS id mol type x y z';lines=[f.readline() for _ in range(n)]
   if step%stride==0:
    a=np.fromstring(b''.join(lines).decode(),sep=' ').reshape(n,6);assert np.isfinite(a).all() and np.array_equal(a[:,0],np.arange(1,n+1));assert np.all(a[:,1]==(a[:,0]-1)//30+1)
    if steps and steps[-1]==step:assert np.allclose(xyz[-1],a[:,3:]);continue
    steps.append(step);xyz.append(a[:,3:].copy())
   total+=1;last=step
 return np.array(steps),np.array(xyz),total,last
audit=[]
for j in jobs:
 p=root/j['name'];log=(p/'log.lammps').read_text();assert 'VALIDATION_RUN_COMPLETED' in log and 'ERROR' not in log and (p/'final.bin').exists()
 entry=dict(j);entry.update(status='complete',snapshot_time=time.strftime('%F %T %z'),last_step=100000000,warnings=[l for l in log.splitlines() if 'WARNING:' in l])
 if j['nchain']==100:
  steps,xyz,total,last=read_dump(p/'trajectory.lammpstrj',500000);assert last==100000000
  np.savez_compressed(str(out/(j['name']+'.npz')),steps=steps,xyz=xyz);entry.update(sampled_frames=len(steps),total_frames=total)
 else:entry['sampled_frames']=1001 if j['nchain']==10 else 201
 for label in ['early','middle','late']:
  fine=p/('fine_'+label+'.lammpstrj')
  if fine.exists():
   steps,xyz,total,last=read_dump(fine,100);np.savez_compressed(str(out/(j['name']+'__'+label+'.npz')),steps=steps,xyz=xyz);print('fine',j['name'],label,len(steps),flush=True)
 (out/(j['name']+'.log')).write_text(log)
 audit.append(entry);print('job',j['name'],flush=True)
(out/'audit.json').write_text(json.dumps(audit,indent=2))
with zipfile.ZipFile(str(root/'final_analysis_cpu5.zip'),'w',zipfile.ZIP_DEFLATED) as z:
 for p in out.iterdir():z.write(str(p),p.name)
print('FINAL_EXTRACT_DONE',flush=True)
