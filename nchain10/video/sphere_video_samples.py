from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'sphere_analysis'
sys.path.insert(0,str(OUT/'video_runtime'))
import cv2
from PIL import Image,ImageDraw
panels=[];videos=[]
for path in sorted(ROOT.glob('*.avi'),key=lambda p:float(p.stem)):
    cap=cv2.VideoCapture(str(path));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
    videos.append({'file':path.name,'frames':n,'fps':fps,'seconds':n/fps if fps else None})
    for frac in [0,.25,.5,.75,.99]:
        idx=min(n-1,int(n*frac));cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,bgr=cap.read()
        if ok:
            im=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB));im.thumbnail((390,310))
            tile=Image.new('RGB',(400,340),'white');tile.paste(im,((400-im.width)//2,25));ImageDraw.Draw(tile).text((8,7),f'F={path.stem}, frame={idx}/{n}',fill='black');panels.append(tile)
    cap.release()
canvas=Image.new('RGB',(400*5,340*len(videos)),'white')
for i,p in enumerate(panels):canvas.paste(p,((i%5)*400,(i//5)*340))
canvas.save(OUT/'video_samples.jpg')
(OUT/'video_metadata.json').write_text(json.dumps(videos,indent=2),encoding='utf-8')
print(json.dumps(videos))
