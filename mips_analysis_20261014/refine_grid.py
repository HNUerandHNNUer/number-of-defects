import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,csv
import numpy as np
from scipy.spatial import cKDTree,ConvexHull
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
import analyze as a
OUT=Path(__file__).resolve().parent
meshes={}
for M in [2048,8192]:
 i=np.arange(M);z=1-2*(i+.5)/M;phi=i*np.pi*(3-np.sqrt(5));grid=np.c_[np.sqrt(1-z*z)*np.cos(phi),np.sqrt(1-z*z)*np.sin(phi),z]
 face=ConvexHull(grid).simplices;e=np.unique(np.sort(np.vstack([face[:,[0,1]],face[:,[1,2]],face[:,[2,0]]]),axis=1),axis=0);adj=csr_matrix((np.ones(len(e)*2),(np.r_[e[:,0],e[:,1]],np.r_[e[:,1],e[:,0]])),shape=(M,M));meshes[M]=(grid,adj)
rows=[]
for n in a.NS:
 info=json.loads((OUT/'runs'/f'n{n}_F10'/'done.json').read_text());folder=Path(info['coordinate_directory']);R=info['R']
 for step in np.linspace(25000000,100000000,13).astype(int):
  step=int(round(step/info['output_step_median'])*info['output_step_median']);file=folder/f'defect_out-{step:010d}.xyz'
  if not file.exists():continue
  xyz=a.load(file);u=xyz/np.linalg.norm(xyz,axis=1)[:,None];tree=cKDTree(u)
  for M,(grid,adj) in meshes.items():
   d=tree.query_ball_point(grid,2*np.sin(3/(2*R)),return_length=True)/(len(u)*(1-np.cos(3/R))/2)
   row=dict(n=n,F=10,step=step,M=M,R=R,cv3=d.std()/d.mean(),void3=float((d<.2).mean()))
   for tag,mask in [('dense11',d>1.1),('dense12',d>1.2),('dense13',d>1.3),('dilute05',d<.5)]:
    ids=np.flatnonzero(mask);nc,lab=connected_components(adj[ids][:,ids],directed=False) if len(ids) else (0,np.array([],int));largest=np.bincount(lab).max()/M if len(ids) else 0
    row[tag+'_largest_area']=largest;row[tag+'_length']=2*R*np.sqrt(largest)
   rows.append(row)
 print('refined',n,flush=True)
with (OUT/'grid_sensitivity.csv').open('w',newline='') as fp:
 w=csv.DictWriter(fp,list(rows[0]));w.writeheader();w.writerows(rows)
