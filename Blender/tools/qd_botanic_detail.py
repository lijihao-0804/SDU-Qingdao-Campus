"""Metric bark lenticels and folded grass-blade ribs, shared across plant instances."""
from collections import defaultdict

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from qd_spring_surfaces import add_image

WHITE_BARK = {'#c7c7bc','#d9d9c9','#dad9ca','#deded0'}
BARK = {'#77756e','#9a9686','#887565','#725c56','#715e50','#846c5d','#696256'}
GRASS = '校园春草 · 叶鞘与渐浅叶尖'
BLADE_UV = ((.12,1.),(.88,1.),(.01,.41),(.99,.41),(.5,0.))


def _normal(dx,dy):
    n=np.stack((-dx,dy,np.ones_like(dx)),axis=-1)
    n/=np.linalg.norm(n,axis=-1,keepdims=True)
    return Image.fromarray(np.uint8(np.clip((n+1)*127.5,0,255)))


def bark_maps(white):
    # One repeat covers 0.52 m horizontally and 0.62 m along the trunk.
    # Horizontal lenticels and a few larger scars follow the bark; a whitewash
    # softens their colour while allowing the underlying contour to read.
    rng=np.random.default_rng(20781)
    h,w=384,384
    y,x=np.mgrid[:h,:w]/np.array([h,w])[:,None,None]
    grain=rng.normal(size=(h,w))
    long=gaussian_filter(grain,(15,3),mode='wrap')
    long/=max(long.std(),1.e-8)
    height=.05*long
    albedo=(246 if white else 242)+long*(1.4 if white else 3.)
    for i in range(102):
        u,v=rng.uniform(0,1,2)
        dx=(x-u+.5)%1-.5;dy=(y-v+.5)%1-.5
        width=rng.uniform(.010,.051)*(1.65 if i%13==0 else 1.)
        thick=rng.uniform(.0018,.0049)
        centre=dy-.09*dx-.0017*np.cos(dx/width*3+i)
        disk=np.exp(-(dx/width)**4-(centre/thick)**2)
        rim=np.exp(-(dx/(width*1.08))**4-((centre-thick*1.3)/(thick*1.2))**2)
        albedo-=disk*(rng.uniform(14,27) if white else rng.uniform(28,51))
        albedo+=rim*(2 if white else 5)
        height+=.14*rim-.38*disk
    rgb=np.stack((albedo+.8,albedo,albedo-.6),axis=-1)
    dx=np.roll(height,-1,1)-np.roll(height,1,1)
    dy=np.roll(height,-1,0)-np.roll(height,1,0)
    return Image.fromarray(np.uint8(np.clip(rgb,0,255))),_normal(dx,dy)


def grass_maps():
    y,x=np.mgrid[:192,:64]/np.array([191,63])[:,None,None]
    mid=.50+.037*np.sin(y*5.)*(1-y)
    ridge=np.exp(-((x-mid)/.064)**2)
    border=np.minimum(x,1-x)
    veins=np.cos((x-mid)*np.pi*18)*.9*(1-.54*y)
    tone=241.+6*ridge-11*np.exp(-border/.045)+veins+3*(1-y)
    color=np.stack((tone-.7,tone,tone-1.8),axis=-1)
    dx=.095*np.tanh((x-mid)*9)+.08*(x-mid)/.064*ridge
    return Image.fromarray(np.uint8(np.clip(color,0,255))),_normal(dx,np.zeros_like(dx))


def _positions(scene,index):
    a=scene.doc['accessors'][index]
    b=scene.doc['bufferViews'][a['bufferView']]
    return np.frombuffer(scene.raw,'<f4',a['count']*3,b.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,3).copy()


def bind(scene):
    materials=scene.doc['materials']
    meshes_by_slot=defaultdict(set)
    kinds_by_slot=defaultdict(set)
    kinds_by_mesh=defaultdict(set)
    for n in scene.doc['nodes']:
        if 'mesh' in n:
            kinds_by_mesh[n['mesh']].add(n.get('extras',{}).get('kind'))
    for i,mesh in enumerate(scene.doc['meshes']):
        for prim in mesh['primitives']:
            slot=prim['material']
            meshes_by_slot[slot].add(i)
            kinds_by_slot[slot].update(kinds_by_mesh[i])
    images={}
    for i,m in enumerate(materials):
        key=m['name']
        if key==GRASS:
            role='grassBlade'
        elif key in WHITE_BARK|BARK and kinds_by_slot[i]=={'flora'}:
            role='whitewashedBark' if key in WHITE_BARK else 'cherryBark'
        else:
            continue
        if m.get('extras',{}).get('botanicSurface')==role:
            continue
        if role not in images:
            if role=='grassBlade':
                color,normal=grass_maps();name='近景春草 · 纵脉与叶缘';repeat=False
            else:
                color,normal=bark_maps(role=='whitewashedBark')
                name='树皮 · 白干下的皮孔' if role=='whitewashedBark' else '树皮 · 横向皮孔与浅痕'
                repeat=True
            images[role]=(add_image(scene,name,color,'PNG',repeat),add_image(scene,name+'法线',normal,'PNG',repeat))
        base,normal=images[role]
        m['pbrMetallicRoughness']['baseColorTexture']=base
        m['normalTexture']={**normal,'scale':.38 if role=='whitewashedBark' else .53}
        m.setdefault('extras',{})['botanicSurface']=role
        for mi in sorted(meshes_by_slot[i]):
            for prim in scene.doc['meshes'][mi]['primitives']:
                if prim['material']!=i:
                    continue
                attrs=prim['attributes']
                if role=='grassBlade':
                    if 'TEXCOORD_0' in attrs:
                        continue
                    count=scene.doc['accessors'][attrs['POSITION']]['count']
                    if count%5:
                        raise ValueError('Unexpected grass blade topology.')
                    uv=np.tile(BLADE_UV,(count//5,1))
                else:
                    x,y,z=_positions(scene,attrs['POSITION']).T
                    uv=np.column_stack(((.79*x+.61*z)/.52,y/.62))
                attrs['TEXCOORD_0']=scene.accessor(uv,'<f4','VEC2',5126,34962)
