#!/bin/bash
set -u
cd /home/user/codex_bd_validation_20261010
HPCX=/opt/nvidia/hpc_sdk/Linux_x86_64/24.11/comm_libs/12.6/hpcx/hpcx-2.20
source "$HPCX/hpcx-init.sh"
hpcx_load
export OPAL_PREFIX="$HPCX/ompi"
export OMP_NUM_THREADS=1
LMP=/home/user/soft/lammps/lammps-22Jul2025/build/lmp
sha256sum "$LMP" /home/user/soft/lammps/lammps-22Jul2025/src/fix_bd_sphere* > source_hashes.txt
for mode in cpu1 cpu2 cpu4 kk1 kk2; do
 mkdir -p "$mode"
 cp sample.data "$mode/sample.data"
 cp in.test "$mode/in.test"
 cd "$mode"
 case "$mode" in
  cpu*) n=${mode#cpu}; timeout 60 "$HPCX/ompi/bin/mpirun" --mca pml ob1 --mca btl self,tcp -np "$n" "$LMP" -in in.test > console.log 2>&1 ;;
  kk*) n=${mode#kk}; timeout 60 "$HPCX/ompi/bin/mpirun" --mca pml ob1 --mca btl self,tcp -np "$n" "$LMP" -k on g 1 -sf kk -in in.test > console.log 2>&1 ;;
 esac
 code=$?
 echo "$mode exit=$code"
 echo "$code" > exit_code.txt
 tail -3 console.log
 cd ..
done
tar -czf backend_outputs.tar.gz source_hashes.txt lmp_help.txt cpu1 cpu2 cpu4 kk1 kk2
