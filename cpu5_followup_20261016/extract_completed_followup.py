from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import json,time,zipfile
root=Path.cwd();out=root/'completed_analysis_20261016';out.mkdir(exist_ok=True)
status=json.load(open(root/'status.json'));manifest={j['name']:j for j in json.load(open(root/'manifest.json'))};audit=[]
for item in status:
 if item['state']!='completed':continue
 name=item['name'];p=root/name;j=manifest[name];target=out/(name+'.npz')
 log=(p/'log.lammps').read_text();assert (p/'final.bin').exists() and 'VALIDATION_RUN_COMPLETED' in log and 'ERROR' not in log
 entry=dict(j);entry['step_convention']='stored steps are physical time / 0.01';entry.update(snapshot_time=time.strftime('%F %T %z'),warnings=[l for l in log.splitlines() if 'WARNING:' in l],log_size=(p/'log.lammps').stat().st_size)
 if not target.exists():
  scale=int(round(.01/j['dt']));stride=(200000 if j['nchain']==10 else 500000)*scale
  saved={};last=-1;total=0
  with (p/'trajectory.lammpstrj').open('rb') as f:
   while True:
    head=f.readline()
    if not head:break
    assert head.strip()==b'ITEM: TIMESTEP';step=int(f.readline());assert f.readline().strip()==b'ITEM: NUMBER OF ATOMS';n=int(f.readline());assert n==j['nchain']*30
    assert f.readline().startswith(b'ITEM: BOX BOUNDS');box=[f.readline() for _ in range(3)]
    assert f.readline().strip()==b'ITEM: ATOMS id mol type x y z'
    keep=(step%stride==0) or (j['nchain']==10 and (step+10000*scale)%stride==0)
    lines=[f.readline() for _ in range(n)]
    if keep:
     a=np.fromstring(b''.join(lines).decode(),sep=' ').reshape(n,6)
     assert np.array_equal(a[:,0],np.arange(1,n+1)) and np.isfinite(a).all()
     assert np.all(a[:,1]==(a[:,0]-1)//30+1) and np.all(a[:,2]==1)
     saved[step//scale]=a[:,3:].copy()
    total+=1;last=step
  assert last==j['production_steps']
  steps=np.array(sorted(saved));xyz=np.array([saved[int(s)] for s in steps])
  np.savez_compressed(str(target),steps=steps,xyz=xyz)
  entry.update(total_frames=total,last_step=last,sampled_frames=len(steps))
 else:
  a=np.load(str(target));entry.update(last_step=int(a['steps'][-1]),sampled_frames=len(a['steps']))
 (out/(name+'.log')).write_text(log);audit.append(entry);print(name,entry['sampled_frames'],flush=True)
(out/'audit.json').write_text(json.dumps(audit,indent=2))
with zipfile.ZipFile(str(root/'completed_analysis_20261016.zip'),'w',zipfile.ZIP_STORED) as z:
 for p in out.iterdir():z.write(str(p),p.name)
print('EXTRACT_DONE',len(audit),flush=True)
