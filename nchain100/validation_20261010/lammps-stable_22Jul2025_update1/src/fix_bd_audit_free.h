#ifdef FIX_CLASS
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
