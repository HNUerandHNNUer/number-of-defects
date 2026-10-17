from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from postprocess_compression import k,unit
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'activity_analysis_20261013';rows=[]
for F,ids in [(6,list(range(500,581))+list(range(800,851))),(7,list(range(500,581)))]:
    z=np.load(OUT/('F_%d'%F)/'trajectory_fields.npz');X=z['coords']
    for f in ids:
        for h in [0,1,1.5,2]:
            r=k.identify(X[f],settings=k.Settings() if h==0 else k.Settings(smooth_k=128,smooth_length=h));rows.append(dict(F=F,frame=f,time=float(z['time'][f]),h=h,count=int(r['mask'].sum()),net_charge=float(r['double_charge'][r['mask']].sum()/2)))
with (OUT/'event_smoothing_every_frame.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
fig=plt.figure(figsize=(12,6))
for panel,F in enumerate([2,4]):
    z=np.load(OUT/('F_%d'%F)/'trajectory_fields.npz');x=z['coords'][750];d=z['directors'][750];u=unit(x);c=np.cross(u,d).reshape(10,30,3).mean(axis=1);axis=unit(c.mean(axis=0));sign=c@axis
    ax=fig.add_subplot(1,2,panel+1,projection='3d')
    for j,chain in enumerate(x.reshape(10,30,3)):
        color='tomato' if sign[j]>0 else 'royalblue';ax.plot(*chain.T,color=color,lw=2);pts=chain[::7];dirs=d[j*30:(j+1)*30:7];ax.quiver(*pts.T,*dirs.T,length=.65,color=color,linewidth=.8)
    a=k.identify(x);p=a['positions'][a['mask']];q=a['double_charge'][a['mask']]/2
    ax.scatter(*p[q>0].T,c='black',s=25);ax.set(xlim=(-6,6),ylim=(-6,6),zlim=(-6,6),title='F=%d, frame=750\nRed: majority circulation; blue: opposite'%F);ax.set_xticks([]);ax.set_yticks([]);ax.set_zticks([])
fig.tight_layout();fig.savefig(OUT/'09_same_nematic_different_polarity.png',dpi=180)
print('Completed',len(rows),'event/scale observations')
