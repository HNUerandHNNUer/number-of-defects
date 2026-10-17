# -*- coding: utf-8 -*-
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import linregress,spearmanr
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent
NS=[10,30,50,100,150,200,300,350]
COLORS=dict(zip(NS,plt.cm.viridis(np.linspace(.05,.95,8))))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
def savefig(fig,name):
 fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/name,dpi=150);plt.close(fig)

def weights(t,lo,hi):
 selected=(t>=lo)&(t<=hi);tt=t[selected]
 if not len(tt):return selected,np.array([])
 edges=np.r_[lo,(tt[1:]+tt[:-1])/2,hi];w=np.diff(edges);return selected,w/w.sum()

def block_sem(t,y,w,lo,hi):
 b=np.clip(((t-lo)/(hi-lo)*6).astype(int),0,5);means=[np.average(y[b==i],weights=w[b==i]) for i in range(6) if np.any(b==i)]
 return np.std(means,ddof=1)/np.sqrt(len(means)) if len(means)>1 else np.nan

def modes(hist):
 p=gaussian_filter1d(hist.astype(float),2,mode='reflect');p/=max(p.sum()*.025,1e-15)
 peaks,_=find_peaks(np.r_[0,p,0],prominence=max(p)*.03,distance=12);peaks=peaks-1;peaks=peaks[(peaks>=0)&(peaks<100)]
 good=[]
 for i in peaks:
  for j in peaks:
   if j<=i:continue
   valley=i+np.argmin(p[i:j+1]);left=hist[:valley+1].sum()/hist.sum();right=1-left
   if p[valley]<.8*min(p[i],p[j]) and min(left,right)>.05:good.append((i,j,valley,left))
 return p,peaks,good

def summarize():
 rows=[];pdfrows=[];gnfrows=[];velrows=[];corrrows=[];cache={};allframe=[]
 for done in sorted((OUT/'runs').glob('*/done.json')):
  info=json.loads(done.read_text());folder=done.parent;n=info['n'];F=info['F'];R=info['R'];d=pd.read_csv(folder/'frames.csv');z=np.load(folder/'fields.npz');t=z['step'];v=pd.read_csv(folder/'velocity_frames.csv');vz=np.load(folder/'velocity.npz');cache[n,F]=(info,d,z,v,vz)
  allframe.append(d)
  for lag in [1,5]:
   ac=vz['lag'+str(lag)];x=(vz['bins'][1:]+vz['bins'][:-1])/2
   for i in range(len(x)):
    if ac[0,i]>0:velrows.append(dict(n=n,F=F,lag=lag,rho_ratio=x[i],count=ac[0,i],speed=ac[1,i]/ac[0,i],projected=ac[2,i]/ac[0,i],speed_sd=np.sqrt(max(0,ac[3,i]/ac[0,i]-(ac[1,i]/ac[0,i])**2))))
  for window,lo,hi in [('late50',t[-1]*.5,t[-1]),('matched',25000000,100000000)]:
   if t[0]>lo or t[-1]<hi:continue
   mask,w=weights(t,lo,hi)
   if mask.sum()<5:continue
   dd=d[mask];row=dict(n=n,F=F,R=R,window=window,lo=lo,hi=hi,nframes=int(mask.sum()))
   for col in ['cv2','cv3','cv5','void2','void3','void5','largest_area_1p1','largest_area_1p2','largest_area_1p3','largest_length_1p2','dense_area_1p2','weighted_length_1p2','nclusters_1p2','moment_min_1p2','moment_max_1p2','xi_fixedq','lowmode_power','lowmode_fraction']:
    y=dd[col].values;row[col]=np.average(y,weights=w);row[col+'_block_sem']=block_sem(t[mask],y,w,lo,hi)
   row['cluster_length_over_R']=row['largest_length_1p2']/R;row['xi_over_R']=row['xi_fixedq']/R
   for ell in [0,1,2]:
    hist=np.average(z['hist'][mask,ell,:],axis=0,weights=w);p,peaks,good=modes(hist)
    row['bimodal'+str([2,3,5][ell])]=bool(good)
    row['mode_positions'+str([2,3,5][ell])]=';'.join('{:.3f}'.format((i+.5)*.025) for i in peaks)
    for i,val in enumerate(p):pdfrows.append(dict(n=n,F=F,window=window,ell=[2,3,5][ell],rho_ratio=(i+.5)*.025,pdf=val))
   # Temporal variance in fixed spherical windows; separate static heterogeneity from fluctuations.
   counts=z['gnf'][mask];mu=np.average(counts,axis=0,weights=w);second=np.average(counts.astype(float)**2,axis=0,weights=w);tv=np.maximum(0,second-mu**2).mean(axis=1)
   pooled=second.mean(axis=1)-mu.mean(axis=1)**2;means=mu.mean(axis=1);radii=z['gnf_radii'];frac=(1-np.cos(radii/R))/2
   for i,r in enumerate(radii):gnfrows.append(dict(n=n,F=F,window=window,cap_radius=r,mean_count=means[i],temporal_std=np.sqrt(tv[i]),pooled_std=np.sqrt(max(0,pooled[i])),temporal_std_finiteN_corrected=np.sqrt(tv[i]/(1-frac[i])),cap_area_fraction=frac[i]))
   valid=(means>=30)&(frac<=.15)&(radii>=3)&(tv>0)
   if valid.sum()>=3:
    fit=linregress(np.log(means[valid]),np.log(np.sqrt(tv[valid]/(1-frac[valid]))));row.update(gnf_alpha=fit.slope,gnf_r2=fit.rvalue**2,gnf_points=int(valid.sum()),gnf_mean_min=means[valid].min(),gnf_mean_max=means[valid].max())
   else:row.update(gnf_alpha=np.nan,gnf_r2=np.nan,gnf_points=int(valid.sum()))
   # Descriptive late coarsening slopes, not asymptotic exponents.
   for col in ['xi_fixedq','largest_length_1p2']:
    good=(dd.step>0)&(dd[col]>0)
    if good.sum()>3:
     xx=np.log(dd.step[good]);yy=np.log(dd[col][good]);fit=np.polyfit(xx,yy,1,w=np.sqrt(w[good]));row[col+'_log_slope']=fit[0]
   # Normalized density autocorrelation, actual lags binned logarithmically.
   arr=z['density'][mask].astype(float);arr-=arr.mean(axis=1)[:,None];norm=np.linalg.norm(arr,axis=1);c=arr.dot(arr.T)/np.maximum(norm[:,None]*norm[None,:],1e-20)
   lag=np.abs(t[mask,None]-t[None,mask]);sel=np.triu(np.ones_like(lag,dtype=bool),1);lv=lag[sel];cv=c[sel]
   if len(lv):
    bins=np.geomspace(max(1,lv.min()),lv.max()*1.001,10)
    for j in range(len(bins)-1):
     q=(lv>=bins[j])&(lv<bins[j+1])
     if q.any():corrrows.append(dict(n=n,F=F,window=window,lag_steps=lv[q].mean(),correlation=cv[q].mean(),pairs=int(q.sum())))
   for lagframes in [1,5]:
    vv=v[v.lag_frames==lagframes]
    for col in ['speed_mean','signed_projection','angle_median','angle_gt_05','angle_gt_1','local_polar','local_nematic','speed_density_corr']:
     row[col+'_lag'+str(lagframes)]=vv[col].mean()
   rows.append(row)
 summary=pd.DataFrame(rows);pdf=pd.DataFrame(pdfrows);gnf=pd.DataFrame(gnfrows);vel=pd.DataFrame(velrows);corr=pd.DataFrame(corrrows)
 for name,df in [('summary',summary),('density_distributions',pdf),('number_fluctuations',gnf),('speed_density',vel),('density_autocorrelation',corr),('all_sampled_frames',pd.concat(allframe,ignore_index=True))]:df.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
 # Rank tests across eight distinct systems, descriptive block errors are not replicate uncertainty.
 monotonic=[]
 for (F,win),group in summary.groupby(['F','window']):
  if len(group)<4:continue
  group=group.sort_values('R')
  for col in ['cv3','void3','largest_area_1p2','largest_length_1p2','xi_fixedq','lowmode_power']:
   sr=spearmanr(group.R,group[col]) if group[col].std()>1e-15 else None;dy=np.diff(group[col]);monotonic.append(dict(F=F,window=win,metric=col,n_sizes=len(group),strictly_nondecreasing=bool(np.all(dy>=0)),decreases=int((dy<0).sum()),spearman_r=sr.correlation if sr else np.nan,p_value_descriptive=sr.pvalue if sr else np.nan))
 pd.DataFrame(monotonic).to_csv(OUT/'radius_monotonicity.csv',index=False)
 scaling=[]
 for (F,win),group in summary.groupby(['F','window']):
  for cutoff in [10,100,150]:
   g=group[group.n>=cutoff]
   if len(g)<4:continue
   for col in ['largest_length_1p2','weighted_length_1p2','xi_fixedq']:
    g2=g[g[col]>0]
    if len(g2)<4:continue
    fit=linregress(np.log(g2.R),np.log(g2[col]));scaling.append(dict(F=F,window=win,min_n=cutoff,metric=col,exponent=fit.slope,r2=fit.rvalue**2,n_sizes=len(g2)))
 pd.DataFrame(scaling).to_csv(OUT/'size_scaling.csv',index=False)
 return summary,pdf,gnf,vel,corr,cache

def plots(s,p,g,v,c,cache):
 late=s[s.window=='late50'];matched=s[s.window=='matched']
 fig,axes=plt.subplots(2,3,figsize=(15,8))
 for n in NS:
  a=late[late.n==n].sort_values('F')
  for ax,col in zip(axes.flat,['cv3','void3','largest_area_1p2','xi_fixedq','gnf_alpha','speed_density_corr_lag1']):
   ax.plot(a.F,a[col],'o-',ms=3,color=COLORS[n],label=str(n));ax.set_xscale('symlog',linthreshx=.01);ax.set_xlabel('Active force F');ax.set_ylabel(col)
 axes[0,0].legend(title='Actual chains',ncol=2,fontsize=8);fig.suptitle('Late-half diagnostics; one trajectory per parameter');fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/'01_activity_overview.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(2,3,figsize=(15,8))
 for F,color in zip([0,.1,1,5,10],plt.cm.plasma(np.linspace(.05,.9,5))):
  a=matched[matched.F==F].sort_values('R')
  for ax,col in zip(axes.flat,['cv3','void3','largest_area_1p2','largest_length_1p2','xi_fixedq','lowmode_power']):
   ax.errorbar(a.R,a[col],yerr=a[col+'_block_sem'],fmt='o-',ms=4,color=color,label=f'F={F:g}');ax.set_xlabel('Measured radius R');ax.set_ylabel(col)
 axes[0,0].legend(fontsize=8);fig.suptitle('Same observation window: steps 2.5e7 to 1e8; bars: temporal block SEM');fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/'02_radius_comparison.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(2,4,figsize=(16,7),sharex=True)
 for ax,n in zip(axes.flat,NS):
  for F in [0,.1,1,5,10]:
   a=p[(p.n==n)&(p.F==F)&(p.window=='late50')&(p.ell==3)]
   ax.plot(a.rho_ratio,a.pdf,label=f'{F:g}')
  ax.set_title(f'{n} chains');ax.set_xlabel('Local density / mean density');ax.set_ylabel('Area-weighted PDF');ax.set_xlim(0,1.8)
 axes[0,0].legend(title='F',fontsize=8);fig.suptitle('Density PDF at fixed cap radius 3; visual smoothing width 0.05');fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/'03_density_pdf.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(2,4,figsize=(16,7))
 for ax,n in zip(axes.flat,NS):
  for F in [0,.1,1,5,10]:
   if (n,F) not in cache:continue
   info,d,_,_,_=cache[n,F];ax.plot(d.step,d.xi_fixedq,label=f'{F:g}')
  ax.set_xscale('log');ax.set_title(f'{n} chains');ax.set_xlabel('Simulation step');ax.set_ylabel('Spectral length (q <= 0.8)')
 axes[0,0].legend(title='F',fontsize=8);fig.suptitle('Whole-run domain-length evolution; no imposed growth law');fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/'04_coarsening.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(2,4,figsize=(16,7))
 for ax,n in zip(axes.flat,NS):
  for F in [0,.1,1,5,10]:
   a=g[(g.n==n)&(g.F==F)&(g.window=='late50')]
   ax.loglog(a.mean_count,a.temporal_std_finiteN_corrected,'o-',ms=3,label=f'{F:g}')
  ax.set_title(f'{n} chains');ax.set_xlabel('Mean bead count');ax.set_ylabel('Temporal count SD / sqrt(1-area fraction)')
 axes[0,0].legend(title='F',fontsize=8);fig.suptitle('Number fluctuations: bead connectivity and passive baseline must be considered');fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/'05_number_fluctuations.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(2,4,figsize=(16,7),sharex=True)
 for ax,n in zip(axes.flat,NS):
  for F in [1,5,10]:
   for lag,style in [(1,'-'),(5,'--')]:
    a=v[(v.n==n)&(v.F==F)&(v.lag==lag)&(v['count']>=100)];ax.plot(a.rho_ratio,a.speed,style,label=f'F={F},lag={lag}')
  ax.set_title(f'{n} chains');ax.set_xlabel('Initial local density / mean');ax.set_ylabel('Finite-lag geodesic speed');ax.set_xlim(.2,1.7)
 axes[0,0].legend(fontsize=6);fig.suptitle('Displacement-speed proxy, not instantaneous swim speed; lag dependence shown');fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/'06_speed_density.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(12,4.5))
 for n in NS:
  a=c[(c.n==n)&(c.F==10)&(c.window=='late50')];axes[0].semilogx(a.lag_steps,a.correlation,'o-',label=str(n),color=COLORS[n])
  a=matched[matched.n==n];a=a[a.F==10]
  if len(a):axes[1].scatter(a.R,a.cluster_length_over_R,label=str(n),color=COLORS[n])
 axes[0].set_xlabel('Lag (steps)');axes[0].set_ylabel('Density-pattern correlation');axes[0].legend(ncol=2,fontsize=8);axes[1].set_xlabel('Radius R');axes[1].set_ylabel('Largest dense-domain equivalent radius / R');fig.suptitle('F=10: pattern persistence and relative cluster size');fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/'07_persistence_scaling.png',dpi=150);plt.close(fig)

if __name__=='__main__':
 result=summarize();plots(*result);s=result[0]
 print(s[(s.F==10)&(s.window=='matched')][['n','R','cv3','void3','largest_area_1p2','xi_fixedq','gnf_alpha','bimodal3']].to_string(index=False))
