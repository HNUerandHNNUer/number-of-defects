import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/'characterization';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'cpu5_followup_20261016'));from fixed_grid import mesh,detect,unit
sys.path.insert(0,str(ROOT/'defect_dynamics_20261015'));from analyze import geometry
GRID=None
def work(j):
 global GRID
 if GRID is None:GRID=mesh(5)
 v,g=GRID;name='n%d_F%g'%(j['n'],j['F']);cache=OUT/(name+'_fixed.csv')
 if cache.exists():return name
 folder=Path(j['coordinate_directory']);steps=[50000000,75000000,100000000]
 if j['F']==10:steps=list(range(50000000,100000001,5000000))
 if j['n'] in (200,350) and j['F'] in (0,.03,.1,.3):steps=sorted(set(steps+list(range(500000000,1000000001,100000000))))
 rows=[]
 for step in steps:
  p=folder/('defect_out-%010d.xyz'%step)
  if not p.exists():continue
  a=np.loadtxt(str(p),skiprows=2);x=a[a[:,0]==1,1:4]
  for h in (1.5,3.):
   r=detect(x,v,g,h);row=dict(n=j['n'],F=j['F'],R=r['radius'],step=step,time=step*j['dt'],h=h,Nplus=r['Nplus'],Nminus=r['Nminus'],composite=r['composite'],fallback=r['fallback'],P4=int(r['Nplus']==4 and r['Nminus']==0),pair_density=r['Nminus']/(4*np.pi*r['radius']**2))
   if row['P4']:row.update(geometry(np.array([p for p,q in zip(r['positions'],r['charges']) if q==1])))
   rows.append(row)
 pd.DataFrame(rows).to_csv(cache,index=False);return name
if __name__=='__main__':
 jobs=pd.read_csv(ROOT/'mips_analysis_20261014/trajectory_inventory.csv').to_dict('records')
 with ProcessPoolExecutor(max_workers=3) as pool:
  for name in pool.map(work,jobs):print('FIXED',name,flush=True)
 frames=pd.concat([pd.read_csv(p) for p in OUT.glob('n*_fixed.csv')],ignore_index=True);frames.to_csv(OUT/'fixed_scan_frames.csv',index=False);print('SCAN_DONE',len(frames))
