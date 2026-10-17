from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json,time,zipfile,numpy as np
root=Path.cwd();out=root/'partial_analysis_20261015';audit=json.loads((out/'audit.json').read_text());audit=[j for j in audit if j['nchain']!=100]
for j in json.load(open(root/'manifest.json')):
 if j['nchain']!=100:continue
 name=j['name'];p=root/name;target=out/(name+'.npz');cap=60000000;saved={};total=0
 with (p/'trajectory.lammpstrj').open('rb') as f:
  while True:
   assert f.readline().strip()==b'ITEM: TIMESTEP';step=int(f.readline());assert f.readline().strip()==b'ITEM: NUMBER OF ATOMS';n=int(f.readline());assert n==j['atoms']
   assert f.readline().startswith(b'ITEM: BOX BOUNDS');box=[f.readline() for _ in range(3)];assert f.readline().strip()==b'ITEM: ATOMS id mol type x y z'
   lines=[f.readline() for _ in range(n)];total+=1
   if step%500000==0:
    a=np.fromstring(b''.join(lines).decode(),sep=' ').reshape(n,6);assert np.array_equal(a[:,0],np.arange(1,n+1)) and np.isfinite(a).all();saved[step]=a[:,3:].copy()
   if step==cap:break
 assert max(saved)==cap;steps=np.array(sorted(saved));np.savez_compressed(str(target),steps=steps,xyz=np.array([saved[int(s)] for s in steps]))
 log=(p/'log.lammps').read_text();entry=dict(j);entry.update(snapshot_time=time.strftime('%F %T %z'),status='interim',last_step=cap,sampled_frames=len(steps),total_frames=total,warnings=[l for l in log.splitlines() if 'WARNING:' in l]);audit.append(entry);print(name,len(steps),flush=True)
(out/'audit.json').write_text(json.dumps(audit,indent=2))
with zipfile.ZipFile(str(root/'partial_analysis_updated.zip'),'w',zipfile.ZIP_STORED) as z:
 for p in out.iterdir():
  if p.name=='audit.json' or p.name.startswith('size_n100') or p.name.startswith('size_n50') and '_r3' in p.name:z.write(str(p),p.name)
print('UPDATED_EXTRACT_DONE',len(audit),flush=True)
