import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,csv
import numpy as np
from scipy.sparse.csgraph import connected_components
import analyze as a
OUT=Path(__file__).resolve().parent
rows=[];sizes=[]
for done in (OUT/'runs').glob('*/done.json'):
 info=json.loads(done.read_text());data=np.load(done.parent/'fields.npz');grid=data['grid'];R=info['R']
 for step,rho in zip(data['step'],data['density']):
  row=dict(n=info['n'],F=info['F'],step=int(step),R=R)
  for tag,mask in [('dilute02',rho<.2),('dilute05',rho<.5),('dilute08',rho<.8),('dense12',rho>1.2)]:
   ids=np.flatnonzero(mask)
   if len(ids):
    nc,labels=connected_components(a.adj[ids][:,ids],directed=False);sz=np.bincount(labels);largest=sz.max();weighted=(sz.astype(float)**2).sum()/sz.sum();which=ids[labels==sz.argmax()];mass=rho[which].sum()/rho.sum()
    if info['F'] in [0,.1,1,5,10]:
     for x in sz:sizes.append(dict(n=info['n'],F=info['F'],step=int(step),kind=tag,area_fraction=x/a.M,equivalent_radius=2*R*np.sqrt(x/a.M)))
   else:nc=0;largest=0;weighted=0;mass=0
   row.update({tag+'_area':float(mask.mean()),tag+'_largest_area':largest/a.M,tag+'_length':2*R*np.sqrt(largest/a.M),tag+'_weighted_length':2*R*np.sqrt(weighted/a.M),tag+'_largest_mass':mass,tag+'_nclusters':nc})
  pos=np.maximum(rho-1,0);den=pos.sum()
  if den>0:
   vals,vec=np.linalg.eigh(grid.T.dot(pos[:,None]*grid)/den);row['bandness']=vals[1]-vals[0];row['capness']=vals[2]-vals[1]
   axis=vec[:,0];lat=grid.dot(axis);b=np.clip(np.digitize(lat,np.linspace(-1,1,17))-1,0,15);pred=np.zeros(len(rho))
   for k in range(16):pred[b==k]=rho[b==k].mean()
   row['axisymmetric_band_explained_variance']=1-np.var(rho-pred)/max(np.var(rho),1e-20)
  rows.append(row)
for name,records in [('morphology_frames',rows),('cluster_size_distribution',sizes)]:
 with (OUT/(name+'.csv')).open('w',newline='') as fp:
  w=csv.DictWriter(fp,list(records[0]));w.writeheader();w.writerows(records)
print('morphology frames',len(rows))
