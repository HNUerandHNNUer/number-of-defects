from tests import *
RESULT.update(json.loads((P/'results.json').read_text()))
def frames(path):
 with path.open() as f:
  while f.readline():
   step=int(f.readline());f.readline();n=int(f.readline())
   for i in range(5):f.readline()
   yield step,np.array([[float(v) for v in f.readline().split()] for k in range(n)])[:,1:4]
rows=[]
for geometry in ['free','sphere']:
 for method in ['custom','official']:
  for dt in [.01,.005,.0025]:
   for seed in [13579,24681,35791]:
    name=f'chain_{geometry}_{method}_{dt}_{seed}';d=P/name;d.mkdir(exist_ok=True)
    s=(np.arange(30)-14.5)*.965
    x=np.column_stack([s,np.zeros(30),np.zeros(30)]) if geometry=='free' else np.column_stack([R*np.cos(s/R),R*np.sin(s/R),np.zeros(30)])
    data(d,x);steps=round(1000/dt);every=round(1/dt)
    if method=='custom':
     style='bd/audit/free' if geometry=='free' else 'bd/sphere'
     fixes=f'fix bd all {style} 1000 1 0 {seed} mchain 30\n'
    else:
     fixes=f'fix bd all brownian 1 {seed} gamma_t 1000 rng uniform\n'
     if geometry=='sphere':fixes+=f'fix ext all bd/audit/forces 1000 0 0 {seed} mchain 30\n'
    text=base()+f'timestep {dt}\n'+fixes+f'''dump d all custom {every} traj.dump id xu yu zu
dump_modify d sort id format float %.12g
run {steps}
'''
    sec=run_lmp(d,text);sample=[];maxbond=0;maxrad=0;badframes=0
    for step,x in frames(d/'traj.dump'):
     b=np.diff(x,axis=0);length=np.linalg.norm(b,axis=1);u=b/length[:,None];cos=np.sum(u[:-1]*u[1:],axis=1)
     maxbond=max(maxbond,float(length.max()));badframes+=int(np.any(length>=1.5))
     if geometry=='sphere':maxrad=max(maxrad,float(np.max(abs(np.linalg.norm(x,axis=1)-R))))
     if step>=steps//2:sample.append([length.mean(),cos.mean(),np.mean(np.sum((x-x.mean(axis=0))**2,axis=1)),np.mean((np.linalg.norm(x,axis=1)-R)**2) if geometry=='sphere' else 0])
    ar=np.array(sample);log=(d/'console.log').read_text();row=dict(geometry=geometry,method=method,dt=dt,seed=seed,physical_time=1000,mean_bond=float(ar[:,0].mean()),mean_cos=float(ar[:,1].mean()),mean_Rg2=float(ar[:,2].mean()),radial_rms=float(np.sqrt(ar[:,3].mean())),max_saved_bond=maxbond,max_saved_radial_error=maxrad,bad_saved_frames=badframes,FENE_warnings=log.count('WARNING: FENE bond too long'),seconds=sec)
    rows.append(row);RESULT['passive_chains']=rows;save();print(row,flush=True)
