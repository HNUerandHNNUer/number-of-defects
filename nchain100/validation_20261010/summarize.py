from pathlib import Path
import json,csv,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
r=json.loads((P/'results.json').read_text())
for row in r['dense_F25_stress']:
 d=P/f"stress_{row['method']}_{row['dt']}";step=int((d/'last.dump').read_text().splitlines()[1]);row['actual_step']=step;row['actual_time']=step*row['dt']
r['fortran_passive_chains']=json.loads((P/'fortran_chain_results.json').read_text())
r['shell_equilibrium']=json.loads((P/'shell_equilibrium_results.json').read_text())
r['backend_forces']=json.loads((P/'backend_results.json').read_text())
r['backend_noise']=json.loads((P/'backend_noise_results.json').read_text())
(P/'all_results.json').write_text(json.dumps(r,indent=2))
for key in ['diffusion','dense_F25_stress','passive_chains','fortran_passive_chains','shell_equilibrium','backend_forces','backend_noise']:
 rows=r[key]
 with (P/(key+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,axs=plt.subplots(1,3,figsize=(14,4.2))
for method,label in [('bd/audit/free','Custom (wall disabled)'),('brownian','Official Brownian')]:
 z=[v for v in r['diffusion'] if v['style']==method]
 axs[0].errorbar([a['dt'] for a in z],[a['D'] for a in z],yerr=[1.96*a['SE'] for a in z],fmt='o-',capsize=3,label=label)
axs[0].axhline(.001,color='black',ls='--');axs[0].set_ylabel('Diffusion coefficient (95% normal-approx. CI)')
for method in ['custom','official']:
 z=[v for v in r['shell_equilibrium'] if v['method']==method]
 axs[1].errorbar([a['dt'] for a in z],[a['radial_variance'] for a in z],yerr=[1.96*a['SE'] for a in z],fmt='o-',capsize=3,label=method)
axs[1].axhline(r['shell_equilibrium'][0]['exact_radial_variance'],color='black',ls='--');axs[1].set_ylabel('Radial second moment (95% approx. CI)')
for method,marker in [('custom','o'),('official','x')]:
 z=[v for v in r['dense_F25_stress'] if v['method']==method]
 axs[2].plot([a['dt'] for a in z],[a['actual_time'] for a in z],marker+'-',label=method)
 for a in z:
  if method=='custom':axs[2].annotate('guard' if a['halted'] else 'censored',(a['dt'],a['actual_time']),xytext=(3,8),textcoords='offset points',fontsize=8)
axs[2].axhline(1000,color='black',ls='--');axs[2].set_ylim(730,1080);axs[2].set_ylabel('F=25: time to r_bond > 1.42 or run end')
for ax in axs:ax.set_xlabel('Time step');ax.legend(fontsize=8);ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(P/'validation_summary.png',dpi=180)
manifest={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in P.glob('*.py')}
(P/'test_script_hashes.json').write_text(json.dumps(manifest,indent=2))
print('Exported merged JSON, CSV and figure; stress cases',len(r['dense_F25_stress']))
