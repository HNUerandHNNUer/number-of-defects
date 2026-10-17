import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,importlib.util,json
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from analyze import unit,local,dirs,GRID
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('nematic',ROOT/'nchain200/sphere_nematic_parallel.py');mod=importlib.util.module_from_spec(spec);sys.modules['nematic']=mod;spec.loader.exec_module(mod)
rows=[]
for n in [100,200,350]:
 for F in [.1,1,10]:
  info=json.loads((ROOT/f'mips_analysis_20261014/runs/n{n}_F{F:g}/done.json').read_text());R=info['R']
  for step in [50000000,60000000,70000000,80000000,90000000,100000000]:
   data=np.loadtxt(Path(info['coordinate_directory'])/f'defect_out-{step:010d}.xyz',skiprows=2);xyz=data[data[:,0]==1,1:];u=unit(xyz);tree=cKDTree(u)
   for h in [0,1.5,3]:
    res=mod.identify(xyz,settings=mod.Settings(smooth_k=0 if h==0 else 128,smooth_length=h));q=res['double_charge'];pos=unit(res['positions']);row=dict(n=n,F=F,step=step,h=h,Nplus=int((q==1).sum()),Nminus=int((q==-1).sum()),net=q.sum()/2,marker_plus=int((data[:,0]==2).sum()))
    for lab,sel in [('plus',q==1),('minus',q==-1),('candidate_faces',np.ones(len(q),dtype=bool))]:
     pp=pos[sel]
     if len(pp):
      rho=tree.query_ball_point(pp,2*np.sin(3/(2*R)),return_length=True)/(len(u)*(1-np.cos(3/R))/2)
      row[lab+'_rho']=rho.mean();row[lab+'_rho_below05']=np.mean(rho<.5)
    rows.append(row)
   print('smooth',n,F,step,flush=True)
pd.DataFrame(rows).to_csv(OUT/'smoothing_frames.csv',index=False)
pd.DataFrame(rows).groupby(['n','F','h']).mean().reset_index().to_csv(OUT/'smoothing_summary.csv',index=False)
