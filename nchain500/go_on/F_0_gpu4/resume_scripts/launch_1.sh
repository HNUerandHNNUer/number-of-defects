#!/bin/bash
cd /home/user/wxd/9.19.2026/nchain500/10.10.2025/1/resume_from_70000000 || exit 1
source /home/user/.lammps_env
export OMP_NUM_THREADS=1
printf '%s\n' "$$" > launcher.pid
date -Is > started_at.txt
"$MPIROOT/bin/mpirun" -np 6 /home/user/soft/lammps/lammps-22Jul2025/build/lmp -in continue.in -log production.log > production.out 2>&1 &
mpi_pid=$!
printf '%s\n' "$mpi_pid" > mpirun.pid
wait "$mpi_pid"
rc=$?
printf '%s\n' "$rc" > exit_code.txt
date -Is > finished_at.txt
exit "$rc"
