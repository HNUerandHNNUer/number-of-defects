/* fix_bd_sphere_kokkos.h */

#ifdef FIX_CLASS
FixStyle(bd/sphere/kk,FixBDSphereKokkos)
#else

#ifndef LMP_FIX_BD_SPHERE_KOKKOS_H
#define LMP_FIX_BD_SPHERE_KOKKOS_H

#include "fix_bd_sphere.h"
#include "kokkos_type.h"
#include <Kokkos_Random.hpp> 

namespace LAMMPS_NS {

class FixBDSphereKokkos : public FixBDSphere {
 public:
  FixBDSphereKokkos(class LAMMPS *, int, char **);
  virtual ~FixBDSphereKokkos();
  void init() override;
  void initial_integrate(int) override;
  void post_force(int) override;
  void final_integrate() override;

 private:
  class AtomKokkos *atomKK;
  
  // KOKKOS 专用的 GPU 随机数生成池
  Kokkos::Random_XorShift64_Pool<LMPDeviceType> rand_pool;
};

}
#endif
#endif