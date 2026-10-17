import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,json,importlib.util
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/os.environ.get('CPU5_ANALYSIS_DIR','completed_analysis_20261016');OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'defect_dynamics_20261015'))
from analyze import unit,dirs,local,GRID,geometry
spec=importlib.util.spec_from_file_location('nematic',ROOT/'nchain200/sphere_nematic_parallel.py');mod=importlib.util.module_from_spec(spec);sys.modules['nematic']=mod;spec.loader.exec_module(mod)
audit=json.loads((OUT/'audit.json').read_text());allrows=[];smooth=[];summ=[]
if len(sys.argv)>1:audit=[j for j in audit if j['name']==sys.argv[1]]
for j in audit:
 name=j['name'];cache=OUT/(name+'_metrics.csv');scache=OUT/(name+'_scale.csv')
 if cache.exists():
  df=pd.read_csv(cache);sd=pd.read_csv(scache);allrows.extend(df.to_dict('records'));smooth.extend(sd.to_dict('records'))
 else:
  data=np.load(str(OUT/(name+'.npz')));steps=data['steps'];coords=data['xyz'];index={int(s):i for i,s in enumerate(steps)};rows=[];sr=[]
  stride=200000 if j['nchain']==10 else 500000
  for step in steps[steps%stride==0]:
   xyz=coords[index[int(step)]];u=unit(xyz);d=dirs(u);R=np.linalg.norm(xyz,axis=1).mean();tree=cKDTree(u);P,S=local(u,d,GRID,R,tree)
   circ=np.cross(u,d).mean(0);axis=unit(circ);cs=np.cross(u,d).reshape(-1,30,3).mean(1).dot(axis)
   bonds=np.linalg.norm(np.diff(xyz.reshape(-1,30,3),axis=1),axis=2)
   res=mod.identify(xyz);q=res['double_charge'];Nplus=int((q==1).sum());Nminus=int((q==-1).sum())
   row=dict(name=name,nchain=j['nchain'],F=j['F'],replicate=j['replicate'],branch=(j.get('geometry','size')+'_'+j.get('pattern',str(j.get('dt',.01)))),step=int(step),R=R,P=P.mean(),S=S.mean(),C=np.linalg.norm(circ),opposite_tangent=int((cs<0).sum()),Nplus=Nplus,Nminus=Nminus,net=q.sum()/2,four=int(Nplus==4 and Nminus==0),pair_density=Nminus/(4*np.pi*R*R),bond_max=bonds.max())
   if row['four']:row.update(geometry(unit(res['positions'][q==1])))
   if int(step)-10000 in index and j['nchain']==10:
    prev=coords[index[int(step)-10000]];X=prev.reshape(-1,30,3);Y=xyz.reshape(-1,30,3)
    U,sv,V=np.linalg.svd(np.einsum('bni,bnj->bij',X,Y));diag=np.tile(np.eye(3),(len(X),1,1));diag[:,-1,-1]=np.linalg.det(U@V);rot=U@diag@V
    rv=Rotation.from_matrix(rot.transpose(0,2,1)).as_rotvec();motion=rv.dot(axis);angles=np.linalg.norm(rv,axis=1)
    U,sv,V=np.linalg.svd(prev.T.dot(xyz));rr=U.dot(np.diag([1,1,np.linalg.det(U.dot(V))])).dot(V)
    row.update(opposite_motion=int((motion<0).sum()),sign_agreement=np.mean(np.sign(cs)==np.sign(motion)),rotation_fraction=1-np.sum((xyz-prev.dot(rr))**2)/np.sum((xyz-prev)**2),max_chain_angle_deg=angles.max()*180/np.pi,lag_steps=10000)
   rows.append(row)
   if step%5000000==0:
    for h in (0,1.5,3):
     z=res if h==0 else mod.identify(xyz,settings=mod.Settings(smooth_k=128,smooth_length=h));charge=z['double_charge'];sr.append(dict(name=name,nchain=j['nchain'],F=j['F'],replicate=j['replicate'],step=int(step),h=h,Nplus=int((charge==1).sum()),Nminus=int((charge==-1).sum()),net=charge.sum()/2))
  df=pd.DataFrame(rows);sd=pd.DataFrame(sr);df.to_csv(cache,index=False);sd.to_csv(scache,index=False);allrows.extend(rows);smooth.extend(sr)
 for label,lo,hi in [('all',0,int(df.step.max())),('late50',50000000,100000000),('late25',75000000,100000000),('matched30_60',30000000,60000000)]:
  if df.step.max()<hi:continue
  sel=df[(df.step>=lo)&(df.step<=hi)];r={k:sel[k].mean() for k in ['P','S','C','Nplus','Nminus','four','pair_density','opposite_tangent','pair_angle_deg','pair_center_deg','rotation_fraction','opposite_motion','sign_agreement'] if k in sel};r.update(name=name,nchain=j['nchain'],F=j['F'],replicate=j['replicate'],branch=df.branch.iloc[0],window=label,frames=len(sel));summ.append(r)
 print('DONE',name,flush=True)
if len(sys.argv)>1:sys.exit(0)
pd.DataFrame(allrows).to_csv(OUT/'frames.csv',index=False);pd.DataFrame(smooth).to_csv(OUT/'scales.csv',index=False);pd.DataFrame(summ).to_csv(OUT/'run_summary.csv',index=False)
df=pd.DataFrame(allrows);bad=df.net.ne(2).sum();assert bad==0
(OUT/'validation.json').write_text(json.dumps(dict(runs=len(audit),analyzed_frames=len(df),charge_failures=int(bad),last_step=int(df.step.max()),max_bond=float(df.bond_max.max())),indent=2))
print('ANALYSIS_COMPLETE',len(df),flush=True)
