/* fix_bd_sphere.cpp */

#include "fix_bd_sphere.h"
#include "atom.h"
#include "update.h"
#include "force.h"
#include "error.h"
#include "domain.h"
#include "comm.h"
#include "random_mars.h"
#include "memory.h"
#include "utils.h"
#include <cmath>
#include <cstdio>

using namespace LAMMPS_NS;
using namespace FixConst;

FixBDSphere::FixBDSphere(LAMMPS *lmp, int narg, char **arg) :
  Fix(lmp, narg, arg), random(nullptr)
{
  if (narg != 9) 
    error->all(FLERR,"Illegal fix bd/sphere command: fix ID group bd/sphere gamma T Fext seed mchain value");

  gamma = utils::numeric(FLERR, arg[3], false, lmp);
  temperature = utils::numeric(FLERR, arg[4], false, lmp);
  Fext = utils::numeric(FLERR, arg[5], false, lmp);
  seed = utils::inumeric(FLERR, arg[6], false, lmp);
  
  if (strcmp(arg[7],"mchain") != 0)
    error->all(FLERR,"Expecting 'mchain' keyword");
  mchain = utils::inumeric(FLERR, arg[8], false, lmp);
  
  random = new RanMars(lmp, seed + comm->me);
  
  rc = pow(2.0, 1.0/6.0);
  wall_epsilon = 100.0;
  
  virial_global_flag = 1;
  virial_peratom_flag = 0;
  thermo_virial = 1;
}

FixBDSphere::~FixBDSphere()
{
  delete random;
}

int FixBDSphere::setmask()
{
  int mask = 0;
  mask |= POST_FORCE;
  mask |= INITIAL_INTEGRATE;
  mask |= FINAL_INTEGRATE;
  return mask;
}

void FixBDSphere::init()
{
  dt = update->dt;
  
  // 检查是否开启了 atom_modify map
  if (atom->map_style == 0) 
    error->all(FLERR, "Fix bd/sphere requires 'atom_modify map array' in input script");

  double xprd = domain->xprd;
  r_sphere = xprd / 2.0 - 2.5;
}

void FixBDSphere::initial_integrate(int /*vflag*/)
{
  double **x = atom->x;
  double **v = atom->v;
  int *mask = atom->mask;
  int nlocal = atom->nlocal;
  
  for (int i = 0; i < nlocal; i++) {
    if (mask[i] & groupbit) {
      x[i][0] += dt * v[i][0];
      x[i][1] += dt * v[i][1];
      x[i][2] += dt * v[i][2];
    }
  }
}

void FixBDSphere::post_force(int /*vflag*/)
{
  double **x = atom->x;
  double **f = atom->f;
  int *tag = atom->tag;
  int *mask = atom->mask;
  int nlocal = atom->nlocal;
  
  double noise_factor = sqrt(24.0 * temperature * gamma / dt);

  for (int i = 0; i < nlocal; i++) {
    if (mask[i] & groupbit) {
      // 1. Random Force
      f[i][0] += (random->uniform() - 0.5) * noise_factor;
      f[i][1] += (random->uniform() - 0.5) * noise_factor;
      f[i][2] += (random->uniform() - 0.5) * noise_factor;
      
      // 2. Active Force
      int atom_id = tag[i];
      int mod_idx = atom_id % mchain;
      
      if (mod_idx != 1 && mod_idx != 0) { 
        int prev_id = atom_id - 1;
        int next_id = atom_id + 1;
        
        int prev_idx = atom->map(prev_id);
        int next_idx = atom->map(next_id);
        
        if (prev_idx >= 0 && next_idx >= 0) {
          double Sext[3];
          Sext[0] = x[next_idx][0] - x[prev_idx][0];
          Sext[1] = x[next_idx][1] - x[prev_idx][1];
          Sext[2] = x[next_idx][2] - x[prev_idx][2];
          
          // [修复] 增加 FLERR 参数以兼容新版 LAMMPS
          domain->minimum_image(FLERR, Sext[0], Sext[1], Sext[2]);
          
          double Rext = sqrt(Sext[0]*Sext[0] + Sext[1]*Sext[1] + Sext[2]*Sext[2]);
          
          if (Rext > 0.0) {
            double scale = Fext / Rext;
            f[i][0] += scale * Sext[0];
            f[i][1] += scale * Sext[1];
            f[i][2] += scale * Sext[2];
          }
        }
      }
      
      // 3. Wall Force
      double r2 = x[i][0]*x[i][0] + x[i][1]*x[i][1] + x[i][2]*x[i][2];
      double pos_mag = sqrt(r2);
      
      if (pos_mag > 0.0) {
        // Wall 1 (Inner)
        double DISi = (r_sphere + rc) - pos_mag;
        if (DISi <= rc) {
           double dist = (DISi < 1e-6) ? 1e-6 : DISi;
           double rm = 1.0 / (dist * dist);
           double rm3 = rm * rm * rm;
           double rm6 = rm3 * rm3;
           double force = wall_epsilon * 24.0 * (2.0 * rm6 - rm3) / (dist * dist);
           
           double dir = dist / pos_mag; 
           f[i][0] -= force * dir * x[i][0];
           f[i][1] -= force * dir * x[i][1];
           f[i][2] -= force * dir * x[i][2];
        }
        
        // Wall 2 (Outer)
        DISi = pos_mag - (r_sphere - rc);
        if (DISi <= rc) {
           double dist = (DISi < 1e-6) ? 1e-6 : DISi;
           double rm = 1.0 / (dist * dist);
           double rm3 = rm * rm * rm;
           double rm6 = rm3 * rm3;
           double force = wall_epsilon * 24.0 * (2.0 * rm6 - rm3) / (dist * dist);
           
           double dir = dist / pos_mag;
           f[i][0] += force * dir * x[i][0];
           f[i][1] += force * dir * x[i][1];
           f[i][2] += force * dir * x[i][2];
        }
      }
    }
  }
}

void FixBDSphere::final_integrate()
{
  double **v = atom->v;
  double **f = atom->f;
  int *mask = atom->mask;
  int nlocal = atom->nlocal;
  
  // 速度限制：防止压缩时力过大导致崩溃
  double max_disp = 0.05; 
  double max_v = max_disp / dt;
  double max_v_sq = max_v * max_v;

  for (int i = 0; i < nlocal; i++) {
    if (mask[i] & groupbit) {
      double vx = f[i][0] / gamma;
      double vy = f[i][1] / gamma;
      double vz = f[i][2] / gamma;
      
      // 速度钳制
      double v_sq = vx*vx + vy*vy + vz*vz;
      if (v_sq > max_v_sq) {
        double scale = sqrt(max_v_sq / v_sq);
        vx *= scale;
        vy *= scale;
        vz *= scale;
      }

      v[i][0] = vx;
      v[i][1] = vy;
      v[i][2] = vz;
    }
  }
}

double FixBDSphere::memory_usage()
{
  return 0.0;
}