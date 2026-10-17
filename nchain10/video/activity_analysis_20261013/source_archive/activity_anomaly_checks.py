from pathlib import Path
import numpy as np, csv, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'activity_analysis_20261013'
rows=[]
fig,axs=plt.subplots(2,1,figsize=(11,7),sharex=True)
for F in [2,4,6,7,8,9]:
    a=np.loadtxt(ROOT/'results_evolution'/str(F)/'defect_results.dat',skiprows=1);t=a[:,0]*.01;n=a[:,4];points=[]
    for lo in np.arange(0,1e6,1e5):
        s=(t>=lo)&(t<lo+1e5);v=n[s];r=dict(F=F,start=lo,end=lo+1e5,n=len(v),mean_count=v.mean(),fraction_four=np.mean(v==4));rows.append(r);points.append(r)
    axs[0].plot([(r['start']+5e4)/1e6 for r in points],[r['fraction_four'] for r in points],'o-',label='F=%s'%F)
    if F in [6,7]:axs[1].plot(t/1e6,n,lw=.8,alpha=.85,label='F=%s'%F)
axs[0].set_ylabel('Four-defect fraction / 100000-time block');axs[0].legend(ncol=3);axs[1].set(xlabel='Time / 1e6',ylabel='Reported count');axs[1].legend();fig.tight_layout();fig.savefig(OUT/'04_intermittent_excursions.png',dpi=170)
with (OUT/'block_statistics.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
# Tests catch column, time-window, and charge-convention errors without treating frames as replicates.
for F in [2,4,6,7,8,9]:
    a=np.loadtxt(ROOT/'results_evolution'/str(F)/'defect_results.dat',skiprows=1)
    assert len(a)==1001 and a[-1,0]==1e8
    assert np.all(np.diff(a[:,0])==100000)
    assert np.all(a[:,4]==4+2*a[:,2])
    block=[r for r in rows if r['F']==F]
    assert abs(np.mean(a[:-1,4])-np.mean([r['mean_count'] for r in block]))<1e-12
(OUT/'validation.json').write_text(json.dumps({'new_runs':6,'charge_and_count_identity':'passed','sampling_consistency':'passed','block_mean_reconstruction':'passed','independent_seeds_per_F':1},indent=2))
