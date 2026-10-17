from audit import connect
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,datetime
remote=r'''from pathlib import Path
import json,re,subprocess,shutil,os
p=Path(ROOT);rows=[]
for q in sorted(p.glob('relax*')):
 if not q.is_dir():continue
 if (q/'delegated.json').exists():rows.append(dict(name=q.name,delegated=True));continue
 log=q/'log.lammps';screen=q/'screen.log';t=log.read_text(errors='replace') if log.exists() else '';s=screen.read_text(errors='replace') if screen.exists() else '';ls=[l for l in t.splitlines() if re.match(r'^\s*\d+\s+[-+\d.]',l)]
 launch=json.loads((q/'launch.json').read_text()) if (q/'launch.json').exists() else {};pid=launch.get('pid');proc=Path('/proc')/str(pid)
 rows.append(dict(name=q.name,step=int(ls[-1].split()[0]) if ls else None,pid=pid,alive=proc.exists(),cwd=str((proc/'cwd').resolve()) if proc.exists() else None,completed=(q/'completed.json').exists(),failed=(q/'failed.json').exists(),final=(q/'final.bin').exists(),marker='VALIDATION_RUN_COMPLETED' in t,errors=len(re.findall('ERROR|Lost atoms',t+s)),fene=len(re.findall('WARNING: FENE',s))))
print(json.dumps(dict(jobs=rows,lmp=subprocess.getoutput('pgrep -xc lmp'),free_GB=shutil.disk_usage(p).free/1024**3,stop_new=(p/'STOP_NEW_JOBS').exists(),runner_tail=(p/'runner.log').read_text()[-500:] if (p/'runner.log').exists() else None)))
'''
def one(port):
 root='/home/user/wxd/9.19.2026/'+('sphere_relaxation_20261016' if port==10055 else 'sphere_distributed_20261017')
 c=connect('10.157.197.181',port);i,o,e=c.exec_command("python3 - <<'PY'\nROOT="+repr(root)+'\n'+remote+'\nPY',timeout=60);x=o.read().decode();err=e.read().decode();c.close();r=dict(port=port,data=json.loads(x),error=err);print(json.dumps(r),flush=True);return r
with ThreadPoolExecutor(max_workers=3) as p:r=list(p.map(one,[10052,10053,10055]))
Path('resource_audit_20261017/monitor_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json').write_text(json.dumps(r,indent=2))

