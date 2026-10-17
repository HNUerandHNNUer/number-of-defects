from audit import connect
import json,io,hashlib
from pathlib import Path
b='/home/user/wxd/9.19.2026/sphere_relaxation_20261016';dest='/home/user/wxd/9.19.2026/sphere_distributed_20261017'
a=connect('10.157.197.181',10055);sf=a.open_sftp();sf.open(b+'/STOP_NEW_JOBS','w').write('Pending r3 jobs delegated to CPU2/CPU3 on 2026-10-17; do not duplicate. Running jobs unchanged.\n')
state=json.loads(sf.open(b+'/status.json').read());jobs=[j for j in state if j['state']=='pending'];assert len(jobs)==8
runner='''import subprocess,os,json,time,pathlib
p=pathlib.Path(__file__).resolve().parent
cmd=['/home/user/anaconda3/bin/mpirun','-np','4',str(p.parent/'bin/lmp'),'-in','in.production','-log','log.lammps','-nonbuf']
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');env['PATH']='/home/user/anaconda3/bin:'+env.get('PATH','')
with open(p/'screen.log','x') as out:
 proc=subprocess.Popen(cmd,cwd=str(p),env=env,stdout=out,stderr=subprocess.STDOUT)
 (p/'launch.json').write_text(json.dumps(dict(pid=proc.pid,command=cmd,time=time.time())))
 rc=proc.wait()
good=rc==0 and (p/'final.bin').exists() and 'VALIDATION_RUN_COMPLETED' in (p/'log.lammps').read_text(errors='replace')
(p/('completed.json' if good else 'failed.json')).write_text(json.dumps(dict(returncode=rc,valid=good,time=time.time())))
'''
records=[]
for port,n in [(10052,200),(10053,350)]:
 c=connect('10.157.197.181',port);i,o,e=c.exec_command('mkdir -p '+dest+'/bin');o.channel.recv_exit_status();f=c.open_sftp()
 if port==10053:
  i,o,e=c.exec_command('cp '+dest+'/bench/lmp '+dest+'/bin/lmp');o.channel.recv_exit_status()
 else:f.put('resource_audit_20261017/lmp',dest+'/bin/lmp')
 f.chmod(dest+'/bin/lmp',0o755)
 for j in jobs:
  if ('n%d_'%n) not in j['name']:continue
  q=dest+'/'+j['name'];i,o,e=c.exec_command('mkdir -p '+q);o.channel.recv_exit_status()
  for name in ['polymer.data','in.production','provenance.json']:
   data=sf.open(b+'/'+j['name']+'/'+name).read();f.putfo(io.BytesIO(data),q+'/'+name)
  f.open(q+'/run_job.py','w').write(runner)
  i,o,e=c.exec_command('cd '+q+' && nohup /home/user/anaconda3/bin/python run_job.py > supervisor.log 2>&1 < /dev/null &');o.channel.recv_exit_status()
  record=dict(name=j['name'],host='10.157.197.181',port=port,path=q,ranks=4,source=b+'/'+j['name'],mode='original coordinates and seed, not restart');records.append(record);sf.open(b+'/'+j['name']+'/delegated.json','w').write(json.dumps(record,indent=2));print('START',record,flush=True)
 c.close()
Path('resource_audit_20261017/delegated_jobs.json').write_text(json.dumps(records,indent=2));a.close()
