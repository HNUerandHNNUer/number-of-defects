from tests import *
RESULT.update(json.loads((P/'results.json').read_text()))
x=np.loadtxt(W/'F_25_bd_cpu2/serial/initial.xyz',skiprows=2)[:,1:4]
rows=[]
for method in ['custom','official']:
 for dt in [.01,.005,.0025]:
  d=P/f'stress_{method}_{dt}';d.mkdir(exist_ok=True);data(d,x)
  steps=round(1000/dt)
  fixes='fix bd all bd/sphere 1000 1 25 123456 mchain 30\n' if method=='custom' else 'fix bd all brownian 1 123456 gamma_t 1000 rng uniform\nfix ext all bd/audit/forces 1000 0 25 123456 mchain 30\n'
  text=base()+f'timestep {dt}\n'+fixes+f'''compute b all bond/local dist
compute bm all reduce max c_b inputs local
variable bondmax equal c_bm
fix guard all halt 1 v_bondmax > 1.42 error soft
thermo 1000
thermo_style custom step pe c_bm
run {steps}
write_dump all custom last.dump id x y z modify sort id format float %.16g
'''
  sec=run_lmp(d,text);log=(d/'console.log').read_text();lines=log.splitlines();thermo=[]
  for line in lines:
   v=line.split()
   if len(v)==3:
    try:thermo.append([float(q) for q in v])
    except ValueError:pass
  final=dump_read(d/'last.dump')[:,1:4];b=np.diff(final.reshape(100,30,3),axis=1);b-=BOX*np.rint(b/BOX)
  laststep=int((d/'last.dump').read_text().splitlines()[1])
  row=dict(method=method,dt=dt,seed=123456,target_time=1000,actual_step=laststep,actual_time=dt*laststep,last_maxbond=float(np.linalg.norm(b,axis=2).max()),halted='Fix halt condition' in log,FENE_warnings=log.count('WARNING: FENE bond too long'),seconds=sec)
  rows.append(row);RESULT['dense_F25_stress']=rows;save();print(row,flush=True)
