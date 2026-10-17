import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import re,json,csv,hashlib,sys,importlib.util
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'activity_analysis_20261013';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('kernel',ROOT/'sphere_nematic_parallel_large_v4.py');k=importlib.util.module_from_spec(spec);sys.modules['kernel']=k;spec.loader.exec_module(k)
def write(name,rows):
    with (OUT/(name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
rows=[];windows=[];episodes=[];provenance=[];series={};hashgroups={}
for p in sorted((ROOT/'results_evolution').iterdir(),key=lambda p:float(p.name) if p.is_dir() else 1e9):
    if not p.is_dir():continue
    F=float(p.name);tab=np.loadtxt(p/'defect_results.dat',skiprows=1);t=tab[:,0]*.01;n=tab[:,4];series[F]=(t,n)
    assert np.all(tab[:,1]-tab[:,2]==4) and np.all(tab[:,3]==2) and np.all(tab[:,1]+tab[:,2]==n)
    log=(p/'log.lammps').read_text(errors='replace');inp=(p/'bd.in').read_text(errors='replace')
    fixes=re.findall(r'^fix\s+bd\s+all\s+(bd/sphere\S*)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+mchain\s+(\d+)',log,re.M)
    raw=(p/'polymer.data').read_bytes();sha=hashlib.sha256(raw).hexdigest();group=hashgroups.setdefault(sha,chr(65+len(hashgroups)))
    lines=raw.decode().splitlines();start=next(i for i,l in enumerate(lines) if l.strip().startswith('Atoms'))+2;a=np.array([[float(v) for v in l.split()] for l in lines[start:start+300]]);a=a[np.argsort(a[:,0])];x=a[:,3:6];r=np.linalg.norm(x,axis=1);u=x/r[:,None];d=k.chain_directors(u,30,k.Settings());rr=k.identify(x)
    vals,vec=np.linalg.eigh(d.T@d/len(d));axis=vec[:,0];az=np.cross(axis,u);az/=np.linalg.norm(az,axis=1)[:,None]
    blocks=re.findall(r'Step\s+Temp\s+KinEng\s+PotEng\s+TotEng\s+Press\s*\n(.*?)(?=Loop time)',log,re.S)
    thermo=[]
    if blocks:
        for line in blocks[-1].splitlines():
            vs=line.split()
            if len(vs)==6:
                try:thermo.append([float(v) for v in vs])
                except ValueError:pass
    th=np.array(thermo);mpi=re.findall(r'(\d+) by (\d+) by (\d+) MPI processor grid',log)
    seed=int(fixes[-1][4]) if fixes else None
    provenance.append(dict(F=F,initial_group=group,initial_sha256=sha,fix_expansions=fixes,production_seed=seed,printed_seeds=re.findall(r'^Random seed for this simulation = (\d+)',log,re.M),MPI=int(np.prod([int(v) for v in mpi[-1]])) if mpi else None,run_steps=re.findall(r'^run\s+(\d+)\s*$',log,re.M),thermo_rows=len(th),has_errors='ERROR:' in log,has_prewarm=len(fixes)>1,log_sha256=hashlib.sha256((p/'log.lammps').read_bytes()).hexdigest()))
    first=np.where(n==4)[0];sustain=next((i for i in range(len(n)-49) if np.mean(n[i:i+50]==4)>=.9),None)
    row=dict(F=F,initial_group=group,frames=len(t),duration=t[-1],sample_dt=np.median(np.diff(t)),reported_initial_defects=n[0],polymer_data_defects=int(rr['mask'].sum()),initial_B=float(np.mean(2*np.sum(az*d,axis=1)**2-1)),first_four_time=t[first[0]] if len(first) else np.nan,first_90pct_four_in_50frames=t[sustain] if sustain is not None else np.nan,production_seed=seed,MPI=provenance[-1]['MPI'],radius=r.mean(),contour_length=np.linalg.norm(np.diff(x.reshape(10,30,3),axis=1),axis=2).sum(axis=1).mean())
    for label,lo,hi in [('all',0,t[-1]),('late_half',t[-1]/2,t[-1]),('common_late',5e5,1e6),('common_early',0,1e5)]:
        sel=(t>=lo)&(t<=hi);v=n[sel];neg=tab[sel,2]
        w=dict(F=F,window=label,start=lo,end=hi,frames=len(v),fraction_four=float(np.mean(v==4)),mean_defects=v.mean(),std_defects=v.std(),mean_negative=neg.mean(),max_defects=v.max(),fraction_ge8=float(np.mean(v>=8)))
        windows.append(w)
        if label in ['late_half','common_late']:
            row[label+'_fraction_four']=w['fraction_four'];row[label+'_mean_defects']=w['mean_defects']
    if len(th):
        mask=th[:,0]*.01>=t[-1]/2;row['late_PE_mean']=float(np.mean(th[mask,3]));row['late_thermo_temp_mean']=float(np.mean(th[mask,1]))
    else:row['late_PE_mean']=np.nan;row['late_thermo_temp_mean']=np.nan
    rows.append(row)
    active=n>4;i=0
    while i<len(t):
        if not active[i]:i+=1;continue
        j=i+1
        while j<len(t) and active[j]:j+=1
        episodes.append(dict(F=F,start=t[i],last_observed=t[j-1],observed_frames=j-i,nominal_duration=(j-i)*np.median(np.diff(t)),left_censored=i==0,right_censored=j==len(t),max_defects=float(n[i:j].max())))
        i=j
write('activity_summary',rows);write('window_statistics',windows);write('excess_count_episodes',episodes)
(OUT/'provenance.json').write_text(json.dumps(provenance,indent=2))
fig,ax=plt.subplots(2,1,figsize=(11,7),sharex=True)
for label,mark in [('common_late','o'),('late_half','s')]:
    a=[w for w in windows if w['window']==label];ax[0].plot([w['F'] for w in a],[w['fraction_four'] for w in a],mark+'-',label=label);ax[1].plot([w['F'] for w in a],[w['mean_defects'] for w in a],mark+'-')
ax[0].legend();ax[0].set_ylabel('Fraction with four defects');ax[1].set(xlabel='Active force F',ylabel='Mean reported defect count');fig.tight_layout();fig.savefig(OUT/'01_activity_dependence.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(4,4,figsize=(15,10));
for a,(F,(t,n)) in zip(ax.ravel(),series.items()):
    a.plot(t/1e6,n,lw=.5);a.set(title='F=%g'%F,xlabel='time / 1e6',ylabel='Reported count');a.axvspan(.5,1,color='green',alpha=.08);a.set_ylim(3, max(10,n.max()+1))
for a in ax.ravel()[len(series):]:a.set_visible(False)
fig.tight_layout();fig.savefig(OUT/'02_count_evolution.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(11,4))
for F in [2,4,6,7,8,9]:
    t,n=series[F];smooth=np.convolve(n,np.ones(10)/10,mode='valid');tc=t[9:];ax[0].plot(tc/1e5,smooth,label=str(F));ax[1].plot(F*tc/1000/5.175492,smooth,label=str(F))
ax[0].set(xlim=(0,2),xlabel='time / 1e5',ylabel='Count, 10-frame moving mean');ax[1].set(xlim=(0,100),xlabel='F t / (gamma R)',ylabel='Count, 10-frame moving mean');ax[1].legend(title='F');fig.tight_layout();fig.savefig(OUT/'03_transient_scaling.png',dpi=170);plt.close(fig)
print(json.dumps(rows,indent=2))
