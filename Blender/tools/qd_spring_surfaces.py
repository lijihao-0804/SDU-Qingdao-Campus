"""Embed a seamless mown sward and a transparent leafy shoot in glTF, in metre-scale UVs."""
import io
import math
import random
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import gaussian_filter
from qd_canopy import LEAF

def leaves():
    size=512;rng=random.Random(50614)
    image=Image.new('RGBA',(size,size),(139,162,96,0));draw=ImageDraw.Draw(image)
    def xy(p):return tuple(round(v) for v in p)
    def stalk(a,b,w):draw.line([xy(a),xy(b)],fill=(123,111,73,255),width=w)
    def leaf(x,y,dx,dy,span):
        n=math.hypot(dx,dy);nx,ny=-dy/n,dx/n
        off=rng.uniform(-.065,.065)*n;points=[]
        for t in np.linspace(0,1,9):
            rad=math.sin(math.pi*t)**.9*span+off*math.sin(math.pi*t)
            points.append(xy((x+dx*t+nx*rad,y+dy*t+ny*rad)))
        for t in np.linspace(1,0,9):
            rad=-math.sin(math.pi*t)**.9*span*.83+off*math.sin(math.pi*t)
            points.append(xy((x+dx*t+nx*rad,y+dy*t+ny*rad)))
        value=rng.uniform(.84,1.14);col=tuple(min(255,round(c*value)) for c in (143,166,91))+(255,)
        draw.polygon(points,fill=col)
        # The midrib divides unequal blade surfaces, with secondary veins
        # curving toward the tip. Retain the original outer alpha silhouette.
        darker=tuple(round(v*f) for v,f in zip(col[:3],(.89,.94,.88)))+(255,)
        draw.polygon([xy((x,y)),*points[:9],xy((x+dx,y+dy))],fill=darker)
        draw.line([xy((x,y)),xy((x+dx*.87,y+dy*.87))],fill=tuple(min(255,v+14) for v in col[:3])+(255,),width=1)
        for t in (.27,.46,.64):
            for sign in (-1,1):
                w=sign*span*math.sin(math.pi*t)*.64
                vein=[xy((x+t*dx,y+t*dy)),
                      xy((x+(t+.06)*dx+nx*w*.55,y+(t+.06)*dy+ny*w*.55)),
                      xy((x+(t+.14)*dx+nx*w,y+(t+.14)*dy+ny*w))]
                draw.line(vein,fill=tuple(min(255,v+7) for v in col[:3])+(255,),width=1)
    root=np.array([230.,506.])
    # A compound spray is assembled from unequal woody shoots carrying broad leaves.
    # Empty pockets between their tips survive both the alpha cutoff and mip filters.
    for tip,mid,turn in [((110,116),(179,299),-.2),((256,45),(226,246),.1),((430,184),(317,300),.36),((44,268),(117,357),-.5),((360,93),(281,268),.36)]:
        end=np.array(tip,dtype=float);knee=np.array(mid,dtype=float)
        stalk(root,knee,4);stalk(knee,end,3)
        for j in range(8):
            t=.12+j*.114
            if t<.52:
                origin=root+(knee-root)*(t/.52);line=knee-root
            else:
                origin=knee+(end-knee)*((t-.52)/.48);line=end-knee
            angle=math.atan2(line[1],line[0])+(-1 if j%2 else 1)*rng.uniform(.63,1.35)+turn
            size=rng.uniform(51,72)*(1.-.22*t);span=rng.uniform(12.8,21.)*(1.-.18*t)
            leaf(*origin,math.cos(angle)*size,math.sin(angle)*size,span)
        leaf(*end,*(end-knee)/np.linalg.norm(end-knee)*43,12)
    return image

def lawn():
    rng=np.random.default_rng(602151);n=512
    def field(scale):
        v=gaussian_filter(rng.normal(size=(n,n)),scale,mode='wrap');return v/(v.std()+1e-6)
    broad=field(21)*2.5+field(5)*2.6+field(.74)*3.1
    rgb=np.stack([130+broad*1.2,158+broad,96+broad*.81],axis=-1)
    im=Image.fromarray(np.uint8(np.clip(rgb,0,255)));d=ImageDraw.Draw(im)
    for _ in range(20000):
        x,y=rng.integers(0,n,size=2);shade=rng.normal(0,12)
        color=tuple(int(np.clip(c+shade,0,255)) for c in (132,160,96))
        angle=rng.normal(-1.1,.77);length=rng.uniform(2,8.2)
        dx,dy=math.cos(angle)*length,math.sin(angle)*length
        for xx in ([x,x+n] if x<9 else [x,x-n] if x>n-9 else [x]):
            for yy in ([y,y+n] if y<9 else [y,y-n] if y>n-9 else [y]):
                d.line((xx,yy,xx+dx,yy+dy),fill=color,width=1)
    return im

def add_image(doc,name,im,format,repeat):
    target=io.BytesIO()
    if format=='JPEG':im.save(target,format,quality=91,subsampling=0)
    else:im.save(target,format)
    data=target.getvalue()
    while len(doc.raw)%4:doc.raw.append(0)
    v=len(doc.doc['bufferViews']);doc.doc['bufferViews'].append(dict(buffer=0,byteOffset=len(doc.raw),byteLength=len(data)));doc.raw.extend(data)
    images=doc.doc.setdefault('images',[]);i=len(images)
    images.append(dict(name=name,mimeType='image/jpeg' if format=='JPEG' else 'image/png',bufferView=v))
    samplers=doc.doc.setdefault('samplers',[]);s=len(samplers)
    samplers.append(dict(wrapS=10497 if repeat else 33071,wrapT=10497 if repeat else 33071,minFilter=9987,magFilter=9729))
    tex=doc.doc.setdefault('textures',[]);key=len(tex);tex.append(dict(source=i,sampler=s))
    return {'index':key}

def bind(doc):
    turf=add_image(doc,'春草 · 修剪草皮',lawn(),'JPEG',True)
    foliage=add_image(doc,'春梢 · 阔叶新梢',leaves(),'PNG',False)
    leafmat=doc.doc['materials'][doc.colors[LEAF]]
    leafmat.update(alphaMode='MASK',alphaCutoff=.29,doubleSided=True)
    leafmat['pbrMetallicRoughness'].update(baseColorFactor=[1,1,1,1],baseColorTexture=foliage,roughnessFactor=.88)
    keys={'grass':(1.,1.,1.),'#87a173':(.89,.94,.84),'#8faa70':(.96,.99,.90),'#93ac72':(.97,1.,.91),'#91a275':(.93,.96,.88)}
    roles={doc.colors[k]:val for k,val in keys.items() if k in doc.colors}
    count=0
    for m in doc.doc['meshes']:
        for pr in m['primitives']:
            if pr['material'] not in roles:continue
            acc=doc.doc['accessors'][pr['attributes']['POSITION']]
            b=doc.doc['bufferViews'][acc['bufferView']]
            pts=np.frombuffer(doc.raw,dtype='<f4',count=acc['count']*3,offset=b['byteOffset']).reshape(-1,3).copy()
            x,z=pts[:,0],pts[:,2]
            # Metric UVs follow the terrain over cell and polygon boundaries.
            pr['attributes']['TEXCOORD_0']=doc.accessor(np.column_stack((x*.42+z*.15,z*.42-x*.15)),'<f4','VEC2',5126,34962)
            v=.50+.23*np.sin(x*.049+np.sin(z*.071))+.16*np.sin(z*.091+x*.038)+.10*np.cos(x*.022-z*.033)
            color=np.column_stack((.84+.145*v,.89+.106*v,.79+.17*v))
            pr['attributes']['COLOR_0']=doc.accessor(color,'<f4','VEC3',5126,34962)
            count+=1
    for i,col in roles.items():
        doc.doc['materials'][i]['pbrMetallicRoughness'].update(baseColorFactor=[*col,1],baseColorTexture=turf,roughnessFactor=.96)
    return dict(texturedLawnPrimitives=count,grassTileMetres=2.24,leafAtlasPixels=512)

