"""Additional independent checks and co-rotating defect tracks."""
from postprocess_compression import *
from scipy.stats import t as student

def read(name):
    with (OUT/(name+'.csv')).open(encoding='utf-8-sig') as f:
        return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]

def main():
    z=np.load(OUT/'trajectory_fields.npz');X=z['coords'];D=z['directors'];axes=z['texture_axes'];C=z['cumulative_material_rotation'];times=z['time'];U=unit(X)
    tracks=[];phases=[];scale=[];prev=None;segment=-1;saved={}
    for f in range(500,len(X)):
        res=k.identify(X[f]);q=res['double_charge'][res['mask']]/2;p=unit(res['positions'][res['mask']])
        if len(q)!=4 or not np.all(q==.5):prev=None;continue
        if prev is None:segment+=1
        else:
            of,op=prev;rot=C[f]@C[of].T
            ii,jj=linear_sum_assignment(np.arccos(np.clip((op@rot.T)@p.T,-1,1)));p=p[jj]
        prev=(f,p);saved[f]=p
        for j,(a,b) in enumerate(zip(p,p@C[f])):
            tracks.append(dict(frame=f,time=times[f],segment=segment,track=j,lab_x=a[0],lab_y=a[1],lab_z=a[2],corot_x=b[0],corot_y=b[1],corot_z=b[2]))
        centers,ori,dist,anti=pair_geometry(p,axes[f]);v=unit(ori-(ori@axes[f])[:,None]*axes[f]);co=v[0]@v[1];si=axes[f]@np.cross(v[0],v[1]);phase=.5*np.arctan2(2*co*si,co*co-si*si)
        phases.append(dict(frame=f,time=times[f],relative_pair_phase_deg=phase*180/np.pi,cos_2phase=np.cos(2*phase),sin_2phase=np.sin(2*phase)))
        if f%10==0:
            for h in [.7,1,1.5,2]:
                sm=k.identify(X[f],settings=k.Settings(smooth_k=128,smooth_length=h));sq=sm['double_charge'][sm['mask']]/2
                if len(sq)==4 and np.all(sq==.5):
                    cc,oo,dd,aa=pair_geometry(unit(sm['positions'][sm['mask']]),axes[f]);scale.append(dict(frame=f,h=h,north_angle=dd[0]*180/np.pi,south_angle=dd[1]*180/np.pi,center_angle=aa*180/np.pi))
    write_csv(OUT/'defect_tracks_corotating.csv',tracks);write_csv(OUT/'relative_pair_phase.csv',phases);write_csv(OUT/'pair_geometry_smoothing.csv',scale)
    metrics=read('frame_metrics');motion=read('defect_relative_motion');material=read('particle_rotation')
    stats={}
    for key in ['pair_north_corot_omega','pair_south_corot_omega']:
        blocks=[]
        for lo in range(500,1000,50):
            vals=[r[key] for r in motion if lo<=r['frame']<lo+50]
            if vals:blocks.append(np.mean(vals))
        m=np.mean(blocks);err=student.ppf(.975,len(blocks)-1)*np.std(blocks,ddof=1)/np.sqrt(len(blocks))
        stats[key]={'block_mean':m,'approx_95pct_block_interval':[m-err,m+err],'blocks':len(blocks),'block_duration':50000,'note':'Single-trajectory uncertainty; blocks may remain correlated.'}
    a=np.array([[r['cos_2phase'],r['sin_2phase']] for r in phases]).mean(axis=0)
    stats['relative_pair_phase']={'locking_magnitude':float(np.linalg.norm(a)),'circular_mean_deg':float(.5*np.arctan2(a[1],a[0])*180/np.pi)}
    stats['late_global_polar_vector_norm_mean']=float(np.linalg.norm(D[500:].mean(axis=1),axis=1).mean())
    stats['late_axis_drift_max_deg']=float(np.max(angles(axes[500:],axes[500]))*180/np.pi)
    stats['late_predicted_omega']=float(np.mean([r['predicted_omega_axis'] for r in metrics if r['frame']>=500]))
    stats['late_observed_omega']=float(np.mean([r['omega_axis'] for r in material if r['frame']>=500]))
    stats['smoothing_geometry']={str(h):{key:float(np.mean([r[key] for r in scale if r['h']==h])) for key in ['north_angle','south_angle','center_angle']} for h in [.7,1,1.5,2]}
    # Numerical correctness: arbitrary rotation recovery and tangent transport.
    rng=np.random.default_rng(193);testu=unit(rng.normal(size=(100,3)));R=Rotation.from_rotvec([.3,-.5,.7]).as_matrix();fit=kabsch(testu,testu@R.T)
    a=testu[:50];b=testu[50:];v=unit(np.cross(a,rng.normal(size=a.shape)));w=pt(v,a,b)
    tests={'kabsch_max_error':float(np.max(np.abs(R-fit))),'pt_max_norm_error':float(np.max(np.abs(np.linalg.norm(w,axis=1)-1))),'pt_max_tangent_error':float(np.max(np.abs(np.sum(w*b,axis=1))))}
    assert max(tests.values())<1e-12
    fields=local_fields(U[750],D[750],np.linalg.norm(X[750],axis=1).mean());flipped=local_fields(U[750],-D[750],np.linalg.norm(X[750],axis=1).mean())
    tests['global_sign_flip_S_error']=float(np.max(np.abs(fields['S']-flipped['S'])));tests['global_sign_flip_P_magnitude_error']=float(np.max(np.abs(fields['P']-flipped['P'])))
    # Counterfactual director signs, not a rerun or evidence of physical dynamics.
    null=[]
    for j in range(100):
        sign=np.repeat(rng.choice([-1,1],size=10),30);f=local_fields(U[750],D[750]*sign[:,None],np.linalg.norm(X[750],axis=1).mean());null.append(f['P'].mean())
    tests['random_chain_sign_counterfactual_P_mean']=float(np.mean(null));tests['actual_frame750_P']=float(fields['P'].mean())
    stats['method_tests']=tests
    (OUT/'additional_checks.json').write_text(json.dumps(stats,indent=2))
    fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True)
    ax[0].plot([r['time']/1e6 for r in phases],[r['relative_pair_phase_deg'] for r in phases],'.',ms=2);ax[0].set_ylabel('Relative pair phase (deg)');ax[0].set_ylim(-95,95)
    for key in ['pair_north_corot_omega','pair_south_corot_omega']:
        ts=[];ys=[]
        for lo in range(500,1000,25):
            vals=[r[key] for r in motion if lo<=r['frame']<lo+25]
            if vals:ts.append((lo+12.5)/1000);ys.append(np.mean(vals)*1e4)
        ax[1].plot(ts,ys,'o-',label=key.replace('pair_','').replace('_corot_omega',''))
    ax[1].axhline(0,color='gray');ax[1].legend();ax[1].set(xlabel='Production time / 1e6',ylabel='Residual pair angular speed / 1e-4');fig.tight_layout();fig.savefig(OUT/'06_relative_pair_phase.png',dpi=170);plt.close(fig)
    # Longest uninterrupted four-defect segment: identities are not bridged across births.
    ids={r['segment'] for r in tracks};best=max(ids,key=lambda s:sum(r['segment']==s for r in tracks));sub=[r for r in tracks if r['segment']==best];start=min(r['frame'] for r in sub);end=max(r['frame'] for r in sub)
    fig=plt.figure(figsize=(12,5))
    for panel,prefix in enumerate(['lab','corot']):
        ax=fig.add_subplot(1,2,panel+1,projection='3d')
        for j in range(4):
            vals=np.array([[r[prefix+'_'+dim] for dim in ['x','y','z']] for r in sub if r['track']==j]);ax.plot(*vals.T,lw=.8,label=str(j));ax.scatter(*vals[0],s=30)
        ax.set(xlim=(-1,1),ylim=(-1,1),zlim=(-1,1),title=('Laboratory frame' if panel==0 else 'Cumulative bead-corotating frame'))
    fig.suptitle('Same tracked defects; frames %d-%d (dots: start)'%(start,end));fig.tight_layout();fig.savefig(OUT/'07_defect_tracks_lab_vs_corot.png',dpi=180);plt.close(fig)
    print(json.dumps(stats,indent=2))
if __name__=='__main__':main()
