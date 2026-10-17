from fixed_grid import *
old=ROOT/'cpu5_validation_20261015/final_analysis_cpu5';x=np.load(str(old/'size_n100_F5_r1__late.npz'))['xyz'][0];v,g=mesh(4)
a=detect(x,v,g,1.5);b=detect(x.reshape(-1,30,3)[:,::-1].reshape(-1,3),v,g,1.5)
assert a['charges']==b['charges'] and np.allclose(a['positions'],b['positions'])
angle=.413;rot=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1.]])
c=detect(x.dot(rot.T),v.dot(rot.T),g,1.5)
assert a['charges']==c['charges'] and np.allclose(np.array(a['positions']).dot(rot.T),c['positions'])
assert a==detect(x,v,g,1.5)
checks=dict(nematic_head_tail_invariance=True,simultaneous_grid_sample_rotation_covariance=True,repeatability=True)
jobs=json.loads((HERE/'sphere_followup_20261016/manifest.json').read_text())
for j in jobs:
 p=HERE/'sphere_followup_20261016'/j['name']/'polymer.data';lines=p.read_text().splitlines();i=next(i for i,s in enumerate(lines) if s.split('#')[0].strip()=='Atoms');rows=[]
 for line in lines[i+1:]:
  s=line.strip()
  if not s:continue
  if not s[0].isdigit():break
  rows.append(s.split())
 rows.sort(key=lambda r:int(r[0]));xyz=np.array([[float(z) for z in r[3:6]] for r in rows]);bonds=np.linalg.norm(np.diff(xyz.reshape(-1,30,3),axis=1),axis=2)
 assert bonds.min()>.5 and bonds.max()<1.5
 if j['experiment']=='polarity_preparation':
  ori=ROOT/'cpu5_validation_20261015/sphere_validation_20261015'/('branch_n10_F2_'+j['geometry']+'_r1')/'polymer.data';ll=ori.read_text().splitlines();idx=next(i for i,s in enumerate(ll) if s.split('#')[0].strip()=='Atoms');rr=[s.split() for s in ll[idx+1:] if s.strip()][:300];xx=np.array([[float(z) for z in r[3:6]] for r in rr]);assert sorted(map(tuple,xyz))==sorted(map(tuple,xx))
checks['all_18_bond_geometry_checks']=True;checks['all_12_preparations_preserve_position_sets']=True
(OUT/'validation.json').write_text(json.dumps(checks,indent=2));print(checks)
