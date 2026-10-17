"""Compile/test supplied serial baseline and OpenMP source in isolated directories.

Python 3 standard library only. Usage: python validate.py --compiler gfortran
No production input or output is modified. Timings are short local benchmarks.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time

P = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--compiler', default='gfortran')
parser.add_argument('--steps', type=int, default=2000)
parser.add_argument('--threads', default='1,2,4')
args = parser.parse_args()
if args.steps < 1:
    parser.error('--steps must be positive')
root = P/'validation'
root.mkdir(exist_ok=True)
original = P/'reference_original' if (P/'reference_original').exists() else P.parent
initial = P/'initial.xyz' if (P/'initial.xyz').exists() else P.parent/'initial.xyz'
compiler = str(Path(args.compiler).resolve()) if Path(args.compiler).exists() else args.compiler
env = os.environ.copy()
env['PATH'] = str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
env.update(BD_SEED='123456', BD_STEPS=str(args.steps), BD_SAVE=str(args.steps),
           OMP_DYNAMIC='FALSE', OMP_PROC_BIND='close', OMP_PLACES='cores')

def clean(path):
    result=[]
    for line in path.read_bytes().decode('utf-8',errors='replace').splitlines():
        quote=None
        for index,char in enumerate(line):
            if char in ("'", '"'):
                if quote==char: quote=None
                elif quote is None: quote=char
            elif char=='!' and quote is None:
                line=line[:index];break
        if line.strip():result.append(line.rstrip())
    return '\n'.join(result)+'\n'


# Baseline: original equations and loops, fixed seed, short run, defined
# diagnostic density, and wider step output only. No force/integrator edits.
refmod=clean(original/'module.f90').replace('CALL SYSTEM_CLOCK(COUNT = clock)', 'clock = 123456')
refsrc=clean(original/'bd_read.f90')
refsrc=refsrc.replace('CALL Evolve_Sample(1000000000)',f'iSave={args.steps}\nCALL Evolve_Sample({args.steps})')
refsrc=refsrc.replace('volume = BoxSize(1) * BoxSize(2) * BoxSize(3)',
                      'volume = BoxSize(1) * BoxSize(2) * BoxSize(3)\ndensity=N/volume')
refsrc=refsrc.replace("'(a,I9,a,3E23.15)'", "'(a,I10,a,3E23.15)'")

def compile_run(name, module, source, flags, threads):
    d=root/name;d.mkdir(exist_ok=True)
    (d/'module.f90').write_text(module,encoding='ascii')
    (d/'bd_read.f90').write_text(source,encoding='ascii')
    shutil.copy2(initial,d/'initial.xyz')
    exe=d/('bd.exe' if os.name=='nt' else 'bd')
    command=[compiler,*flags,'-ffree-line-length-none','module.f90','bd_read.f90','-o',str(exe)]
    result=subprocess.run(command,cwd=d,env=env,capture_output=True,text=True)
    (d/'compile.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(f'Compile failed: {d}/compile.log')
    runenv=env.copy();runenv['OMP_NUM_THREADS']=str(threads)
    start=time.perf_counter()
    result=subprocess.run([str(exe)],cwd=d,env=runenv,capture_output=True,text=True,timeout=180)
    elapsed=time.perf_counter()-start
    (d/'run.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(f'Run failed: {d}/run.log')
    snapshot=d/f'out-{args.steps:010d}.xyz'
    data=snapshot.read_bytes()
    coords=[[float(v) for v in line.split()[1:]] for line in data.decode().splitlines()[2:]]
    if not all(math.isfinite(v) for row in coords for v in row):
        raise RuntimeError(f'Non-finite coordinates: {snapshot}')
    return dict(seconds=elapsed,sha256=hashlib.sha256(data).hexdigest(),coords=coords)

flags=['-O3','-ffp-contract=off']
results={}
reference=compile_run('reference',refmod,refsrc,flags,1)
results['reference']=reference
for threads in [int(t) for t in args.threads.split(',')]:
    r=compile_run(f'omp_{threads}',(P/'module.f90').read_text(),(P/'bd_read.f90').read_text(),
                  flags+['-fopenmp'],threads)
    r['max_coordinate_error_vs_original']=max(abs(a-b) for x,y in zip(reference['coords'],r['coords']) for a,b in zip(x,y))
    r['speedup_vs_original']=reference['seconds']/r['seconds']
    results[f'omp_{threads}']=r
    print(f'Threads {threads}: {r["seconds"]:.3f}s, speedup {r["speedup_vs_original"]:.3f}, '
          f'max error {r["max_coordinate_error_vs_original"]:.3g}',flush=True)
debug=compile_run('debug',(P/'module.f90').read_text(),(P/'bd_read.f90').read_text(),
                  ['-O0','-g','-fopenmp','-fcheck=all','-fbacktrace','-ffpe-trap=invalid,zero,overflow'],4)
results['debug']=debug
for value in results.values():value.pop('coords')
report=dict(steps=args.steps,seed=123456,compiler=subprocess.check_output([compiler,'--version'],env=env,text=True).splitlines()[0],
            results=results)
(root/'results.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
if len({r['sha256'] for k,r in results.items() if k.startswith('omp_')}) != 1:
    raise RuntimeError('OpenMP thread counts produced different snapshots')
if any(r['max_coordinate_error_vs_original'] > 1.e-10 for k,r in results.items() if k.startswith('omp_')):
    raise RuntimeError('Coordinates differ from serial baseline by more than 1e-10')
