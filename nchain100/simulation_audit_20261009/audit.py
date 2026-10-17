from pathlib import Path
import numpy as np, json, csv, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
RUNS={'parallel':ROOT/'F_25_bd_cpu2/parallel','serial':ROOT/'F_25_bd_cpu2/serial','lammps':ROOT/'F_25_gpu4'}
L=37.732684; R=L/2-2.5
def read(p):
    return np.loadtxt(p,skiprows=2,usecols=(1,2,3))
summary={}; series={}
for name,folder in RUNS.items():
    rows=[]; prev=None
    files=sorted(folder.glob('out-*.xyz'))
    for p in files:
        step=int(p.stem.split('-')[-1]); x=read(p)
        if x.shape!=(3000,3) or not np.isfinite(x).all():
            raise ValueError(str(p))
        r=np.linalg.norm(x,axis=1); chains=x.reshape(100,30,3)
        b=np.diff(chains,axis=1); b-=L*np.rint(b/L)
        bl=np.linalg.norm(b,axis=2)
        tang=chains[:,2:]-chains[:,:-2]; tang/=np.linalg.norm(tang,axis=2)[...,None]
        u=chains[:,1:-1]/np.linalg.norm(chains[:,1:-1],axis=2)[...,None]
        radial=np.sum(tang*u,axis=2)
        polar=np.linalg.norm(tang.mean(axis=(0,1)))
        circulation=np.linalg.norm(np.cross(u,tang).mean(axis=(0,1)))
        cosine=np.sum(b[:,:-1]*b[:,1:],axis=2)/(bl[:,:-1]*bl[:,1:])
        speed=align=np.nan
        if prev is not None:
            xp,tp,dp=prev; delta=x-xp; delta-=L*np.rint(delta/L)
            speed=np.sqrt(np.mean(np.sum(delta*delta,axis=1)))/((step-tp)*.01)
            dc=delta.reshape(100,30,3)[:,1:-1]; norms=np.linalg.norm(dc,axis=2)
            align=np.mean(np.sum(dc*dp,axis=2)/np.maximum(norms,1e-12))
        prev=(x,step,tang)
        rows.append([step,r.min(),r.max(),np.sqrt(np.mean((r-R)**2)),bl.min(),bl.max(),np.sum(bl>=1.5),np.sum(bl>1.5*np.sqrt(.9)),bl.mean(),np.mean(cosine),np.sqrt(np.mean(radial**2)),polar,circulation,speed,align])
    a=np.array(rows); series[name]=a
    headers=['step','r_min','r_max','r_rms_error','bond_min','bond_max','bonds_ge_1p5','bonds_gt_clamp','bond_mean','adjacent_cosine','director_radial_rms','polar_order_3d','circulation_order','lag_rms_speed','lag_displacement_director_alignment']
    np.savetxt(OUT/f'{name}_trajectory_metrics.csv',a,delimiter=',',header=','.join(headers),comments='')
    defects=np.loadtxt(folder/'results/defect_results.dat',skiprows=1)
    bad=a[a[:,6]>0]
    summary[name]={'frames':len(a),'last_step':int(a[-1,0]),'radius_range':[a[:,1].min(),a[:,2].max()],'max_bond':a[:,5].max(),'frames_bond_ge_1p5':len(bad),'first_bad_bond_step':int(bad[0,0]) if len(bad) else None,'defect_frames':len(defects),'defect_last_step':int(defects[-1,0]),'defects_initial':defects[0,-1],'defects_last':defects[-1,-1],'defects_range':[defects[:,-1].min(),defects[:,-1].max()],'net_charge_range':[defects[:,-2].min(),defects[:,-2].max()]}
    for lo,hi,label in [(0,9e6,'common_early'),(1e6,9e6,'common_1m_9m'),(0,a[-1,0]+1,'all'),(a[-1,0]/2,a[-1,0]+1,'last_half')]:
        z=defects[(defects[:,0]>=lo)&(defects[:,0]<hi),-1]
        if len(z): summary[name][label]={'n':len(z),'mean':z.mean(),'std':z.std(),'min':z.min(),'max':z.max()}
    print(name,json.dumps(summary[name]),flush=True)
with (OUT/'summary.json').open('w') as f: json.dump(summary,f,indent=2)
fig,axs=plt.subplots(3,2,figsize=(12,11))
for name,a in series.items():
    d=np.loadtxt(RUNS[name]/'results/defect_results.dat',skiprows=1)
    axs[0,0].plot(d[:,0]*.01,d[:,-1],label=name,lw=.8)
    z=d[d[:,0]<=15e6]; axs[0,1].plot(z[:,0]*.01,z[:,-1],label=name,lw=.8)
    axs[1,0].plot(a[:,0]*.01,a[:,5],label=name,lw=.8)
    axs[1,1].plot(a[:,0]*.01,a[:,3],label=name,lw=.8)
    axs[2,0].plot(a[:,0]*.01,a[:,12],label=name,lw=.8)
    axs[2,1].plot(a[:,0]*.01,a[:,14],label=name,lw=.8)
for ax,title in zip(axs.flat,['Raw charged-face count','Early charged-face count','Maximum bond length','RMS radial deviation','Director circulation (not velocity)','Displacement/director alignment (lag=1000)']):
    ax.set_title(title); ax.set_xlabel('Simulation time (step x 0.01)'); ax.legend(); ax.grid(alpha=.2)
axs[1,0].axhline(1.5,color='k',ls='--'); axs[1,0].set_yscale('log')
fig.tight_layout(); fig.savefig(OUT/'audit_overview.png',dpi=170)
