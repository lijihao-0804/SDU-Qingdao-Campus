"""Draped land cover over a common TIN and cached Mapzen Terrarium terrain."""
from pathlib import Path
import math, json
from urllib.request import urlopen,Request
from io import BytesIO
from PIL import Image
import numpy as np
from scipy.ndimage import gaussian_filter
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.geometry.polygon import orient
from shapely.prepared import prep
import mapbox_earcut as ear

ROOT=Path(__file__).resolve().parents[1]
LON,LAT=120.68204,36.36559
def project(lon,lat):return ((lon-LON)*111320*math.cos(math.radians(LAT)),-(lat-LAT)*111320)
def worldpix(x,z):
    lon=LON+x/(111320*math.cos(math.radians(LAT))); lat=LAT-z/111320
    size=256*(2**13);a=math.radians(lat)
    return ((lon+180)/360*size,(1-math.asinh(math.tan(a))/math.pi)/2*size)
def polygons(shape):
    if shape.is_empty:return
    if shape.geom_type=='Polygon':
        if shape.area>.04:yield shape
    elif hasattr(shape,'geoms'):
        for sub in shape.geoms:yield from polygons(sub)
def face(shape,geom,material,y):
    for p in polygons(geom):
        p=orient(p,sign=1);rings=[list(r.coords)[:-1] for r in (p.exterior,*p.interiors)]
        coords=[(a,b) for ring in rings for a,b,*_ in ring]
        if len(coords)<3:continue
        a=np.array(coords,np.float64)
        tri=ear.triangulate_float64(a,np.cumsum([len(r) for r in rings],dtype=np.uint32)).reshape(-1,3)
        pts=[(x,y(x,z) if callable(y) else y,z) for x,z in coords]
        shape.mesh('铺面',pts,[tuple(reversed(t)) for t in tri],material)
def sourcepolygon(row):
    try:return Polygon(row['poly'],row.get('holes',[])).buffer(0)
    except (ValueError,TypeError,KeyError):return Polygon()
class Terrain:
    step=42.
    def __init__(self,bounds,datum_bounds=None):
        x0,z0,x1,z1=bounds
        st=self.step
        self.x0=math.floor((x0-2)/st)*st;self.z0=math.floor((z0-2)/st)*st
        nx=math.ceil((x1-self.x0)/st)+2;nz=math.ceil((z1-self.z0)/st)+2
        path=ROOT/'data'/'terrain';path.mkdir(exist_ok=True)
        self.cached={};values=np.zeros((nz,nx))
        for j in range(nz):
            for i in range(nx):
                a,b=worldpix(self.x0+i*st,self.z0+j*st);key=(int(a)//256,int(b)//256)
                if key not in self.cached:
                    tx,ty=key;tile=path/f'13-{tx}-{ty}.png'
                    if not tile.exists():
                        url=f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/13/{tx}/{ty}.png'
                        with urlopen(Request(url,headers={'User-Agent':'SDU-Qingdao-campus-model/1.0'}),timeout=30) as reply: sample=reply.read()
                        img=Image.open(BytesIO(sample));img.load();tile.write_bytes(sample)
                    self.cached[key]=np.asarray(Image.open(tile).convert('RGB'),dtype=float)
                px=self.cached[key][int(b)%256,int(a)%256]
                values[j,i]=px[0]*256+px[1]+px[2]/256-32768
        # Keep the original campus height reference as the high-detail band extends north.
        datum_values=values
        if datum_bounds is not None:
            x0,z0,x1,z1=datum_bounds
            cx=math.floor((x0-2)/st)*st;cz=math.floor((z0-2)/st)*st
            i=round((cx-self.x0)/st);j=round((cz-self.z0)/st)
            ni=math.ceil((x1-cx)/st)+2;nj=math.ceil((z1-cz)/st)+2
            datum_values=values[j:j+nj,i:i+ni]
        self.datum=float(np.median(datum_values))
        self.heights=gaussian_filter(values,0.95)-self.datum
        self.terrainRange=[float(values.min()),float(values.max())]
    def level_pads(self,pads):
        src=self.heights.copy()
        for poly in sorted(pads,key=lambda k:k.area,reverse=True):
            if poly.is_empty:continue
            from shapely.geometry import Point
            cx,cz=poly.representative_point().coords[0]
            y=self.y(cx,cz);xmin,zmin,xmax,zmax=poly.bounds
            for j in range(max(0,int((zmin-self.z0)/self.step)-1),min(self.heights.shape[0],int((zmax-self.z0)/self.step)+3)):
                for i in range(max(0,int((xmin-self.x0)/self.step)-1),min(self.heights.shape[1],int((xmax-self.x0)/self.step)+3)):
                    p=Point(self.x0+i*self.step,self.z0+j*self.step);dist=p.distance(poly)
                    if dist<24:
                        t=(1-dist/24)**2
                        self.heights[j,i]=self.heights[j,i]*(1-t)+y*t
    def y(self,x,z):
        u=(x-self.x0)/self.step;v=(z-self.z0)/self.step
        i=max(0,min(int(u),self.heights.shape[1]-2));j=max(0,min(int(v),self.heights.shape[0]-2));a=u-i;b=v-j
        q=self.heights[j:j+2,i:i+2]
        if a+b<=1:return float(q[0,0]+a*(q[0,1]-q[0,0])+b*(q[1,0]-q[0,0]))
        return float(q[1,1]+(1-a)*(q[1,0]-q[1,1])+(1-b)*(q[0,1]-q[1,1]))
    def skin(self,shape,geom,material,lift=0):
        if geom.is_empty:return
        bound=geom.bounds;st=self.step;fast=prep(geom)
        def yy(x,z):return self.y(x,z)+lift
        for j in range(max(0,int((bound[1]-self.z0)/st)),min(self.heights.shape[0]-1,int((bound[3]-self.z0)/st)+1)):
            z=self.z0+j*st
            for i in range(max(0,int((bound[0]-self.x0)/st)),min(self.heights.shape[1]-1,int((bound[2]-self.x0)/st)+1)):
                x=self.x0+i*st;cell=box(x,z,x+st,z+st)
                if not fast.intersects(cell):continue
                corners=[(x,z),(x+st,z),(x,z+st),(x+st,z+st)]
                tris=((0,2,1),(3,1,2))
                if fast.covers(cell):
                    shape.mesh('地表',[(a,yy(a,b),b) for a,b in corners],tris,material);continue
                for ids in tris:
                    tri=Polygon([corners[k] for k in ids]);cl=geom.intersection(tri);face(shape,cl,material,yy)

