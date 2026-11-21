"""Read the selected open Copernicus scene by TIFF ranges and project onto the campus grid."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import math, json, zlib, io
import numpy as np
import requests,tifffile
from PIL import Image
from scipy.ndimage import binary_closing,binary_fill_holes, label,gaussian_filter
ROOT=Path(__file__).resolve().parents[1]
ITEM="S2B_51STA_20261007_0_L2A"
META="https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/"+ITEM
BASE="https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/51/S/TA/2026/10/"+ITEM+"/"
def utm(lon,lat):
    lon,lat=np.deg2rad(lon),np.deg2rad(lat)
    ecc2=0.0066943799901413165;ep=ecc2/(1-ecc2); a=6378137.;k=.9996
    n=a/np.sqrt(1-ecc2*np.sin(lat)**2)
    t=np.tan(lat)**2;c=ep*np.cos(lat)**2; aa=(lon-math.radians(123))*np.cos(lat)
    m=a*((1-ecc2/4-3*ecc2**2/64-5*ecc2**3/256)*lat-(3*ecc2/8+3*ecc2**2/32+45*ecc2**3/1024)*np.sin(2*lat)+(15*ecc2**2/256+45*ecc2**3/1024)*np.sin(4*lat)-(35*ecc2**3/3072)*np.sin(6*lat))
    return (500000+k*n*(aa+(1-t+c)*aa**3/6+(5-18*t+t*t+72*c-58*ep)*aa**5/120),
      k*(m+n*np.tan(lat)*(aa**2/2+(5-t+9*c+4*c*c)*aa**4/24+(61-58*t+t*t+600*c-330*ep)*aa**6/720)))

site=json.loads((ROOT/'data/map/campus.json').read_text(encoding='utf8'))
meters=site['metadata']['metres_per_degree'];axis=np.arange(-9995,10000,10,dtype=float)
col=np.empty((2000,2000),dtype=np.int32);row=col.copy()
for k in range(0,len(axis),80):
    x,z=np.meshgrid(axis,axis[k:k+80])
    e,n=utm(120.68204+x/meters['longitude'],36.36559-z/meters['latitude'])
    col[k:k+len(x)]=((e-199980)/10).astype(np.int32)
    row[k:k+len(x)]=((4100040-n)/10).astype(np.int32)

def getband(bn):
    url=BASE+bn+'.tif'
    def fetch(start,end):
        for attempt in range(3):
            try:
                r=requests.get(url,headers={'Range':f'bytes={start}-{end}'},timeout=45)
                r.raise_for_status()
                if len(r.content)!=end-start+1:raise ValueError((len(r.content),end-start+1))
                return r.content
            except (requests.RequestException,ValueError):
                if attempt==2:raise
    t=tifffile.TiffFile(io.BytesIO(fetch(0,65535))).pages[0]
    th,tw=t.tilelength,t.tilewidth; columns=math.ceil(t.imagewidth/tw)
    assert min(row.min(),col.min())>=0 and max(col.max(),row.max())<t.imagewidth
    assert t.geotiff_tags['ModelTiepoint'][3:5]==[199980.0,4100040.0]
    nd=3 if bn=='TCI' else 1
    im=np.zeros((*col.shape,nd),dtype=t.dtype)
    tid=(row//th)*columns+col//tw
    for idx in np.unique(tid):
        idx=int(idx);start=t.dataoffsets[idx];count=t.databytecounts[idx]
        block=np.frombuffer(zlib.decompress(fetch(start,start+count-1)),dtype=t.dtype).reshape(th,tw,nd)
        if t.predictor==2:block=np.cumsum(block,axis=1,dtype=t.dtype)
        use=tid==idx;im[use]=block[row[use]%th,col[use]%tw]
    return im if nd>1 else im[:,:,0]
stac=requests.get(META,timeout=20).json()
with ThreadPoolExecutor(max_workers=3) as pool:
    rgb,green,nir=list(pool.map(getband,('TCI','B03','B08')))
assert np.count_nonzero((rgb==0).all(axis=2))<200
green=green.astype(np.float32);nir=nir.astype(np.float32)
ndwi=(green-nir)/(green+nir+1)
wet=binary_closing((ndwi>-.04)&(nir<1400),structure=np.ones((3,3)),border_value=0)
classes,nclasses=label(wet)
seeds=classes[2:-2,-3];valid=seeds[seeds>0]
basin=np.argmax(np.bincount(valid)[1:])+1
sea=classes==basin
# Preserve offshore islands and tidal inlets, fill only trivial holes (fewer than four 10m pixels).
cut,n=label(~sea); freq=np.bincount(cut.ravel()); tiny=np.flatnonzero(freq<4)
sea|=np.isin(cut,tiny)
sea[:,0]=sea[:,1];sea[:,-1]=sea[:,-2];sea[0]=sea[1];sea[-1]=sea[-2]
float_rgb=rgb.astype(np.float32)/255.
lum=np.sum(float_rgb*np.array([.243,.645,.112],np.float32),axis=2,keepdims=True)
land=np.power(np.clip(.85*float_rgb+.15*lum,0,1),.77)*.93+.036
# Retain the relative reflectance differences over sandbars and coastal water.
water_tint=np.array([.34,.54,.58],np.float32)[None,None,:]+.56*(float_rgb-.18)
alpha=gaussian_filter(sea.astype('f'),.70)[:,:,None]
graded=np.clip(land*(1-alpha)+water_tint*alpha,0,1)
Image.fromarray(np.uint8(graded*255+.5)).save(ROOT/'assets/海岸环境.jpg',quality=91,subsampling=0,optimize=True)
Image.fromarray(sea.astype(np.uint8)*255).save(ROOT/'assets/海陆掩膜.png',optimize=True)
metadata=dict(xmin=-10000,zmin=-10000,xmax=10000,zmax=10000,
    width=2000,height=2000,metres_per_pixel=10,
    origin={'lon':120.68204,'lat':36.36559,'crs':'WGS84'},orientation='north up, +X east, +Z south',
    registration='Bounds are OUTER pixel edges. Pixel(row,column) centre = (-10000+(column+0.5)*10, -10000+(row+0.5)*10).',
    texture='assets/海岸环境.jpg',mask='assets/海陆掩膜.png',mask_values={'255':'Sea and connected estuaries','0':'Land, islands, and disconnected inland water'},
    source=stac['id'],item_url=META,date=stac['properties']['datetime'],scene_cloud_cover_percent=stac['properties']['eo:cloud_cover'],
    native_crs='EPSG:32651 (WGS 84 / UTM zone 51N)',source_assets={k:BASE+v+'.tif' for k,v in [('rgb','TCI'),('green','B03'),('nir','B08')]},
    attribution='Contains modified Copernicus Sentinel data 2026.',terms='https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice',
    colour='True-colour TCI, mildly desaturated with lifted shadows. Blue-green water tint preserves relative nearshore texture. RGB is colour graded for a 3D distant backdrop.',
    mask_method='Connected component seeded on eastern open-water edge; (B03-B08)/(B03+B08)>-0.04 and B08 DN<1400. Three-pixel morphological closing. Coast is approximate at the 10 m pixel scale.',
    mask_ocean_fraction=round(float(sea.mean()),5),product='Copernicus Sentinel-2B level-2A / Element 84 Earth Search')
(ROOT/'data/coastal-context.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
print(metadata['mask_ocean_fraction'],stac['properties']['datetime'],np.unique(sea,return_counts=True),flush=True)
