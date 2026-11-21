"""Finish uncatalogued architectural parts in their own slots, using the authored part names."""
import copy
from functools import lru_cache
import re

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

LANDSCAPE=re.compile('绿岛修剪|绿岛植土|修剪绿岛|绿篱|矮篱|植栽|花灌|花木|草坪|草地(?!石边)|草皮|屋顶绿化|种植土|树冠|树枝|树干|乔木|植被|树叶|灌木|花瓣|草花|planting|foliage|shrub|hedge|tree crown',re.I)
HARDWARE=re.compile('旗杆|铜片|铜板|不锈钢|锌板|铝板|铝框|铝合金|金属框|金属格栅|金属封边|金属收边|金属支架|把手|实心钢|钢索|钢缆|钢管|金属杆|stainless|galvanized|patinated copper',re.I)
PANE=re.compile('玻璃|玻窗|窗扇|窗芯|侧窗|深蓝窗|窗玻|暗窗|采光带|光伏|集热板|分层窗带|glaz|glasses|glass|window panes?',re.I)
TRIM=re.compile('框|梃|梴|横档|窗套|窗台|窗洞|边缘|饰条|窗罩|过梁|金属封边|背面石|frames?|mullions?|jamb|cill|sill|lintel',re.I)
FIRED=re.compile('红瓦|陶瓦|铺瓦坡面|瓦脊收口|瓦顶|fired tile|clay tile',re.I)

# These attachments contain unlike materials in one mesh. The original
# palette identifies the tubular handrail even where a branch helper made it.
ANNEX={'#a46153':'matte','#535859':'metal','#c6c2b4':'matte',
       '#adab9b':'matte','#919269':'plant','#505758':'metal'}
BASEMENT={'#bab7a8':'matte','#a9aaa0':'matte','#536166':'glass',
          '#83847c':'matte','#adae9f':'matte','#72746e':'matte'}
INDOOR={'#9c5b59':'courtFinish','风雨操场 · 内侧漫射采光带':'luminaire',
        '#c0c7be':'paintedSteel','#b3c0b6':'paintedSteel',
        '#747f78':'metal','#7d8982':'metal'}

def attachment_palette(node):
    e=node.get('extras',{})
    if e.get('arenaSouth')=='retaining':return BASEMENT
    if e.get('kind')=='plazaDetail' and e.get('owner')=='way-982199358':return ANNEX
    if e.get('sportHall')=='floor':return INDOOR
    return {}

@lru_cache(maxsize=4096)
def part_hint(name):
    if LANDSCAPE.search(name):return 'plant'
    if HARDWARE.search(name):return 'metal'
    if TRIM.search(name):return 'matte'
    if PANE.search(name):return 'glass'
    if FIRED.search(name):return 'clay'
    return 'matte'

def architectural_node(node):
    e=node.get('extras',{})
    return (bool(attachment_palette(node)) or e.get('kind') in ('building','worksCabin') or
            e.get('surface') in ('settlement','parkBuilding') or
            (e.get('kind')=='landmark' and e.get('key') not in ('blue_track','east_track','yuxian')))

def mineral_tile():
    rng=np.random.default_rng(18853)
    grain=rng.normal(size=(256,256))
    mottling=gaussian_filter(grain,7,mode='wrap')
    mottling/=mottling.std()
    sand=gaussian_filter(grain,.68,mode='wrap')
    tone=245+2.4*mottling+4.4*sand
    color=Image.fromarray(np.repeat(np.clip(tone,0,255).astype('uint8')[:,:,None],3,axis=2))
    relief=gaussian_filter(grain,.82,mode='wrap')*.18
    dx=np.roll(relief,-1,1)-np.roll(relief,1,1)
    dy=np.roll(relief,-1,0)-np.roll(relief,1,0)
    normal=np.stack([-dx,dy,np.ones_like(dx)],axis=-1)
    normal/=np.linalg.norm(normal,axis=2,keepdims=True)
    return color,Image.fromarray(np.uint8(127.5+127.5*normal))

def bind(scene):
    from qd_arch_colours import bind_uv
    from qd_geometry import GLAZING_ROUGHNESS
    from qd_video_horizon import CLAY as DISTANT_TILE
    from qd_spring_surfaces import add_image
    mats=scene.doc['materials']
    fired=next((m for m in mats if m.get('extras',{}).get('archFinish')=='clay'),None)
    raw={};plaster=None
    for node in scene.doc['nodes']:
        if 'mesh' not in node or not architectural_node(node):continue
        region=node.get('extras',{}).get('surface','')
        palette=attachment_palette(node)
        for prim in scene.doc['meshes'][node['mesh']]['primitives']:
            idx=prim['material'];old=mats[idx];extras=old.get('extras',{})
            if 'archFinish' in extras or 'rawArchFinish' in extras:continue
            name=old['name'].lower()
            hints=scene.part_finishes.get(id(prim),set())
            treatment=palette.get(name)
            if treatment in ('courtFinish','luminaire'):
                prim.setdefault('extras',{})['sportSurface']=treatment
                continue
            if treatment=='plant' or (treatment is None and ('plant' in hints or name=='grass')):
                prim.setdefault('extras',{})['landscapePart']=True
                continue
            if treatment:role='matte' if treatment=='paintedSteel' else treatment
            elif name in GLAZING_ROUGHNESS or (region=='settlement' and name in ('#697982','#8e999b')):role='glass'
            elif region=='settlement' and name in DISTANT_TILE:role='clay'
            elif 'metal' in hints:role='metal'
            elif 'glass' in hints:role='glass'
            elif 'clay' in hints:role='clay'
            else:role='matte'
            cache_key=(idx,role,treatment=='paintedSteel')
            if cache_key not in raw:
                mat=copy.deepcopy(old);pbr=mat['pbrMetallicRoughness']
                label='涂装钢构' if treatment=='paintedSteel' else {'matte':'矿物饰面','glass':'窗玻璃','clay':'红瓦','metal':'金属'}[role]
                mat['name']='建筑构件·'+label+'·'+old['name']
                mat['extras']={**extras,'rawArchFinish':role,'sourceSurface':old['name']}
                optics=mat.setdefault('extensions',{})
                if role=='clay':
                    if fired is None:raise ValueError('缺少红瓦基准材质')
                    for channel in ('baseColorTexture','metallicRoughnessTexture'):
                        pbr[channel]=fired['pbrMetallicRoughness'][channel]
                    pbr.update(roughnessFactor=1.,metallicFactor=0.)
                    mat['normalTexture']=dict(fired['normalTexture'])
                    mat['extensions']=copy.deepcopy(fired['extensions'])
                elif role=='matte':
                    pbr.update(metallicFactor=0.,roughnessFactor=.94)
                    optics['KHR_materials_specular']={'specularFactor':0.}
                    if treatment=='paintedSteel':
                        mat['extras']['surfaceTreatment']=treatment
                    elif 'baseColorTexture' not in pbr:
                        if plaster is None:
                            c,n=mineral_tile()
                            plaster=(add_image(scene,'干燥矿物饰面 · 细砂色差',c,'JPEG',True),
                                     add_image(scene,'干燥矿物饰面 · 亚毫米起伏',n,'PNG',True))
                        pbr['baseColorTexture']=plaster[0]
                        mat['normalTexture']=dict(plaster[1],scale=.15)
                else:
                    pbr.update(metallicFactor=.9 if role=='metal' else 0.,
                               roughnessFactor=.51 if role=='metal' else .23)
                    optics['KHR_materials_specular']={'specularFactor':.93 if role=='glass' else 1.}
                raw[cache_key]=len(mats);mats.append(mat)
            prim['material']=raw[cache_key]
            if role=='clay':bind_uv(scene,prim,'clay',(2.08,2.16))
            elif role=='matte' and treatment!='paintedSteel' and 'baseColorTexture' not in old['pbrMetallicRoughness']:
                bind_uv(scene,prim,role,(2.75,2.75))
    return len(raw)
