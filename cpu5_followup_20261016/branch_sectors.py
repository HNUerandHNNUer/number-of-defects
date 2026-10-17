import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/'completed_analysis_20261016'
sys.path.insert(0,str(ROOT/'defect_dynamics_20261015'))
from analyze import unit,dirs
rows=[];summ=[]
for j in json.loads((OUT/'audit.json').read_text()):
 if j['nchain']!=10:continue
 data=np.load(str(OUT/(j['name']+'.npz')));coords=data['xyz'];index={int(t):i for i,t in enumerate(data['steps'])};prev=None;seq=[]
 for k,step in enumerate(data['steps']):
  if step%200000:continue
  u=unit(coords[k]);d=dirs(u);spin=np.cross(u,d).reshape(10,30,3).mean(1);w,V=np.linalg.eigh(spin.T.dot(spin));axis=V[:,-1]
  if prev is not None and axis.dot(prev)<0:axis=-axis
  prev=axis;proj=spin.dot(axis);cos=proj/np.maximum(np.linalg.norm(spin,axis=1),1e-15);nneg=int((proj<0).sum());minor=min(nneg,10-nneg)
  r=dict(name=j['name'],geometry=j['geometry'],pattern=j['pattern'],replicate=j['replicate'],step=int(step),time=step*.01,minority=minor,negative=nneg,min_abs_cos=float(abs(cos).min()),axis_fraction=float(w[-1]/w.sum()),labels=''.join('+' if z>0 else '-' for z in proj))
  if int(step)-10000 in index:
   X=coords[index[int(step)-10000]].reshape(10,30,3);Y=coords[k].reshape(10,30,3);U,sv,V=np.linalg.svd(np.einsum('bni,bnj->bij',X,Y));diag=np.tile(np.eye(3),(10,1,1));diag[:,-1,-1]=np.linalg.det(U@V);rot=U@diag@V;motion=Rotation.from_matrix(rot.transpose(0,2,1)).as_rotvec().dot(axis);neg=int((motion<0).sum());r.update(motion_minority=min(neg,10-neg),motion_sign_agreement=float(np.mean(np.sign(motion)==np.sign(proj))))
  rows.append(r);seq.append(r)
 a=pd.DataFrame(seq);late=a[a.step>=50000000];changes=[];state=a.minority.iloc[0]
 for i in range(1,len(a)-2):
  nxt=a.minority.iloc[i]
  if nxt!=state and np.all(a.minority.iloc[i:i+3]==nxt) and a.min_abs_cos.iloc[i:i+3].min()>.2:
   changes.append(dict(time=float(a.time.iloc[i]),before=int(state),after=int(nxt)));state=nxt
 summ.append(dict(name=j['name'],geometry=j['geometry'],pattern=j['pattern'],replicate=j['replicate'],initial_minority=int(a.minority.iloc[0]),final_minority=int(a.minority.iloc[-1]),late_minor_mean=late.minority.mean(),late_minor_min=int(late.minority.min()),late_minor_max=int(late.minority.max()),late_axis_fraction=late.axis_fraction.mean(),late_min_abs_cos=late.min_abs_cos.min(),persistent_sector_changes=changes))
pd.DataFrame(rows).to_csv(OUT/'branch_sector_frames.csv',index=False);(OUT/'branch_sector_summary.json').write_text(json.dumps(summ,indent=2));print(json.dumps(summ,indent=2))
