#!/bin/bash
cd /home/user/wxd/9.19.2026/nchain500/10.10.2025/F_0.003/gpu_run_20261010 || exit 1
source /home/user/.lammps_env
export OMP_NUM_THREADS=1
printf '%s\n' "$$" > launcher.pid
date -Is > started_at.txt
"$MPIROOT/bin/mpirun" -np 1 /home/user/soft/lammps/lammps-22Jul2025/build/lmp -k on g 1 -sf kk -in bd.in -log production.log > production.out 2>&1 &
mpi_pid=$!
printf '%s\n' "$mpi_pid" > mpirun.pid
wait "$mpi_pid"
rc=$?
printf '%s\n' "$rc" > exit_code.txt
date -Is > finished_at.txt
exit "$rc"
