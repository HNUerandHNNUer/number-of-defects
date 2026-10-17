from pathlib import Path
import json,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
here=Path(__file__).resolve().parent;out=here/'completed_analysis_20261016'
def run(j):
 with (out/(j['name']+'_analysis.log')).open('w') as f:subprocess.check_call([sys.executable,str(here/'analyze_completed.py'),j['name']],stdout=f,stderr=subprocess.STDOUT)
 print('DONE',j['name'],flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,json.loads((out/'audit.json').read_text())))
subprocess.check_call([sys.executable,str(here/'analyze_completed.py')])
