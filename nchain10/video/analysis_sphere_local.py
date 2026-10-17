from pathlib import Path
import json, csv, hashlib, importlib.util, sys
import numpy as np
try:
    import cv2
except ImportError:
    cv2=None
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'sphere_analysis'
OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('sphere_kernel',ROOT/'sphere_nematic_parallel_large_v4.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
rows=[]; details={}
for folder in sorted((ROOT/'results_evolution').iterdir(),key=lambda p: float(p.name) if p.is_dir() else 1e9):
    if not folder.is_dir():continue
    lines=(folder/'polymer.data').read_text().splitlines()
    first=next(i for i,s in enumerate(lines) if s.strip()=='Atoms')+2
    atoms=np.array([[float(x) for x in s.split()] for s in lines[first:first+300]])
    coords=atoms[:,3:6];r=np.linalg.norm(coords,axis=1);u=coords/r[:,None]
    chains=coords.reshape(10,30,3);bond=np.linalg.norm(np.diff(chains,axis=1),axis=2)
    d=mod.chain_directors(u,30,mod.Settings())
    # Best axis for circumferential alignment: minimize mean(a dot d)^2.
    vals,vecs=np.linalg.eigh(d.T@d/len(d));axis=vecs[:,0]
    if axis[2]<0:axis=-axis
    azi=np.cross(axis,u);aznorm=np.linalg.norm(azi,axis=1);azi/=aznorm[:,None]
    align=float(np.mean(2*np.einsum('ij,ij->i',azi,d)**2-1))
    circulation=float(np.mean(np.einsum('ij,ij->i',np.cross(u,d),np.broadcast_to(axis,u.shape))))
    result=mod.identify(coords,settings=mod.Settings())
    mask=result['mask'];pos=result['positions'][mask]/result['diagnostics']['radius'];charges=result['double_charge'][mask]/2
    tab=np.loadtxt(folder/'defect_results.dat',skiprows=1)
    counts=tab[:,4];neg=tab[:,2];steps=tab[:,0]
    late=tab[steps>=steps[-1]/2]
    row=dict(activity=float(folder.name),radius=float(r.mean()),nominal_radius=7.675492-2.5,n_frames=len(tab),last_step=int(steps[-1]),physical_time=float(steps[-1]*.01),fraction_four=float(np.mean(counts==4)),fraction_extra_pairs=float(np.mean(neg>0)),mean_defects=float(counts.mean()),max_defects=int(counts.max()),late_fraction_four=float(np.mean(late[:,4]==4)),late_mean_defects=float(late[:,4].mean()),contour_length=float(bond.sum(axis=1).mean()),end_to_end=float(np.linalg.norm(chains[:,-1]-chains[:,0],axis=1).mean()),initial_azimuthal_nematic=align,initial_signed_circulation=circulation)
    rows.append(row)
    internal=chains[:,2:]-chains[:,:-2]
    internal/=np.linalg.norm(internal,axis=2)[:,:,None]
    torque=np.cross(chains[:,1:-1],internal).sum(axis=(0,1))
    drag_tensor=(np.sum(coords*coords,axis=1)[:,None,None]*np.eye(3)-coords[:,:,None]*coords[:,None,:]).sum(axis=0)
    omega=np.linalg.solve(1000*drag_tensor,torque)
    details[folder.name]={'initial_file_sha256':hashlib.sha256((folder/'polymer.data').read_bytes()).hexdigest(),'axis':axis.tolist(),'director_eigenvalues':vals.tolist(),'initial_defect_positions_unit':pos.tolist(),'initial_defect_charges':charges.tolist(),'initial_defect_polar_cosine':(pos@axis).tolist(),'initial_diagnostics':result['diagnostics'],'initial_active_torque_per_F':torque.tolist(),'initial_omega_per_F_no_noise_or_clipping':omega.tolist(),'row':row}
with (OUT/'summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
(OUT/'initial_and_counts.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
print(json.dumps({'summary':rows,'initial_axes':{k:v['axis'] for k,v in details.items()},'initial_defects':{k:[v['initial_defect_charges'],v['initial_defect_polar_cosine']] for k,v in details.items()}},indent=2))
if cv2 is None:
    print('OpenCV unavailable: counts and initial geometry saved; video extraction requires another runtime.')
    sys.exit(0)
videos=[]; panels=[]
for path in sorted(ROOT.glob('*.avi'),key=lambda p:float(p.stem)):
    cap=cv2.VideoCapture(str(path));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
    videos.append({'file':path.name,'frames':n,'fps':fps,'seconds':n/fps if fps else None})
    for frac in [0,.25,.5,.75,.99]:
        idx=min(n-1,int(n*frac));cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,bgr=cap.read()
        if ok:
            im=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB));im.thumbnail((310,270))
            tile=Image.new('RGB',(320,300),'white');tile.paste(im,((320-im.width)//2,25));ImageDraw.Draw(tile).text((8,7),f'F={path.stem}, frame={idx}/{n}',fill='black');panels.append(tile)
    cap.release()
canvas=Image.new('RGB',(320*5,300*len(videos)),'white')
for i,p in enumerate(panels):canvas.paste(p,((i%5)*320,(i//5)*300))
canvas.save(OUT/'video_samples.jpg')
(OUT/'video_metadata.json').write_text(json.dumps(videos,indent=2),encoding='utf-8')
print(json.dumps({'summary':rows,'initial_axes':{k:v['axis'] for k,v in details.items()},'initial_defects':{k:[v['initial_defect_charges'],v['initial_defect_polar_cosine']] for k,v in details.items()},'videos':videos},indent=2))
