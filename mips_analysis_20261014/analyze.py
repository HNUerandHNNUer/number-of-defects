# -*- coding: utf-8 -*-
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import re,json,csv,time,argparse
import numpy as np
from scipy.spatial import cKDTree,ConvexHull
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.special import sph_harm

ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
NS=[10,30,50,100,150,200,300,350]
M=2048;idx=np.arange(M);z=1-2*(idx+.5)/M;az=idx*np.pi*(3-np.sqrt(5))
GRID=np.c_[np.sqrt(1-z*z)*np.cos(az),np.sqrt(1-z*z)*np.sin(az),z]
faces=ConvexHull(GRID).simplices
edges=np.unique(np.sort(np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
adj=csr_matrix((np.ones(len(edges)*2),(np.r_[edges[:,0],edges[:,1]],np.r_[edges[:,1],edges[:,0]])),shape=(M,M))
ell_idx=np.concatenate([np.full(2*l+1,l) for l in range(1,25)])
Y=np.array([sph_harm(m,l,np.mod(az,2*np.pi),np.arccos(z)).conj() for l in range(1,25) for m in range(-l,l+1)])
links=json.loads((OUT/'shortcuts.json').read_text(encoding='utf-8-sig'))
linkmap={str(Path(v['link']).parent):Path(v['target']) for v in links if v['exists']}

def load(p):
 with p.open() as f:
  f.readline();head=f.readline();a=np.fromstring(f.read(),sep=' ')
 if len(a)%4:raise ValueError('not type x y z '+str(p))
 a=a.reshape(-1,4);xyz=a[a[:,0]==1,1:]
 return xyz

def components(mask):
 ids=np.flatnonzero(mask)
 if not len(ids):return 0,0,0.,0.,0.
 nc,lab=connected_components(adj[ids][:,ids],directed=False);sizes=np.bincount(lab);big=ids[lab==sizes.argmax()]
 ev=np.linalg.eigvalsh(GRID[big].T.dot(GRID[big])/len(big))
 return nc,int(sizes.max()),float((sizes*sizes).sum()/sizes.sum()),float(ev[0]),float(ev[-1])

def field(xyz,R):
 u=xyz/np.linalg.norm(xyz,axis=1)[:,None];tree=cKDTree(u);rho0=len(u)/(4*np.pi*R*R)
 counts={ell:tree.query_ball_point(GRID,2*np.sin(ell/(2*R)),return_length=True) for ell in [2.,3.,5.]}
 fields={ell:c/(len(u)*(1-np.cos(ell/R))/2) for ell,c in counts.items()}
 return u,tree,fields

def metrics(xyz,R):
 u,tree,fields=field(xyz,R);d=fields[3.];row={}
 for ell,a in fields.items():
  row['cv'+str(int(ell))]=float(a.std()/a.mean());row['void'+str(int(ell))]=float((a<.2).mean())
 for th in [1.1,1.2,1.3]:
  nc,largest,weighted,e0,e2=components(d>th);tag=str(th).replace('.','p')
  row.update({f'nclusters_{tag}':nc,f'largest_area_{tag}':largest/M,f'dense_area_{tag}':float((d>th).mean()),f'weighted_length_{tag}':2*R*np.sqrt(weighted/M),f'largest_length_{tag}':2*R*np.sqrt(largest/M),f'moment_min_{tag}':e0,f'moment_max_{tag}':e2})
 coeff=(4*np.pi/M)*Y.dot(d-d.mean());power=np.bincount(ell_idx,weights=np.abs(coeff)**2,minlength=25)[1:]/(4*np.pi)
 q=np.sqrt(np.arange(1,25)*np.arange(2,26))/R;valid=q<=.8
 row['lowmode_power']=float(power[:2].sum());row['lowmode_fraction']=float(power[:2].sum()/max(power.sum(),1e-30))
 row['xi_fixedq']=float(power[valid].sum()/max(np.dot(q[valid],power[valid]),1e-30))
 # Counts in fixed physical spherical caps; temporal and pooled variances stored later.
 radii=np.array([2.,3.,4.,5.,7.,10.,14.,18.,24.]);radii=radii[radii<=.8*R]
 gnf=np.array([tree.query_ball_point(GRID[::4],2*np.sin(r/(2*R)),return_length=True) for r in radii])
 hist=np.array([np.histogram(fields[e],bins=np.linspace(0,2.5,101))[0] for e in [2.,3.,5.]])
 return row,d,power,radii,gnf,hist

def velocity(xyz,other,R,dt):
 u=xyz/np.linalg.norm(xyz,axis=1)[:,None];v=other/np.linalg.norm(other,axis=1)[:,None]
 cosine=np.clip((u*v).sum(axis=1),-1,1);angle=np.arccos(cosine)
 direction=v-cosine[:,None]*u;direction/=np.maximum(np.linalg.norm(direction,axis=1)[:,None],1e-15)
 vel=direction*(R*angle/dt)[:,None];speed=np.linalg.norm(vel,axis=1)
 chain=u.reshape(-1,30,3);tangent=np.empty_like(chain);tangent[:,1:-1]=chain[:,2:]-chain[:,:-2];tangent[:,0]=chain[:,1]-chain[:,0];tangent[:,-1]=chain[:,-1]-chain[:,-2]
 tangent=tangent.reshape(-1,3);tangent-=(tangent*u).sum(axis=1)[:,None]*u;tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-15)
 projected=(vel*tangent).sum(axis=1)
 # Conditional density evaluated at beads (particle weighted), with the tagged bead removed.
 count=cKDTree(u).query_ball_point(u,2*np.sin(3/(2*R)),return_length=True)-1
 dens=count/((len(u)-1)*(1-np.cos(3/R))/2)
 bins=np.linspace(0,2.5,26);b=np.clip(np.digitize(dens,bins)-1,0,24)
 accum=np.array([np.bincount(b,minlength=25),np.bincount(b,weights=speed,minlength=25),np.bincount(b,weights=projected,minlength=25),np.bincount(b,weights=speed**2,minlength=25)])
 # Local polar/nematic coherence of finite-lag displacements, transported to bead tangent planes.
 ds,ids=cKDTree(u).query(u,k=min(24,len(u)));a=u[ids];base=u[:,None,:];vv=direction[ids]
 trans=vv-((vv*base).sum(axis=2)/(1+(a*base).sum(axis=2)))[:,:,None]*(a+base)
 weights=np.exp(-.5*(R*2*np.arcsin(np.clip(ds/2,0,1))/3)**2);w=weights.sum(axis=1)
 pol=np.linalg.norm((trans*weights[:,:,None]).sum(axis=1)/w[:,None],axis=1)
 t=tangent;cross=np.cross(u,t);ca=(trans*t[:,None,:]).sum(axis=2);si=(trans*cross[:,None,:]).sum(axis=2)
 nem=np.abs(((ca+1j*si)**2*weights).sum(axis=1)/w)
 row=dict(speed_mean=float(speed.mean()),signed_projection=float(projected.mean()),angle_median=float(np.median(angle)),angle_gt_05=float((angle>.5).mean()),angle_gt_1=float((angle>1).mean()),local_polar=float(pol.mean()),local_nematic=float(nem.mean()),speed_density_corr=float(np.corrcoef(dens,speed)[0,1]))
 return accum,row

def run(folder,n,F):
 target=folder/'defect_out'
 if not target.is_dir():target=linkmap.get(str(folder),target)
 if not target.is_dir():return dict(n=n,F=F,path=str(folder),status='missing coordinate directory')
 files=[]
 for ent in os.scandir(str(target)):
  ma=re.match(r'defect_out-(\d+)\.xyz$',ent.name)
  if ma:files.append((int(ma[1]),Path(ent.path)))
 files.sort();steps=np.array([x[0] for x in files],dtype=np.int64)
 if len(files)<10:return dict(n=n,F=F,path=str(folder),status='fewer than 10 coordinate frames',frames=len(files))
 name=f'n{n}_F{F:g}';dest=OUT/'runs'/name;dest.mkdir(parents=True,exist_ok=True)
 if (dest/'done.json').exists():return json.loads((dest/'done.json').read_text())
 bd=(folder/'bd.in').read_text(errors='replace');match=re.search(r'^timestep\s+([\d.eE+-]+)',bd,re.M);dt=float(match[1]) if match else np.nan
 xyz=load(files[0][1]);R=np.linalg.norm(xyz,axis=1).mean()
 if len(xyz)!=30*n:raise ValueError('wrong actual bead count '+str(folder))
 targetsteps=np.r_[np.linspace(steps[0],steps[-1],41 if F in [0,.1,1,5,10] else 25),np.geomspace(max(steps[1],1),steps[-1],12)]
 if F<=10 and steps[0]<=25000000 and steps[-1]>=100000000:targetsteps=np.r_[targetsteps,np.linspace(25000000,100000000,25)]
 take=np.unique(np.clip(np.searchsorted(steps,targetsteps),0,len(steps)-1));records=[];densities=[];powers=[];gnfs=[];hists=[]
 for ind in take:
  xyz=load(files[ind][1]);row,d,p,radii,gnf,hist=metrics(xyz,R);row.update(step=int(steps[ind]),time=float(steps[ind]*dt),n=n,F=F,R=R);records.append(row);densities.append(d);powers.append(p);gnfs.append(gnf);hists.append(hist)
 with (dest/'frames.csv').open('w',newline='') as fp:
  w=csv.DictWriter(fp,list(records[0]));w.writeheader();w.writerows(records)
 np.savez_compressed(dest/'fields.npz',grid=GRID,step=steps[take],density=np.asarray(densities,dtype=np.float32),power=np.asarray(powers),gnf=np.asarray(gnfs),gnf_radii=radii,hist=np.asarray(hists),hist_edges=np.linspace(0,2.5,101))
 # Velocity diagnostics at identical available sampling lags; all frames remain ordered by particle id in source.
 vt=np.unique(np.clip(np.searchsorted(steps,np.linspace(max(steps[0],steps[-1]*.5),steps[-1]*.98,12)),0,len(steps)-6))
 accum={1:np.zeros((4,25)),5:np.zeros((4,25))};vrows=[]
 for ind in vt:
  xyz=load(files[ind][1])
  for lag in [1,5]:
   other=load(files[ind+lag][1]);elapsed=(steps[ind+lag]-steps[ind])*dt
   ac,vr=velocity(xyz,other,R,elapsed);accum[lag]+=ac;vr.update(step=int(steps[ind]),lag_frames=lag,delta_step=int(steps[ind+lag]-steps[ind]),delta_time=elapsed,n=n,F=F);vrows.append(vr)
 with (dest/'velocity_frames.csv').open('w',newline='') as fp:
  w=csv.DictWriter(fp,list(vrows[0]));w.writeheader();w.writerows(vrows)
 np.savez_compressed(dest/'velocity.npz',bins=np.linspace(0,2.5,26),lag1=accum[1],lag5=accum[5])
 info=dict(n=n,F=F,path=str(folder),coordinate_directory=str(target),status='ok',coordinate_frames=len(files),analyzed_frames=len(take),first_step=int(steps[0]),last_step=int(steps[-1]),output_step_median=float(np.median(np.diff(steps))),dt=dt,R=R,beads=len(xyz),radial_max_relative=float(np.max(np.abs(np.linalg.norm(xyz,axis=1)/R-1))),velocity_pairs=len(vrows),out=str(dest))
 (dest/'done.json').write_text(json.dumps(info,indent=2),encoding='utf-8');return info

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--n',type=int,nargs='*',default=NS);parser.add_argument('--forces',type=float,nargs='*');args=parser.parse_args()
 inventory=[];start=time.time()
 for n in args.n:
  folders=[]
  for folder in (ROOT/f'nchain{n}').iterdir():
   ma=re.match(r'F_([0-9.]+)',folder.name)
   if folder.is_dir() and ma:
    F=float(ma[1])
    if args.forces is None or F in args.forces:folders.append((F,folder))
  for F,folder in sorted(folders):
   try:info=run(folder,n,F)
   except Exception as e:info=dict(n=n,F=F,path=str(folder),status='ERROR: '+repr(e))
   inventory.append(info);print(n,F,info['status'],'frames',info.get('analyzed_frames'), 'elapsed',round(time.time()-start),flush=True)
 (OUT/('inventory_'+'_'.join(map(str,args.n))+'.json')).write_text(json.dumps(inventory,indent=2),encoding='utf-8')
if __name__=='__main__':main()
