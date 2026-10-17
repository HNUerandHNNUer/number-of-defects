"""Cross-activity full-coordinate comparison, conditional on observed states."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'activity_analysis_20261013'
def read(p):
    with p.open(encoding='utf-8-sig') as f:return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
def write(name,rows):
    with (OUT/(name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
rows=[];conditional=[];smooth=[];chainrows=[];sources={}
for F in [1,2,4,6,7,8,9]:
    p=ROOT.parent/'gpu2'/'postprocess_F1_20261012' if F==1 else OUT/('F_%s'%F);sources[F]=p
    a=read(p/'frame_metrics.csv');m=read(p/'particle_rotation.csv');pairs=read(p/'defect_pair_geometry.csv');sc=read(p/'smoothing_sensitivity.csv') if False else None
    # sensitivity CSV contains a status string; parse only numeric fields.
    with (p/'smoothing_sensitivity.csv').open(encoding='utf-8-sig') as f:sc=[{k:float(v) for k,v in r.items() if k!='status'} for r in csv.DictReader(f)]
    late=[r for r in a if r['time']>=5e5];mlate=[r for r in m if r['time']>=5e5];plate=[r for r in pairs if r['time']>=5e5]
    row={'F':F,'frames':len(a)}
    for key in ['P_local_area_mean','S_local_area_mean','interchain_polar_correlation','B_azimuthal','circulation_norm','polarcap_relative_density','equatorial_relative_density','predicted_omega_axis','radial_relative_max','max_bond']:
        row[key]=np.mean([r[key] for r in late])
    for key in ['omega_axis','rigid_rotation_fraction','rotation_angle_deg']:
        row[key]=np.mean([r[key] for r in mlate])
    row['rotation_angle_max_deg']=max(r['rotation_angle_deg'] for r in mlate)
    row['torque_mean_relative_difference']=abs(row['omega_axis']-row['predicted_omega_axis'])/abs(row['predicted_omega_axis'])
    row['abs_omega_gammaR_over_F']=abs(row['omega_axis'])*1000*np.mean([r['R'] for r in late])/F
    for key in ['north_pair_angle_deg','south_pair_angle_deg','pair_center_separation_deg']:
        row[key]=np.mean([r[key] for r in plate]) if plate else np.nan
    means=[np.mean([r['chain_%02d_signed_circulation'%j] for r in late]) for j in range(10)]
    sign=np.sign(np.mean([r['signed_circulation'] for r in late]));row['chains_opposite_mean_circulation']=sum(x*sign<0 for x in means)
    for j,v in enumerate(means):chainrows.append(dict(F=F,chain=j,mean_signed_circulation=v))
    if F!=1:
        orig=np.loadtxt(ROOT/'results_evolution'/str(F)/'defect_results.dat',skiprows=1)
        assert np.array_equal(orig[:,4],np.array([r['n_defects'] for r in a]))
    for condition,sel in [('four',[r for r in late if r['n_defects']==4]),('excess',[r for r in late if r['n_defects']>4]),('ge8',[r for r in late if r['n_defects']>=8])]:
        cr=dict(F=F,condition=condition,frames=len(sel))
        for key in ['P_local_area_mean','S_local_area_mean','interchain_polar_correlation','B_azimuthal','circulation_norm','polarcap_relative_density','equatorial_relative_density','predicted_omega_axis']:
            cr[key]=np.mean([r[key] for r in sel]) if sel else np.nan
        ids={r['frame'] for r in sel};sm=[r for r in mlate if r['frame'] in ids]
        cr['rigid_fraction']=np.mean([r['rigid_rotation_fraction'] for r in sm]) if sm else np.nan;conditional.append(cr)
    for h in [.7,1,1.5,2]:
        sub=[r for r in sc if r['time']>=5e5 and r['h']==h];smooth.append(dict(F=F,h=h,frames=len(sub),fraction_four=np.mean([r['n_smoothed_defects']==4 for r in sub]),mean_defects=np.mean([r['n_smoothed_defects'] for r in sub])))
    rows.append(row)
write('full_coordinate_summary',rows);write('state_conditional_metrics',conditional);write('smoothing_across_F',smooth);write('chain_circulation_across_F',chainrows)
fig,ax=plt.subplots(2,2,figsize=(12,8));ff=[r['F'] for r in rows]
ax[0,0].plot(ff,[abs(r['omega_axis']) for r in rows],'o-',label='Measured');ax[0,0].plot(ff,[abs(r['predicted_omega_axis']) for r in rows],'s--',label='Active torque');ax[0,0].set_ylabel('|Angular speed|');ax[0,0].legend()
for key,label in [('P_local_area_mean','Local polar P'),('S_local_area_mean','Local nematic S'),('interchain_polar_correlation','Inter-chain polar')]:ax[0,1].plot(ff,[r[key] for r in rows],'o-',label=label)
ax[0,1].legend();ax[0,1].set_ylabel('Order')
for key,label in [('north_pair_angle_deg','Pair N'),('south_pair_angle_deg','Pair S')]:ax[1,0].plot(ff,[r[key] for r in rows],'o-',label=label)
ax[1,0].legend();ax[1,0].set_ylabel('Within-pair angle (deg), raw four-only')
ax[1,1].plot(ff,[r['rigid_rotation_fraction'] for r in rows],'o-');ax[1,1].set_ylabel('Rigid motion fraction, lag=1000')
for a in ax.ravel():a.set_xlabel('F')
fig.tight_layout();fig.savefig(OUT/'06_full_coordinate_comparison.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(4,2,figsize=(14,10),sharex=True)
for col,F in enumerate([6,7]):
    p=sources[F];a=read(p/'frame_metrics.csv');m=read(p/'particle_rotation.csv');t=np.array([r['time'] for r in a])/1e6
    axs[0,col].plot(t,[r['n_defects'] for r in a],lw=.7,label='Raw')
    with (p/'smoothing_sensitivity.csv').open(encoding='utf-8-sig') as f:sc=list(csv.DictReader(f))
    ss=[r for r in sc if float(r['h'])==1.5];axs[0,col].plot([float(r['time'])/1e6 for r in ss],[float(r['n_smoothed_defects']) for r in ss],'.-',ms=2,lw=.7,label='Q smoothed, h=1.5');axs[0,col].legend();axs[0,col].set_title('F=%d'%F)
    for key,label in [('P_local_area_mean','P'),('S_local_area_mean','S')]:axs[1,col].plot(t,[r[key] for r in a],label=label,lw=.8)
    axs[1,col].legend();axs[2,col].plot(t,[r['circulation_norm'] for r in a],lw=.8)
    axs[3,col].plot([r['time']/1e6 for r in m],[r['rigid_rotation_fraction'] for r in m],lw=.7);axs[3,col].set_xlabel('Time / 1e6')
for i,l in enumerate(['Defect count','Local order','Circulation magnitude','Rigid fraction']):axs[i,0].set_ylabel(l)
fig.tight_layout();fig.savefig(OUT/'07_burst_mechanism_diagnostics.png',dpi=170);plt.close(fig)
print(json.dumps(rows,indent=2,default=lambda v:v.item()))
