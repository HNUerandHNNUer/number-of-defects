# -*- coding: utf-8 -*-
from pathlib import Path
import numpy as np,pandas as pd,json
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
SRC=ROOT/'defect_focus_20261016/progress_20261016_2305'
def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-14)
rows=[]
for p in SRC.glob('*.npz'):
 a=np.load(str(p));name=p.stem;n=int(name.split('_')[1][1:]);F=float(name.split('_')[2][1:]);seed=int(name[-1])
 for step,x in zip(a['steps'],a['xyz']):
  x=x.reshape(n,30,3);u=unit(x);R=np.linalg.norm(x,axis=-1).mean();co=np.clip((u[:,1:]*u[:,:-1]).sum(-1),-1,1);arc=R*np.arccos(co);length=arc.sum(1)
  # Incoming and outgoing great-circle tangents at each interior bead.
  incoming=unit(u[:,1:-1]*co[:,:-1,None]-u[:,:-2]);outgoing=unit(u[:,2:]-u[:,1:-1]*co[:,1:,None]);turn=np.arccos(np.clip((incoming*outgoing).sum(-1),-1,1));ds=(arc[:,:-1]+arc[:,1:])/2
  endarc=R*np.arccos(np.clip((u[:,0]*u[:,-1]).sum(-1),-1,1));row=dict(name=name,n=n,F=F,seed=seed,step=int(step),geodesic_bend=np.mean(turn**2/ds**2),turn_cost=np.mean(1-np.cos(turn)),extension=np.mean(endarc/length),contour=length.mean(),bond_max=np.linalg.norm(np.diff(x,axis=1),axis=-1).max());rows.append(row)
c=pd.DataFrame(rows);c.to_csv(OUT/'chain_frames.csv',index=False)
d=pd.read_csv(SRC/'fixed_frames.csv');m=d.merge(c,on=['name','step'],validate='many_to_one');assert len(m)==494
m['window']=np.where(m.step<=20000000,'early','late');s=m[m.step>=5000000].groupby(['n','F','seed','h','window'],as_index=False)[['Nplus','Nminus','pair_density','geodesic_bend','extension']].mean();s.to_csv(OUT/'chain_seed_windows.csv',index=False)
cor=[]
for (name,h),a in m.groupby(['name','h']):
 for q in ('geodesic_bend','extension'):
  r,pv=spearmanr(a[q],a.Nminus);dr,dp=spearmanr(np.diff(a[q]),np.diff(a.Nminus));cor.append(dict(name=name,h=h,metric=q,rho=r,pvalue_descriptive=pv,difference_rho=dr))
pd.DataFrame(cor).to_csv(OUT/'descriptive_correlations.csv',index=False)
g=s.groupby(['n','F','h','window'],as_index=False)[['Nplus','geodesic_bend','extension']].mean();g.to_csv(OUT/'chain_group_windows.csv',index=False)
data={'groups':g.to_dict('records'),'curves':m.groupby(['n','F','h','step'],as_index=False)[['Nplus','geodesic_bend','extension']].mean().to_dict('records'),'checks':{'frames':len(c),'merged_rows':len(m),'max_bond':float(c.bond_max.max()),'min_extension':float(c.extension.min()),'max_extension':float(c.extension.max())}}
(OUT/'data.json').write_text(json.dumps(data,indent=2));print(g[g.h==1.5].to_string(index=False))
