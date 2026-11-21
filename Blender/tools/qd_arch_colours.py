"""Embed calibrated architectural finishes in the portable model, in metre-scale UVs."""
import copy
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from qd_geometry import lin
from qd_spring_surfaces import add_image

ROOT = Path(__file__).resolve().parents[1]
ROLES = { # Chinese label, roughness, metalness, texture repeat in metres
    'stone': ('建筑石材', .905, 0., (3.84, 2.40)),
    'granite': ('花岗岩', .855, 0., (3.0, 1.68)),
    'clay': ('陶瓦', .68, 0., (2.08, 2.16)),
    'brick': ('砖面', .93, 0., (2.08, 1.28)),
    'panel': ('陶板', .89, 0., None),
    'deck': ('屋面面层', .94, 0., (5.4, 5.4)),
    'metal': ('金属', .58, 0., None),
    'glass': ('玻璃', .22, 0., None),
    'ink': ('哑光题字', .92, 0., None),
}
# Only identified bare stainless steel and zinc trim expose a metallic surface.
# Enamelled stadium panels and powder-coated frames reflect through their binder.
BARE_METALS = {('图书馆','adb4af'):(.37,.98), ('会文与淦昌','91948b'):(.52,.89),
               ('第周苑','78878a'):(.48,.91)}
SPECULAR = {'stone':0., 'granite':0., 'brick':0., 'panel':0., 'deck':0.,
            'metal':0., 'glass':.93, 'ink':0.}
SKYLIGHT_GLASS={'274b61','30596c','39697d','244b60'}
COBALT_GLASS={'274781','315997','2a4b84','426bb0'}
LANDMARKS = {'way-868015914':'双创中心','way-1020621360':'凤凰居六角亭','way-982199336':'训练馆','library':'图书馆','museum':'博物馆','huagang':'公共教学苑','zhensheng':'公共教学苑',
             'song_arena':'体育馆','east_gate':'校门','south_gate':'校门','west_gate':'校门','north_gate':'校门','assembly':'会堂','xiyuan':'曦园'}

def family(n):
    e=n['extras'];key=e.get('key','');name=n['name']
    if e.get('surface')=='parkBuilding':return '海滨构筑'
    if key in LANDMARKS:return LANDMARKS[key]
    if e['kind']!='building':return None
    if name.startswith(('会文','淦昌')):return '会文与淦昌'
    if key=='s2-research-m':return '研究院M区'
    if name.startswith('专家公寓'):return '专家公寓'
    if name.startswith('第周'):return '第周苑'
    if e.get('refinedResidence'):
        return ('晨园' if key=='s2-b6' else '阅海居' if key.startswith('s2-') else '凤凰居')
    return '其他建筑'

def texture_set(role):
    rng=np.random.default_rng(81+list(ROLES).index(role));q=512
    y,x=np.mgrid[:q,:q]/q
    grain=rng.standard_normal((q,q))
    broad=gaussian_filter(grain,12,mode='wrap');broad/=broad.std()
    def edge(v):return np.minimum(v%1,1-v%1)
    rough_map=None
    if role=='clay':
        from qd_v6_roof import tile_maps
        return (*tile_maps()[:2],None)
    elif role=='deck':
        seam=np.exp(-(edge(5*x)/.018)**2)
        lum=245+1.1*broad+1.4*grain-7*seam
        height=.14*grain-.36*seam
    else:
        cols,rows=(4,4) if role!='brick' else (8,16)
        yy=y*rows;xx=x*cols+.5*(np.floor(yy)%2)
        joints=np.exp(-(edge(xx)/(.014 if role!='brick' else .040))**2)+np.exp(-(edge(yy)/(.018 if role!='brick' else .055))**2)
        cells=rng.uniform(-2.8,2.8,(rows,cols))[yy.astype(int)%rows,np.floor(xx).astype(int)%cols]
        crystals=gaussian_filter(grain,.54,mode='wrap')
        lum=244+1.35*cells+2.15*broad+crystals*(7.4 if role=='granite' else 3.3)-joints*(17 if role!='brick' else 13)
        height=.045*crystals-joints*.44
        if role in ('stone','granite'):
            # A honed limestone face, and a more granular exposed stone base.
            # Slab-to-slab differences persist in mipmaps; grain stays subtle.
            mineral=gaussian_filter(grain,1.2,mode='wrap')
            mineral=np.tanh(mineral/mineral.std())
            rough=(ROLES[role][1]+.012*broad+.009*cells+.055*np.minimum(joints,1)
                   +(.043 if role=='granite' else .011)*mineral)
            packed=np.zeros((q,q,3),np.uint8)
            packed[:,:,1]=np.rint(255*np.clip(rough,.75,.98)).astype(np.uint8)
            rough_map=Image.fromarray(packed)
    lum=np.uint8(np.clip(lum,0,255))
    base=Image.fromarray(np.repeat(lum[...,None],3,axis=2))
    dx=np.roll(height,-1,1)-np.roll(height,1,1);dy=np.roll(height,-1,0)-np.roll(height,1,0)
    normal=np.stack([-dx,dy,np.ones_like(dx)],axis=2);normal/=np.linalg.norm(normal,axis=2,keepdims=True)
    return base,Image.fromarray(np.uint8(np.clip((normal+1)*127.5,0,255))),rough_map

def bind_uv(scene,prim,role,scale):
    def values(idx):
        a=scene.doc['accessors'][idx];v=scene.doc['bufferViews'][a['bufferView']]
        return np.frombuffer(scene.raw,'<f4',count=a['count']*3,offset=v['byteOffset']).reshape(-1,3).copy()
    attrs=prim['attributes'];pos=values(attrs['POSITION']);normal=values(attrs['NORMAL'])
    x,y,z=pos.T;nx,ny,nz=normal.T
    h=np.hypot(nx,nz);sloped=(abs(ny)>.045)&(h>.04)
    # The tile course direction is perpendicular to the local fall line. Coplanar
    # faces share world-unit phase, including rotated wings and opposing slopes.
    if role=='clay':
        ut=np.column_stack((nz,np.zeros_like(nz),-nx))/np.maximum(h,.0001)[:,None]
        vt=np.cross(normal,ut)
        u=np.where(sloped,(pos*ut).sum(1),x);v=np.where(sloped,(pos*vt).sum(1),z)
        # Aerial views resolve broad, faint differences between fired batches.
        # Object-space colour is continuous across adjoining triangles and UV seams.
        if 'COLOR_0' not in attrs:
            patina=.5+.23*np.sin(.19*x+.113*z)+.17*np.cos(.083*x-.14*z)+.10*np.cos(.057*x+.22*z)
            rgb=1-patina[:,None]*np.array([.043,.069,.082])
            attrs['COLOR_0']=scene.accessor(rgb,'<f4','VEC3',5126,34962)
    else:
        lateral=(x*nz-z*nx)/np.maximum(h,.0001)
        u=np.where(abs(ny)>.74,x,lateral);v=np.where(abs(ny)>.74,z,-y)
    attrs['TEXCOORD_0']=scene.accessor(np.column_stack((u/scale[0],v/scale[1])),'<f4','VEC2',5126,34962)

def finish_plaza_paving(scene):
    """Carry the existing pale stone through the plaza, with world-scale slab joints."""
    materials=scene.doc['materials']
    granite=next(m for m in materials if m.get('extras',{}).get('archFinish')=='granite'
                 and 'normalTexture' in m)
    replacements={}
    for node in scene.doc['nodes']:
        names=({'#c9c3b5'} if node['name']=='石材广场与步行带' else
               {'#cac7b6'} if node.get('extras',{}).get('key')=='yuxian' else set())
        if not names:
            continue
        for prim in scene.doc['meshes'][node['mesh']]['primitives']:
            idx=prim['material'];old=materials[idx]
            if old['name'].lower() not in names:
                continue
            if idx not in replacements:
                mat=copy.deepcopy(old)
                mat['name']='广场浅色石板 · '+old['name']
                mat['extras']={**old.get('extras',{}),'sourceSurface':old['name']}
                mat['normalTexture']=dict(granite['normalTexture'],scale=.15)
                source_pbr=granite['pbrMetallicRoughness']
                mat['pbrMetallicRoughness'].update(baseColorTexture=source_pbr['baseColorTexture'],
                                                   metallicRoughnessTexture=source_pbr['metallicRoughnessTexture'],
                                                   roughnessFactor=1.,metallicFactor=0.)
                mat['extensions']=copy.deepcopy(granite['extensions'])
                replacements[idx]=len(materials)
                materials.append(mat)
            prim['material']=replacements[idx]
            bind_uv(scene,prim,'granite',(3.6,1.8))
    return len(replacements)

def sample_photos(config):
    samples=[]
    for file,patches in config['samples']:
        path=next((ROOT/'实景参照').rglob(file))
        with Image.open(path) as raw:
            im=raw.convert('RGB');w,h=im.size
            for x,y,label in patches:
                coords=(round((x-2)/320*w),round((y-2)/162*h),round((x+2)/320*w),round((y+2)/162*h))
                rgb=np.median(np.asarray(im.crop(coords)).reshape(-1,3),axis=0).astype(int)
                samples.append(dict(photo=path.relative_to(ROOT).as_posix(),surface=label,box=coords,
                                    observedSRGB='#'+''.join(f'{a:02x}' for a in rgb)))
    return samples

def bind(scene):
    config=json.loads((ROOT/'data/建筑饰面选色.json').read_text('utf8'));groups={}
    for name,surfaces in config['groups'].items():
        palette={}
        for role,entries in surfaces.items():
            for entry in entries.split():
                source,target=entry.split('=');palette[source]=(role,target)
        groups[name]=palette
    tiles={};variants={};owners=[];mats=scene.doc['materials']
    for n in scene.doc['nodes']:
        group=family(n)
        if group is None:continue
        roles=Counter()
        for prim in scene.doc['meshes'][n['mesh']]['primitives']:
            idx=prim['material'];old=mats[idx];source=old['name'].lower().lstrip('#')
            if source not in groups[group]:continue
            role,rgb=groups[group][source];label,rough,metal,scale=ROLES[role]
            if (group,idx) not in variants:
                mat=copy.deepcopy(old);mat['name']=f'{group}·{label}·{source}'
                mat['extras']={'archFinish':role,'sourceSurface':old['name'],'architectureGroup':group}
                values=mat['pbrMetallicRoughness']
                if role=='metal':
                    rough,metal=BARE_METALS.get((group,source),(.90,0.))
                if role=='glass':
                    if source in SKYLIGHT_GLASS:rough=.25
                    elif source in COBALT_GLASS:rough=.19
                if role in SPECULAR:
                    mat.setdefault('extensions',{})['KHR_materials_specular']={'specularFactor':1. if metal>.8 else SPECULAR[role]}
                values.update(baseColorFactor=[lin(int(rgb[k:k+2],16)/255) for k in (0,2,4)]+[1.],
                              roughnessFactor=rough,metallicFactor=metal)
                if scale:
                    if role not in tiles:
                        base,norm,rough_map=texture_set(role)
                        tiles[role]=(add_image(scene,label+' · 色泽',base,'JPEG',True),
                                     add_image(scene,label+' · 微表面',norm,'PNG',True),
                                     add_image(scene,label+' · 板面与细缝粗糙度',rough_map,'PNG',True)
                                     if rough_map is not None else None)
                    values['baseColorTexture']=tiles[role][0]
                    mat['normalTexture']=dict(**tiles[role][1],scale=.18 if role=='stone' else .24)
                    if tiles[role][2] is not None:
                        values.update(roughnessFactor=1.,metallicRoughnessTexture=tiles[role][2])
                variants[group,idx]=len(mats);mats.append(mat)
            prim['material']=variants[group,idx];roles[role]+=1
            if scale:bind_uv(scene,prim,role,scale)
        if not roles:raise ValueError('No mapped building finishes: '+n['name'])
        owners.append(dict(key=n['extras'].get('key'),name=n['name'],family=group,roles=roles))
    from qd_v6_roof import bind as finish_roofs
    coated=finish_roofs(scene)
    plaza_finishes=finish_plaza_paving(scene)
    from qd_raw_arch_finishes import bind as finish_raw_parts
    raw_count=finish_raw_parts(scene)
    result=dict(satinTileMaterials=coated,method=config['basis'],samples=sample_photos(config),buildings=owners,materials=len(variants),
        roles=list(ROLES),embeddedPairs=list(tiles))
    (ROOT/'data/建筑配色取样.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    return {'plazaPavingFinishes':plaza_finishes,'finishBuildings':len(owners),'architecturalMaterials':len(variants),
            'rawArchitecturalMaterials':raw_count,'surfaceAtlasPairs':len(tiles)}

