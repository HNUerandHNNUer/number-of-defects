"""Reproducible F=1 spherical-filament trajectory analysis; never edits inputs.
Run with Python + numpy/scipy/matplotlib. All time is LJ time (step*0.01).
"""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
from pathlib import Path
import sys, json, csv, hashlib, importlib.util, itertools
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import linear_sum_assignment
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'gpu2'
SOURCE=BASE/'compress_defect_out'
OUT=BASE/'postprocess_F1_20261012'
OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('sphere_kernel',BASE/'sphere_nematic_parallel_large_v4.py')
k=importlib.util.module_from_spec(spec);sys.modules[spec.name]=k;spec.loader.exec_module(k)
DT=.01; H=1.5; GRID_N=512

def unit(x):
    return x/np.linalg.norm(x,axis=-1,keepdims=True)
def angles(a,b):
    return np.arccos(np.clip(np.sum(a*b,axis=-1),-1,1))
def kabsch(x,y):
    U,s,Vt=np.linalg.svd(x.T@y)
    D=np.diag([1.,1.,np.linalg.det(Vt.T@U.T)])
    return Vt.T@D@U.T
def pt(v,a,b):
    return v-(np.sum(v*b,axis=-1)/(1+np.sum(a*b,axis=-1)))[...,None]*(a+b)
def fib(n):
    z=1-2*(np.arange(n)+.5)/n;phi=np.arange(n)*np.pi*(3-np.sqrt(5))
    return np.column_stack((np.sqrt(1-z*z)*np.cos(phi),np.sqrt(1-z*z)*np.sin(phi),z))
grid=fib(GRID_N)
e1=unit(np.cross(grid,np.eye(3)[np.argmin(np.abs(grid),axis=1)]));e2=np.cross(grid,e1)
chain_id=np.repeat(np.arange(10),30)
cross_chain=chain_id[:,None]!=chain_id[None,:]

def local_fields(u,d,r,h=H):
    cos=grid@u.T;arc=r*np.arccos(np.clip(cos,-1,1))
    W=np.exp(-.5*(arc/h)**2);W[arc>3*h]=0
    den=W.sum(axis=1)
    td=pt(d[None,:,:],u[None,:,:],grid[:,None,:])
    a=np.einsum('gni,gi->gn',td,e1);b=np.einsum('gni,gi->gn',td,e2)
    px=np.sum(W*a,axis=1)/den;py=np.sum(W*b,axis=1)/den
    qx=np.sum(W*(a*a-b*b),axis=1)/den;qy=np.sum(W*(2*a*b),axis=1)/den
    P=np.hypot(px,py);S=np.hypot(qx,qy)
    th=np.linspace(0,min(np.pi,3*h/r),1001)
    norm=2*np.pi*r*r*np.trapz(np.exp(-.5*(r*th/h)**2)*np.sin(th),th)
    rho=den/norm
    neff=den**2/np.sum(W*W,axis=1)
    # Sum weights on different molecules; this is a diagnostic for correlated beads.
    molecule_w=W.reshape(GRID_N,10,30).sum(axis=2)
    chain_neff=den**2/np.sum(molecule_w*molecule_w,axis=1)
    return dict(P=P,S=S,rho=rho,neff=neff,chain_neff=chain_neff,px=px,py=py,qx=qx,qy=qy)

def interchain(u,d,r,h=H):
    dot=u@u.T;arc=r*np.arccos(np.clip(dot,-1,1));W=np.exp(-.5*(arc/h)**2)*cross_chain
    W[arc>3*h]=0
    trans=pt(d[None,:,:],u[None,:,:],u[:,None,:])
    cos=np.einsum('ijk,ik->ij',trans,d)
    return float(np.sum(W*cos)/W.sum()),float(np.sum(W*(2*cos*cos-1))/W.sum())

def pair_geometry(p,axis):
    best=None
    for pairs in [[(0,1),(2,3)],[(0,2),(1,3)],[(0,3),(1,2)]]:
        cost=sum(float(angles(p[i],p[j])) for i,j in pairs)
        if best is None or cost<best[0]:best=(cost,pairs)
    pairs=best[1]
    centers=unit(np.array([p[i]+p[j] for i,j in pairs]))
    ori=unit(np.array([p[i]-p[j] for i,j in pairs]))
    dist=np.array([angles(p[i],p[j]) for i,j in pairs])
    if centers[0]@axis<centers[1]@axis:
        centers=centers[::-1];ori=ori[::-1];dist=dist[::-1]
    return centers,ori,dist,float(angles(centers[0],centers[1]))

def phase_increment(oldc,oldo,newc,newo,axis):
    trans=pt(oldo,oldc,newc)
    a=np.sum(trans*newo,axis=1);b=np.sum(newc*np.cross(trans,newo),axis=1)
    phase=.5*np.arctan2(2*a*b,a*a-b*b)
    return phase*np.sign(newc@axis)

def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)

def main():
    paths=sorted(SOURCE.glob('defect_out-*.xyz'))
    frames=[];markers=[];charges=[];steps=[];manifest=[]
    for p in paths:
        raw=p.read_bytes();lines=raw.decode().splitlines();a=np.loadtxt(lines[2:]);assert len(a)==int(lines[0])
        assert np.all(a[:300,0]==1) and np.all(a[300:,0]!=1)
        q=np.where(a[300:,0]%2==0,1,-1)*np.floor(a[300:,0]/2)*.5
        frames.append(a[:300,1:4]);markers.append(a[300:,1:4]);charges.append(q)
        steps.append(int(p.stem.split('-')[-1]));manifest.append({'file':p.name,'sha256':hashlib.sha256(raw).hexdigest()})
    X=np.array(frames);steps=np.array(steps);time=steps*DT;T=len(X)
    assert T>2 and np.all(np.diff(steps)>0)
    Rmean=np.linalg.norm(X,axis=2).mean(axis=1);U=unit(X)
    D=np.array([k.chain_directors(u,30,k.Settings()) for u in U])
    rows=[];scale_rows=[];motion=[];defmotion=[];pair_rows=[];lat_rows=[];snapshots={};prevaxis=None
    axes=[];Cum=np.eye(3);Cum_all=[Cum.copy()];rotations=[np.eye(3)];pairs_cache=[];validation=[]
    for f in range(T):
        u=U[f];d=D[f];r=Rmean[f]
        vals,vec=np.linalg.eigh(d.T@d/300);axis=vec[:,0]
        if prevaxis is not None and axis@prevaxis<0:axis=-axis
        if prevaxis is None and axis[2]<0:axis=-axis
        axes.append(axis);prevaxis=axis
        az=unit(np.cross(axis,u));align=np.sum(az*d,axis=1)
        C=np.cross(u,d).mean(axis=0)
        fields=local_fields(u,d,r);cp,cn=interchain(u,d,r)
        result=k.identify(X[f]);rawq=result['double_charge'][result['mask']]/2
        rawp=result['positions'][result['mask']]
        assert np.isclose(rawq.sum(),2)
        samecounts=sorted(rawq.tolist())==sorted(charges[f].tolist())
        err=0.
        if samecounts:
            for qq in np.unique(rawq):
                a=unit(rawp[rawq==qq]);b=unit(markers[f][charges[f]==qq]);rr,cc=linear_sum_assignment(np.arccos(np.clip(a@b.T,-1,1)))
                err=max(err,float(np.max(angles(a[rr],b[cc]))))
        validation.append(dict(frame=f,step=int(steps[f]),same_charge_counts=samecounts,max_marker_angle_error_rad=err if samecounts else np.nan))
        q=rawq;p=unit(rawp)
        z=u@axis;cap=np.abs(z)>=np.cos(np.pi/6);band=np.abs(z)<=.5
        tsec=X[f].reshape(10,30,3)[:,2:]-X[f].reshape(10,30,3)[:,:-2]
        tau=np.cross(X[f].reshape(10,30,3)[:,1:-1],unit(tsec)).sum(axis=(0,1))
        A=(np.sum(X[f]**2,axis=1)[:,None,None]*np.eye(3)-X[f,:, :,None]*X[f,:,None,:]).sum(axis=0)
        wpred=np.linalg.solve(1000*A,tau)
        bond=np.linalg.norm(np.diff(X[f].reshape(10,30,3),axis=1),axis=2)
        row=dict(frame=f,step=int(steps[f]),time=float(time[f]),n_positive=int(np.sum(q>0)),n_negative=int(np.sum(q<0)),n_defects=len(q),net_charge=float(q.sum()),R=float(r),radial_relative_max=float(result['diagnostics']['max_relative_radial_deviation']),max_bond=float(bond.max()),contour_length=float(bond.sum(axis=1).mean()),B_azimuthal=float(np.mean(2*align**2-1)),signed_azimuthal_polarity=float(align.mean()),circulation_norm=float(np.linalg.norm(C)),signed_circulation=float(C@axis),P_local_area_mean=float(fields['P'].mean()),S_local_area_mean=float(fields['S'].mean()),P_local_density_weighted=float(np.average(fields['P'],weights=fields['rho'])),S_local_density_weighted=float(np.average(fields['S'],weights=fields['rho'])),effective_chains_median=float(np.median(fields['chain_neff'])),interchain_polar_correlation=cp,interchain_nematic_correlation=cn,polarcap_relative_density=float(cap.mean()/(1-np.cos(np.pi/6))),equatorial_relative_density=float(band.mean()/.5),defect_abs_cos_axis=float(np.mean(np.abs(p[q>0]@axis))),axis_x=float(axis[0]),axis_y=float(axis[1]),axis_z=float(axis[2]),predicted_omega_axis=float(wpred@axis),max_mesh_edge_deg=float(result['edge_angles'].max()*180/np.pi))
        for j in range(10):row['chain_%02d_signed_circulation'%j]=float(np.mean(np.cross(u,d).reshape(10,30,3)[j]@axis))
        rows.append(row)
        clean=len(q)==4 and np.all(q==.5)
        pc=None
        if clean:
            centers,ori,dist,anti=pair_geometry(p,axis);pc=(centers,ori,dist,anti,p)
            six=sorted([float(angles(p[i],p[j])) for i,j in itertools.combinations(range(4),2)])
            pr=dict(frame=f,step=int(steps[f]),time=float(time[f]),north_pair_angle_deg=float(dist[0]*180/np.pi),south_pair_angle_deg=float(dist[1]*180/np.pi),north_pair_distance=float(r*dist[0]),south_pair_distance=float(r*dist[1]),pair_center_separation_deg=float(anti*180/np.pi),pair_center_axis_north_deg=float(angles(centers[0],axis)*180/np.pi),pair_center_axis_south_deg=float(angles(centers[1],-axis)*180/np.pi))
            for j,a in enumerate(six):pr['sorted_angle_%d_deg'%(j+1)]=a*180/np.pi
            pair_rows.append(pr)
        pairs_cache.append(pc)
        if f:
            dt=time[f]-time[f-1];rot=kabsch(U[f-1],u);rotations.append(rot);Cum=rot@Cum;Cum_all.append(Cum.copy())
            raw=angles(U[f-1],u);res=angles(U[f-1]@rot.T,u)
            w=Rotation.from_matrix(rot).as_rotvec()/dt
            mr=dict(frame=f,step=int(steps[f]),time=float(time[f]),omega_x=float(w[0]),omega_y=float(w[1]),omega_z=float(w[2]),omega_axis=float(w@axis),omega_norm=float(np.linalg.norm(w)),rigid_rotation_fraction=float(1-np.sum(res*res)/np.sum(raw*raw)),particle_lab_rms_speed=float(r*np.sqrt(np.mean(raw*raw))/dt),particle_corotating_rms_speed=float(r*np.sqrt(np.mean(res*res))/dt),rotation_angle_deg=float(np.linalg.norm(w)*dt*180/np.pi),max_particle_step_angle_deg=float(raw.max()*180/np.pi),predicted_omega_axis_mid=float((rows[f]['predicted_omega_axis']+rows[f-1]['predicted_omega_axis'])/2))
            motion.append(mr)
            if clean and pairs_cache[f-1] is not None:
                oldc,oldo,oldd,olda,oldp=pairs_cache[f-1]
                # Pair labels chosen by axis; apolar pair orientation removes within-pair label ambiguity.
                labphase=phase_increment(oldc,oldo,centers,ori,axis)
                relphase=phase_increment(oldc@rot.T,oldo@rot.T,centers,ori,axis)
                ri,cj=linear_sum_assignment(np.arccos(np.clip((oldp@rot.T)@p.T,-1,1)))
                lab=angles(oldp[ri],p[cj]);rel=angles(oldp[ri]@rot.T,p[cj])
                dr=dict(frame=f,step=int(steps[f]),time=float(time[f]),lab_defect_rms_speed=float(r*np.sqrt(np.mean(lab*lab))/dt),corotating_defect_rms_speed=float(r*np.sqrt(np.mean(rel*rel))/dt),pair_north_lab_omega=float(labphase[0]/dt),pair_south_lab_omega=float(labphase[1]/dt),pair_north_corot_omega=float(relphase[0]/dt),pair_south_corot_omega=float(relphase[1]/dt),max_pair_phase_increment_deg=float(np.max(np.abs(labphase))*180/np.pi),max_matched_defect_step_deg=float(lab.max()*180/np.pi))
                defmotion.append(dr)
        gz=grid@axis
        edges=np.linspace(-1,1,21)
        for j in range(20):
            sel=(gz>=edges[j])&(gz<edges[j+1])
            lat_rows.append(dict(frame=f,time=float(time[f]),cos_theta=float((edges[j]+edges[j+1])/2),relative_density=float(np.mean(fields['rho'][sel])/(300/(4*np.pi*r*r))),P=float(np.mean(fields['P'][sel])),S=float(np.mean(fields['S'][sel]))))
        if f%10==0 or f==T-1:
            for h in [.7,1.,1.5,2.]:
                sf=local_fields(u,d,r,h)
                try:
                    sm=k.identify(X[f],settings=k.Settings(smooth_k=128,smooth_length=h));nsm=int(sm['mask'].sum());nneg=int(np.sum(sm['double_charge']<0));errstr=''
                except Exception as exc:nsm=-1;nneg=-1;errstr=str(exc)
                scale_rows.append(dict(frame=f,time=float(time[f]),h=h,P_mean=float(sf['P'].mean()),S_mean=float(sf['S'].mean()),n_smoothed_defects=nsm,n_smoothed_negative=nneg,status=errstr or 'ok'))
        if f in [0,10,25,50,100,250,500,750,T-1]:
            snapshots[str(f)]=dict(coords=X[f],directors=d,defect_positions=rawp,charges=q,axis=axis,**fields)
        if f%100==0:print('Processed %d/%d frames, defects=%d, S=%.3f, P=%.3f, B=%.3f'%(f,T,len(q),fields['S'].mean(),fields['P'].mean(),row['B_azimuthal']),flush=True)
    axes=np.array(axes);Cum_all=np.array(Cum_all)
    for name,data in [('frame_metrics',rows),('particle_rotation',motion),('defect_pair_geometry',pair_rows),('defect_relative_motion',defmotion),('latitude_profiles',lat_rows),('smoothing_sensitivity',scale_rows),('marker_validation',validation)]:
        if data:write_csv(OUT/(name+'.csv'),data)
    np.savez_compressed(OUT/'trajectory_fields.npz',time=time,step=steps,coords=X,directors=D,texture_axes=axes,cumulative_material_rotation=Cum_all,grid=grid,**{key+'_'+n:v for key,s in snapshots.items() for n,v in s.items()} )
    (OUT/'input_manifest.json').write_text(json.dumps(manifest,indent=2))
    summary={}
    for name,lo,hi in [('all',0,time[-1]),('early_10pct',0,.1*time[-1]),('middle_25_50pct',.25*time[-1],.5*time[-1]),('late_50pct',.5*time[-1],time[-1]),('late_25pct',.75*time[-1],time[-1])]:
        inds=[i for i,row in enumerate(rows) if lo<=row['time']<=hi];sel=[rows[i] for i in inds]
        stats={'frames':len(sel),'four_defect_fraction':float(np.mean([r['n_defects']==4 for r in sel]))}
        for key in ['n_defects','B_azimuthal','circulation_norm','signed_circulation','P_local_area_mean','S_local_area_mean','P_local_density_weighted','S_local_density_weighted','effective_chains_median','interchain_polar_correlation','interchain_nematic_correlation','polarcap_relative_density','equatorial_relative_density','defect_abs_cos_axis','max_mesh_edge_deg']:
            val=np.array([r[key] for r in sel]);stats[key]={'mean':float(val.mean()),'std':float(val.std()),'median':float(np.median(val)),'p10':float(np.percentile(val,10)),'p90':float(np.percentile(val,90))}
        for label,data,keys in [('material',motion,['omega_axis','omega_norm','rigid_rotation_fraction','particle_lab_rms_speed','particle_corotating_rms_speed','rotation_angle_deg']),('pairs',pair_rows,['north_pair_angle_deg','south_pair_angle_deg','pair_center_separation_deg','north_pair_distance','south_pair_distance']),('defect_motion',defmotion,['lab_defect_rms_speed','corotating_defect_rms_speed','pair_north_lab_omega','pair_south_lab_omega','pair_north_corot_omega','pair_south_corot_omega'])]:
            sub=[r for r in data if lo<=r['time']<=hi];stats[label]={'n':len(sub)}
            if sub:
                for key in keys:
                    val=np.array([r[key] for r in sub]);stats[label][key]={'mean':float(val.mean()),'median':float(np.median(val)),'std':float(val.std())}
        summary[name]=stats
    n=np.array([r['n_defects'] for r in rows]);summary['provenance']={'F':1,'gamma':1000,'temperature':1,'seed':190835668,'n_beads':300,'chain_length':30,'n_chains':10,'dt':DT,'sample_dt':float(np.median(np.diff(time))),'frames':T,'initial_defects':int(n[0]),'final_defects':int(n[-1]),'first_four_step':int(steps[np.flatnonzero(n==4)[0]]) if np.any(n==4) else None,'all_marker_counts_match_recomputed':all(r['same_charge_counts'] for r in validation),'max_marker_error_rad':float(np.nanmax([r['max_marker_angle_error_rad'] for r in validation])),'axis_total_drift_deg':float(angles(axes[0],axes[-1])*180/np.pi),'h_primary':H,'grid_points':GRID_N}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    # Temporal coarse-graining check: same definition, different observation intervals.
    lag_rows=[]
    for lag in [1,2,5,10]:
        for i in range(T//2,T-lag,lag):
            rot=kabsch(U[i],U[i+lag]);dt=time[i+lag]-time[i];w=Rotation.from_matrix(rot).as_rotvec()/dt
            raw=angles(U[i],U[i+lag]);res=angles(U[i]@rot.T,U[i+lag])
            lag_rows.append(dict(lag=lag,time=float(time[i]),sample_dt=float(dt),omega_axis=float(w@axes[i]),omega_norm=float(np.linalg.norm(w)),rigid_fraction=float(1-np.sum(res*res)/np.sum(raw*raw)),rotation_angle_deg=float(np.linalg.norm(w)*dt*180/np.pi)))
    write_csv(OUT/'temporal_resolution.csv',lag_rows)
    plot_all(rows,motion,pair_rows,defmotion,lat_rows,snapshots,time,X,U,Cum_all)
    print(json.dumps(summary['provenance'],indent=2),flush=True)

def plot_all(rows,motion,pair_rows,defmotion,lat_rows,snapshots,time,X,U,Cum):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    t=time/1e6
    fig,ax=plt.subplots(4,1,figsize=(11,11),sharex=True)
    ax[0].plot(t,[r['n_defects'] for r in rows],lw=.8,color='k');ax[0].axhline(4,color='gray',ls='--');ax[0].set_ylabel('Reported defects')
    for key,label in [('B_azimuthal','Azimuthal nematic B'),('S_local_area_mean','Local nematic S'),('P_local_area_mean','Local polar P')]:ax[1].plot(t,[r[key] for r in rows],label=label,lw=1)
    ax[1].legend(ncol=3,fontsize=9);ax[1].set_ylabel('Order (h=1.5)')
    ax[2].plot(t,[r['interchain_nematic_correlation'] for r in rows],label='Inter-chain nematic');ax[2].plot(t,[r['interchain_polar_correlation'] for r in rows],label='Inter-chain polar');ax[2].legend();ax[2].set_ylabel('Neighbour alignment')
    ax[3].plot(t,[r['polarcap_relative_density'] for r in rows],label='Polar caps (30 deg)');ax[3].plot(t,[r['equatorial_relative_density'] for r in rows],label='Equatorial belt (+/-30 deg)');ax[3].axhline(1,color='gray',ls='--');ax[3].legend();ax[3].set(xlabel='Production time / 1e6 (LJ)',ylabel='Density / uniform density')
    fig.tight_layout();fig.savefig(OUT/'01_ordering_and_defects.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True)
    tm=np.array([r['time'] for r in motion])/1e6
    ax[0].plot(tm,np.array([r['omega_axis'] for r in motion])*1e4,lw=.8,label='Material rotation fitted from bead identities');ax[0].plot(t,np.array([r['predicted_omega_axis'] for r in rows])*1e4,lw=.8,alpha=.7,label='Instantaneous active-torque predictor (F=1)');ax[0].set_ylabel('Signed angular speed / 1e-4');ax[0].legend(fontsize=8)
    ax[1].plot(tm,[r['rigid_rotation_fraction'] for r in motion],lw=.8);ax[1].set_ylabel('Bead motion explained\nby a rigid rotation')
    if defmotion:
        td=np.array([r['time'] for r in defmotion])/1e6
        for key,label in [('lab_defect_rms_speed','Defects: laboratory frame'),('corotating_defect_rms_speed','Defects: bead-corotating frame')]:ax[2].plot(td,[r[key] for r in defmotion],'.',ms=2,alpha=.6,label=label)
    ax[2].legend(fontsize=8);ax[2].set(xlabel='Production time / 1e6 (LJ)',ylabel='Defect RMS speed (LJ)')
    fig.tight_layout();fig.savefig(OUT/'02_material_and_defect_motion.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True)
    tp=np.array([r['time'] for r in pair_rows])/1e6
    if pair_rows:
        for key,label in [('north_pair_angle_deg','Pair N'),('south_pair_angle_deg','Pair S')]:ax[0].plot(tp,[r[key] for r in pair_rows],'.',ms=2,label=label)
        ax[0].legend();ax[0].set_ylabel('Within-pair angle (deg)')
        ax[1].plot(tp,[r['pair_center_separation_deg'] for r in pair_rows],'.',ms=2);ax[1].axhline(180,color='gray',ls='--');ax[1].set_ylabel('Pair-centre separation (deg)')
        for j in range(6):ax[2].plot(tp,[r['sorted_angle_%d_deg'%(j+1)] for r in pair_rows],'.',ms=1.5,label=str(j+1))
        ax[2].axhline(109.47,color='gray',ls='--',label='Tetrahedron');ax[2].legend(ncol=7,fontsize=8)
    ax[2].set(xlabel='Production time / 1e6 (LJ)',ylabel='Six sorted defect angles (deg)')
    fig.suptitle('Only frames with exactly four +1/2 and no negative defects',fontsize=12);fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(OUT/'03_defect_pair_geometry.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(1,3,figsize=(14,4))
    for a,key,title,limits in zip(ax,['relative_density','P','S'],['Density / uniform density','Local polar order P','Local nematic order S'],[(0,1.5),(0,1),(0,1)]):
        mat=np.array([r[key] for r in lat_rows]).reshape(len(time),20).T
        im=a.imshow(mat,origin='lower',aspect='auto',extent=[0,t[-1],-1,1],vmin=limits[0],vmax=limits[1],cmap='viridis');a.set(title=title,xlabel='Production time / 1e6',ylabel='cos(theta), texture axis');fig.colorbar(im,ax=a)
    fig.tight_layout();fig.savefig(OUT/'04_latitude_kymographs.png',dpi=170);plt.close(fig)
    fig=plt.figure(figsize=(14,8))
    for panel,f in enumerate([0,25,100,250,500,len(time)-1]):
        ax=fig.add_subplot(2,3,panel+1,projection='3d');s=snapshots[str(f)]
        for chain in X[f].reshape(10,30,3):ax.plot(*chain.T,lw=1.1)
        for charge,color,marker in [(.5,'black','o'),(-.5,'red','x')]:
            p=s['defect_positions'][s['charges']==charge]
            if len(p):ax.scatter(*p.T,c=color,marker=marker,s=28)
        a=s['axis']*5.8;ax.plot(*np.array([-a,a]).T,color='gray',ls='--')
        ax.set(xlim=(-6,6),ylim=(-6,6),zlim=(-6,6),title='t=%.3f x 1e6, Ndef=%d'%(t[f],len(s['charges'])))
        ax.set_xticks([]);ax.set_yticks([]);ax.set_zticks([])
    fig.tight_layout();fig.savefig(OUT/'05_structural_evolution.png',dpi=180);plt.close(fig)

if __name__=='__main__':main()
