import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys,re
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/'progress_r3_first100m';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'cpu5_followup_20261016'))
from fixed_grid import mesh,detect
sys.path.insert(0,str(ROOT/'defect_dynamics_20261015'))
from analyze import geometry
def counts():
 rows=[]
 for j in pd.read_csv(ROOT/'defect_dynamics_20261015/count_coverage.csv').to_dict('records'):
  if j['n']==200 and j['F']==.003:continue
  a=pd.read_csv(j['path'],sep=r'\s+');steps=a.iloc[:,0].values;last=steps[-1]
  for label,lo,hi in [('last75',.25,1),('q2',.25,.5),('q3',.5,.75),('q4',.75,1)]:
   z=a[(steps>=lo*last)&(steps<=hi*last)]['+1/2'].values
   rows.append(dict(n=j['n'],F=j['F'],window=label,last_step=last,Nplus=z.mean(),sd=z.std(),samples=len(z)))
 pd.DataFrame(rows).to_csv(OUT/'legacy_discard25.csv',index=False)
def work(path):
 p=Path(path);dest=OUT/(p.stem+'_fixed.csv')
 if dest.exists():return p.stem
 a=np.load(str(p));v,g=mesh(5);rows=[]
 dt=.01 if p.stem.startswith('relax') else (.0025 if '0p0025' in p.stem else .005)
 for step,x in zip(a['steps'],a['xyz']):
  for h in (1.5,3.):
   r=detect(x,v,g,h);row=dict(name=p.stem,step=int(step),time=float(step*dt),h=h,Nplus=r['Nplus'],Nminus=r['Nminus'],R=r['radius'],P4=int(r['Nplus']==4 and r['Nminus']==0),pair_density=r['Nminus']/(4*np.pi*r['radius']**2),composite=r['composite'])
   if row['P4']:row.update(geometry(np.array([p for p,q in zip(r['positions'],r['charges']) if q==1])))
   rows.append(row)
 pd.DataFrame(rows).to_csv(dest,index=False);return p.stem
if __name__=='__main__':
 pass # No redundant legacy recount
 with ProcessPoolExecutor(max_workers=3) as pool:
  for n in pool.map(work,list(OUT.glob('*.npz'))):print(n,flush=True)
 frames=pd.concat([pd.read_csv(p) for p in OUT.glob('*_fixed.csv')],ignore_index=True);frames.to_csv(OUT/'fixed_frames.csv',index=False)
 print('DONE',len(frames))



