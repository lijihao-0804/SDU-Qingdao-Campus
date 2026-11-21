"""Georeferenced 20-km Sentinel and relief context beyond the detailed campus."""
from pathlib import Path
from io import BytesIO
from urllib.request import urlopen,Request
import json,math
import numpy as np
import shapely
from PIL import Image
from shapely.geometry import Polygon,box,Point
from shapely.ops import unary_union
from shapely.prepared import prep
from skimage.measure import find_contours
from qd_terrain import face,polygons,worldpix
from qd_geometry import Shape
from qd_natural_finishes import apply_water
ROOT=Path(__file__).resolve().parents[1]
B=(-10000,-10000,10000,10000)
def sealine(maskPath):
    a=np.asarray(Image.open(maskPath).convert('L').resize((420,420),Image.Resampling.BILINEAR))>127
    a=np.pad(a,1);shape=Polygon()
    for ring in find_contours(a.astype('uint8'),.5):
        xy=[(B[0]+(col-.5)/420*(B[2]-B[0]),B[1]+(row-.5)/420*(B[3]-B[1])) for row,col in ring]
        p=Polygon(xy).buffer(0).simplify(23)
        if p.area>4000:shape=shape.symmetric_difference(p)
    return shape.buffer(0).intersection(box(*B))
def elevations():
    cache={};tileDir=ROOT/'data/terrain'
    def height(x,z):
        a,b=worldpix(x,z);a/=4;b/=4;k=(int(a)//256,int(b)//256)
        if k not in cache:
            tx,ty=k;f=tileDir/f'11-{tx}-{ty}.png'
            if not f.exists():
                url=f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/11/{tx}/{ty}.png'
                with urlopen(Request(url,headers={'User-Agent':'SDU-Qingdao-campus/1.0'}),timeout=30) as resp:raw=resp.read()
                Image.open(BytesIO(raw)).verify();f.write_bytes(raw)
            cache[k]=np.asarray(Image.open(f).convert('RGB'),dtype=float)
        p=cache[k][int(b)%256,int(a)%256]
        return max(-2,float(p[0]*256+p[1]+p[2]/256-32768))
    return height
def coastal_albedo(texture,domain,waterfront=None):
    from PIL import ImageDraw
    from scipy.ndimage import distance_transform_edt
    im=Image.open(texture).convert('RGB')
    width,height=im.size
    def pixel(pt):
        return ((pt[0]-B[0])*width/(B[2]-B[0])-.5,(pt[1]-B[1])*height/(B[3]-B[1])-.5)
    inside=Image.new('L',im.size,0);pen=ImageDraw.Draw(inside)
    for poly in polygons(domain):
        pen.polygon([pixel(pt) for pt in poly.exterior.coords],fill=255)
        for ring in poly.interiors:pen.polygon([pixel(pt) for pt in ring.coords],fill=0)
    # Match the meadow albedo at the surveyed area's edge, then recover the
    # satellite colour over 160 metres. Keep fine local tonal variation outside.
    d=distance_transform_edt(np.asarray(inside)==0,sampling=((B[3]-B[1])/height,(B[2]-B[0])/width))
    t=np.clip((d-1.5)/160,0,1);mix=(t*t*(3-2*t)).astype('float32')[:,:,None]
    rgb=np.asarray(im,dtype='float32');local=rgb.mean(axis=2,keepdims=True)
    tint=np.array([168,190,128],dtype='float32')+(local-118)*mix*.08
    if waterfront is not None:
        # Sand next to the shore should blend into the satellite's beach hue.
        sand=Image.new('L',im.size,0);brush=ImageDraw.Draw(sand)
        for p in polygons(waterfront.beach):
            brush.polygon([pixel(pt) for pt in p.exterior.coords],fill=255)
        near_sand=distance_transform_edt(np.asarray(sand)==0,sampling=((B[3]-B[1])/height,(B[2]-B[0])/width))
        weight=np.clip(1-near_sand/50,0,1).astype('float32')[:,:,None]
        tint=tint*(1-weight)+np.array([208,195,164],dtype='float32')*weight
    pixels=np.uint8(np.clip(tint*(1-mix)+rgb*mix,0,255))
    bb=BytesIO();Image.fromarray(pixels).save(bb,format='JPEG',quality=91,subsampling=0);return bb.getvalue()
def add(doc,terrain,domain,nearOcean,nearBounds,waterfront=None):
    tex=ROOT/'assets/海岸环境.jpg';mask=ROOT/'assets/海陆掩膜.png'
    if not tex.exists() or not mask.exists():raise FileNotFoundError('20km coastal image and sea mask are required')
    ocean=sealine(mask).difference(nearBounds).union(nearOcean).buffer(0)
    # The park and the ocean have coincident shores. Floating overlays on
    # those 160 m cells can invert an almost-zero sliver into a full tile.
    # An explicit millimetre grid is well below both the DEM and GLB precision.
    dry=shapely.difference(shapely.difference(box(*B),ocean,grid_size=.001),domain,grid_size=.001)
    # The animated shallow strip replaces the far-water face geometrically.
    offshore=ocean.difference(waterfront.surf.area) if waterfront is not None else ocean
    sh=Shape('鳌山湾与黄海');ocean_mat='鳌山湾 · 外海水色';face(sh,offshore,ocean_mat,-terrain.datum-.02)
    doc.node(sh.name,shape=sh,kind='sea')
    s=np.array([67,113,131])/255
    clr=np.where(s<.04045,s/12.92,((s+.055)/1.055)**2.4)
    sea_material=doc.doc['materials'][doc.mat(ocean_mat)]
    sea_material['pbrMetallicRoughness']['baseColorFactor']=[*clr,1.]
    apply_water(sea_material,'bay')
    land=Shape('鳌山湾沿岸 · 卫星地形背景');tag='Sentinel-2 · coastal landscape'
    ground=elevations();step=160;prepared=prep(dry)
    edge=domain.boundary
    def y(x,z):
        yy=ground(x,z)-terrain.datum;pt=Point(x,z)
        if nearBounds.covers(pt):
            d=edge.distance(pt);w=1-min(1,d/130)
            yy=yy*(1-w)+terrain.y(x,z)*w
        return yy-.12
    for iz in range(125):
        z=B[1]+iz*step
        for ix in range(125):
            x=B[0]+ix*step;cell=box(x,z,x+step,z+step)
            if not prepared.intersects(cell):continue
            if prepared.covers(cell):
                vs=[(xx,y(xx,zz),zz) for xx,zz in [(x,z),(x+step,z),(x,z+step),(x+step,z+step)]]
                land.mesh('沿岸',vs,[(0,2,1),(3,1,2)],tag)
            else:face(land,shapely.intersection(dry,cell,grid_size=.001),tag,y)
    verts=land.parts[tag][0];uv=[((x-B[0])/(B[2]-B[0]),(z-B[1])/(B[3]-B[1])) for x,_,z in verts]
    mi=doc.shape(land);pr=doc.doc['meshes'][mi]['primitives'][0]
    pr['attributes']['TEXCOORD_0']=doc.accessor(uv,'<f4','VEC2',5126,34962)
    raw=coastal_albedo(tex,domain,waterfront)
    while len(doc.raw)%4:doc.raw.append(0)
    vi=len(doc.doc['bufferViews']);doc.doc['bufferViews'].append(dict(buffer=0,byteOffset=len(doc.raw),byteLength=len(raw)));doc.raw.extend(raw)
    doc.doc['images']=[{'name':'青岛沿海 · Sentinel-2','mimeType':'image/jpeg','bufferView':vi}]
    doc.doc['textures']=[{'source':0}]
    mat=doc.doc['materials'][pr['material']]
    mat['pbrMetallicRoughness'].update(baseColorFactor=[1,1,1,1],baseColorTexture={'index':0},roughnessFactor=1)
    doc.node(land.name,mesh=mi,kind='terrainContext')

