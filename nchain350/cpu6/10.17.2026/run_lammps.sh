#!/usr/bin/env bash
# Launch one independent LAMMPS MPI job in each sibling F_* directory.
set -u

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
NP=4

for cmd in mpirun lmp; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        printf '[ERROR] Command not found: %s\n' "$cmd" >&2
        exit 1
    fi
done

shopt -s nullglob
started=0
skipped=0

printf 'Base directory: %s\nMPI ranks per job: %s\n' "$BASE_DIR" "$NP"

for dir in "$BASE_DIR"/F_*; do
    [[ -d "$dir" ]] || continue
    name="${dir##*/}"

    if [[ ! -f "$dir/bd.in" ]]; then
        printf '[SKIP] %s: bd.in not found\n' "$name"
        ((skipped+=1))
        continue
    fi

    if [[ -f "$dir/lammps.pid" ]]; then
        old_pid="$(cat "$dir/lammps.pid")"
        if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
            printf '[SKIP] %s: previous launch PID %s still exists\n' "$name" "$old_pid"
            ((skipped+=1))
            continue
        fi
    fi

    (
        cd -- "$dir" || exit 1
        nohup mpirun -np "$NP" lmp -in bd.in > nohup.out 2>&1 < /dev/null &
        pid=$!
        printf '%s\n' "$pid" > lammps.pid
        printf '[START] %s: PID=%s, log=%s/nohup.out\n' "$name" "$pid" "$dir"
    ) || { printf '[ERROR] Failed to launch %s\n' "$name" >&2; ((skipped+=1)); continue; }
    ((started+=1))
done

printf '\nLaunch complete: started=%d skipped=%d; %d MPI ranks per started job.\n' "$started" "$skipped" "$NP"
