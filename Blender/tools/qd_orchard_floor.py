"""Blend spring grass, loam and mulch in the photographed orchards, on the original terrain TIN."""
from collections import defaultdict
from pathlib import Path
import math
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import distance_transform_edt,gaussian_filter
from shapely.geometry import Polygon
from shapely.ops import unary_union
from qd_geometry import Shape
from qd_spring import SITES
from qd_spring_surfaces import add_image,lawn

LABEL='园下草土 · '
def regions(domain):
    return {s.key:Polygon(s.polygon).intersection(domain) for s in SITES}

def bind(doc,terrain,plots):
    stats={};fine=np.asarray(lawn(),dtype=np.float32)
    centres=defaultdict(list)
    for n in doc.doc['nodes']:
        ex=n.get('extras',{})
        if ex.get('kind')=='flora' and ex.get('site') in plots and (not ex['shrub'] or ex.get('species')=='蓝莓'):
            x,_,z=n['translation'];centres[ex['site']].append((x,z))
    moods={'spring_north_cherries':(.93,2.9),'spring_student_farm':(.83,2.2),
           'spring_arena_orchard':(.66,2.15),'spring_huagang_grove':(.76,2.4),'spring_yuehai_walk':(.63,1.7)}
    for k,(site,plot) in enumerate(plots.items()):
        if plot.is_empty:continue
        x0,z0,x1,z1=plot.bounds
        ppm=14;w,h=math.ceil((x1-x0)*ppm)+4,math.ceil((z1-z0)*ppm)+4
        px=np.arange(w,dtype=np.float32)[None,:];pz=np.arange(h,dtype=np.float32)[:,None]
        x=x0+(px-1.5)/ppm;z=z0+(pz-1.5)/ppm
        u=np.floor((x*.42+z*.15)*512).astype(int)%512;v=np.floor((z*.42-x*.15)*512).astype(int)%512
        turf=fine[v,u,:]
        def pixel(xx,zz):return (round((xx-x0)*ppm+1.5),round((zz-z0)*ppm+1.5))
        mask=Image.new('L',(w,h),0);d=ImageDraw.Draw(mask)
        parts=[plot] if plot.geom_type=='Polygon' else list(plot.geoms)
        for part in parts:
            if part.geom_type!='Polygon':continue
            d.polygon([pixel(a,b) for a,b in part.exterior.coords],fill=255)
            for hole in part.interiors:d.polygon([pixel(a,b) for a,b in hole.coords],fill=0)
        edge=np.minimum(1,distance_transform_edt(np.asarray(mask)>0)/(ppm*3.8));edge=edge*edge*(3-2*edge)
        dots=np.ones((h,w),bool)
        for tx,tz in centres[site]:
            xx,zz=pixel(tx,tz)
            if 0<=xx<w and 0<=zz<h:dots[zz,xx]=False
        dist=distance_transform_edt(dots)/ppm
        power,radius=moods[site]
        rng=np.random.default_rng(71450+k);grain=rng.normal(size=(h,w)).astype(np.float32)
        def noise(scale):
            field=gaussian_filter(grain,scale,mode='reflect');return field/(field.std()+1.e-6)
        strata=noise(15);fibre=noise(2.2)
        rim=np.sin(x*1.25+z*.82)*.12+strata*.22
        broad=np.maximum(0,1-(dist/(radius*3.0+rim))**1.7)
        if site=='spring_north_cherries':broad=.31+.69*broad
        blend=np.clip(broad*power+(.11*strata+.063*fibre)*broad,0,.96)*edge
        if site=='spring_student_farm':blend=np.minimum(1.,blend+(.09+.09*np.cos(x*3.3+z*.74))*edge)
        base=np.exp(-(dist/.62)**2)
        granular=.7*grain+1.6*fibre+2.7*strata
        ground=np.stack([154-16*base+granular*1.13,134-15*base+granular,99-14*base+granular*.76],axis=-1)
        rgb=turf*(1-blend[:,:,None])+ground*blend[:,:,None]
        tex=Image.fromarray(np.uint8(np.clip(rgb,0,255)))
        material=LABEL+site;token=add_image(doc,material,tex,'JPEG',False)
        skin=Shape(material);terrain.skin(skin,plot,material,0)
        doc.node(material,shape=skin,kind='ground')
        mi=doc.colors[material];mat=doc.doc['materials'][mi]
        mat['pbrMetallicRoughness'].update(baseColorTexture=token,baseColorFactor=[1,1,1,1],roughnessFactor=.95)
        for prim in doc.doc['meshes'][-1]['primitives']:
            a=doc.doc['accessors'][prim['attributes']['POSITION']]
            view=doc.doc['bufferViews'][a['bufferView']]
            pts=np.frombuffer(doc.raw,dtype='<f4',count=a['count']*3,offset=view['byteOffset']).reshape(-1,3).copy()
            xx,zz=pts[:,0],pts[:,2]
            prim['attributes']['TEXCOORD_0']=doc.accessor(np.column_stack((((xx-x0)*ppm+2)/w,((zz-z0)*ppm+2)/h)),'<f4','VEC2',5126,34962)
            t=.50+.23*np.sin(xx*.049+np.sin(zz*.071))+.16*np.sin(zz*.091+xx*.038)+.10*np.cos(xx*.022-zz*.033)
            prim['attributes']['COLOR_0']=doc.accessor(np.column_stack((.84+.145*t,.89+.106*t,.79+.17*t)),'<f4','VEC3',5126,34962)
        stats[site]=[w,h]
    return stats
