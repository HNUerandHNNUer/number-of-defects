from pathlib import Path
import numpy as np, importlib.util, sys, csv, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent; OUT=Path(__file__).resolve().parent
p=ROOT/'F_25_bd_cpu2/serial/sphere_nematic_parallel_large_v4.py'
spec=importlib.util.spec_from_file_location('sphereaudit',p); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
runs={'parallel':ROOT/'F_25_bd_cpu2/parallel','serial':ROOT/'F_25_bd_cpu2/serial','lammps':ROOT/'F_25_gpu4'}
rows=[]
for name,folder in runs.items():
    files=sorted(folder.glob('out-*.xyz')); selected=[files[i] for i in sorted(set([0,10,50,80,len(files)//2,len(files)-1]))]
    for p in selected:
        x=np.loadtxt(p,skiprows=2,usecols=(1,2,3)); step=int(p.stem.split('-')[-1])
        for k,ell in [(0,0),(32,1),(64,2),(128,3)]:
            result=m.identify(x,settings=m.Settings(smooth_k=k,smooth_length=ell)); d=result['diagnostics']
            rows.append([name,step,k,ell,d['charged_faces'],d['mean_order'],d['minimum_order'],d['net_charge'],d['near_branch_edges']])
with (OUT/'defect_scale_sensitivity.csv').open('w',newline='') as f:
    w=csv.writer(f); w.writerow(['run','step','neighbors','length','count','mean_S','min_S','net_charge','near_branch_edges']); w.writerows(rows)
print('SENSITIVITY',json.dumps(rows),flush=True)
