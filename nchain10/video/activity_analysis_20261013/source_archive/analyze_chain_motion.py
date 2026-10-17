from pathlib import Path
import csv,json
import numpy as np
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from postprocess_compression import unit,kabsch
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'activity_analysis_20261013'
rows=[];summary=[]
fig,axs=plt.subplots(2,3,figsize=(15,8),sharex=True,sharey=True)
for ax,F in zip(axs.ravel(),[2,4,6,7,8,9]):
    p=OUT/('F_%d'%F);z=np.load(p/'trajectory_fields.npz');X=z['coords'];U=unit(X);D=z['directors'];axes=z['texture_axes'];t=z['time'];chainC=np.mean(np.cross(U,D).reshape(-1,10,30,3),axis=2)
    # Orient the circulation axis by the instantaneous total circulation, not an
    # apolar eigenvector. A common eigenaxis flip is not a physical chain reversal.
    totalC=chainC.mean(axis=1);axes=unit(totalC);ci=np.einsum('fji,fi->fj',chainC,axes)
    velocity=np.zeros((len(X)-1,10))
    for f in range(1,len(X)):
        for j in range(10):
            s=slice(j*30,(j+1)*30);rot=kabsch(U[f-1,s],U[f,s]);rv=Rotation.from_matrix(rot).as_rotvec();velocity[f-1,j]=rv@axes[f]/(t[f]-t[f-1])
            rows.append(dict(F=F,frame=f,time=t[f],chain=j,circulation_axis=ci[f,j],principal_angular_velocity_axis=velocity[f-1,j],rotation_angle_deg=np.linalg.norm(rv)*180/np.pi,high_F_alias_caution=F>=6))
    for j in range(10):ax.plot(t/1e6,ci[:,j],lw=.8,label=str(j))
    ax.axhline(0,color='k',lw=.5);ax.set_title('F=%d'%F);ax.set_xlabel('Time / 1e6');ax.set_ylabel('Chain circulation / majority axis')
    for lo,hi,label in [(1e5,4e5,'before'),(6e5,1e6,'after'),(5e5,1e6,'late')]:
        sel=(t>=lo)&(t<=hi);vsel=(t[1:]>=lo)&(t[1:]<=hi);c=ci[sel];v=velocity[vsel];sign=np.sign(c.mean())
        summary.append(dict(F=F,window=label,mean_chain_circulation=c.mean(axis=0).tolist(),mean_chain_velocity=v.mean(axis=0).tolist(),mean_counter_chains=float(np.mean(np.sum(c*sign<-.1,axis=1))),counterflow_fraction=float(np.mean((np.min(v,axis=1)<-1e-5)&(np.max(v,axis=1)>1e-5))) if F<=4 else None,high_F_velocity_alias_caution=F>=6,signed_circulation_speed_correlation=float(np.corrcoef(c.ravel(),v.ravel())[0,1])) )
fig.tight_layout();fig.savefig(OUT/'08_chain_polarity_evolution.png',dpi=170)
with (OUT/'chain_motion_timeseries.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
(OUT/'chain_motion_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps([r for r in summary if r['window']=='after'],indent=2))
