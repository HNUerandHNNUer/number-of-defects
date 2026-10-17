import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,json,importlib.util,time
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/'final_analysis_cpu5'
spec=importlib.util.spec_from_file_location('nematic',ROOT/'nchain200/sphere_nematic_parallel.py');mod=importlib.util.module_from_spec(spec);sys.modules['nematic']=mod;spec.loader.exec_module(mod)
p=Path(sys.argv[1]);tag=p.stem;data=np.load(str(p));steps=data['steps'];xyz=data['xyz'];R=float(np.linalg.norm(xyz[0],axis=1).mean());records=[];series={};counts=[]
for h in (0,1.5):
 cache=OUT/(tag+'_h%g_markers.json'%h)
 if cache.exists():seq=json.loads(cache.read_text())
 else:
  seq=[]
  for k,x in enumerate(xyz):
   z=mod.identify(x,settings=mod.Settings(smooth_k=128 if h else 0,smooth_length=h));q=z['double_charge'];assert q.sum()==4
   seq.append({str(s):(z['positions'][q==s]/R).tolist() for s in (-1,1)})
  cache.write_text(json.dumps(seq,separators=(',',':')))
 series[h]=seq
 for k,s in enumerate(steps):counts.append(dict(window=tag,step=int(s),h=h,Nplus=len(seq[k]['1']),Nminus=len(seq[k]['-1'])))
 print('FIELD_DONE',tag,h,len(seq),flush=True)

def track(seq,times,sign,gate):
 tracks=[];active=[];before=np.empty((0,3));matched_dist=[];births=0;deaths=0
 for k,(entry,t) in enumerate(zip(seq,times)):
  now=np.array(entry[str(sign)]).reshape(-1,3);now=now/np.maximum(np.linalg.norm(now,axis=1,keepdims=True),1e-15);pairs=[]
  if len(before) and len(now):
   chord=np.linalg.norm(before[:,None,:]-now[None,:,:],axis=2);dist=2*R*np.arcsin(np.clip(chord/2,0,1));cost=np.where(dist<=gate,dist,1e6)
   a,b=linear_sum_assignment(cost);pairs=[(int(i),int(j)) for i,j in zip(a,b) if dist[i,j]<=gate];matched_dist.extend([float(dist[i,j]) for i,j in pairs])
  newactive=[None]*len(now);used_old=set();used_new=set()
  for i,j in pairs:
   idx=active[i];tracks[idx]['end']=int(t);tracks[idx]['observations']+=1;newactive[j]=idx;used_old.add(i);used_new.add(j)
  for i in set(range(len(before)))-used_old:deaths+=1
  for j in set(range(len(now)))-used_new:
   idx=len(tracks);tracks.append(dict(start=int(t),end=int(t),left_censored=k==0,right_censored=False,observations=1));newactive[j]=idx
   if k:births+=1
  before=now;active=newactive
 for idx in active:tracks[idx]['right_censored']=True
 complete=[z for z in tracks if not z['left_censored'] and not z['right_censored']];life=np.array([z['end']-z['start'] for z in complete])
 result=dict(births=births,deaths=deaths,tracks=len(tracks),complete_tracks=len(complete),censored_tracks=len(tracks)-len(complete),mean_observed_span_steps=float(life.mean()) if len(life) else None,median_observed_span_steps=float(np.median(life)) if len(life) else None,single_frame_fraction=float(np.mean(life==0)) if len(life) else None,max_match_distance=max(matched_dist) if matched_dist else None)
 return result,tracks

for h,seq in series.items():
 for every in (100,1000,10000):
  stride=every//100;tt=steps[::stride];ss=seq[::stride]
  for gate in (0.75,1.5,3.0):
   for sign in (-1,1):
    result,tracks=track(ss,tt,sign,gate);result.update(window=tag,h=h,every=every,gate=gate,sign=sign,frames=len(tt),duration_steps=int(tt[-1]-tt[0]),mean_count=np.mean([len(x[str(sign)]) for x in ss]));records.append(result)
    if every==100 and gate==1.5:
     pd.DataFrame(tracks).to_csv(OUT/(tag+'_h%g_sign%d_tracks.csv'%(h,sign)),index=False)
pd.DataFrame(records).to_csv(OUT/(tag+'_tracking.csv'),index=False);pd.DataFrame(counts).to_csv(OUT/(tag+'_fine_counts.csv'),index=False)
print('FINE_COMPLETE',tag,flush=True)
