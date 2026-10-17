from pathlib import Path
import sys,json
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'nchain10/video/sphere_analysis/video_runtime'))
import cv2
OUT=Path(__file__).resolve().parent
meta=[]
for n in [100,150,200,250,300,350]:
 canvas=Image.new('RGB',(5*320,5*265),'white');draw=ImageDraw.Draw(canvas)
 for row,f in enumerate(['0.003','0.1','1','5','10']):
  path=ROOT/f'nchain{n}'/'video'/f'{f}.avi'
  cap=cv2.VideoCapture(str(path));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
  meta.append(dict(label=n,F=f,frames=count,fps=fps,path=str(path)))
  for col,q in enumerate([.05,.25,.5,.75,.95]):
   cap.set(cv2.CAP_PROP_POS_FRAMES,int(q*max(0,count-1)));ok,im=cap.read()
   if ok:
    im=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB));im.thumbnail((320,235));canvas.paste(im,(320*col,265*row+25))
   draw.text((320*col+5,265*row+4),f'folder={n} F={f} video={q:.0%}',fill='black')
  cap.release()
 canvas.save(OUT/f'video_{n}.jpg')
(OUT/'video_metadata.json').write_text(json.dumps(meta,indent=2))
