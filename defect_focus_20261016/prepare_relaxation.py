from pathlib import Path
import ast,json,shutil,hashlib,zipfile,re
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;PACK=HERE/'sphere_relaxation_20261016';PACK.mkdir(exist_ok=True)
source=(ROOT/'cpu5_validation_20261015/prepare.py').read_text();tree=ast.parse(source)
for name in ('sha','prepare_data'):
 node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);exec(compile(ast.Module(body=[node]),'<prepare>','exec'))
HEADER=(ROOT/'cpu5_validation_20261015/sphere_validation_20261015/branch_n10_F2_co_r1/in.production').read_text().split('# The custom')[0]
jobs=[]
for rep in (1,2,3):
 for n in (200,350):
  folder=ROOT/('nchain%d/F_0_cpu%d'%(n,2 if n==200 else 5))
  for F in (0,.03,.1,.3):
   name='relax_n%d_F%g_r%d'%(n,F,rep);p=PACK/name;p.mkdir(exist_ok=True)
   record=prepare_data(folder/'polymer.data',p/'polymer.data',folder/'defect_out/defect_out-1000000000.xyz');seed=9210001+len(jobs)*10007
   record.update(name=name,nchain=n,F=F,replicate=rep,seed=seed,dt=.01,production_steps=1000000000,physical_duration=10000000,mpi_ranks=2,dump_every=100000,preparation='same aged F0 geometry per radius; new independent noise, zero velocity; coordinate reseeding, not exact restart',source_age_steps=1000000000)
   body=HEADER+'fix bd all bd/sphere 1000.0 1.0 %g %d mchain 30\n'%(F,seed)
   body+='dump traj all custom 100000 trajectory.lammpstrj id mol type x y z\ndump_modify traj sort id format float %.10g\nrestart 10000000 restart_A.bin restart_B.bin\n'
   for stage in range(1,11):body+='run 100000000\nwrite_data milestone_%02d.data\nprint "MILESTONE_%02d_COMPLETED"\n'%(stage,stage)
   body+='write_restart final.bin\nwrite_data final.data\nprint "VALIDATION_RUN_COMPLETED"\n';(p/'in.production').write_text(body)
   (p/'in.smoke').write_text(HEADER+'fix bd all bd/sphere 1000.0 1.0 %g %d mchain 30\ndump ck all custom 1000 smoke.lammpstrj id mol type x y z\ndump_modify ck sort id\nrun 20000\nprint "SMOKE_OK"\n'%(F,seed))
   (p/'provenance.json').write_text(json.dumps(record,indent=2));jobs.append(record)
(PACK/'manifest.json').write_text(json.dumps(jobs,indent=2))
runner=(ROOT/'cpu5_validation_20261015/runner.py').read_text()
runner=runner.replace("while len(active)<16 and pending:","count=subprocess.run(['pgrep','-c','-x','lmp'],stdout=subprocess.PIPE,text=True)\n        free_slots=max(0,(32-int(count.stdout.strip() or '0'))//2)\n        while len(active)<16 and pending and free_slots>0:\n            free_slots-=1")
runner=runner.replace("max 16 simultaneous jobs, 2 MPI ranks/job", "max 32 total lmp ranks across existing and new campaigns, 2 MPI ranks/job")
(PACK/'runner.py').write_text(runner)
with zipfile.ZipFile(str(HERE/'sphere_relaxation_20261016.zip'),'w',zipfile.ZIP_DEFLATED) as z:
 for p in PACK.rglob('*'):
  if p.is_file():z.write(str(p),str(p.relative_to(HERE)))
print('PREPARED',len(jobs));print([(j['name'],j['bond_max']) for j in jobs[:8]])
