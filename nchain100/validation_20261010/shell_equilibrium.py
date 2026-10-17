from tests import *
from scipy.integrate import quad
def pot(y):
 d=RC-abs(y)
 return 400*(d**-12-d**-6)+100
norm=quad(lambda y:(R+y)**2*np.exp(-pot(y)),-.2,.2,epsabs=1e-12)[0]
exact=quad(lambda y:y*y*(R+y)**2*np.exp(-pot(y)),-.2,.2,epsabs=1e-12)[0]/norm
rows=[]
for method in ['custom','official']:
 for dt in [.01,.005,.0025]:
  d=P/f'shell_equilibrium_{method}_{dt}';d.mkdir(exist_ok=True);n=6000
  # independent noninteracting particles, deterministic Fibonacci-sphere initial locations
  z=1-2*(np.arange(n)+.5)/n;ang=np.arange(n)*np.pi*(3-np.sqrt(5));x=R*np.column_stack([np.sqrt(1-z*z)*np.cos(ang),np.sqrt(1-z*z)*np.sin(ang),z]);data(d,x)
  fixes='fix bd all bd/sphere 1000 1 0 123456 mchain 30\n' if method=='custom' else 'fix bd all brownian 1 123456 gamma_t 1000 rng uniform\nfix ext all bd/audit/forces 1000 0 0 123456 mchain 30\n'
  text=base().replace('pair_style lj/cut 1.122462048309373','pair_style zero 2').replace('pair_coeff 1 1 1 1','pair_coeff * *').replace('pair_modify shift yes','').replace('bond_style fene','bond_style zero').replace('bond_coeff 1 30 1.5 1 1','bond_coeff *').replace('angle_style cosine','angle_style zero').replace('angle_coeff 1 30','angle_coeff *')
  text+=f'timestep {dt}\n'+fixes+f'run {round(20/dt)}\nwrite_dump all custom last.dump id x y z modify sort id format float %.16g\n'
  sec=run_lmp(d,text);x=dump_read(d/'last.dump')[:,1:];y=np.linalg.norm(x,axis=1)-R;y2=y*y;mean=y2.mean();se=y2.std(ddof=1)/np.sqrt(n)
  row=dict(method=method,dt=dt,n=n,time=20,radial_variance=float(mean),SE=float(se),exact_radial_variance=exact,z=float((mean-exact)/se),radial_rms=float(np.sqrt(mean)),seconds=sec)
  rows.append(row);(P/'shell_equilibrium_results.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
