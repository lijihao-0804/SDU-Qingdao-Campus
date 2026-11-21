"""Metre-scale interlocking clay tiles with a varying, dielectric fired surface."""
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
from qd_spring_surfaces import add_image

from functools import lru_cache

@lru_cache(maxsize=1)
def tile_maps():
    # Each tile is 26 cm wide with 36 cm exposed downslope; laps overlap the next course.
    q=512
    y,x=(np.mgrid[:q,:q]+.5)/q
    row=np.floor(6*y).astype(int)
    v=(6*y)%1
    u=(8*x+.12*(row%2))%1
    # Clay-roll profile and the capillary channel meet smoothly at tile boundaries.
    roll=(.5+.5*np.cos(2*np.pi*(u-.13)))**2.3
    channel=np.exp(-((u-.69)/.085)**2)
    lip=np.exp(-((v-.92)/.064)**2)
    relief=.012*roll-.0035*channel+.0034*lip+.0040*v
    rng=np.random.default_rng(86029)
    noise=gaussian_filter(rng.normal(size=(q,q)),1.7,mode='wrap');noise/=noise.std()
    tiles=rng.uniform(-1,1,(6,8))[row,(8*x+.12*(row%2)).astype(int)%8]
    height=relief+.000065*noise
    du=(np.roll(height,-1,1)-np.roll(height,1,1))*q/(2*2.08)
    dv=(np.roll(height,-1,0)-np.roll(height,1,0))*q/(2*2.16)
    n=np.stack([-du,dv,np.ones_like(du)],axis=-1);n/=np.linalg.norm(n,axis=2,keepdims=True)
    normal=Image.fromarray(np.uint8(np.clip(127.5+127.5*n,0,255)))
    col=np.uint8(np.clip(242+tiles*7+roll*7-lip*9-channel*4+noise*1.3,0,255))
    base=Image.fromarray(np.repeat(col[:,:,None],3,axis=2))
    # A narrow band on the fired crest retains its glaze. Weathering breaks it
    # at the lower lip and varies by tile. At distance the mip averages stay dull.
    broad=gaussian_filter(noise,7,mode='wrap');broad/=broad.std()
    crest=np.clip((roll-.72)/.28,0,1)**2
    glaze=crest*np.clip(.78+.17*tiles+.08*broad,0,1)*(1-.86*lip)
    rough=np.clip(.75-.055*roll-.14*glaze+.048*channel+.030*lip+.018*tiles+.005*noise,.53,.86)
    raw=np.zeros((q,q,3),np.uint8)
    raw[:,:,0]=np.rint(255*glaze).astype(np.uint8)  # KHR_materials_clearcoat reads red.
    raw[:,:,1]=np.rint(255*rough).astype(np.uint8)  # glTF roughness reads green.
    return base,normal,Image.fromarray(raw)

def bind(scene):
    _,_,mr=tile_maps()
    surface=add_image(scene,'陶瓦 · 迎光凸棱与风化瓦沟',mr,'PNG',True)
    mats=[m for m in scene.doc['materials'] if m.get('extras',{}).get('archFinish')=='clay']
    for mat in mats:
        mat['pbrMetallicRoughness'].update(metallicFactor=0.,roughnessFactor=1.,metallicRoughnessTexture=surface)
        mat['normalTexture']['scale']=1.
        optics=mat.setdefault('extensions',{})
        optics['KHR_materials_clearcoat']={'clearcoatFactor':.035,'clearcoatTexture':surface,
                                          'clearcoatRoughnessFactor':.57,'clearcoatNormalTexture':dict(mat['normalTexture'])}
        optics['KHR_materials_specular']={'specularFactor':.14}
        mat['extras']['tileFinish']='烧结陶瓦 · 瓦脊局部薄釉与风化瓦沟'
    used=scene.doc.setdefault('extensionsUsed',[])
    for extension in ('KHR_materials_clearcoat','KHR_materials_specular'):
        if extension not in used:used.append(extension)
    return len(mats)

