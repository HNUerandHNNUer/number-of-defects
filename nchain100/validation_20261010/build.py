from pathlib import Path
import os,shutil,subprocess,json,hashlib
P=Path(__file__).resolve().parent
tool=P.parent/'parallel_source/validation/toolchain/w64devkit/bin'
env=os.environ.copy();env['PATH']=str(tool)+os.pathsep+env['PATH']
src=P/'lammps-stable_22Jul2025_update1';build=P/'build'
snap=P/'source_snapshot';snap.mkdir(exist_ok=True)
hashes={}
for f in (P.parent/'F_25_gpu4/fix_source').glob('*'):
 if f.is_file():
  shutil.copy2(f,snap/f.name);hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
  if 'kokkos' not in f.name:shutil.copy2(f,src/'src'/f.name)
(P/'source_hashes.json').write_text(json.dumps(hashes,indent=2))
# A derived diagnostic style changes only wall strength to zero. Original methods are inherited.
(src/'src/fix_bd_audit_free.h').write_text('''#ifdef FIX_CLASS
FixStyle(bd/audit/free,FixBDAuditFree)
#else
#ifndef LMP_FIX_BD_AUDIT_FREE_H
#define LMP_FIX_BD_AUDIT_FREE_H
#include "fix_bd_sphere.h"
namespace LAMMPS_NS {
class FixBDAuditFree : public FixBDSphere {
 public:
 FixBDAuditFree(LAMMPS *lmp,int narg,char **arg) : FixBDSphere(lmp,narg,arg) {wall_epsilon=0;}
};
}
#endif
#endif
''')
cmd=[str(tool/'cmake.exe'),'-S',str(src/'cmake'),'-B',str(build),'-G','MinGW Makefiles','-D','CMAKE_BUILD_TYPE=Release','-D','BUILD_MPI=OFF','-D','BUILD_OMP=OFF','-D','PKG_MOLECULE=ON','-D','PKG_BROWNIAN=ON','-D','BUILD_SHARED_LIBS=OFF','-D','WITH_JPEG=OFF','-D','WITH_PNG=OFF','-D','WITH_FFMPEG=OFF','-D','CMAKE_CXX_COMPILER='+str(tool/'g++.exe'),'-D','CMAKE_C_COMPILER='+str(tool/'gcc.exe')]
(src/'src/fix_bd_audit_forces.h').write_text('''#ifdef FIX_CLASS
FixStyle(bd/audit/forces,FixBDAuditForces)
#else
#ifndef LMP_FIX_BD_AUDIT_FORCES_H
#define LMP_FIX_BD_AUDIT_FORCES_H
#include "fix_bd_sphere.h"
namespace LAMMPS_NS {
class FixBDAuditForces : public FixBDSphere {
 public:
 FixBDAuditForces(LAMMPS *lmp,int narg,char **arg) : FixBDSphere(lmp,narg,arg) {temperature=0;}
 int setmask() override {return FixConst::POST_FORCE;}
 void setup(int vflag) override {post_force(vflag);}
};
}
#endif
#endif
''')
for name,cmd in [('configure',cmd),('compile',[str(tool/'cmake.exe'),'--build',str(build),'--parallel','4'])]:
 with (P/(name+'.log')).open('w') as log:
  r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 print(name,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
