# -*- coding: utf-8 -*-
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from concurrent.futures import ProcessPoolExecutor
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/'dt_matched_20261016';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'cpu5_followup_20261016'));from fixed_grid import mesh,detect
sys.path.insert(0,str(ROOT/'defect_dynamics_20261015'));from analyze import unit,dirs,local,GRID
def work(job):
 path,dt=job;p=Path(path);dest=OUT/(p.stem+'_matched.csv')
 if dest.exists():return p.stem
 a=np.load(str(p));v,g=mesh(5);rows=[]
 times=a['steps']*(dt if dt==.0025 else .01)
 for t in np.arange(250000,750001,50000):
  ix=np.where(times==t)[0];assert len(ix)==1,(p,t);x=a['xyz'][ix[0]];u=unit(x);R=np.linalg.norm(x,axis=1).mean();tree=cKDTree(u);P,S=local(u,dirs(u),GRID,R,tree);ct=tree.query_ball_point(GRID,2*np.sin(3/(2*R)),return_length=True)
  for h in (1.5,3.):
   z=detect(x,v,g,h);rows.append(dict(name=p.stem,dt=dt,seed=int(p.stem[-1]),time=t,h=h,Nplus=z['Nplus'],Nminus=z['Nminus'],P4=int(z['Nplus']==4 and z['Nminus']==0),rho_pair=z['Nminus']/(4*np.pi*R**2),P=P.mean(),S=S.mean(),cv3=ct.std()/ct.mean()))
 pd.DataFrame(rows).to_csv(dest,index=False);return p.stem
if __name__=='__main__':
 jobs=[]
 for r in (1,2,3):
  jobs.extend([(ROOT/'cpu5_validation_20261015/final_analysis_cpu5'/('size_n100_F5_r%d.npz'%r),.01),(ROOT/'cpu5_followup_20261016/completed_analysis_20261016'/('dt_n100_F5_0p005_r%d.npz'%r),.005),(OUT/('dt_n100_F5_0p0025_r%d.npz'%r),.0025)])
 with ProcessPoolExecutor(max_workers=3) as pool:
  for name in pool.map(work,jobs):print(name,flush=True)
 a=pd.concat([pd.read_csv(p) for p in OUT.glob('*_matched.csv')]);a.to_csv(OUT/'frames.csv',index=False)
 s=a.groupby(['dt','seed','h'],as_index=False)[['Nplus','Nminus','P4','rho_pair','P','S','cv3']].mean();s.to_csv(OUT/'seed_summary.csv',index=False)
 g=s.groupby(['dt','h']).agg(['mean','std']);g.to_csv(OUT/'group_summary.csv');print(g.to_string())
