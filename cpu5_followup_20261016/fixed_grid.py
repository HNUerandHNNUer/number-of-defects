import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,importlib.util,json
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull,cKDTree
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=HERE/'fixed_grid_results';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('nematic',ROOT/'nchain200/sphere_nematic_parallel.py');m=importlib.util.module_from_spec(spec);sys.modules['nematic']=m;spec.loader.exec_module(m)
def unit(a):return a/np.maximum(np.linalg.norm(a,axis=-1,keepdims=True),1e-15)
def mesh(level):
 t=(1+np.sqrt(5))/2;v=[]
 for a in (-1,1):
  for b in (-t,t):v.extend([[0,a,b],[a,b,0],[b,0,a]])
 v=unit(np.array(v));f=ConvexHull(v).simplices
 for _ in range(level):
  vv=v.tolist();cache={};ff=[]
  def mid(a,b):
   key=tuple(sorted((a,b)))
   if key not in cache:cache[key]=len(vv);vv.append(unit(v[a]+v[b]).tolist())
   return cache[key]
  for a,b,c in f:
   ab=mid(a,b);bc=mid(b,c);ca=mid(c,a);ff.extend([[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]])
  v=np.array(vv);f=np.array(ff)
 return v,m.build_mesh(v,m.Settings())
def field(x,v,h):
 R=np.linalg.norm(x,axis=1).mean();u=unit(x);d=m.chain_directors(u,30,m.Settings());tree=cKDTree(u)
 ref=np.tile([0.,0.,1.],(len(v),1));ref[np.abs(v[:,2])>.9]=[1.,0.,0.];e=unit(np.cross(v,ref));e2=np.cross(v,e);q=np.empty(len(v),complex)
 for lo in range(0,len(v),256):
  sl=slice(lo,min(lo+256,len(v)));b=v[sl,None,:];ds,ids=tree.query(v[sl],k=min(128,len(u)));a=u[ids];dd=d[ids];trans=dd-((dd*b).sum(2)/(1+(a*b).sum(2)))[:,:,None]*(a+b);z=(trans*e[sl,None,:]).sum(2)+1j*(trans*e2[sl,None,:]).sum(2);w=np.exp(-.5*(2*R*np.arcsin(np.clip(ds/2,0,1))/h)**2);q[sl]=(w*z*z).sum(1)/w.sum(1)
 angle=np.angle(q)/2;direct=np.cos(angle)[:,None]*e+np.sin(angle)[:,None]*e2
 return R,direct,np.abs(q)
def detect(x,v,geo,h):
 R,d,S=field(x,v,h);faces,edges,inv,sgn,area,angles=geo;i,j=edges.T;tr=m.parallel_transport(d[i],v[i],v[j]);co=(tr*d[j]).sum(1);si=(v[j]*np.cross(tr,d[j])).sum(1);delta=.5*np.arctan2(2*si*co,co*co-si*si);qraw=((sgn*delta[inv]).sum(1)+area)/(2*np.pi);q=np.rint(2*qraw).astype(int)
 assert q.sum()==4 and np.max(np.abs(qraw-q/2))<1e-8
 pos=[];charges=[];fallback=0
 for fi in np.where(q!=0)[0]:
  ids=faces[fi];base=unit(v[ids].sum(0));ref=np.array([0.,0.,1.]) if abs(base[2])<.9 else np.array([1.,0.,0.]);e=unit(np.cross(base,ref));e2=np.cross(base,e);tr=m.parallel_transport(d[ids],v[ids],np.tile(base,(3,1)));z=S[ids]*((tr*e).sum(1)+1j*(tr*e2).sum(1))**2;A=np.array([z.real,z.imag,np.ones(3)])
  try:w=np.linalg.solve(A,[0,0,1])
  except np.linalg.LinAlgError:w=np.array([-1.,0,2])
  if np.min(w)<-1e-6 or np.max(w)>1+1e-6:point=base;fallback+=1
  else:point=unit((w[:,None]*v[ids]).sum(0))
  pos.append(point.tolist());charges.append(int(q[fi]))
 return dict(positions=pos,charges=charges,fallback=fallback,Nplus=int((q==1).sum()),Nminus=int((q==-1).sum()),composite=int((np.abs(q)>1).sum()),radius=float(R))
def main():
 old=ROOT/'cpu5_validation_20261015/final_analysis_cpu5';rows=[]
 for name in ['branch_n10_F2_co_r1','branch_n10_F2_counter_r1','size_n100_F5_r1']:
  dat=np.load(str(old/(name+'__late.npz')))
  for level in (3,4,5):
   v,g=mesh(level)
   for h in (1.5,3.):
    seq=[]
    for k in range(0,len(dat['steps']),100):
     r=detect(dat['xyz'][k],v,g,h);r.update(step=int(dat['steps'][k]),case=name,level=level,h=h);seq.append(r);rows.append({a:b for a,b in r.items() if a not in ('positions','charges')})
    (OUT/('%s_L%d_h%g_pilot.json'%(name,level,h))).write_text(json.dumps(seq))
    print(name,level,h,np.mean([r['Nplus'] for r in seq]),flush=True)
 pd.DataFrame(rows).to_csv(OUT/'spatial_pilot.csv',index=False)
if __name__=='__main__':main()
