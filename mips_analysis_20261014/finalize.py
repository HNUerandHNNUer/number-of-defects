import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import linregress
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from summarize import weights,block_sem,NS,COLORS
OUT=Path(__file__).resolve().parent
s=pd.read_csv(OUT/'summary.csv');m=pd.read_csv(OUT/'morphology_frames.csv');rows=[]
for (n,F),d in m.groupby(['n','F']):
 d=d.sort_values('step');t=d.step.values
 for window,lo,hi in [('late50',t[-1]*.5,t[-1]),('matched',25000000,100000000)]:
  if t[0]>lo or t[-1]<hi:continue
  mask,w=weights(t,lo,hi)
  if mask.sum()<5:continue
  dd=d[mask];row=dict(n=n,F=F,R=d.R.iloc[0],window=window)
  for col in d.columns:
   if col in ['n','F','R','step']:continue
   row[col]=np.average(dd[col],weights=w);row[col+'_block_sem']=block_sem(t[mask],dd[col].values,w,lo,hi)
  band=(dd.bandness>.15)&(dd.bandness>dd.capness)&(dd.axisymmetric_band_explained_variance>.5)
  row['strong_global_band_fraction']=np.average(band.astype(float),weights=w)
  rows.append(row)
ms=pd.DataFrame(rows);ms.to_csv(OUT/'morphology_summary.csv',index=False,encoding='utf-8-sig')
sf=[]
for (F,win),d in ms.groupby(['F','window']):
 d=d[d.n>=150]
 if len(d)<4:continue
 for col in ['dilute05_length','dilute05_weighted_length','dense12_length']:
  dd=d[d[col]>0]
  if len(dd)<4:continue
  fit=linregress(np.log(dd.R),np.log(dd[col]));sf.append(dict(F=F,window=win,metric=col,exponent=fit.slope,r2=fit.rvalue**2,n_sizes=len(dd)))
pd.DataFrame(sf).to_csv(OUT/'morphology_scaling.csv',index=False)
# Conditional uncertainty across temporal blocks, not independent simulation repeats.
rng=np.random.RandomState(20261014);boot={};obs=[]
for n in NS:
 d=pd.read_csv(OUT/'runs'/f'n{n}_F10'/'frames.csv');t=d.step.values;mask,w=weights(t,25000000,100000000);dd=d[mask];tt=t[mask];b=np.clip(((tt-25000000)/75000000*6).astype(int),0,5)
 val=np.array([np.average(dd.cv3.values[b==i],weights=w[b==i]) for i in range(6)])
 boot[n]=val[rng.randint(0,6,(5000,6))].mean(axis=1);obs.append(val.mean())
array=np.array([boot[n] for n in NS]).T;diff=boot[200]-boot[150]
bs=dict(F=10,window='steps 2.5e7 to 1e8',n_boot=5000,n_blocks=6,conditional_probability_all_cv_increasing=float(np.mean((np.diff(array,axis=1)>=0).all(axis=1))),difference_200_minus_150_mean=float(diff.mean()),difference_200_minus_150_percentile95=np.percentile(diff,[2.5,97.5]).tolist(),note='Temporal-block resampling of one trajectory per size; not uncertainty across seeds or a posterior probability of physical monotonicity.')
(OUT/'temporal_block_bootstrap.json').write_text(json.dumps(bs,indent=2))

fig,ax=plt.subplots(1,3,figsize=(15,4.5));a=s[(s.F==10)&(s.window=='matched')].sort_values('R');b=ms[(ms.F==10)&(ms.window=='matched')].sort_values('R')
for th in ['1p1','1p2','1p3']:ax[0].plot(a.R,a['largest_area_'+th],'o-',label='rho/mean > '+th.replace('p','.'))
ax[0].set_xlabel('R');ax[0].set_ylabel('Largest dense-component area / sphere area');ax[0].legend(fontsize=8)
ax[1].plot(b.R,b.dilute05_length,'o-',label='Largest dilute domain (rho/mean < 0.5)');ax[1].plot(b.R,b.dilute05_weighted_length,'s--',label='Area-weighted dilute-domain scale');ax[1].plot(a.R,a.xi_fixedq,'^-',label='Spectral density scale');ax[1].set_xlabel('R');ax[1].set_ylabel('Physical length');ax[1].legend(fontsize=7)
ref=pd.read_csv(OUT/'grid_sensitivity.csv')
for grid in [2048,8192]:
 d=ref[ref.M==grid].groupby('n').mean().sort_values('R');ax[2].plot(d.R,d.dense12_largest_area,'o-',label=f'{grid} grid points')
ax[2].set_xlabel('R');ax[2].set_ylabel('Largest dense area fraction, threshold 1.2');ax[2].legend(fontsize=8);fig.suptitle('F=10: threshold and grid sensitivity; dense connectivity alone is not a phase test');fig.tight_layout(rect=(0,0,1,.93));fig.savefig(OUT/'08_cluster_sensitivity.png',dpi=150);plt.close(fig)
fig=plt.figure(figsize=(14,8))
for row,n in enumerate([10,50,150,350]):
 z=np.load(OUT/'runs'/f'n{n}_F10'/'fields.npz');grid=z['grid'];lon=np.arctan2(grid[:,1],grid[:,0]);lat=np.arcsin(grid[:,2])
 for col,target in enumerate([50000000,100000000]):
  j=np.argmin(abs(z['step']-target));axis=fig.add_subplot(4,2,row*2+col+1,projection='mollweide');im=axis.scatter(lon,lat,c=z['density'][j],s=4,cmap='viridis',vmin=0,vmax=1.5,linewidth=0);axis.set_title(f'{n} chains, F=10, step={z["step"][j]:.2g}',fontsize=9);axis.set_xticklabels([]);axis.set_yticklabels([]);axis.grid(alpha=.2)
fig.subplots_adjust(left=.03,right=.88,bottom=.04,top=.93,hspace=.35);ca=fig.add_axes([.91,.2,.018,.55]);fig.colorbar(im,cax=ca,label='Local density / mean (cap radius 3)');fig.suptitle('Equal-area spherical density maps: identical physical observation times');fig.savefig(OUT/'09_density_maps.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,4.5))
for n in [50,100,150,200,300,350]:
 folder=OUT/'runs'/f'n{n}_F10';info=json.loads((folder/'done.json').read_text());z=np.load(folder/'fields.npz');mask,w=weights(z['step'],25000000,100000000);p=np.average(z['power'][mask],axis=0,weights=w);q=np.sqrt(np.arange(1,25)*np.arange(2,26))/info['R'];valid=q<=.8;axes[0].plot(q[valid],p[valid]/np.sum(p[valid]),'o-',ms=3,color=COLORS[n],label=str(n))
 a=s[(s.n==n)&(s.F==10)&(s.window=='late50')].iloc[0];axes[1].plot([1,5],[a.speed_density_corr_lag1,a.speed_density_corr_lag5],'o-',color=COLORS[n],label=str(n))
axes[0].set_xlabel('Spherical wavenumber sqrt(l(l+1))/R');axes[0].set_ylabel('Fractional power per spherical l-bin');axes[0].legend(fontsize=8,ncol=2);axes[1].set_xlabel('Lag in saved-frame intervals');axes[1].set_ylabel('Density vs displacement-speed correlation');axes[1].set_xticks([1,5]);axes[1].axhline(0,color='gray',lw=1);fig.suptitle('F=10: density spectrum and finite-lag sensitivity');fig.tight_layout(rect=(0,0,1,.93));fig.savefig(OUT/'10_spectrum_velocity_lag.png',dpi=150);plt.close(fig)
infos=[json.loads(p.read_text()) for p in (OUT/'runs').glob('*/done.json')]
pd.DataFrame(infos).sort_values(['n','F']).to_csv(OUT/'trajectory_inventory.csv',index=False,encoding='utf-8-sig')
print('runs',len(infos),'sampled frames',sum(x['analyzed_frames'] for x in infos),'velocity pairs',sum(x['velocity_pairs'] for x in infos));print(bs)
print(ms[(ms.F==10)&(ms.window=='matched')][['n','dilute05_length','dilute05_weighted_length','dilute05_nclusters','strong_global_band_fraction']].sort_values('n').to_string(index=False))
