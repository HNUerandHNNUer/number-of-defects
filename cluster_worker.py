"""Runs one staged job on a Linux node and writes a durable completion marker."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(str(temporary), str(path))


def main():
    directory = Path(sys.argv[1]).resolve()
    spec = json.loads((directory / ".cluster-job.json").read_text(encoding="utf-8"))
    marker = directory / ".cluster-status.json"
    atomic_json(marker, {"state": "running", "started": time.time(), "pid": os.getpid()})
    with (directory / "cluster.stdout.log").open("wb") as stdout, (directory / "cluster.stderr.log").open("wb") as stderr:
        result = subprocess.run(["bash", "-lc", spec["command"]], cwd=str(directory), stdout=stdout, stderr=stderr)
    atomic_json(marker, {"state": "done" if result.returncode == 0 else "failed", "exit_code": result.returncode, "finished": time.time()})


if __name__ == "__main__":
    main()
