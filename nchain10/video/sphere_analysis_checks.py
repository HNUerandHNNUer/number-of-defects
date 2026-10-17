from pathlib import Path
import sys,importlib.util,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'sphere_analysis'
spec=importlib.util.spec_from_file_location('sphere_kernel',ROOT/'sphere_nematic_parallel_large_v4.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
records={}
fig=plt.figure(figsize=(11,4.5))
for panel,name in enumerate(['0.1','0.3']):
    lines=(ROOT/'results_evolution'/name/'polymer.data').read_text().splitlines();start=lines.index('Atoms')+2
    c=np.array([[float(x) for x in s.split()[3:6]] for s in lines[start:start+300]])
    base=m.identify(c);rot=Rotation.from_rotvec([.41,-.76,.33]).as_matrix();rr=m.identify(c@rot.T)
    same=np.array_equal(base['faces'],rr['faces']) and np.array_equal(base['double_charge'],rr['double_charge'])
    sign=m.identify(c,directors=-base['directors'])
    bflip=np.array_equal(base['double_charge'],sign['double_charge'])
    mask=base['mask'];p=base['positions'][mask];u=base['u']
    faces=base['faces'];a,b,cc=(u[faces[:,i]] for i in range(3));normal=m.unit(np.cross(b-a,cc-a));normal*=np.where(m.dot(normal,a)<0,-1.,1.)[:,None]
    discrepancy=np.arccos(np.clip(m.dot(normal[mask],m.unit(p)),-1,1))*180/np.pi
    records[name]={'rotation_invariant_faces_and_charges':same,'nematic_sign_invariant_charges':bflip,'marker_circumcenter_vs_barycenter_degrees':discrepancy.tolist(),'rotation_max_position_error':float(np.abs(rr['positions']-base['positions']@rot.T).max()),'max_edge_degrees':float(base['edge_angles'].max()*180/np.pi)}
    ax=fig.add_subplot(1,2,panel+1,projection='3d')
    for chain in c.reshape(10,30,3):ax.plot(*chain.T,lw=1.5)
    ax.scatter(*p.T,c='black',s=70,marker='x',label='+1/2 (face barycentres)')
    ax.set(xlim=(-6,6),ylim=(-6,6),zlim=(-6,6),xlabel='x',ylabel='y',zlabel='z',title=f'Initial state, F={name}: 10 chains, 300 beads')
    ax.legend(loc='lower left',fontsize=7)
fig.tight_layout();fig.savefig(OUT/'initial_geometry.png',dpi=160);plt.close(fig)
(OUT/'kernel_checks.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
fig,axs=plt.subplots(1,2,figsize=(10,4))
for folder in sorted((ROOT/'results_evolution').iterdir(),key=lambda p:float(p.name) if p.is_dir() else 1e9):
    if not folder.is_dir():continue
    t=np.loadtxt(folder/'defect_results.dat',skiprows=1);late=t[t[:,0]>=t[-1,0]/2]
    vals,cnt=np.unique(t[:,4],return_counts=True);axs[0].plot(vals,cnt/len(t),'o-',label=folder.name)
    common=t[t[:,0]<=1e8];axs[1].scatter(float(folder.name),np.mean(common[:,2]>0),marker='o',color='tab:blue')
    axs[1].scatter(float(folder.name),np.mean(late[:,2]>0),marker='x',color='tab:orange')
axs[0].set(xlabel='Reported defect count',ylabel='Fraction of stored frames',yscale='log');axs[0].legend(title='F',ncol=2)
axs[1].set(xlabel='Activity F',ylabel='Fraction with reported negative defects',xscale='log');axs[1].plot([],[],'o',color='tab:blue',label='Common first 1e8 steps');axs[1].plot([],[],'x',color='tab:orange',label='Last half of each run');axs[1].legend(fontsize=8)
fig.tight_layout();fig.savefig(OUT/'defect_statistics.png',dpi=160)
print(json.dumps(records,indent=2))
