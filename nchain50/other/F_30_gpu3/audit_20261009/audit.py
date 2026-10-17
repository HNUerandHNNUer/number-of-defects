from pathlib import Path
import sys,json,re,csv
import numpy as np
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import sphere_nematic_parallel_large_v4 as nem
out=Path(__file__).parent
files=sorted((ROOT/'defect_out').glob('*.xyz'))
rows=[]; sensitivity=[]
sample=set(np.linspace(0,len(files)-1,25,dtype=int))
for idx,p in enumerate(files):
    a=np.loadtxt(str(p),skiprows=2); x=a[a[:,0]==1,1:4]
    assert x.shape==(1500,3)
    t=int(re.search(r'(\d+)\.xyz',p.name).group(1))
    r=np.linalg.norm(x,axis=1); u=x/r[:,None]
    dx=np.diff(x.reshape(50,30,3),axis=1); b=np.linalg.norm(dx,axis=2)
    near=cKDTree(x).query(x,k=2)[0][:,1]
    tang=x.reshape(50,30,3)[:,2:]-x.reshape(50,30,3)[:,:-2]
    tang/=np.linalg.norm(tang,axis=2)[:,:,None]
    radial=np.abs((tang*u.reshape(50,30,3)[:,1:-1]).sum(axis=2))
    rows.append([t,r.min(),r.mean(),r.max(),r.std(),b.min(),b.mean(),b.max(),(b>1.5*np.sqrt(.9)).sum(),(b>=1.5).sum(),near.min(),np.sqrt((radial**2).mean()),(a[:,0]==2).sum(),(a[:,0]==3).sum()])
    if idx in sample:
        for k,l in [(0,0),(12,1.5),(24,2.0),(48,3.0)]:
            result=nem.identify(x,settings=nem.Settings(smooth_k=k,smooth_length=l))
            d=result['diagnostics']; sensitivity.append(dict(step=t,k=k,length=l,**d))
    if idx%1000==0: print(idx,flush=True)
names=['step','rmin','rmean','rmax','rstd','bmin','bmean','bmax','b_clipped','b_ge_R0','nearest','radial_tangent_rms','plus','minus']
with (out/'frame_metrics.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(names);w.writerows(rows)
(out/'sensitivity.json').write_text(json.dumps(sensitivity,indent=2))
v=np.asarray(rows); summary={'frames':len(rows),'first':int(v[0,0]),'last':int(v[-1,0]),'metrics':{n:{'min':float(v[:,i].min()),'mean':float(v[:,i].mean()),'max':float(v[:,i].max())} for i,n in enumerate(names[1:],1)},'frames_clipped':int((v[:,8]>0).sum()),'frames_beyond_R0':int((v[:,9]>0).sum()),'max_bond_step':int(v[np.argmax(v[:,7]),0])}
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axs=plt.subplots(3,1,figsize=(11,9),sharex=True)
axs[0].plot(v[:,0],v[:,7],lw=.5);axs[0].axhline(1.5,color='r',ls='--');axs[0].axhline(1.5*np.sqrt(.9),color='orange',ls='--');axs[0].set_ylabel('Max bond length')
axs[1].plot(v[:,0],v[:,1],lw=.5);axs[1].plot(v[:,0],v[:,3],lw=.5);axs[1].set_ylabel('Min / max radius')
axs[2].plot(v[:,0],v[:,12]+v[:,13],lw=.5,label='original markers')
for k,l in [(0,0),(12,1.5),(24,2.),(48,3.)]:
    s=[d for d in sensitivity if d['k']==k];axs[2].plot([d['step'] for d in s],[d['charged_faces'] for d in s],'.-',label=f'k={k}, length={l}')
axs[2].set_ylabel('Charged faces');axs[2].set_xlabel('Simulation step');axs[2].legend(ncol=2)
fig.tight_layout();fig.savefig(str(out/'audit_metrics.png'),dpi=160)
