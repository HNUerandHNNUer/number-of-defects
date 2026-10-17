import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import linregress
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
NS=[10,30,50,100,150,200,300,350];colors=dict(zip(NS,plt.cm.viridis(np.linspace(.05,.95,8))))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
def save(fig,name):fig.tight_layout(rect=(0,0,1,.94));fig.savefig(OUT/name,dpi=160);plt.close(fig)
def weighted(t,y,lo,hi):
 w=np.diff(np.r_[lo,(t[1:]+t[:-1])/2,hi]);ok=np.isfinite(y);y=y[ok];w=w[ok]
 if len(y)<1:return np.nan
 return np.average(y,weights=w) if w.sum()>0 else y.mean()
def main():
 raw=pd.read_csv(OUT/'spatial_frames.csv');count=pd.read_csv(OUT/'count_summary.csv');rows=[]
 for (n,F),d in raw.groupby(['n','F']):
  d=d.sort_values('step');last=d.coordinate_last.iloc[0]
  for window,lo,hi in [('late50',last*.5,last),('matched',2.5e7,1e8)]:
   if last<hi:continue
   a=d[(d.step>=lo)&(d.step<=hi)];t=a.step.values
   row=dict(n=n,F=F,R=d.R.iloc[0],window=window,sampled_frames=len(a))
   for col in ['Nplus','Nminus','cv3','xi','plus_rho','minus_rho','plus_rho_below05','minus_rho_below05','grid_rho_below05','plus_rho_above12','minus_rho_above12','grid_rho_above12','plus_nearest_minus','P_local','S_local','circulation','pair_angle_deg','pair_center_deg','bipolar_moment','planarity','plus_S','minus_S']:
    row[col]=weighted(t,a[col].values,lo,hi)
   row['four_geometry_frames']=int(a.pair_angle_deg.notna().sum())
   for col in ['cv3','S_local','P_local']:
    dd=a[['Nplus',col]].dropna();row['corr_Nplus_'+col]=dd.corr().iloc[0,1] if len(dd)>5 else np.nan
   rows.append(row)
 s=pd.DataFrame(rows);s.to_csv(OUT/'spatial_summary.csv',index=False)
 late=count[count.window=='late50'];matched=count[count.window=='matched']
 fig,axs=plt.subplots(1,3,figsize=(15,4.5))
 for n in NS:
  d=late[(late.n==n)&(late.F<=10)&(late.F>0)].sort_values('F')
  for ax,y in zip(axs,['Nplus','pair_density','four_fraction']):ax.plot(d.F,d[y],'-o',ms=3,label=str(n),color=colors[n]);ax.set_xscale('log');ax.set_xlabel('Active force F')
 axs[0].set_ylabel('Mean N+ (raw detection)');axs[1].set_ylabel('Excess-pair density N- / area');axs[2].set_ylabel('Fraction with exactly four +1/2');axs[0].legend(title='nchain',ncol=2,fontsize=8);fig.suptitle('Defect population: last half of each trajectory (not a steady-state certificate)');save(fig,'01_population.png')
 fig,axs=plt.subplots(1,3,figsize=(15,4.5))
 for ax,F in zip(axs,[.03,.1,10]):
  for n in [10,100,200,350]:
   run=next((x for x in pd.read_csv(OUT/'count_coverage.csv').to_dict('records') if x['n']==n and x['F']==F),None)
   if run is None:continue
   d=pd.read_csv(run['path'],sep=r'\s+');t=d.iloc[:,0].values;y=d['+1/2'].values
   bins=np.array_split(np.arange(len(t)),min(100,len(t)));ax.plot([t[b].mean() for b in bins],[y[b].mean() for b in bins],label=str(n),color=colors[n])
  ax.set_xscale('log');ax.set_xlabel('Simulation step');ax.set_ylabel('Block-mean N+');ax.set_title(f'F={F:g}');ax.legend(title='nchain',fontsize=8)
 fig.suptitle('Slow relaxation at weak driving versus fluctuating populations at strong driving');save(fig,'02_time_evolution.png')
 fig,axs=plt.subplots(1,3,figsize=(15,4.5))
 for F in [.1,1,5,10]:
  d=s[(s.F==F)&(s.window=='matched')].sort_values('R');axs[0].plot(d.R,d.plus_rho,'-o',label=f'+, F={F:g}');axs[0].plot(d.R,d.minus_rho,'--s',label=f'-, F={F:g}')
  axs[1].plot(d.R,d.P_local,'-o',label=f'F={F:g}');axs[2].plot(d.R,d.circulation,'-o',label=f'F={F:g}')
 axs[0].axhline(1,color='k',ls=':',lw=1);axs[0].set_ylabel('Density at raw defect markers / mean');axs[0].legend(fontsize=7,ncol=2)
 axs[1].set_ylabel('Area-mean local polar order (h=1.5)');axs[2].set_ylabel('|mean(u cross chain tangent)|')
 for ax in axs:ax.set_xlabel('Sphere radius R')
 axs[1].legend();fig.suptitle('Density-defect association and loss of global circulation; common time window');save(fig,'03_density_order.png')
 fig,axs=plt.subplots(1,3,figsize=(15,4.5))
 for n in [10,30,50,100]:
  d=s[(s.n==n)&(s.F>0)&(s.F<=10)&(s.window=='late50')&(s.four_geometry_frames>=5)].sort_values('F')
  for ax,y in zip(axs,['pair_angle_deg','pair_center_deg','bipolar_moment']):ax.plot(d.F,d[y],'-o',label=str(n),color=colors[n]);ax.set_xscale('log');ax.set_xlabel('F')
 axs[0].set_ylabel('Mean within-pair angle (degrees)');axs[1].set_ylabel('Pair-center separation (degrees)');axs[2].set_ylabel('Largest eigenvalue of mean(u_def u_def)');axs[2].axhline(1/3,color='grey',ls=':',label='tetrahedron');axs[0].legend(title='nchain');fig.suptitle('Four-defect geometry, conditional on exactly four +1/2 markers (>=5 sampled frames)');save(fig,'04_four_geometry.png')
 old=ROOT/'nchain10/video/activity_analysis_20261013';a=pd.read_csv(old/'full_coordinate_summary.csv');a=a[a.F.isin([2,4,6,7,8,9])]
 a.to_csv(OUT/'n10_existing_full_trajectory_summary.csv',index=False)
 fig,axs=plt.subplots(1,3,figsize=(14,4.5));x=np.arange(len(a));axs[0].bar(x-.18,a.P_local_area_mean,width=.36,label='polar P');axs[0].bar(x+.18,a.S_local_area_mean,width=.36,label='nematic S');axs[0].legend();axs[0].set_ylabel('Local order');axs[1].bar(x,100*a.rigid_rotation_fraction);axs[1].set_ylabel('Rigid rotation explained displacement (%)');axs[2].bar(x,a.chains_opposite_mean_circulation);axs[2].set_ylabel('Chains opposite mean circulation')
 for ax in axs:ax.set_xticks(x);ax.set_xticklabels(a.F.astype(int));ax.set_xlabel('F (individual trajectories)')
 fig.suptitle('gpu2 trajectories only: similar bipolar texture, different polar organization (prior full analysis)');save(fig,'05_hidden_polarity.png')
 scale=[]
 for window in ['late50','matched']:
  for F in [1,5,10]:
   a=count[(count.window==window)&(count.n>=100)&(count.F==F)];lr=linregress(np.log(a.R),np.log(a.Nminus));scale.append(dict(window=window,F=F,points=len(a),Nminus_R_exponent=lr.slope,r2=lr.rvalue**2))
 pd.DataFrame(scale).to_csv(OUT/'raw_size_scaling.csv',index=False)
 print('F10 matched counts\n',matched[matched.F==10][['n','R','Nplus','pair_density','four_fraction']].to_string(index=False))
 print('F10 matched spatial\n',s[(s.F==10)&(s.window=='matched')][['n','plus_rho','minus_rho','P_local','S_local','circulation','corr_Nplus_cv3']].to_string(index=False))
 print('geometry n10\n',s[(s.n==10)&(s.F<=10)&(s.window=='late50')][['F','pair_angle_deg','pair_center_deg','four_geometry_frames']].to_string(index=False))
 print('scaling',scale)
if __name__=='__main__':main()
