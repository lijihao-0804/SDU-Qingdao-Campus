"""Split playing colour, fencing and lights for the eastern courts captured in clip V3."""
from math import ceil,cos,pi,sin
import numpy as np
from PIL import Image,ImageDraw
from qd_spring_surfaces import add_image
WIRE='#426c66'

def tennis(s,w,d):
    for hand in (-1,1):
        z=hand*(d/2-.16)
        span=w*.97;count=max(1,round(span/2.75))
        for i in range(count+1):
            x=span*(i/count-.5)
            s.cyl('网球场端网立柱',x,1.59,z,.058,3.12,'#506e69',8)
        s.box('端网顶部压管',0,3.11,z,span,.054,.06,'#52736b')
        s.mesh('球场围网',[(x,y,z) for x,y in [(-span/2,.12),(span/2,.12),(span/2,3.09),(-span/2,3.09)]],[(0,1,2,3)],WIRE)
    # Shared side fence sits inside the local eastern margin to avoid double
    # mesh along adjacent courts. Players enter through the central opening.
    x=w/2-.10
    for side in (-1,1):
        a=side*1.35;b=side*(d/2-.2)
        s.mesh('球场围网',[(x,.12,a),(x,.12,b),(x,2.78,b),(x,2.78,a)],[(0,1,2,3)],WIRE)
        s.box('球场侧网压管',x,2.82,(a+b)/2,.07,.065,abs(b-a),'#52736b')
        for t in np.linspace(0,1,int(abs(b-a)/2.85)+2):
            s.cyl('球场侧网柱',x,1.42,a+(b-a)*t,.053,2.8,'#506e69',8)
    for hand in (-1,1):
        x=hand*(w/2-.45);z=hand*d*.225
        s.cyl('白色照明柱',x,4.92,z,.105,9.8,'#d0d7d1',10)
        s.box('灯头横臂',x-hand*.48,9.73,z,.98,.096,.1,'#b7c1c2')
        s.box('场地矩形投光灯',x-hand*.89,9.70,z,.50,.23,.57,'#c6cdcb')

def bind(scene):
    if WIRE not in scene.colors:return
    n=256;yy,xx=np.mgrid[:n,:n]
    a=np.minimum((xx+yy)%32,32-(xx+yy)%32)
    b=np.minimum((xx-yy)%32,32-(xx-yy)%32)
    alpha=np.uint8(np.clip(2.55-np.minimum(a,b),0,1)*255)
    rgb=np.ones((n,n,4),np.uint8)*255;rgb[:,:,3]=alpha
    tex=add_image(scene,'球场围网 · 钢丝菱网',Image.fromarray(rgb),'PNG',True)
    idx=scene.colors[WIRE];mat=scene.doc['materials'][idx]
    mat.update(alphaMode='MASK',alphaCutoff=.34)
    mat['pbrMetallicRoughness'].update(baseColorTexture=tex,roughnessFactor=.67)
    def getv(i):
        a=scene.doc['accessors'][i];v=scene.doc['bufferViews'][a['bufferView']]
        return np.frombuffer(scene.raw,'<f4',count=a['count']*3,offset=v['byteOffset']).reshape(-1,3).copy()
    for m in scene.doc['meshes']:
        for p in m['primitives']:
            if p['material']!=idx:continue
            pos=getv(p['attributes']['POSITION']);norm=getv(p['attributes']['NORMAL'])
            u=np.where(abs(norm[:,0])>.5,pos[:,2],pos[:,0]);uv=np.column_stack((u,-pos[:,1]))/.88
            p['attributes']['TEXCOORD_0']=scene.accessor(uv,'<f4','VEC2',5126,34962)

