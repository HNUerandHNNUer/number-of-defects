/* fix_bd_sphere.h */

#ifdef FIX_CLASS
FixStyle(bd/sphere,FixBDSphere)
#else

#ifndef LMP_FIX_BD_SPHERE_H
#define LMP_FIX_BD_SPHERE_H

#include "fix.h"

namespace LAMMPS_NS {

class FixBDSphere : public Fix {
 public:
  FixBDSphere(class LAMMPS *, int, char **);
  virtual ~FixBDSphere();
  int setmask() override;
  void init() override;
  void initial_integrate(int) override;
  void post_force(int) override;
  void final_integrate() override;
  double memory_usage() override;

 protected:
  double gamma;          // friction coefficient
  double temperature;    // temperature
  double r_sphere;       // sphere radius
  double Fext;           // active force
  int mchain;            // atoms per chain
  int seed;              // random seed
  double dt;             // timestep
  double rc;             // cutoff
  double wall_epsilon;   // wall strength
  
  class RanMars *random;
};

}
#endif
#endif