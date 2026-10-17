from pathlib import Path
import json,re,shutil,hashlib,zipfile
import numpy as np
HERE=Path(__file__).resolve().parent; OLD=HERE.parent/'cpu5_validation_20261015'; PACK=HERE/'sphere_followup_20261016';PACK.mkdir(exist_ok=True)
header=(OLD/'sphere_validation_20261015/branch_n10_F2_co_r1/in.production').read_text().split('# The custom')[0]
jobs=[]
def create(name,text,dt,F,rep,meta,warm=False):
 p=PACK/name;p.mkdir(exist_ok=True);(p/'polymer.data').write_text(text)
 seed=8610001+len(jobs)*10007;scale=round(.01/dt);steps=100000000*scale
 h=header.replace('timestep 0.01','timestep %g'%dt)
 if warm:h+='fix bd all bd/sphere 1000.0 1.0 0.1 %d mchain 30\nrun %d\nunfix bd\nreset_timestep 0\n'%(seed+110003,10000000*scale)
 body=h+'fix bd all bd/sphere 1000.0 1.0 %g %d mchain 30\n'%(F,seed)
 body+='dump traj all custom %d trajectory.lammpstrj id mol type x y z\ndump_modify traj sort id format float %%.10g\nrestart %d restart_A.bin restart_B.bin\n'%(10000*scale,5000000*scale)
 body+='run %d\nwrite_restart final.bin\nwrite_data final.data\nprint "VALIDATION_RUN_COMPLETED"\n'%steps
 (p/'in.production').write_text(body)
 smoke=header.replace('timestep 0.01','timestep %g'%dt)+'fix bd all bd/sphere 1000.0 1.0 %g %d mchain 30\nrun 20000\nprint "SMOKE_OK"\n'%(F,seed)
 (p/'in.smoke').write_text(smoke)
 rec=dict(name=name,dt=dt,F=F,replicate=rep,seed=seed,production_steps=steps,physical_duration=1e6,warmup_steps=10000000*scale if warm else 0,mpi_ranks=2,data_sha256=hashlib.sha256(text.encode()).hexdigest(),**meta)
 (p/'provenance.json').write_text(json.dumps(rec,indent=2));jobs.append(rec)
# Independent re-equilibration at equal physical warmup duration: not Brownian path paired.
for dt in (.005,.0025):
 for rep in (1,2,3):
  text=(OLD/'sphere_validation_20261015/size_n100_F5_r1/polymer.data').read_text()
  create('dt_n100_F5_%s_r%d'%(str(dt).replace('.','p'),rep),text,dt,5,rep,dict(nchain=100,experiment='timestep',preparation='same initial geometry; independent equal-time F0.1 warmup'),True)
# Control head-tail order with identical bead positions and nematic geometry.
for geom in ('co','counter'):
 text=(OLD/('sphere_validation_20261015/branch_n10_F2_%s_r1/polymer.data'%geom)).read_text();lines=text.splitlines();start=next(i for i,s in enumerate(lines) if s.strip().split('#')[0].strip()=='Atoms')
 ids=[]
 for i in range(start+1,len(lines)):
  s=lines[i].strip()
  if not s:continue
  if not s[0].isdigit():break
  ids.append(i)
 rows=[lines[i].split() for i in ids];xyz=np.array([[float(t) for t in r[3:6]] for r in rows]);xyz=xyz[np.argsort([int(r[0]) for r in rows])];c=xyz.reshape(10,30,3);u=c/np.linalg.norm(c,axis=2,keepdims=True);d=np.diff(u,axis=1);d/=np.linalg.norm(d,axis=2,keepdims=True);spin=np.cross(u[:,:-1],d).mean(1);_,_,vh=np.linalg.svd(spin);axis=vh[0];signed=spin.dot(axis)
 if signed.sum()<0:signed=-signed
 for pattern in ('aligned','balanced'):
  target=np.ones(10)
  if pattern=='balanced':target[np.argsort(np.abs(signed))[:5]]=-1
  flips=np.where(np.sign(signed)!=target)[0];new=c.copy();new[flips]=new[flips,::-1,:];new=new.reshape(-1,3);ll=lines.copy()
  for i,r in zip(ids,rows):ll[i]=' '.join(r[:3]+['%.12g'%v for v in new[int(r[0])-1]])
  for rep in (1,2,3):create('prep_n10_F2_%s_%s_r%d'%(geom,pattern,rep),'\n'.join(ll)+'\n',.01,2,rep,dict(nchain=10,experiment='polarity_preparation',geometry=geom,pattern=pattern,reversed_chains=(flips+1).tolist(),restart='coordinate reseeding with zero velocities; not exact restart'))
(PACK/'manifest.json').write_text(json.dumps(jobs,indent=2));shutil.copy2(str(OLD/'runner.py'),str(PACK/'runner.py'))
with zipfile.ZipFile(str(HERE/'sphere_followup_20261016.zip'),'w',zipfile.ZIP_DEFLATED) as z:
 for p in PACK.rglob('*'):
  if p.is_file():z.write(str(p),str(p.relative_to(HERE)))
print('Prepared',len(jobs),'jobs')
