from analyze import *
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows=[];frames=[]
for branch,folder in [('direct',ROOT/'nchain10/F_2_cpu2'),('gpu2',ROOT/'nchain10/gpu2/F_2')]:
 prev=load(folder/'defect_out/defect_out-0049900000.xyz');prev=prev[prev[:,0]==1,1:]
 for frame in range(500,1001):
  a=load(folder/f'defect_out/defect_out-{frame*100000:010d}.xyz');xyz=a[a[:,0]==1,1:];u=unit(xyz);d=dirs(u);R=np.linalg.norm(xyz,axis=1).mean();P,S=local(u,d,GRID,R,cKDTree(u));axis=unit(np.cross(u,d).mean(0));cs=np.cross(u,d).reshape(10,30,3).mean(1).dot(axis);velsign=[];ang=[];fit=[]
  for x,y in zip(prev.reshape(10,30,3),xyz.reshape(10,30,3)):
   U,sv,V=np.linalg.svd(x.T.dot(y));rot=U.dot(np.diag([1,1,np.linalg.det(U.dot(V))])).dot(V);rv=Rotation.from_matrix(rot.T).as_rotvec();velsign.append(rv.dot(axis));ang.append(np.linalg.norm(rv));fit.append(1-np.sum((y-x.dot(rot))**2)/max(np.sum((y-x)**2),1e-15))
  U,sv,V=np.linalg.svd(prev.T.dot(xyz));rot=U.dot(np.diag([1,1,np.linalg.det(U.dot(V))])).dot(V);rigid=1-np.sum((xyz-prev.dot(rot))**2)/np.sum((xyz-prev)**2)
  frames.append(dict(branch=branch,frame=frame,P=P.mean(),S=S.mean(),Nplus=int((a[:,0]==2).sum()),Nminus=int((a[:,0]==3).sum()),opposite_director=int((cs<0).sum()),opposite_displacement=int((np.array(velsign)<0).sum()),sign_agreement=np.mean(np.sign(cs)==np.sign(velsign)),max_chain_angle_deg=max(ang)*180/np.pi,mean_chain_rotation_fit=np.mean(fit),global_rotation_fit=rigid))
  prev=xyz
 df=pd.DataFrame(frames);r=df[df.branch==branch].mean(numeric_only=True).to_dict();r.update(branch=branch,source=str(folder));rows.append(r)
pd.DataFrame(frames).to_csv(OUT/'F2_branch_check_frames.csv',index=False);pd.DataFrame(rows).to_csv(OUT/'F2_branch_check_summary.csv',index=False);print(rows,flush=True)
fig,axs=plt.subplots(1,3,figsize=(14,4.2));d=pd.DataFrame(rows);x=np.arange(2)
axs[0].bar(x-.18,d.P,width=.36,label='polar P');axs[0].bar(x+.18,d.S,width=.36,label='nematic S');axs[0].legend();axs[0].set_ylabel('Local order, same estimator')
axs[1].bar(x,100*d.global_rotation_fit);axs[1].set_ylabel('Global rotation explained displacement (%)')
axs[2].bar(x-.18,d.opposite_director,width=.36,label='chain direction');axs[2].bar(x+.18,d.opposite_displacement,width=.36,label='actual displacement');axs[2].legend(fontsize=8);axs[2].set_ylabel('Opposite chains out of 10')
for ax in axs:ax.set_xticks(x);ax.set_xticklabels(['direct F_2_cpu2','gpu2/F_2'])
fig.suptitle('Same nominal n=10 and F=2, distinct trajectories: preparation/backend not controlled');fig.tight_layout(rect=(0,0,1,.93));fig.savefig(OUT/'09_same_force_branches.png',dpi=160);plt.close(fig)
