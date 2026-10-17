from audit import connect
from pathlib import Path
import json
c=connect('10.157.197.181',10055);cmd="python3 - <<'PY'\nfrom pathlib import Path\nimport re,json,subprocess\np=Path('/home/user/wxd/9.19.2026/sphere_relaxation_20261016');r=[]\nfor q in sorted(p.glob('relax*')):\n if not (q/'log.lammps').exists():continue\n t=(q/'log.lammps').read_text();s=(q/'screen.log').read_text();a=[l for l in t.splitlines() if re.match(r'^\\s*\\d+\\s+[-+\\d.]',l)];r.append(dict(name=q.name,step=int(a[-1].split()[0]),errors=len(re.findall('ERROR|Lost atoms',t+s)),FENE=len(re.findall('WARNING: FENE',s))))\nprint(json.dumps(dict(lmp=subprocess.getoutput('pgrep -xc lmp'),jobs=r)))\nPY"
i,o,e=c.exec_command(cmd);x=o.read().decode();Path('resource_audit_20261017/cpu5_latest.json').write_text(x);print(x);c.close()
