#ifdef FIX_CLASS
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
