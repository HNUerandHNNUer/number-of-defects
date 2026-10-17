from audit import connect
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
cmd="python3 - <<'PY'\nfrom pathlib import Path\nimport re,json,subprocess\np=Path('/home/user/wxd/9.19.2026/sphere_distributed_20261017');rows=[]\nfor q in sorted(p.glob('relax*')):\n t=(q/'log.lammps').read_text() if (q/'log.lammps').exists() else '';ls=[l for l in t.splitlines() if re.match(r'^\\s*\\d+\\s+[-+\\d.]',l)];rows.append(dict(name=q.name,step=int(ls[-1].split()[0]) if ls else None,error='ERROR' in t,failed=(q/'failed.json').exists(),launch=(q/'launch.json').exists()))\nprint(json.dumps(dict(lmp=subprocess.getoutput('pgrep -xc lmp'),jobs=rows)))\nPY"
def f(port):
 c=connect('10.157.197.181',port);i,o,e=c.exec_command(cmd);r=dict(port=port,output=o.read().decode(),error=e.read().decode());print(r);c.close();return r
with ThreadPoolExecutor(max_workers=2) as p:r=list(p.map(f,[10052,10053]))
Path('resource_audit_20261017/launch_verified.json').write_text(json.dumps(r,indent=2))
