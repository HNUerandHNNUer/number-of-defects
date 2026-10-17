from fixed_grid import *
import ast
from scipy.optimize import linear_sum_assignment
source=(ROOT/'cpu5_validation_20261015/fine_worker.py').read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='track');exec(compile(ast.Module(body=[node]),'<track>','exec'))
case=sys.argv[1];level=int(sys.argv[2]);h=1.5
window=sys.argv[3] if len(sys.argv)>3 else 'late'
dat=np.load(str(ROOT/'cpu5_validation_20261015/final_analysis_cpu5'/(case+'__'+window+'.npz')));v,g=mesh(level);seq=[];counts=[]
if window!='late':case+='__'+window
cache=OUT/('%s_L%d_full.json'%(case,level))
if cache.exists():raw=json.loads(cache.read_text())
else:
 raw=[]
 for k,x in enumerate(dat['xyz']):
  r=detect(x,v,g,h);raw.append(r)
  if k%100==0:print(case,level,k,flush=True)
 cache.write_text(json.dumps(raw,separators=(',',':')))
R=raw[0]['radius']
for k,r in enumerate(raw):
 seq.append({str(s):[p for p,q in zip(r['positions'],r['charges']) if q==s] for s in (-1,1)})
 counts.append(dict(case=case,level=level,step=int(dat['steps'][k]),Nplus=r['Nplus'],Nminus=r['Nminus'],fallback=r['fallback'],composite=r['composite']))
rows=[]
for stride in (1,10,100):
 for gate in (.75,1.5,3.):
  for sign in (-1,1):
   res,tracks=track(seq[::stride],dat['steps'][::stride],sign,gate);res.update(case=case,level=level,every=stride*100,gate=gate,sign=sign,mean_count=np.mean([len(z[str(sign)]) for z in seq[::stride]]));rows.append(res)
pd.DataFrame(rows).to_csv(OUT/('%s_L%d_tracking.csv'%(case,level)),index=False)
pd.DataFrame(counts).to_csv(OUT/('%s_L%d_counts.csv'%(case,level)),index=False)
print('COMPLETE',case,level,flush=True)
