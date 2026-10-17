import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,sys,importlib.util
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze import unit,geometry,local,dirs,GRID,load
from scipy.spatial import cKDTree
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
def save(fig,name):fig.tight_layout(rect=(0,0,1,.93));fig.savefig(OUT/name,dpi=160);plt.close(fig)
s=pd.read_csv(OUT/'smoothing_summary.csv');fig,axs=plt.subplots(1,3,figsize=(15,4.5))
for ax,n in zip(axs,[100,200,350]):
 for F in [.1,1,10]:
  a=s[(s.n==n)&(s.F==F)];ax.plot(a.h,a.Nplus,'-o',label=f'F={F:g}')
 ax.set_xlabel('Q smoothing length h');ax.set_ylabel('Mean N+');ax.set_title(f'nchain={n}');ax.axhline(4,ls=':',color='grey');ax.legend()
fig.suptitle('Scale sensitivity: same six frames per run, steps 5e7 to 1e8');save(fig,'06_scale_sensitivity.png')
d=pd.read_csv(OUT/'spatial_frames.csv');fig,axs=plt.subplots(1,3,figsize=(14,4.5))
for ax,n in zip(axs,[100,200,350]):
 a=d[(d.n==n)&(d.F==10)&(d.step>=2.5e7)&(d.step<=1e8)];ax.scatter(a.cv3,a.Nplus,c=a.step/1e8,cmap='viridis',s=25);ax.set_title(f'n={n}, r={a[["cv3","Nplus"]].corr().iloc[0,1]:.2f}');ax.set_xlabel('Density CV (cap radius 3)');ax.set_ylabel('Raw N+')
fig.suptitle('Within-run density-defect cofluctuations: correlation does not establish event causality');save(fig,'07_cofluctuation.png')
# A directly observed field with two analysis scales, avoiding projection-based density estimates.
spec=importlib.util.spec_from_file_location('nematic',ROOT/'nchain200/sphere_nematic_parallel.py');mod=importlib.util.module_from_spec(spec);sys.modules['nematic']=mod;spec.loader.exec_module(mod)
info=json.loads((ROOT/'mips_analysis_20261014/runs/n350_F10/done.json').read_text());a=load(Path(info['coordinate_directory'])/'defect_out-0070000000.xyz');xyz=a[a[:,0]==1,1:];u=unit(xyz);R=info['R'];ii=np.arange(8192);z=1-2*(ii+.5)/len(ii);az=ii*np.pi*(3-np.sqrt(5));g=np.c_[np.sqrt(1-z*z)*np.cos(az),np.sqrt(1-z*z)*np.sin(az),z];rho=cKDTree(u).query_ball_point(g,2*np.sin(3/(2*R)),return_length=True)/(len(u)*(1-np.cos(3/R))/2)
fig=plt.figure(figsize=(14,5));axes=[fig.add_subplot(1,2,i+1,projection='mollweide') for i in range(2)]
for ax,h in zip(axes,[0,3]):
 res=mod.identify(xyz,settings=mod.Settings(smooth_k=128 if h else 0,smooth_length=h));q=res['double_charge'];p=unit(res['positions']);sc=ax.scatter(np.arctan2(g[:,1],g[:,0]),np.arcsin(g[:,2]),c=rho,s=7,cmap='viridis',vmin=0,vmax=1.5,rasterized=True)
 for charge,color,marker in [(1,'red','o'),(-1,'white','x')]:
  v=p[q==charge];ax.scatter(np.arctan2(v[:,1],v[:,0]),np.arcsin(v[:,2]),s=12 if h==0 else 50,facecolors='none' if charge==1 else color,edgecolors=color,marker=marker,lw=.7,label='+1/2' if charge==1 else '-1/2')
 ax.set_title(f'h={h}; N+={(q==1).sum()}, N-={(q==-1).sum()}');ax.grid(alpha=.2);ax.legend(loc='lower right',fontsize=8)
fig.suptitle('n=350, F=10, step=7e7: same density field; raw versus coarse-grained defects');fig.subplots_adjust(top=.84,bottom=.18,wspace=.12);cax=fig.add_axes([.32,.09,.36,.025]);fig.colorbar(sc,cax=cax,orientation='horizontal',label='Local bead density / mean');fig.savefig(OUT/'08_same_field_two_scales.png',dpi=170);plt.close(fig)
# Numerical and provenance checks.
tet=unit(np.array([[1,1,1],[1,-1,-1],[-1,1,-1],[-1,-1,1.]]));square=np.array([[1.,0,0],[0,1,0],[-1,0,0],[0,-1,0]])
checks={'tetrahedron':geometry(tet),'square':geometry(square),'sampled_half_net_bad':int(np.sum(d.half_net!=2)),'other_marker_frames':int(np.sum(d.other_markers!=0)),'raw_recompute_count_mismatches':int(np.sum(pd.read_csv(OUT/'smoothing_frames.csv').query('h==0').Nplus.values!=pd.read_csv(OUT/'smoothing_frames.csv').query('h==0').marker_plus.values))}
assert abs(checks['tetrahedron']['bipolar_moment']-1/3)<1e-12
assert abs(checks['square']['bipolar_moment']-.5)<1e-12
(OUT/'validation.json').write_text(json.dumps(checks,indent=2))
print(checks)
