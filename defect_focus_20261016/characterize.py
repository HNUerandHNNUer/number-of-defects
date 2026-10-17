import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys,json,re,hashlib
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/'characterization';OUT.mkdir(exist_ok=True)
inv=pd.read_csv(ROOT/'mips_analysis_20261014/trajectory_inventory.csv');cov=pd.read_csv(ROOT/'defect_dynamics_20261015/count_coverage.csv');rows=[];aud=[]
for _,j in cov.iterrows():
 match=inv[(inv.n==j.n)&(inv.F==j.F)];dt=float(match.dt.iloc[0]) if len(match) else .01;p=Path(j.path);a=pd.read_csv(p,sep=r'\s+');t=a.iloc[:,0].values*dt;y=a['+1/2'].values;neg=a['-1/2'].values if '-1/2' in a else y-4
 rec=dict(n=int(j.n),F=j.F,count_path=str(p),dt=dt,dt_source='trajectory_inventory' if len(match) else 'unverified_default',last_time=float(t[-1]),samples=len(t),net_failures=int(np.count_nonzero(y-neg!=4)))
 source=Path(match.path.iloc[0]) if len(match) else p.parent;inputs=list(source.glob('*.in'));deck=next((q for q in inputs if q.name=='bd.in'),inputs[0] if inputs else None)
 if deck:
  txt=deck.read_text(errors='replace');rec.update(input_path=str(deck),fix_lines=[z.strip() for z in txt.splitlines() if re.match(r'\s*fix\s+.*bd/sphere',z)],runs=[z.strip() for z in txt.splitlines() if re.match(r'\s*run\s+',z)])
 data=source/'polymer.data'
 if data.exists():rec['data_sha256']=hashlib.sha256(data.read_bytes()).hexdigest()
 aud.append(rec)
 windows=[('common',250000.,1000000.),('late_half',t[-1]*.5,t[-1])]
 for b in range(10):windows.append(('relative_decile_%02d'%b,t[-1]*b/10,t[-1]*(b+1)/10))
 for label,lo,hi in windows:
  if hi>t[-1]:continue
  mask=(t>=lo)&(t<=hi);tt=t[mask];z=y[mask];nn=neg[mask]
  if len(z)<8:continue
  blocks=np.array([v.mean() for v in np.array_split(z,8)]);d=z-z.mean();var=np.dot(d,d);corr=np.correlate(d,d,mode='full')[len(d)-1:]/var if var>0 else np.zeros(len(d));zero=np.where(corr<=0)[0];stop=int(zero[0]) if len(zero) else len(z)//2;tau=float(np.median(np.diff(tt))*(.5+corr[1:stop].sum())) if var>0 else 0
  rows.append(dict(n=int(j.n),F=j.F,R=float(match.R.iloc[0]) if len(match) else np.nan,window=label,t_start=lo,t_end=hi,frames=len(z),Nplus=z.mean(),Nminus=nn.mean(),Nplus_sd=z.std(),block_sem=blocks.std(ddof=1)/np.sqrt(8),P4=np.mean((z==4)&(nn==0)),pair_density=nn.mean()/(4*np.pi*float(match.R.iloc[0])**2) if len(match) else np.nan,drift_first_last=blocks[-1]-blocks[0],slope_per_million=np.polyfit((tt-tt.mean())/1e6,z,1)[0],count_correlation_time=tau,nonstationary_flag=abs(blocks[-1]-blocks[0])>max(1,3*blocks.std(ddof=1)/np.sqrt(8))))
pd.DataFrame(rows).to_csv(OUT/'time_window_metrics.csv',index=False);(OUT/'input_audit.json').write_text(json.dumps(aud,indent=2));print('COUNT_DONE',len(aud),len(rows))
