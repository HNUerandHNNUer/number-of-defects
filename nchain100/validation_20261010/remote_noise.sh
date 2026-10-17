#!/bin/bash
set -u
cd /home/user/codex_bd_validation_20261010
HPCX=/opt/nvidia/hpc_sdk/Linux_x86_64/24.11/comm_libs/12.6/hpcx/hpcx-2.20
source "$HPCX/hpcx-init.sh"; hpcx_load
export OPAL_PREFIX="$HPCX/ompi"
export OMP_NUM_THREADS=1
LMP=/home/user/soft/lammps/lammps-22Jul2025/build/lmp
for mode in cpu1 cpu2 cpu4 kk1 kk2; do
 mkdir -p "noise_$mode"
 cp noise.data "noise_$mode/sample.data"
 cp in.noise "noise_$mode/in.test"
 cd "noise_$mode"
 case "$mode" in
  cpu*) n=${mode#cpu}; timeout 30 "$HPCX/ompi/bin/mpirun" --mca pml ob1 --mca btl self,tcp -np "$n" "$LMP" -in in.test > console.log 2>&1 ;;
  kk*) n=${mode#kk}; timeout 30 "$HPCX/ompi/bin/mpirun" --mca pml ob1 --mca btl self,tcp -np "$n" "$LMP" -k on g 1 -sf kk -in in.test > console.log 2>&1 ;;
 esac
 echo "$mode noise exit=$?"
 cd ..
done
tar -czf noise_outputs.tar.gz noise_cpu1 noise_cpu2 noise_cpu4 noise_kk1 noise_kk2
