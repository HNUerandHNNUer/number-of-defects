#!/bin/bash
set -u
cd /home/user/codex_bd_validation_20261010
HPCX=/opt/nvidia/hpc_sdk/Linux_x86_64/24.11/comm_libs/12.6/hpcx/hpcx-2.20
if [ -f "$HPCX/hpcx-init.sh" ]; then source "$HPCX/hpcx-init.sh"; hpcx_load; fi
export OPAL_PREFIX="$HPCX/ompi"
export OMP_NUM_THREADS=1
LMP=/home/user/soft/lammps/lammps-22Jul2025/build/lmp
if [ "$(ps -p 532775 -o args=)" = "/usr/local/bin/lmp -h" ]; then kill 532775; fi
timeout 8 "$HPCX/ompi/bin/mpirun" --version
timeout 8 "$HPCX/ompi/bin/mpirun" -np 1 hostname
echo "launcher exit=$?"
timeout 15 "$HPCX/ompi/bin/mpirun" --mca pml ob1 --mca btl self,tcp -np 1 "$LMP" -h > lmp_help.txt 2>&1
echo "help exit=$?"
head -15 lmp_help.txt
grep -E 'bd/sphere|brownian|KOKKOS' lmp_help.txt || true
grep -E 'MPI_CXX_COMPILER:|Kokkos_ENABLE_CUDA:|CMAKE_CXX_COMPILER:' /home/user/soft/lammps/lammps-22Jul2025/build/CMakeCache.txt || true
ps -u user -o pid,args | grep -E '^[ ]*[0-9]+ /usr/local/bin/lmp -h$' || true
