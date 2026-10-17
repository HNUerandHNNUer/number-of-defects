from pathlib import Path
import subprocess,sys,concurrent.futures,os
HERE=Path(__file__).resolve().parent;OUT=HERE/'final_analysis_cpu5'
def run(p):
 target=OUT/(p.stem+'_tracking.csv')
 if target.exists() and not os.environ.get('CPU5_RETRACK'):return p.stem+' cached'
 with (OUT/(p.stem+'_worker.log')).open('w') as log:
  r=subprocess.run([sys.executable,str(HERE/'fine_worker.py'),str(p)],stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(p.stem+' failed: '+(OUT/(p.stem+'_worker.log')).read_text()[-2000:])
 return p.stem+' done'
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for f in concurrent.futures.as_completed([pool.submit(run,p) for p in sorted(OUT.glob('*__*.npz'))]):print(f.result(),flush=True)
