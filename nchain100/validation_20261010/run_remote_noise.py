from tests import *
remote='/home/user/codex_bd_validation_20261010/'
d=P/'shell_equilibrium_custom_0.01'
sample=(d/'sample.data').read_text().split('\nBonds\n')[0]
sample=re.sub(r'\d+ bonds','0 bonds',sample);sample=re.sub(r'\d+ angles','0 angles',sample)
(P/'noise.data').write_text(sample)
text=(d/'in.test').read_text();text=re.sub(r'run \d+','run 2',text);(P/'in.noise').write_text(text)
lines=['option batch abort','open 10004 -timeout=60 -rawsettings Shell=/bin/bash']
for local,name in [(P/'noise.data','noise.data'),(P/'in.noise','in.noise'),(P/'remote_noise.sh','remote_noise.sh')]:lines+=['put "'+str(local)+'" '+remote+name]
lines+=['call bash '+remote+'remote_noise.sh','get '+remote+'noise_outputs.tar.gz "'+str(P/'noise_outputs.tar.gz')+'"','exit']
cmd=P/'winscp_noise.txt';cmd.write_text('\n'.join(lines),encoding='utf-8-sig')
r=subprocess.run(['D:/WinSCP/WinSCP.com','/ini=D:/WinSCP/WinSCP.ini','/script='+str(cmd)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(P/'remote_noise.log').write_bytes(r.stdout);print('WinSCP exit',r.returncode)
for line in r.stdout.decode('gb18030',errors='replace').splitlines():
 if 'exit=' in line or 'ERROR' in line:print(line.encode('ascii',errors='replace').decode())
