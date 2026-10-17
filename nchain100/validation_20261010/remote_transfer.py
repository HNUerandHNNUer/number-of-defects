from pathlib import Path
import subprocess,sys
P=Path(__file__).resolve().parent
commands=['option batch abort','open 10004 -timeout=30 -rawsettings Shell=/bin/bash']
if sys.argv[1]=='init':commands+=['mkdir /home/user/codex_bd_validation_20261010']
commands += ['put "'+str(P/'remote_inspect.sh')+'" /home/user/codex_bd_validation_20261010/remote_inspect.sh','call bash /home/user/codex_bd_validation_20261010/remote_inspect.sh','exit']
p=P/'winscp_commands.txt';p.write_text('\n'.join(commands),encoding='utf-8-sig')
r=subprocess.run(['D:/WinSCP/WinSCP.com','/ini=D:/WinSCP/WinSCP.ini','/script='+str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(P/'remote_inspection.log').write_bytes(r.stdout);print(r.stdout.decode('utf8',errors='replace'));raise SystemExit(r.returncode)
