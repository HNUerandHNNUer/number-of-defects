# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
import numpy as np
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent/'progress_20261017_0040';a=pd.read_csv(P/'fixed_frames.csv')
assert (a.Nplus-a.Nminus==4).all() and a.composite.eq(0).all()
assert a.groupby(['name','h']).step.nunique().eq(21).all()
a['n']=a.name.str.extract(r'n(\d+)_').astype(int);a['F']=a.name.str.extract(r'_F([\d.]+)_').astype(float);a['seed']=a.name.str.extract(r'_r(\d+)').astype(int)
rows=[]
for w,lo,hi in [('early',5000000,45000000),('late',50000000,100000000)]:
 s=a[a.step.between(lo,hi)].groupby(['n','F','seed','h'],as_index=False)[['Nplus','Nminus','P4','pair_density']].mean();s['window']=w;rows.append(s)
s=pd.concat(rows);s.to_csv(P/'seed_windows.csv',index=False);g=s.groupby(['n','F','h','window']).agg(Nplus=('Nplus','mean'),sd=('Nplus','std'),seeds=('seed','count'),P4=('P4','mean'));g.to_csv(P/'window_summary.csv');print(g.to_string())
fig,axes=plt.subplots(1,2,figsize=(10,4),squeeze=False)
for i,n in enumerate([200]):
 for j,h in enumerate([1.5,3.]):
  z=a[(a.n==n)&(a.h==h)].groupby(['F','step'],as_index=False).Nplus.mean()
  for F,d in z.groupby('F'):axes[i,j].plot(d.step/1e6,d.Nplus,'o-',ms=3,label='F=%g'%F)
  axes[i,j].set(title='n=%d, h=%g'%(n,h),xlabel='Production steps / 1e6',ylabel='Positive defects');axes[i,j].legend()
fig.tight_layout();fig.savefig(str(P/'evolution.png'),dpi=180)
(P/'validation.json').write_text(json.dumps(dict(rows=len(a),net_charge_pass=True,composite_zero=True,frames_per_seed=21,latest_step=100000000),indent=2))


