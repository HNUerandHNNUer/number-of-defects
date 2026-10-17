/* fix_bd_sphere_kokkos.cpp */

#include "fix_bd_sphere_kokkos.h"
#include "atom_kokkos.h"
#include "update.h"
#include "error.h"
#include "domain.h"
#include "comm.h"
#include "math_special.h"
#include "atom_masks.h" 
#include <cmath>

using namespace LAMMPS_NS;

FixBDSphereKokkos::FixBDSphereKokkos(LAMMPS *lmp, int narg, char **arg) :
  FixBDSphere(lmp, narg, arg)
{
  kokkosable = 1;
  atomKK = (AtomKokkos *) atom;
  execution_space = ExecutionSpaceFromDevice<LMPDeviceType>::space;
  datamask_read = EMPTY_MASK;
  datamask_modify = EMPTY_MASK;
  
  // 初始化 GPU 随机数池
  rand_pool = Kokkos::Random_XorShift64_Pool<LMPDeviceType>(seed + comm->me);
}

FixBDSphereKokkos::~FixBDSphereKokkos() {}

void FixBDSphereKokkos::init()
{
  FixBDSphere::init();
}

void FixBDSphereKokkos::initial_integrate(int vflag)
{
  // 强制同步 CPU-GPU 状态
  atomKK->sync(execution_space, X_MASK | V_MASK | MASK_MASK);
  atomKK->modified(execution_space, X_MASK);

  // 获取 GPU 显存视图
  auto x = atomKK->k_x.view<LMPDeviceType>();
  auto v = atomKK->k_v.view<LMPDeviceType>();
  auto mask = atomKK->k_mask.view<LMPDeviceType>();
  
  int nlocal = atom->nlocal;
  double dt_l = dt;
  int gbit = groupbit;

  Kokkos::parallel_for("FixBDSphereKK::init_int", nlocal, KOKKOS_LAMBDA(int i) {
    if (mask(i) & gbit) {
      x(i,0) += dt_l * v(i,0);
      x(i,1) += dt_l * v(i,1);
      x(i,2) += dt_l * v(i,2);
    }
  });
}

void FixBDSphereKokkos::post_force(int vflag)
{
  int nlocal = atom->nlocal;

  atomKK->sync(execution_space, X_MASK | F_MASK | TAG_MASK | MASK_MASK);
  
  // 优化点：使用 LAMMPS 原生的 Kokkos map array 进行同步，避免每步的 deep_copy
  atomKK->k_map_array.template sync<LMPDeviceType>();

  auto x = atomKK->k_x.view<LMPDeviceType>();
  auto f = atomKK->k_f.view<LMPDeviceType>();
  auto tag = atomKK->k_tag.view<LMPDeviceType>();
  auto mask = atomKK->k_mask.view<LMPDeviceType>();
  auto d_map = atomKK->k_map_array.template view<LMPDeviceType>();

  // 提取局部标量
  double n_fac = sqrt(24.0 * temperature * gamma / dt);
  double Fext_l = Fext;
  int mchain_l = mchain;
  double rs_l = r_sphere;
  double rc_l = rc;
  double weps_l = wall_epsilon;
  int gbit = groupbit;
  int map_tag_max = atomKK->map_tag_max;

  double prd_x = domain->xprd;
  double prd_y = domain->yprd;
  double prd_z = domain->zprd;
  double hprd_x = prd_x * 0.5;
  double hprd_y = prd_y * 0.5;
  double hprd_z = prd_z * 0.5;
  
  auto rand_pool_l = rand_pool;

  Kokkos::parallel_for("FixBDSphereKK::post_force", nlocal, KOKKOS_LAMBDA(int i) {
    if (mask(i) & gbit) {
      // 1. 随机力
      auto rand_gen = rand_pool_l.get_state();
      double rx = rand_gen.drand() - 0.5;
      double ry = rand_gen.drand() - 0.5;
      double rz = rand_gen.drand() - 0.5;
      rand_pool_l.free_state(rand_gen);

      double fx = rx * n_fac;
      double fy = ry * n_fac;
      double fz = rz * n_fac;

      // 2. 活性推力 (FENE chain逻辑)
      int atom_id = tag(i);
      int mod_idx = atom_id % mchain_l;

      if (mod_idx != 1 && mod_idx != 0) {
        int prev_id = atom_id - 1;
        int next_id = atom_id + 1;
        int prev_idx = -1;
        int next_idx = -1;

        if (prev_id >= 0 && prev_id <= map_tag_max) prev_idx = d_map(prev_id);
        if (next_id >= 0 && next_id <= map_tag_max) next_idx = d_map(next_id);

        if (prev_idx >= 0 && next_idx >= 0) {
          double dx = x(next_idx,0) - x(prev_idx,0);
          double dy = x(next_idx,1) - x(prev_idx,1);
          double dz = x(next_idx,2) - x(prev_idx,2);

          // 最小镜像约定
          if (dx > hprd_x) dx -= prd_x; else if (dx < -hprd_x) dx += prd_x;
          if (dy > hprd_y) dy -= prd_y; else if (dy < -hprd_y) dy += prd_y;
          if (dz > hprd_z) dz -= prd_z; else if (dz < -hprd_z) dz += prd_z;

          double Rext = sqrt(dx*dx + dy*dy + dz*dz);
          if (Rext > 0.0) {
            double scale = Fext_l / Rext;
            fx += scale * dx;
            fy += scale * dy;
            fz += scale * dz;
          }
        }
      }

      // 3. 球面边界排斥力
      double pos_x = x(i,0);
      double pos_y = x(i,1);
      double pos_z = x(i,2);
      double pos_mag = sqrt(pos_x*pos_x + pos_y*pos_y + pos_z*pos_z);

      if (pos_mag > 0.0) {
        // 外壁排斥
        double DISi = (rs_l + rc_l) - pos_mag;
        if (DISi <= rc_l) {
          double dist = (DISi < 1e-6) ? 1e-6 : DISi;
          double rm = 1.0 / (dist * dist);
          double rm3 = rm * rm * rm;
          double force = weps_l * 24.0 * (2.0 * rm3*rm3 - rm3) / (dist * dist);
          double dir = dist / pos_mag;
          fx -= force * dir * pos_x;
          fy -= force * dir * pos_y;
          fz -= force * dir * pos_z;
        }

        // 内壁排斥
        DISi = pos_mag - (rs_l - rc_l);
        if (DISi <= rc_l) {
          double dist = (DISi < 1e-6) ? 1e-6 : DISi;
          double rm = 1.0 / (dist * dist);
          double rm3 = rm * rm * rm;
          double force = weps_l * 24.0 * (2.0 * rm3*rm3 - rm3) / (dist * dist);
          double dir = dist / pos_mag;
          fx += force * dir * pos_x;
          fy += force * dir * pos_y;
          fz += force * dir * pos_z;
        }
      }

      f(i,0) += fx;
      f(i,1) += fy;
      f(i,2) += fz;
    }
  });

  atomKK->modified(execution_space, F_MASK);
}

void FixBDSphereKokkos::final_integrate()
{
  atomKK->sync(execution_space, F_MASK | V_MASK | MASK_MASK);
  atomKK->modified(execution_space, V_MASK);

  auto v = atomKK->k_v.view<LMPDeviceType>();
  auto f = atomKK->k_f.view<LMPDeviceType>();
  auto mask = atomKK->k_mask.view<LMPDeviceType>();

  int nlocal = atom->nlocal;
  double max_disp = 0.05;
  double max_v = max_disp / dt;
  double max_v_sq = max_v * max_v;
  double g_l = gamma;
  int gbit = groupbit;

  Kokkos::parallel_for("FixBDSphereKK::final_int", nlocal, KOKKOS_LAMBDA(int i) {
    if (mask(i) & gbit) {
      double vx = f(i,0) / g_l;
      double vy = f(i,1) / g_l;
      double vz = f(i,2) / g_l;

      double v_sq = vx*vx + vy*vy + vz*vz;
      if (v_sq > max_v_sq) {
        double scale = sqrt(max_v_sq / v_sq);
        vx *= scale;
        vy *= scale;
        vz *= scale;
      }

      v(i,0) = vx;
      v(i,1) = vy;
      v(i,2) = vz;
    }
  });
}