from fixed_grid import *
sys.path.insert(0,str(ROOT/'defect_dynamics_20261015'))
from analyze import GRID
new=HERE/'completed_analysis_20261016';old=ROOT/'cpu5_validation_20261015/final_analysis_cpu5';v,g=mesh(4);rows=[]
jobs=[(new,j) for j in json.loads((new/'audit.json').read_text())]+[(old,dict(name='size_n100_F5_r%d'%r,nchain=100,dt=.01,replicate=r)) for r in (1,2,3)]
for folder,j in jobs:
 cache=new/(j['name']+'_fixed.csv')
 if cache.exists():rows.extend(pd.read_csv(cache).to_dict('records'));continue
 data=np.load(str(folder/(j['name']+'.npz')));sr=[]
 for k,step in enumerate(data['steps']):
  if step<50000000 or step%5000000:continue
  x=data['xyz'][k];u=unit(x);R=np.linalg.norm(x,axis=1).mean();counts=cKDTree(u).query_ball_point(GRID,2*np.sin(3/(2*R)),return_length=True);cv=counts.std()/counts.mean()
  for h in (1.5,3.):
   d=detect(x,v,g,h);sr.append(dict(name=j['name'],nchain=j['nchain'],dt=j['dt'],replicate=j['replicate'],geometry=j.get('geometry','size'),pattern=j.get('pattern','size'),step=int(step),h=h,Nplus=d['Nplus'],Nminus=d['Nminus'],four=int(d['Nplus']==4 and d['Nminus']==0),pair_density=d['Nminus']/(4*np.pi*R**2),cv3=cv,fallback=d['fallback']))
 pd.DataFrame(sr).to_csv(cache,index=False);rows.extend(sr);print('FIXED',j['name'],flush=True)
pd.DataFrame(rows).to_csv(new/'fixed_comparison.csv',index=False)
