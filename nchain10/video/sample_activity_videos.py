from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'activity_analysis_20261013'
sys.path.insert(0,str(ROOT/'sphere_analysis'/'video_runtime'))
import cv2
from PIL import Image,ImageDraw
meta=[]
for F in [2,4,6,7,8,9]:
    cap=cv2.VideoCapture(str(ROOT/('%s.avi'%F)));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS);tiles=[]
    meta.append(dict(F=F,frames=n,fps=fps,width=cap.get(3),height=cap.get(4)))
    for idx in [0,min(50,n-1),int(n*.5),int(n*.75),n-1]:
        cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,frame=cap.read()
        if not ok:continue
        im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));im.thumbnail((500,440));tile=Image.new('RGB',(500,470),'white');tile.paste(im,((500-im.width)//2,30));ImageDraw.Draw(tile).text((8,8),'F=%s frame=%d/%d'%(F,idx,n),fill='black');tiles.append(tile)
    canvas=Image.new('RGB',(500*len(tiles),470),'white')
    for j,im in enumerate(tiles):canvas.paste(im,(500*j,0))
    canvas.save(OUT/('video_F%s_samples.jpg'%F));cap.release()
(OUT/'video_metadata.json').write_text(json.dumps(meta,indent=2));print(meta)
