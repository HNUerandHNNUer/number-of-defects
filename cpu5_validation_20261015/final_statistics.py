import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,json,re
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;P=HERE/'final_analysis_cpu5'
sys.path.insert(0,str(ROOT/'defect_dynamics_20261015'))
from analyze import GRID,unit,dirs
d=pd.read_csv(P/'frames.csv');r=pd.read_csv(P/'run_summary.csv');sc=pd.read_csv(P/'scales.csv');late=r[r.window=='late50']
rows=[]
for keys,z in late.groupby(['nchain','F','branch']):
 row=dict(zip(['nchain','F','branch'],keys));row['seeds']=len(z)
 for key in ['P','S','C','Nplus','Nminus','four','pair_density','pair_angle_deg','pair_center_deg','opposite_motion','rotation_fraction']:
  if key in z:row[key]=z[key].mean();row[key+'_seed_sd']=z[key].std()
 rows.append(row)
pd.DataFrame(rows).to_csv(P/'group_summary.csv',index=False)
blocks=[]
for name,z in d.groupby('name'):
 for block in range(4):
  t=z[(z.step>=block*25000000)&((z.step<(block+1)*25000000) if block<3 else (z.step<=100000000))]
  row=dict(name=name,nchain=int(z.nchain.iloc[0]),F=int(z.F.iloc[0]),replicate=int(z.replicate.iloc[0]),block=block,frames=len(t))
  for key in ['P','S','C','Nplus','four']:row[key]=t[key].mean()
  blocks.append(row)
pd.DataFrame(blocks).to_csv(P/'quarter_blocks.csv',index=False)
sc[sc.step>=50000000].groupby(['name','nchain','F','h']).Nplus.mean().reset_index().to_csv(P/'scale_seed_means.csv',index=False)
rho=[]
for j in json.loads((P/'audit.json').read_text()):
 name=j['name'];npz=np.load(str(P/(name+'.npz')));indices={int(s):i for i,s in enumerate(npz['steps'])}
 for step in range(50000000,100000001,5000000):
  x=npz['xyz'][indices[step]];u=unit(x);R=np.linalg.norm(x,axis=1).mean();tree=cKDTree(u);rr=tree.query_ball_point(GRID,2*np.sin(3/(2*R)),return_length=True)/(len(x)*(1-np.cos(3/R))/2)
  rho.append(dict(name=name,nchain=j['nchain'],F=j['F'],replicate=j['replicate'],step=step,cv3=rr.std()/rr.mean(),rho_below05=np.mean(rr<.5),rho_above15=np.mean(rr>1.5),rho_max=rr.max()))
pd.DataFrame(rho).to_csv(P/'density_frames.csv',index=False)
warnings=[]
for j in json.loads((P/'audit.json').read_text()):
 for line in j['warnings']:
  match=re.search(r'FENE bond too long: (\d+) (\d+) (\d+) ([\d.eE+-]+)',line)
  if match:warnings.append(dict(name=j['name'],step=int(match[1]),atom1=int(match[2]),atom2=int(match[3]),length=float(match[4]),threshold=1.5*np.sqrt(.9)))
pd.DataFrame(warnings).to_csv(P/'fene_warnings.csv',index=False)
print(pd.DataFrame(rows)[['nchain','F','branch','Nplus','Nplus_seed_sd','P','S','C','four','pair_density']].to_string(index=False))
print('DENSITY',pd.DataFrame(rho).groupby(['nchain','F']).cv3.mean().to_string())
