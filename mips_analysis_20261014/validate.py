import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json
import numpy as np
from scipy.spatial import cKDTree,ConvexHull
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
OUT=Path(__file__).resolve().parent
import analyze as a
rows=[];rng=np.random.RandomState(471)
for N,R in [(300,5.1756),(10500,30.6187)]:
 xyz=rng.normal(size=(N,3));xyz*=R/np.linalg.norm(xyz,axis=1)[:,None]
 u,tree,fields=a.field(xyz,R);f=(1-np.cos(3/R))/2;expected=np.sqrt((1-f)/(N*f))
 rows.append(dict(test='uniform independent spherical particles',N=N,measured_cv3=fields[3.].std()/fields[3.].mean(),binomial_expected_cv3=expected,measured_mean_density_ratio=fields[3.].mean()))
for name,mask,expected in [('cap',a.GRID[:,2]>.5,1),('two caps',np.abs(a.GRID[:,2])>.7,2),('equatorial band',np.abs(a.GRID[:,2])<.2,1)]:
 got=a.components(mask)[0];assert got==expected;rows.append(dict(test=name,components=got,expected_components=expected))
for n in [10,350]:
 p=OUT/'runs'/f'n{n}_F10'/'done.json';info=json.loads(p.read_text());xyz=a.load(Path(info['coordinate_directory'])/f"defect_out-{info['last_step']:010d}.xyz");R=info['R'];u=xyz/np.linalg.norm(xyz,axis=1)[:,None]
 for M in [2048,8192]:
  i=np.arange(M);z=1-2*(i+.5)/M;phi=i*np.pi*(3-np.sqrt(5));grid=np.c_[np.sqrt(1-z*z)*np.cos(phi),np.sqrt(1-z*z)*np.sin(phi),z]
  d=cKDTree(u).query_ball_point(grid,2*np.sin(3/(2*R)),return_length=True)/(len(u)*(1-np.cos(3/R))/2)
  face=ConvexHull(grid).simplices;e=np.unique(np.sort(np.vstack([face[:,[0,1]],face[:,[1,2]],face[:,[2,0]]]),axis=1),axis=0);adj=csr_matrix((np.ones(len(e)*2),(np.r_[e[:,0],e[:,1]],np.r_[e[:,1],e[:,0]])),shape=(M,M));ids=np.flatnonzero(d>1.2)
  nc,lab=connected_components(adj[ids][:,ids],directed=False) if len(ids) else (0,np.array([],int));largest=np.bincount(lab).max()/M if len(ids) else 0
  rows.append(dict(test='grid resolution',n=n,grid_points=M,cv3=d.std()/d.mean(),largest_area_1p2=largest,void3=float((d<.2).mean())))
# Great-circle finite-difference sanity check at a known rigid rotation angle.
theta=.1;R=10;dt=1000
u=np.array([[1.,0,0]]);v=np.array([[np.cos(theta),np.sin(theta),0]])
speed=R*np.arccos(np.sum(u*v,axis=1))[0]/dt
assert abs(speed-R*theta/dt)<1e-12
rows.append(dict(test='geodesic displacement speed',measured=speed,expected=R*theta/dt))
(OUT/'validation.json').write_text(json.dumps(rows,indent=2))
for r in rows:print(r)
