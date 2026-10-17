"""Apply the established F=1 pipeline to the newly supplied full trajectories."""
from pathlib import Path
import types,sys,json
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'activity_analysis_20261013'
source=(ROOT/'postprocess_compression.py').read_text(encoding='utf-8')
source=source.replace('DT=.01; H=1.5; GRID_N=512','ACTIVE_F=1.; ACTIVE_SEED=190835668\nDT=.01; H=1.5; GRID_N=512')
source=source.replace('np.linalg.solve(1000*A,tau)','np.linalg.solve(1000*A,ACTIVE_F*tau)')
source=source.replace("'F':1,'gamma':1000,'temperature':1,'seed':190835668","'F':ACTIVE_F,'gamma':1000,'temperature':1,'seed':ACTIVE_SEED")
source=source.replace('Instantaneous active-torque predictor (F=1)','Instantaneous active-torque predictor')
(OUT/'generalized_pipeline_source.py').write_text(source,encoding='utf-8')
mod=types.ModuleType('activity_pipeline');mod.__file__=str(ROOT/'postprocess_compression.py');sys.modules[mod.__name__]=mod;exec(compile(source,mod.__file__,'exec'),mod.__dict__)
provenance=json.loads((OUT/'provenance.json').read_text())
for F in [2,4,6,7,8,9]:
    mod.ACTIVE_F=F;mod.ACTIVE_SEED=next(p['production_seed'] for p in provenance if p['F']==F)
    mod.SOURCE=ROOT.parent/'gpu2'/('F_%s'%F)/'defect_out';mod.OUT=OUT/('F_%s'%F);mod.OUT.mkdir(exist_ok=True)
    if (mod.OUT/'summary.json').exists() and (mod.OUT/'05_structural_evolution.png').exists():print('Already completed F=',F,flush=True);continue
    print('START F=',F,'source=',mod.SOURCE,flush=True);mod.main()
