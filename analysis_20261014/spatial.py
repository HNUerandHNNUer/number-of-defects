from pathlib import Path
import sys,json,csv,importlib.util
import numpy as np
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('nematic',ROOT/'nchain200/sphere_nematic_parallel.py');mod=importlib.util.module_from_spec(spec);sys.modules['nematic']=mod;spec.loader.exec_module(mod)
audit=json.loads((OUT/'audit.json').read_text());rows=[]
for n in [200,250,350]:
 for f in [.1,10]:
  run=next(r for r in audit if r['label']==n and r['F']==f);folder=ROOT/run['path']
  for frac in [.5,.75,1.]:
   step=int(run['end']*frac);p=folder/'defect_out'/f'defect_out-{step:010d}.xyz'
   if not p.exists():continue
   data=np.loadtxt(p,skiprows=2);xyz=data[data[:,0]==1,1:4];R=np.linalg.norm(xyz,axis=1).mean();u=xyz/np.linalg.norm(xyz,axis=1)[:,None]
   # Equal-area Fibonacci grid, cap density in fixed physical radius 3.
   i=np.arange(4096);z=1-2*(i+.5)/len(i);a=i*np.pi*(3-np.sqrt(5));g=np.c_[np.sqrt(1-z*z)*np.cos(a),np.sqrt(1-z*z)*np.sin(a),z]
   ct=cKDTree(u).query_ball_point(g,2*np.sin(3/(2*R)),return_length=True);rho=ct/(2*np.pi*R*R*(1-np.cos(3/R)))
   for ell in [0,1,2,3]:
    settings=mod.Settings(smooth_k=0 if ell==0 else 128,smooth_length=ell)
    result=mod.identify(xyz,settings=settings);diag=result['diagnostics'];q=result['double_charge']
    row=dict(label=n,F=f,step=step,ell=ell,Nplus=int((q==1).sum()),marker_plus=int((data[:,0]==2).sum()),density_cv=float(rho.std()/rho.mean()),low_density_area_fraction=float((rho<.2*len(xyz)/(4*np.pi*R*R)).mean()),low_order_vertices=diag['low_order_vertices'])
    rows.append(row);print(row,flush=True)
with (OUT/'spatial.csv').open('w',newline='') as fp:
 w=csv.DictWriter(fp,rows[0]);w.writeheader();w.writerows(rows)
