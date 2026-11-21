"""Panel cladding joints and recessed daylight glazing from the campus residential photographs."""
from io import BytesIO
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from qd_spring_surfaces import add_image
from qd_geometry import lin

PANEL={'#b2644c':'#b97458','#b77261':'#c5816d','#a45b48':'#a65f4c'}
GLASS=('#516671','#687b83')
def tile():
    rng=np.random.default_rng(7112);h,w=512,768
    yy,xx=np.mgrid[0:h,0:w];sx,sy=w/2,h/4
    # Fine dark bedding lines surround the larger matte façade panels.
    dx=np.minimum(xx%sx,sx-xx%sx);dy=np.minimum(yy%sy,sy-yy%sy)
    edge=np.minimum(dx,dy);joint=np.exp(-(edge/1.23)**2)
    grains=rng.normal(size=(h,w));tone=np.array([[.1,1.9],[-.9,1.1],[.5,-1.2],[-.6,1.]])[(yy//sy).astype(int),(xx//sx).astype(int)]
    plate=248.-43*joint+tone+1.7*gaussian_filter(grains,1.4,mode='wrap')+1.1*grains
    base=Image.fromarray(np.repeat(np.uint8(np.clip(plate,0,255))[:,:,None],3,axis=2))
    height=1-joint
    xn=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*.32
    yn=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*.32
    n=np.stack([-xn,yn,np.ones_like(xn)],axis=-1);n/=np.linalg.norm(n,axis=-1,keepdims=True)
    normal=Image.fromarray(np.uint8(np.clip(127.5*(n+1),0,255)))
    return base,normal

def bind(doc):
    base,normal=tile()
    channel=add_image(doc,'红陶墙板 · 细缝与板面',base,'JPEG',True)
    bump=add_image(doc,'红陶墙板 · 接缝倒角',normal,'PNG',True)
    ids={doc.colors[name] for name in PANEL if name in doc.colors}
    def values(idx):
        a=doc.doc['accessors'][idx];v=doc.doc['bufferViews'][a['bufferView']]
        return np.frombuffer(doc.raw,dtype='<f4',count=a['count']*3,offset=v['byteOffset']).reshape(-1,3).copy()
    for mesh in doc.doc['meshes']:
        for p in mesh['primitives']:
            if p['material'] not in ids:continue
            pt=values(p['attributes']['POSITION']);n=values(p['attributes']['NORMAL'])
            x,y,z=pt.T;nx,ny,nz=n.T
            lateral=np.where(np.abs(nx)>np.abs(nz),z,-x)
            u=np.where(np.abs(ny)>.72,x,lateral)/4.8;v=np.where(np.abs(ny)>.72,z,-y)/2.68
            p['attributes']['TEXCOORD_0']=doc.accessor(np.column_stack((u,v)),'<f4','VEC2',5126,34962)
    for name,rgb in PANEL.items():
        if name not in doc.colors:continue
        mat=doc.doc['materials'][doc.colors[name]]
        factor=[lin(int(rgb[j:j+2],16)/255.) for j in (1,3,5)]
        mat['pbrMetallicRoughness'].update(baseColorTexture=channel,baseColorFactor=factor+[1.],roughnessFactor=.76)
        mat['normalTexture']={'index':bump['index'],'scale':.47}
    return {'wallPanelMaterials':len(ids),'glazingColours':sum(name in doc.colors for name in GLASS)}
