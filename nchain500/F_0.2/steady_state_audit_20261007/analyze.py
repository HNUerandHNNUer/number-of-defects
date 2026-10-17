from pathlib import Path
import json, hashlib, re
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
RUNS = ['1yi/1', '1yi/2', '10yi']

def acf_stats(x):
    n=len(x); z=x-x.mean()
    f=np.fft.rfft(z,n=2**int(np.ceil(np.log2(2*n))))
    c=np.fft.irfft(f*f.conj())[:n]
    if c[0] == 0: return np.ones(n), 1., 0
    rho=c/c[0]
    # Initial positive, monotone paired sequence: diagnostic for these NESS
    # data, not a proof of reversibility or stationarity.
    pairs=rho[:2*(n//2)].reshape(-1,2).sum(axis=1)
    stop=np.flatnonzero(pairs<=0)
    k=int(stop[0]) if len(stop) else len(pairs)
    g=max(1., float(-1+2*np.minimum.accumulate(pairs[:k]).sum()))
    return rho,g,2*k

def block_values(x,b):
    m=len(x)//b
    return x[:m*b].reshape(m,b).mean(axis=1)

def summarize(t,x):
    rho,g,k=acf_stats(x)
    return dict(start=int(t[0]),end=int(t[-1]),n=len(x),mean=float(x.mean()),sd=float(x.std(ddof=1)),
                minimum=float(x.min()),maximum=float(x.max()),g=g,ess=len(x)/g,
                tau_int_steps=g*.5*float(np.median(np.diff(t))),acf_cutoff_frames=k,
                sem_acf=float(x.std(ddof=1)*np.sqrt(g/len(x))))

all_results={}; series={}; logstats={}
for name in RUNS:
    path=ROOT/name/'defect_results.dat'
    a=np.loadtxt(str(path),skiprows=1); t=a[:,0]; x=a[:,4]
    assert np.isfinite(a).all() and np.all(np.diff(t)==100000)
    assert np.all(a[:,1:3]>=0) and np.all(a[:,1:3]==np.rint(a[:,1:3]))
    assert np.all(a[:,1]+a[:,2]==x)
    assert np.all((a[:,1]-a[:,2])/2==a[:,3])
    series[name]=(t,x)
    windows=[]; blocking=[]; chunks=[]
    for frac in [0,.1,.2,.25,.3,.4,.5,.6,.7,.8]:
        start=int(len(x)*frac); tt=t[start:]; xx=x[start:]
        s=summarize(tt,xx); s['discard_fraction']=frac
        windows.append(s)
        for b in [1,2,5,10,20,50,100,200,250,500,750,1000]:
            y=block_values(xx,b); m=len(y)
            if m<4: continue
            se=float(y.std(ddof=1)/np.sqrt(m))
            reg=stats.linregress(np.arange(m),y)
            blocking.append(dict(discard_fraction=frac,block_frames=b,block_steps=b*100000,
                nblocks=m,used_frames=m*b,mean=float(y.mean()),sem=se,
                ci95_half=float(stats.t.ppf(.975,m-1)*se),
                block_lag1=float(np.corrcoef(y[:-1],y[1:])[0,1]),
                trend_over_span=float(reg.slope*(m-1)),trend_p=float(reg.pvalue),
                trend_ci95_half=float(stats.t.ppf(.975,m-2)*reg.stderr*(m-1))))
    width=100000000 if name=='10yi' else 10000000
    # Exclude step zero, use right-closed equal physical-time blocks.
    for lo in range(0,int(t[-1]),width):
        mask=(t>lo)&(t<=lo+width)
        s=summarize(t[mask],x[mask]); s['interval_left_exclusive']=lo; chunks.append(s)
    text=(ROOT/name/'log.lammps').read_text(errors='replace')
    thermo=[]
    for line in text.splitlines():
        fields=line.split()
        if len(fields)==6:
            try: vals=[float(q) for q in fields]
            except ValueError: continue
            if vals[0]>=0 and vals[0].is_integer(): thermo.append(vals)
    therm=np.array(thermo)
    warnings={}
    for l in text.splitlines():
        if l.startswith('WARNING:'):
            key=l.split(' (src/')[0]
            if 'FENE bond too long' in key: key='WARNING: FENE bond too long'
            warnings[key]=warnings.get(key,0)+1
    logstats[name]=dict(warnings=warnings,thermo_rows=len(therm),
        last_step=float(therm[-1,0]),pe_blocks=[float(z[:,3].mean()) for z in np.array_split(therm[1:],10)],
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),seed=(ROOT/name/'random_seed.txt').read_text().strip())
    all_results[name]=dict(full=summarize(t,x),net_charge_unique=np.unique(a[:,3]).tolist(),
        windows=windows,blocking=blocking,chunks=chunks)

# Long-run interval comparisons with moving-block bootstrap; intervals chosen
# on an explicit coarse grid, so these are exploratory, not confirmatory tests.
rng=np.random.default_rng(20261007)
def boot_means(x,b,reps=4000):
    starts=rng.integers(0,len(x)-b+1,size=(reps,int(np.ceil(len(x)/b))))
    idx=(starts[:,:,None]+np.arange(b)).reshape(reps,-1)[:,:len(x)]
    return x[idx].mean(axis=1)
t,x=series['10yi']; comparisons=[]
for lo,mid,hi in [(0,5e8,1e9),(1e8,5.5e8,1e9),(2.5e8,6.25e8,1e9),(5e8,7.5e8,1e9)]:
    xa=x[(t>lo)&(t<=mid)]; xb=x[(t>mid)&(t<=hi)]
    for b in [50,100,250,500]:
        if min(len(xa),len(xb))<b*4: continue
        d=boot_means(xb,b)-boot_means(xa,b)
        comparisons.append(dict(start=lo,mid=mid,end=hi,block_frames=b,
            first_mean=float(xa.mean()),second_mean=float(xb.mean()),difference=float(xb.mean()-xa.mean()),
            difference_ci95=np.quantile(d,[.025,.975]).tolist(),
            first_sd=float(xa.std(ddof=1)),second_sd=float(xb.std(ddof=1))))

long_estimates=[]
for lo in [0,1e8,2.5e8,5e8]:
    mask=t>lo; tt=t[mask]; xx=x[mask]
    s=summarize(tt,xx); s['left_exclusive']=int(lo)
    s['positive_mean']=(s['mean']+4)/2
    s['negative_mean']=(s['mean']-4)/2
    s['block_estimates']=[]
    for b in [100,250,500,750,1000,1500,2000]:
        y=block_values(xx,b); m=len(y)
        if m<4: continue
        se=float(y.std(ddof=1)/np.sqrt(m)); half=float(stats.t.ppf(.975,m-1)*se)
        s['block_estimates'].append(dict(block_frames=b,nblocks=m,mean=float(y.mean()),
            used_frames=m*b,sem=se,ci95=[float(y.mean()-half),float(y.mean()+half)],
            block_lag1=float(np.corrcoef(y[:-1],y[1:])[0,1])))
    long_estimates.append(s)
result=dict(runs=all_results,logs=logstats,comparisons=comparisons,long_estimates=long_estimates,
    interpretation_notes=['ACF/ESS and nominal regression p-values for drifting windows are diagnostics only.',
    'Block t intervals assume sufficiently independent representative blocks; few blocks and residual slow modes limit accuracy.',
    'User states common configuration provenance; actual step-zero defects and energies differ between short and long runs.',
    'Long-run cutoffs are sensitivity analyses, not verified physical equilibration times.'])
(OUT/'statistics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
lines=[]
for name,r in all_results.items():
    lines += [name, 'FULL '+str(r['full']), 'CHUNKS '+str([round(s['mean'],3) for s in r['chunks']])]
    for s in r['windows']:
        lines.append('WINDOW '+str({k:round(v,5) if isinstance(v,float) else v for k,v in s.items()}))
    lines.append('BLOCKING 25% '+str([s for s in r['blocking'] if s['discard_fraction']==.25]))
lines.append('COMPARISONS '+str(comparisons)); lines.append('LOGS '+str(logstats))
(OUT/'numerical_summary.txt').write_text('\n'.join(lines),encoding='utf-8')

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(3,2,figsize=(13,10),constrained_layout=True)
for row,name in enumerate(RUNS):
    t,x=series[name]; r=all_results[name]; ax=axs[row,0]
    ax.plot(t/1e8,x,color='steelblue',alpha=.4,lw=.65)
    for s in r['chunks']:
        ax.hlines(s['mean'],s['interval_left_exclusive']/1e8,s['end']/1e8,color='darkred',lw=2.5)
    ax.set(title=name+' | raw counts and equal-time block means',xlabel='Simulation step / 1e8',ylabel='Total defects')
    ax=axs[row,1]
    for f in [0,.25,.5]:
        rho,g,k=acf_stats(x[int(len(x)*f):]); n=min(501,len(rho))
        ax.plot(np.arange(n)*.1,rho[:n],label='discard '+str(f))
    ax.axhline(0,color='grey',lw=.5)
    ax.set(xlabel='Lag / 1e6 steps',ylabel='Autocorrelation',title=name+' | window-dependent ACF'); ax.legend()
fig.savefig(OUT/'time_series_acf.png',dpi=170); plt.close(fig)

fig,axs=plt.subplots(1,3,figsize=(15,4.4),constrained_layout=True)
for ax,name in zip(axs,RUNS):
    r=all_results[name]
    for f in [0,.25,.5]:
        a=[v for v in r['blocking'] if v['discard_fraction']==f]
        ax.plot([s['block_steps']/1e6 for s in a],[s['sem'] for s in a],'-o',label='discard '+str(f))
    ax.set(xscale='log',xlabel='Block length / 1e6 steps',ylabel='Estimated SEM',title=name); ax.legend()
fig.savefig(OUT/'blocking_sem.png',dpi=170); plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(12,4.3),constrained_layout=True)
for name in RUNS:
    w=all_results[name]['windows']
    axs[0].plot([s['discard_fraction'] for s in w],[s['mean'] for s in w],'-o',label=name)
t,x=series['10yi']
for lo,hi in [(0,2.5e8),(2.5e8,5e8),(5e8,7.5e8),(7.5e8,1e9)]:
    y=x[(t>lo)&(t<=hi)]
    axs[1].hist(y,bins=np.arange(x.min()-1,x.max()+3,2),density=True,histtype='step',label=f'{lo/1e8:g}-{hi/1e8:g}e8')
axs[0].set(xlabel='Discarded fraction',ylabel='Remaining-window mean',title='Sensitivity to starting time')
axs[1].set(xlabel='Total defects',ylabel='Probability density',title='Long run: successive quarter distributions')
for ax in axs: ax.legend()
fig.savefig(OUT/'window_sensitivity.png',dpi=170); plt.close(fig)
print('\n'.join(lines[:3])); print('Saved',OUT)
