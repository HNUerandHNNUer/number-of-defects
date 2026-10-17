from pathlib import Path
import subprocess,sys
from concurrent.futures import ThreadPoolExecutor
here=Path(__file__).resolve().parent
jobs=[(c,w) for c in ('branch_n10_F2_co_r1','branch_n10_F2_counter_r1','size_n100_F5_r1') for w in ('early','middle')]
def run(job):
 c,w=job
 with (here/(c+'_'+w+'.log')).open('w') as f:
  subprocess.check_call([sys.executable,str(here/'track_fixed.py'),c,'4',w],stdout=f,stderr=subprocess.STDOUT)
 print('DONE',c,w,flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,jobs))
