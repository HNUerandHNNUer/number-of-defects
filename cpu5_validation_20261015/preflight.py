from pathlib import Path
import subprocess,os,json,math,re,time
ROOT=Path(__file__).resolve().parent
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
env['PATH']='/home/user/anaconda3/bin:'+env.get('PATH','')
jobs=json.loads((ROOT/'manifest.json').read_text())
selected=[j for j in jobs if j['replicate']==1]
results=[]
for j in selected:
    p=ROOT/j['name'];t=time.time()
    cmd=['/home/user/anaconda3/bin/mpirun','-np','2',str(ROOT/'bin/lmp'),'-in','in.smoke','-log','smoke.log','-screen','smoke.screen']
    r=subprocess.run(cmd,cwd=str(p),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
    log=(p/'smoke.log').read_text(errors='replace') if (p/'smoke.log').exists() else ''
    valid=r.returncode==0 and 'SMOKE_OK' in log and 'ERROR' not in log and 'WARNING: FENE' not in log
    results.append(dict(name=j['name'],returncode=r.returncode,valid=valid,seconds=time.time()-t,performance=re.findall(r'Performance:.*',log)))
    print(results[-1],flush=True)
    if not valid: print(log[-5000:]);break
(ROOT/'preflight.json').write_text(json.dumps(results,indent=2))
assert len(results)==len(selected) and all(r['valid'] for r in results)
print('ALL_PREFLIGHT_PASSED',flush=True)
