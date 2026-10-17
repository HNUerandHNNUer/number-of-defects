from pathlib import Path
import sys,json
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'nchain10/video/sphere_analysis/video_runtime'))
import cv2
meta=[]
for n,fs in [(10,[.1,1,5,10]),(30,[.1,1,5,10]),(100,[.1,1,5,10]),(200,[.03,.1,1,5,10]),(300,[.03,.1,1,5,10]),(350,[0,.003,.03])]:
 canvas=Image.new('RGB',(4*410,len(fs)*355),'white');draw=ImageDraw.Draw(canvas)
 for row,F in enumerate(fs):
  paths=list((ROOT/f'nchain{n}'/'video').glob(f'{F:g}.avi'));p=paths[0] if paths else ROOT/f'nchain{n}/video/{F:g}.avi';cap=cv2.VideoCapture(str(p));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
  record=dict(n=n,F=F,path=str(p),frames=count,fps=fps,samples=[])
  for col,q in enumerate([.1,.4,.7,.95]):
   k=int(q*max(0,count-1));cap.set(cv2.CAP_PROP_POS_FRAMES,k);ok,im=cap.read();record['samples'].append(dict(frame=k,read=bool(ok)))
   if ok:
    pic=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB));pic.thumbnail((410,325));canvas.paste(pic,(col*410,row*355+28))
   draw.text((col*410+5,row*355+5),f'n={n} F={F:g} frame={k}/{count} ({q:.0%})',fill='black')
  cap.release();meta.append(record)
 canvas.save(OUT/f'video_n{n}.jpg',quality=93)
 print('video',n,flush=True)
# Short contiguous windows: visual evidence of motion, not just separated snapshots.
for n,F,frac in [(10,.1,.75),(10,5,.75),(200,10,.7),(300,10,.7)]:
 p=ROOT/f'nchain{n}/video/{F:g}.avi';cap=cv2.VideoCapture(str(p));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));start=int(frac*count);cap.set(cv2.CAP_PROP_POS_FRAMES,start)
 canvas=Image.new('RGB',(5*330,4*290),'white');draw=ImageDraw.Draw(canvas)
 for k in range(20):
  ok,im=cap.read();col=k%5;row=k//5
  if ok:
   pic=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB));pic.thumbnail((330,260));canvas.paste(pic,(col*330,row*290+25))
  draw.text((col*330+3,row*290+3),f'n={n} F={F} frame={start+k}',fill='black')
 cap.release();canvas.save(OUT/f'filmstrip_n{n}_F{F}.jpg',quality=93)
(OUT/'video_inventory.json').write_text(json.dumps(meta,indent=2))
