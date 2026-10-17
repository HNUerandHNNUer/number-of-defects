#!/usr/bin/env python3
"""Sixteen concurrent jobs, two MPICH ranks each; adopt existing MPI jobs."""
from pathlib import Path
import subprocess, os, json, time, shutil, fcntl, hashlib
ROOT=Path(__file__).resolve().parent
os.chdir(str(ROOT))
lock=open('runner.lock','w')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
lock.write(str(os.getpid()));lock.flush()
jobs=json.loads((ROOT/'manifest.json').read_text())
MPIRUN='/home/user/anaconda3/bin/mpirun'
LMP=str(ROOT/'bin/lmp')
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
env['PATH']='/home/user/anaconda3/bin:'+env.get('PATH','')
active={}
class AdoptedProcess:
    def __init__(self,pid):
        self.pid=pid
        self.start=(Path('/proc')/str(pid)/'stat').read_text().split()[21]
    def poll(self):
        try:
            fields=(Path('/proc')/str(self.pid)/'stat').read_text().split()
            return None if fields[21]==self.start and fields[2]!='Z' else 0
        except FileNotFoundError:
            return 0
def event(s):
    print(time.strftime('%Y-%m-%d %H:%M:%S'),s,flush=True)
def save():
    status=[]
    for j in jobs:
        p=ROOT/j['name'];state='pending'
        if (p/'completed.json').exists():state='completed'
        elif (p/'failed.json').exists():state='failed'
        elif j['name'] in active:state='running'
        status.append(dict(name=j['name'],state=state,pid=active[j['name']][0].pid if j['name'] in active else None))
    tmp=ROOT/'status.tmp';tmp.write_text(json.dumps(status,indent=2));tmp.replace(ROOT/'status.json')
for j in jobs:
    p=ROOT/j['name']
    if any((p/f).exists() for f in ['completed.json','failed.json']):continue
    if not (p/'launch.json').exists():continue
    pid=json.loads((p/'launch.json').read_text())['pid']
    procdir=Path('/proc')/str(pid)
    try:
        command=(procdir/'cmdline').read_bytes().replace(b'\x00',b' ').decode()
        if str((procdir/'cwd').resolve())==str(p) and LMP in command and 'mpirun' in command:
            active[j['name']]=(AdoptedProcess(pid),None)
            event(j['name']+' ADOPT existing pid='+str(pid))
        elif (p/'final.bin').exists() and 'VALIDATION_RUN_COMPLETED' in (p/'log.lammps').read_text(errors='replace'):
            (p/'completed.json').write_text(json.dumps(dict(valid=True,time=time.time(),recovered=True)))
    except FileNotFoundError:
        if (p/'final.bin').exists() and 'VALIDATION_RUN_COMPLETED' in (p/'log.lammps').read_text(errors='replace'):
            (p/'completed.json').write_text(json.dumps(dict(valid=True,time=time.time(),recovered=True)))
event('Queue start: max 16 simultaneous jobs, 2 MPI ranks/job')
while True:
    for name,(proc,out) in list(active.items()):
        rc=proc.poll()
        if rc is None:continue
        if out is not None:out.close()
        p=ROOT/name
        good=rc==0 and (p/'final.bin').exists() and 'VALIDATION_RUN_COMPLETED' in (p/'log.lammps').read_text(errors='replace')
        (p/('completed.json' if good else 'failed.json')).write_text(json.dumps(dict(returncode=rc,time=time.time(),valid=good),indent=2))
        event(name+' '+('COMPLETED' if good else 'FAILED'))
        del active[name]
    pending=[j for j in jobs if j['name'] not in active and not any((ROOT/j['name']/f).exists() for f in ['completed.json','failed.json'])]
    if not (ROOT/'STOP_NEW_JOBS').exists() and shutil.disk_usage(str(ROOT)).free>50*1024**3:
        while len(active)<16 and pending:
            j=pending.pop(0);p=ROOT/j['name']
            # Existing log without a terminal marker means interrupted work: do not overwrite it.
            if (p/'log.lammps').exists():
                (p/'failed.json').write_text(json.dumps(dict(reason='Existing production log; explicit restart required')))
                event(j['name']+' SKIPPED existing production log');continue
            out=open(str(p/'screen.log'),'w')
            cmd=[MPIRUN,'-np','2',LMP,'-in','in.production','-log','log.lammps','-nonbuf']
            proc=subprocess.Popen(cmd,cwd=str(p),env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
            (p/'launch.json').write_text(json.dumps(dict(pid=proc.pid,command=cmd,time=time.time()),indent=2))
            active[j['name']]=(proc,out);event(j['name']+' START pid='+str(proc.pid))
    save()
    if not active and not pending:break
    if not active and (ROOT/'STOP_NEW_JOBS').exists():event('Queue stopped by STOP_NEW_JOBS');break
    time.sleep(15)
event('Queue finished')
