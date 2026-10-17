from pathlib import Path
import re,json,csv,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
rows=[]
series={}
for n in [150,200,250,300,350,100,50,30,10]:
 for folder in sorted((ROOT/f'nchain{n}').glob('F_*')):
  if not folder.is_dir():continue
  m=re.match(r'F_([0-9.]+)',folder.name)
  if not m:continue
  f=float(m[1]); row=dict(label=n,F=f,path=str(folder.relative_to(ROOT)))
  p=folder/'polymer.data'
  if p.exists():
   head=p.read_text(errors='replace')[:1200];a=re.search(r'(\d+) atoms',head)
   if a:row['input_atoms']=int(a[1]);row['actual_chains']=int(a[1])/30
  log=folder/'log.lammps'
  if log.exists():
   with log.open(errors='replace') as fp:s=fp.read(16000)
   a=re.search(r'reading atoms\s*\.\.\.\s*(\d+) atoms',s)
   if a:row['log_atoms']=int(a[1])
  known=folder/'defect_out'/'defect_out-0000100000.xyz'
  frames=[known] if known.exists() else []
  if frames:
   a=np.loadtxt(frames[min(1,len(frames)-1)],skiprows=2);xyz=a[a[:,0]==1,1:4]
   row['frame_atoms']=len(xyz);row['R']=np.linalg.norm(xyz,axis=1).mean()
  p=folder/'defect_results.dat'
  if p.exists():
   data=np.loadtxt(p,skiprows=1);header=p.open().readline().split();y=data[:,header.index('+1/2')];t=data[:,0]
   z=y[len(y)//4:];blocks=np.array([q.mean() for q in np.array_split(z,10)])
   row.update(frames=len(y),start=t[0],end=t[-1],mean75=z.mean(),sd75=z.std(ddof=1),mean50=y[len(y)//2:].mean(),mean25=y[3*len(y)//4:].mean(),block_sem=blocks.std(ddof=1)/np.sqrt(10),quarter1=y[:len(y)//4].mean(),quarter2=y[len(y)//4:len(y)//2].mean(),quarter3=y[len(y)//2:3*len(y)//4].mean(),quarter4=y[3*len(y)//4:].mean(),block_min=blocks.min(),block_max=blocks.max())
   row['net_bad']=int(np.count_nonzero(data[:,header.index('net_charge')]!=2))
   series[n,f]=(t,y)
  rows.append(row)
  print('checked',n,f,flush=True)
keys=list(dict.fromkeys(k for r in rows for k in r))
with (OUT/'audit.csv').open('w',newline='',encoding='utf-8-sig') as fp:
 w=csv.DictWriter(fp,keys);w.writeheader();w.writerows(rows)
(OUT/'audit.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
fig,axs=plt.subplots(2,3,figsize=(14,7))
for ax,f in zip(axs.flat,[.003,.03,.1,1,5,10]):
 for n in [150,200,250]:
  if (n,f) not in series:continue
  t,y=series[n,f];inds=np.array_split(np.arange(len(y)),min(100,len(y)))
  ax.plot([t[i].mean()/1e8 for i in inds],[y[i].mean() for i in inds],label=f'folder {n}')
 ax.set_title(f'F={f}');ax.set_xlabel('step / 1e8');ax.set_ylabel('N+');ax.legend(fontsize=8)
fig.tight_layout();fig.savefig(OUT/'time_comparison.png',dpi=150);plt.close(fig)
for n in [150,200,250,300,350]:
 rr=[r for r in rows if r['label']==n and 'mean75'in r]
 print('LABEL',n,'actual',sorted(set(r.get('actual_chains',-1) for r in rr)))
 for r in rr:
  print(r['F'],r.get('actual_chains'),round(r.get('R',0),3),*[round(r[k],2) for k in ['mean75','mean50','mean25','block_sem']],int(r['end']))
