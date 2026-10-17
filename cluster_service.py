"""Run the scheduler without a console and retain diagnostics."""
import sys
import traceback
from pathlib import Path

import cluster_queue


with (Path(__file__).resolve().parent / "cluster_service.log").open("a", encoding="utf-8", buffering=1) as log:
    sys.stdout = log
    sys.stderr = log
    sys.argv = [str(Path(__file__).resolve()), "run"]
    try:
        cluster_queue.main()
    except Exception:
        traceback.print_exc(file=log)
        raise
