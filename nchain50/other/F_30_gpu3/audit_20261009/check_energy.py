from pathlib import Path
import numpy as np,re,csv
from scipy.spatial import cKDTree
p=Path(__file__).resolve().parent.parent
log={}
for line in (p/'log.lammps').read_text().splitlines():
    a=line.split()
    if len(a)==6 and a[0].isdigit():
        try: log[int(a[0])]=float(a[3])
        except ValueError: pass
files=sorted((p/'defect_out').glob('*.xyz')); rows=[]
for z in range(len(files)):
    f=files[z];t=int(re.search(r'(\d+)\.xyz',f.name).group(1))
    x=np.loadtxt(str(f),skiprows=2)[:1500,1:4];ch=x.reshape(50,30,3);vec=np.diff(ch,axis=1);rs=(vec**2).sum(axis=2)
    bond=(-.5*30*1.5**2*np.log(np.maximum(1-rs/1.5**2,.1))).sum()
    def lj(rs):
        rs=rs[rs<2**(1/3)];sr6=rs**-3;return (4*(sr6**2-sr6)+1).sum()
    bond+=lj(rs)
    ang=(30*(1-(vec[:,:-1]*vec[:,1:]).sum(axis=2)/np.sqrt(rs[:,:-1]*rs[:,1:]))).sum()
    pairs=np.array(list(cKDTree(x).query_pairs(2**(1/6))))
    i,j=pairs.T;keep=~((j==i+1)&(i//30==j//30));i=i[keep];j=j[keep]
    pair=lj(((x[i]-x[j])**2).sum(axis=1));pe=(bond+ang+pair)/1500
    rows.append([t,pe,log.get(t,float('nan')),pe-log.get(t,float('nan'))])
with (p/'audit_20261009/energy_crosscheck.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['step','reconstructed_pe','log_pe','difference']);w.writerows(rows)
a=np.array(rows);print('samples',len(a),'mismatch > .001',sum(abs(a[:,3])>.001),'max diff',max(abs(a[:,3])));print(a[:8]);print(a[-4:])

