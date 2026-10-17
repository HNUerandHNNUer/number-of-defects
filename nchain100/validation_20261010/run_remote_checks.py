from pathlib import Path
import subprocess
P=Path(__file__).resolve().parent;remote='/home/user/codex_bd_validation_20261010/'
lines=['option batch abort','open 10004 -timeout=75 -rawsettings Shell=/bin/bash']
for local,name in [(P/'forces/sample.data','sample.data'),(P/'forces/in.test','in.test'),(P/'remote_checks.sh','remote_checks.sh')]:lines+=['put "'+str(local)+'" '+remote+name]
lines+=['call bash '+remote+'remote_checks.sh','get '+remote+'backend_outputs.tar.gz "'+str(P/'backend_outputs.tar.gz')+'"','exit']
cmd=P/'winscp_backend.txt';cmd.write_text('\n'.join(lines),encoding='utf-8-sig')
r=subprocess.run(['D:/WinSCP/WinSCP.com','/ini=D:/WinSCP/WinSCP.ini','/script='+str(cmd)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(P/'remote_checks.log').write_bytes(r.stdout)
print('WinSCP exit',r.returncode,flush=True)
for line in r.stdout.decode('gb18030',errors='replace').splitlines():
 if 'exit=' in line or 'ERROR' in line:print(line.encode('ascii',errors='replace').decode(),flush=True)
raise SystemExit(r.returncode)
