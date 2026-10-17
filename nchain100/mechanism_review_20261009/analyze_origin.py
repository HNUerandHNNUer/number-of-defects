from pathlib import Path
import json,re,csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent; NEW=OUT.parent.parent
data=json.loads((OUT/'origin_data.json').read_text(encoding='utf-8'))[0]['sheets'][0]['data']
rows=[]; summaries=[]
for group,nchain in enumerate([10,30,50,100,500,1000]):
    folder=NEW/f'nchain{nchain}'; candidates=[]
    for p in folder.glob('*.txt'):
        s=p.read_text(encoding='utf-8-sig',errors='replace')
        y=re.search(r'^\+1/2 defect (\d+) ± ([\d.]+)',s,re.M)
        raw=re.search(r'^\+1/2 defect raw_mean=([\d.]+)',s,re.M)
        timestep=re.search(r'# 固定统计时间步: (\d+) — (\d+)',s)
        if y:
            candidates.append((p,float(y[1]),float(y[2]),float(raw[1]) if raw else None,timestep.groups() if timestep else None,s.splitlines()[0][9:]))
    for d in data:
        pe,y,sd=d[3*group:3*group+3]
        if pe is None or pe=='': continue
        match=[q for q in candidates if q[1]==y and abs(q[2]-sd)<1e-5 and re.match(r'^'+re.escape(str(pe).removesuffix('.0') if hasattr(str(pe),'removesuffix') else ('%g'%pe))+r'(?:_|\.txt)',q[0].name)]
        if not match: match=[q for q in candidates if q[1]==y and abs(q[2]-sd)<1e-5]
        q=match[0] if len(match)==1 else None
        R=np.sqrt(30*nchain/(16*.7)); area=4*np.pi*R*R
        raw=q[3] if q and q[3] is not None else y
        rows.append({'nchain':nchain,'R_inferred':R,'Pe':pe,'Nplus_plotted':y,'SDplus_time':sd,'Nplus_raw':raw,'Ntotal_reconstructed':2*raw-4,'pair_density':(raw-4)/area,'total_density':(2*raw-4)/area,'summary_path':str(q[0]) if q else '', 'start_step':q[4][0] if q and q[4] else '', 'end_step':q[4][1] if q and q[4] else '', 'source_dat':q[5] if q else ''})
with (OUT/'origin_verified_long_table.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Origin points',len(rows),'matched summaries',sum(bool(r['summary_path']) for r in rows))
fig,axs=plt.subplots(1,3,figsize=(15,4.5))
for nchain in [10,30,50,100,500,1000]:
    z=[r for r in rows if r['nchain']==nchain and r['Pe']>0];x=[r['Pe'] for r in z]
    axs[0].errorbar(x,[r['Nplus_plotted'] for r in z],yerr=[r['SDplus_time'] for r in z],label=str(nchain),marker='.',lw=1,capsize=2)
    axs[1].plot(x,[r['pair_density'] for r in z],'.-',label=str(nchain))
    axs[2].plot(x,[float(r['end_step'])*.01 if r['end_step'] else np.nan for r in z],'.-',label=str(nchain))
    if nchain>=500:
        m=min(z,key=lambda r:r['Nplus_plotted']);print('minimum',nchain,m['Pe'],m['Nplus_plotted'],m['SDplus_time'])
for ax,title,ylab in zip(axs,['Actual plotted quantity','Excess-pair density (reconstructed)','Simulation duration used in summaries'],['Mean positive half defects','(mean N+ - 4) / area','Last step x 0.01']):
    ax.set_xscale('log');ax.set_xlabel('Pe = F sigma / kBT');ax.set_ylabel(ylab);ax.set_title(title);ax.grid(alpha=.25);ax.legend(title='Chains',fontsize=8)
axs[2].set_yscale('log');fig.tight_layout();fig.savefig(OUT/'origin_reanalysis.png',dpi=180)
# Recompute accessible raw count histories, not prior audit summaries.
paths={'500_Pe0.2_short1':NEW/'nchain500/F_0.2/1yi/1/defect_results.dat','500_Pe0.2_short2':NEW/'nchain500/F_0.2/1yi/2/defect_results.dat','500_Pe0.2_long':NEW/'nchain500/F_0.2/10yi/defect_results.dat'}
for r in rows:
    p=Path(r['source_dat'])
    if p.is_file() and r['nchain'] in [500,1000] and r['Pe']<=.1: paths[f"{r['nchain']}_Pe{r['Pe']}"]=p
ts={};fig,axs=plt.subplots(1,2,figsize=(12,4.5))
for name,p in paths.items():
    a=np.loadtxt(p,skiprows=1);z=a[len(a)//4:,1]; blocks=np.array_split(a[:,1],10)
    ts[name]={'path':str(p),'n':len(a),'first_Nplus':a[0,1],'last_Nplus':a[-1,1],'post25_mean_Nplus':z.mean(),'post25_sd_Nplus':z.std(ddof=1),'decile_Nplus':[b.mean() for b in blocks]}
    ax=axs[0] if 'Pe0.2' in name else axs[1]
    ax.plot(a[:,0]*.01,a[:,1],label=name,lw=.6)
for ax in axs:ax.set_xlabel('Time');ax.set_ylabel('Positive half defects');ax.legend(fontsize=7);ax.grid(alpha=.25)
axs[0].set_title('Preparation/time dependence at Pe=0.2');axs[1].set_title('Accessible low-activity trajectories')
fig.tight_layout();fig.savefig(OUT/'count_time_histories.png',dpi=180)
(OUT/'time_history_statistics.json').write_text(json.dumps(ts,indent=2),encoding='utf-8')
print(json.dumps(ts,indent=2))
