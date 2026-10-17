from pathlib import Path
import subprocess, struct, json
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent; OUT=Path(__file__).resolve().parent
ffmpeg=r'C:\Users\wxd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
meta={}; fig,axs=plt.subplots(2,3,figsize=(15,8))
for row,name in enumerate(['parallel','serial']):
    video=ROOT/'F_25_bd_cpu2'/name/'defect_out/1.avi'; data=video.read_bytes()[:1000]; i=data.index(b'avih')+8
    h=struct.unpack_from('<14I',data,i); fps=1e6/h[0]; n=h[4]; meta[name]={'frames':n,'fps':fps}
    for ax,fraction in zip(axs[row],[0,.5,.99]):
        ix=int((n-1)*fraction); target=OUT/f'{name}_video_{ix}.png'
        subprocess.run([ffmpeg,'-v','error','-y','-ss',str(ix/fps),'-i',str(video),'-frames:v','1',str(target)],check=True)
        ax.imshow(Image.open(target)); ax.set_title(f'{name}, video frame {ix}/{n}'); ax.axis('off')
fig.tight_layout(); fig.savefig(OUT/'video_contact_sheet.png',dpi=130)
(OUT/'video_metadata.json').write_text(json.dumps(meta,indent=2)); print(meta)
