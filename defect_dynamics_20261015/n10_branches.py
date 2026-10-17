from analyze import *
from scipy.spatial.transform import Rotation
rows=[];validation=[]
for F in [2,4,6,7,8,9]:
 z=np.load(str(ROOT/f'nchain10/video/activity_analysis_20261013/F_{F}/trajectory_fields.npz'));err=[]
 for frame in [0,500,750,1000]:
  a=load(ROOT/f'nchain10/gpu2/F_{F}/defect_out/defect_out-{frame*100000:010d}.xyz');err.append(float(np.max(np.abs(a[a[:,0]==1,1:]-z['coords'][frame]))))
 validation.append(dict(F=F,source=f'nchain10/gpu2/F_{F}/defect_out',max_coordinate_difference=max(err),checked_frames=[0,500,750,1000]))
 info=json.loads((MIPS/f'runs/n10_F{F}/done.json').read_text());folder=Path(info['coordinate_directory']);prev=None;out=[]
 for frame in range(1001):
  a=load(folder/f'defect_out-{frame*100000:010d}.xyz');xyz=a[a[:,0]==1,1:];u=unit(xyz);d=dirs(u);R=np.linalg.norm(xyz,axis=1).mean();tree=cKDTree(u);p,s=local(u,d,GRID,R,tree);circ=np.cross(u,d).mean(0);axis=unit(circ);chaincirc=np.cross(u,d).reshape(10,30,3).mean(1).dot(axis)
  row=dict(F=F,frame=frame,step=frame*100000,Nplus=int((a[:,0]==2).sum()),Nminus=int((a[:,0]==3).sum()),P=p.mean(),S=s.mean(),circulation=np.linalg.norm(circ),opposite_chains=int((chaincirc<0).sum()))
  if prev is not None:
   U,sv,V=np.linalg.svd(prev.T.dot(xyz));D=np.diag([1,1,np.linalg.det(U.dot(V))]);rot=U.dot(D).dot(V);res=((xyz-prev.dot(rot))**2).sum();total=((xyz-prev)**2).sum();row['rigid_fraction']=1-res/max(total,1e-30)
  out.append(row);prev=xyz
 pd.DataFrame(out).to_csv(OUT/f'n10_current_F{F}_full.csv',index=False);late=pd.DataFrame(out).query('frame>=500');r=late.mean().to_dict();r.update(F=F,source=info['coordinate_directory'],four_fraction=float(np.mean((late.Nplus==4)&(late.Nminus==0))));rows.append(r);print('branch',F,r,flush=True)
pd.DataFrame(rows).to_csv(OUT/'n10_current_branch_summary.csv',index=False)
(OUT/'prior_cache_validation_correct_source.json').write_text(json.dumps(validation,indent=2))
