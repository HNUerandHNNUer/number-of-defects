import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,itertools
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
MIPS=ROOT/'mips_analysis_20261014'
ii=np.arange(512);zz=1-2*(ii+.5)/len(ii);aa=ii*np.pi*(3-np.sqrt(5))
GRID=np.c_[np.sqrt(1-zz*zz)*np.cos(aa),np.sqrt(1-zz*zz)*np.sin(aa),zz]
def unit(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-15)
def load(p):
 with p.open() as f:f.readline();f.readline();a=np.fromstring(f.read(),sep=' ').reshape(-1,4)
 return a
def dirs(u):
 c=u.reshape(-1,30,3);d=np.empty_like(c);d[:,1:-1]=c[:,2:]-c[:,:-2];d[:,0]=c[:,1]-c[:,0];d[:,-1]=c[:,-1]-c[:,-2];d=d.reshape(-1,3);return unit(d-(d*u).sum(1)[:,None]*u)
def local(u,d,p,R,tree,h=1.5):
 if not len(p):return np.array([]),np.array([])
 ds,ids=tree.query(p,k=min(96,len(u)));a=u[ids];base=p[:,None,:];v=d[ids]
 trans=v-((v*base).sum(2)/np.maximum(1+(a*base).sum(2),1e-12))[:,:,None]*(a+base)
 ref=np.tile([0.,0.,1.],(len(p),1));ref[np.abs(p[:,2])>.9]=[1.,0.,0.]
 e=unit(np.cross(p,ref));e2=np.cross(p,e);c=(trans*e[:,None,:]).sum(2)+1j*(trans*e2[:,None,:]).sum(2)
 w=np.exp(-.5*(2*R*np.arcsin(np.clip(ds/2,0,1))/h)**2);s=np.maximum(w.sum(1),1e-30)
 return np.abs((w*c).sum(1)/s),np.abs((w*c*c).sum(1)/s)
def geometry(p):
 vals=[]
 for a,b,c,d in [(0,1,2,3),(0,2,1,3),(0,3,1,2)]:
  ang=np.arccos(np.clip([p[a].dot(p[b]),p[c].dot(p[d])],-1,1));cent=unit(np.array([p[a]+p[b],p[c]+p[d]]));sep=np.arccos(np.clip(cent[0].dot(cent[1]),-1,1));vals.append((ang.sum(),ang.mean(),sep))
 best=min(vals)
 allang=np.arccos(np.clip(p.dot(p.T)[np.triu_indices(4,1)],-1,1))
 ev=np.linalg.eigvalsh(p.T.dot(p)/4)
 return dict(pair_angle_deg=best[1]*180/np.pi,pair_center_deg=best[2]*180/np.pi,bipolar_moment=ev[-1],planarity=ev[0],six_angle_mean=allang.mean()*180/np.pi)
def analyze():
 allrows=[];counts=[];coverage=[]
 entries=[(done,json.loads(done.read_text())) for done in sorted((MIPS/'runs').glob('*/done.json'))]
 missing=ROOT/'nchain50/F_7_cpu2'
 if (missing/'defect_results.dat').exists():
  lines=(missing/'polymer.data').read_text().splitlines();idx=lines.index('Atoms')+2;xyz=np.array([[float(v) for v in line.split()[3:6]] for line in lines[idx:idx+1500]])
  entries.append((None,dict(n=50,F=7.,R=float(np.linalg.norm(xyz,axis=1).mean()),path=str(missing),last_step=np.nan)))
 for done,info in entries:
  n=info['n'];F=info['F'];R=info['R'];tag=f'n{n}_F{F:g}';cache=OUT/(tag+'.csv');p=Path(info['path'])/'defect_results.dat'
  if p.exists():
   tab=pd.read_csv(p,sep=r'\s+');t=tab.iloc[:,0].values;y=tab['+1/2'].values;neg=tab['-1/2'].values if '-1/2' in tab else y-4
   coverage.append(dict(n=n,F=F,count_first=t[0],count_last=t[-1],coordinate_last=info['last_step'],frames=len(t),path=str(p)))
   for window,lo,hi in [('late50',t[-1]*.5,t[-1]),('matched',2.5e7,1e8),('late25',t[-1]*.75,t[-1])]:
    if t[-1]<hi:continue
    sel=(t>=lo)&(t<=hi);tt=t[sel];a=y[sel];b=neg[sel];blocks=[x.mean() for x in np.array_split(a,6)]
    dif=np.diff(a);duration=tt[-1]-tt[0]
    row=dict(n=n,F=F,R=R,window=window,lo=lo,hi=hi,frames=len(a),Nplus=a.mean(),Nminus=b.mean(),Nplus_sem=np.std(blocks,ddof=1)/np.sqrt(6),pair_density=b.mean()/(4*np.pi*R*R),four_fraction=np.mean((a==4)&(b==0)),Nplus_sd=a.std(),net_bad=int(np.count_nonzero(tab['net_charge'].values[sel]!=2)),net_up_per_million=dif[dif>0].sum()/duration*1e6,net_down_per_million=-dif[dif<0].sum()/duration*1e6,change_fraction=np.mean(dif!=0),quarter_first=a[:max(1,len(a)//4)].mean(),quarter_last=a[-max(1,len(a)//4):].mean())
    counts.append(row)
  if done is None:continue
  if cache.exists():allrows.append(pd.read_csv(cache));continue
  spatial=pd.read_csv(done.parent/'frames.csv');rows=[]
  for _,r in spatial.iterrows():
   step=int(r['step']);data=load(Path(info['coordinate_directory'])/f'defect_out-{step:010d}.xyz');xyz=data[data[:,0]==1,1:];u=unit(xyz);tree=cKDTree(u);p=unit(data[data[:,0]==2,1:]);m=unit(data[data[:,0]==3,1:]);other=data[(data[:,0]!=1)&(data[:,0]!=2)&(data[:,0]!=3)]
   row=dict(n=n,F=F,R=R,step=step,coordinate_last=info['last_step'],Nplus=len(p),Nminus=len(m),other_markers=len(other),half_net=.5*(len(p)-len(m)),cv3=r['cv3'],xi=r['xi_fixedq'])
   for label,points in [('plus',p),('minus',m),('grid',GRID)]:
    if len(points):
     dens=tree.query_ball_point(points,2*np.sin(3/(2*R)),return_length=True)/(len(u)*(1-np.cos(3/R))/2)
     row[label+'_rho']=dens.mean();row[label+'_rho_below05']=np.mean(dens<.5);row[label+'_rho_above12']=np.mean(dens>1.2)
   if len(m) and len(p):
    dist=cKDTree(m).query(p)[0];row['plus_nearest_minus']=np.mean(2*R*np.arcsin(np.clip(dist/2,0,1)))
   if len(p)==4 and len(m)==0 and len(other)==0:row.update(geometry(p))
   if F in [0,.03,.1,1,5,10]:
    d=dirs(u);P,S=local(u,d,GRID,R,tree);row['P_local']=P.mean();row['S_local']=S.mean();row['circulation']=np.linalg.norm(np.cross(u,d).mean(0));row['director_axis_min']=np.linalg.eigvalsh(d.T.dot(d)/len(d))[0]
    for label,pts in [('plus',p),('minus',m)]:
     if len(pts):pp,ss=local(u,d,pts,R,tree);row[label+'_S']=ss.mean()
   rows.append(row)
  df=pd.DataFrame(rows);df.to_csv(cache,index=False);allrows.append(df);print('done',tag,len(df),flush=True)
 pd.concat(allrows,ignore_index=True).to_csv(OUT/'spatial_frames.csv',index=False)
 pd.DataFrame(counts).to_csv(OUT/'count_summary.csv',index=False)
 pd.DataFrame(coverage).to_csv(OUT/'count_coverage.csv',index=False)
 print('COMPLETE',sum(len(x) for x in allrows),len(counts),flush=True)
if __name__=='__main__':analyze()
