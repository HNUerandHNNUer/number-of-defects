from pathlib import Path
import json, re, hashlib, shutil, zipfile
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PACK = HERE / 'sphere_validation_20261015'
PACK.mkdir(exist_ok=True)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def prepare_data(source, target, late=None):
    text = source.read_text()
    n = int(re.search(r'(\d+) atoms', text).group(1))
    lines = text.splitlines()
    start = next(i for i,s in enumerate(lines) if s.strip().split('#')[0].strip() == 'Atoms')
    indices=[]
    for i in range(start+1,len(lines)):
        s=lines[i].strip()
        if not s: continue
        if not s[0].isdigit(): break
        indices.append(i)
    assert len(indices)==n
    rows=[lines[i].split() for i in indices]
    assert sorted(int(r[0]) for r in rows)==list(range(1,n+1))
    assert all(int(r[1])==(int(r[0])-1)//30+1 and int(r[2])==1 for r in rows)
    if late:
        a=np.loadtxt(str(late),skiprows=2)
        a=a[a[:,0]==1,1:4]
        assert a.shape==(n,3)
        for i,r in zip(indices,rows):
            r=r[:3]+['%.12g'%v for v in a[int(r[0])-1]]
            lines[i]=' '.join(r)
    xyz=np.array([[float(v) for v in r[3:6]] for r in rows]) if not late else a
    bonds=np.linalg.norm(np.diff(xyz.reshape(-1,30,3),axis=1),axis=2)
    assert bonds.max()<1.5 and bonds.min()>0.5
    # Original data have no velocities; initialize zero drift and new Brownian noise.
    assert not any(s.strip()=='Velocities' for s in lines)
    target.write_text('\n'.join(lines)+'\n')
    return dict(source=str(source.relative_to(ROOT)),source_sha256=sha(source),
                late_source=str(late.relative_to(ROOT)) if late else None,
                late_sha256=sha(late) if late else None,atoms=n,chains=n//30,
                radius_mean=float(np.linalg.norm(xyz,axis=1).mean()),
                bond_min=float(bonds.min()),bond_max=float(bonds.max()),
                staged_sha256=sha(target))

HEADER='''units lj
dimension 3
boundary p p p
atom_style molecular
atom_modify map array
neighbor 0.5 bin
neigh_modify every 1 delay 0 check yes
special_bonds fene
read_data polymer.data
comm_modify cutoff 3.0
pair_style lj/cut 1.122462048309373
pair_coeff 1 1 1.0 1.0 1.122462048309373
pair_modify shift yes
bond_style fene
bond_coeff 1 30.0 1.5 1.0 1.0
angle_style cosine
angle_coeff 1 30.0
timestep 0.01
thermo 10000
thermo_style custom step atoms temp pe ebond eangle etotal
thermo_modify flush yes lost error
'''

jobs=[]
def job(name,n,F,rep,source,late=None,dense=False):
    p=PACK/name;p.mkdir(exist_ok=True)
    record=prepare_data(source,p/'polymer.data',late)
    seed=7301001+len(jobs)*10007
    warmseed=4101001+len(jobs)*10009
    record.update(name=name,nchain=n,F=F,replicate=rep,seed=seed,warmseed=warmseed,
                  production_steps=100000000,warmup_steps=0 if late else 10000000,
                  dump_every=1000 if dense else 10000,dense=dense,mpi_ranks=2)
    warm='' if late else '''fix bd all bd/sphere 1000.0 1.0 0.1 %d mchain 30
restart 5000000 warm_A.bin warm_B.bin
run 10000000
write_data equilibrated.data
unfix bd
restart 0
reset_timestep 0
'''%warmseed
    body=HEADER+warm+'''# The custom bd/sphere fix is the ONLY integrator and noise source.
fix bd all bd/sphere 1000.0 1.0 %g %d mchain 30
dump traj all custom %d trajectory.lammpstrj id mol type x y z
dump_modify traj sort id format float %%.10g
restart 5000000 restart_A.bin restart_B.bin
'''%(F,seed,record['dump_every'])
    if dense:
        # Three 1e5-step windows; same fix persists across run commands.
        for label,steps in [('early',100000),('middle',100000),('late',100000)]:
            if label=='middle': body+='run 49900000\n'
            if label=='late': body+='run 49800000\n'
            body+='dump fine all custom 100 fine_%s.lammpstrj id mol type x y z\n'%label
            body+='dump_modify fine sort id format float %%.10g\nrun %d\nundump fine\n'%steps
    else: body+='run 100000000\n'
    body+='write_restart final.bin\nwrite_data final.data\nprint "VALIDATION_RUN_COMPLETED"\n'
    (p/'in.production').write_text(body)
    smoke=HEADER+'fix bd all bd/sphere 1000.0 1.0 %g %d mchain 30\n'%(F,seed)
    smoke+='dump check all custom 1000 smoke.lammpstrj id mol type x y z\ndump_modify check sort id format float %.10g\nrun 10000\nwrite_restart smoke.bin\nprint "SMOKE_OK"\n'
    (p/'in.smoke').write_text(smoke)
    (p/'provenance.json').write_text(json.dumps(record,indent=2))
    jobs.append(record)

for rep in range(1,4):
    for label,folder in [('counter','nchain10/F_2_cpu2'),('co','nchain10/gpu2/F_2')]:
        source=ROOT/folder
        job('branch_n10_F2_%s_r%d'%(label,rep),10,2,rep,source/'polymer.data',
            source/'defect_out/defect_out-0100000000.xyz',dense=(rep==1))
sources={30:ROOT/'nchain30/F_2_cpu1/polymer.data',50:ROOT/'nchain50/F_2_gpu3/polymer.data',100:ROOT/'nchain100/polymer.data'}
for rep in range(1,4):
    for n in (30,50,100):
        for F in (2,5):
            job('size_n%d_F%d_r%d'%(n,F,rep),n,F,rep,sources[n],dense=(n==100 and F==5 and rep==1))

(PACK/'manifest.json').write_text(json.dumps(jobs,indent=2))
for fn in ['runner.py','preflight.py','README.md']:
    if (HERE/fn).exists(): shutil.copy2(str(HERE/fn),str(PACK/fn))
with zipfile.ZipFile(str(HERE/'sphere_validation_20261015.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in PACK.rglob('*'):
        if p.is_file(): z.write(str(p),str(p.relative_to(HERE)))
print('Prepared %d jobs; package %s'%(len(jobs),HERE/'sphere_validation_20261015.zip'))
print(json.dumps([{k:r[k] for k in ['name','atoms','bond_min','bond_max','radius_mean']} for r in jobs[:2]],indent=2))
