"""Continuous, looping shallow swell and fragmented foam for Aoshan Bay.

The actual modelled shoreline bounds the water. Analytic morph targets and the
foam atlas share phases, distance and alongshore coordinates. Ordinary glTF
readers get the shape-key animation and a static first foam frame.
"""
from io import BytesIO
import math

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from shapely import box, distance, get_coordinates, line_interpolate_point, line_locate_point, points, segmentize
from shapely.geometry import Point, Polygon
from qd_geometry import Shape
from qd_terrain import face

PERIOD=11.2
FRAMES=48
TILE=80
ROWS=512
CYCLE_S=223.
FOAM_RANGE=26.
WIDTH=108.
MATERIAL='鳌山湾 · 春日浅海与碎浪'
IMAGE='鳌山湾 · 循环浪沫与潮痕'
HARMONICS=(2,3)


def smooth(x):
    t=np.clip(x,0,1)
    return t*t*(3-2*t)


def wave_phase(d,s):
    a=s*(2*np.pi/CYCLE_S)
    p=.581*d+1.10*np.log1p(d/3.9)+.80*np.sin(a*2)+.34*np.sin(7*a+.47)+.22*np.sin(12*a-.24)
    q=.78*d+.48*np.log1p(d/4)+1.65*np.sin(a)+.46*np.sin(5*a+.7)+.33*np.cos(10*a)
    return p,q


def foam_field(d,s,seconds):
    tau=2*np.pi
    p,q=wave_phase(d,s)
    a=tau*s/CYCLE_S
    t=seconds*tau/PERIOD
    crest=np.cos(p+2*t-np.pi/2)
    cross=np.cos(q+3*t-np.pi/2)
    # Discontinuous spilling crests across a shallow bay, followed by thinner
    # receding striations. Every temporal expression closes on the same period.
    patch=np.clip(.42+.28*np.sin(5*a+.42*d)+.22*np.sin(11*a-.14*d+np.sin(a))+.14*np.sin(23*a+.6),0,1)
    grains=.5+.5*np.sin(33*a+.81*d+1.3*np.sin(9*a-.4*d))
    narrow=smooth((crest-.76)/.23)
    breakage=smooth((patch+.15*cross+.11*grains-.28)/.60)
    lace_fibre=.5+.5*np.sin(88*a+2.05*d+1.6*np.sin(39*a-1.4*d))
    pores=smooth((lace_fibre+.3*grains-.13)/.90)
    primary=narrow*breakage*(.32+.68*grains)*(.36+.64*pores)
    minor=smooth((cross-.88)/.115)*smooth((.45+np.sin(7*a-.23*d)*.45-.39)/.61)*.30
    lace=smooth((crest-.25)/.65)*(1-narrow)*smooth((np.sin(21*a+.81*d+1.8*np.sin(11*a))-.28)/.72)*.19
    edge=(.77+.23*smooth(d/3))*(1-smooth((d-5.8)/15.5))
    return np.clip((primary*.88+minor+lace)*edge,0,.92)


def atlas_bytes():
    d=np.clip((np.arange(TILE)-1)/(TILE-3),0,1)[None,:]*FOAM_RANGE
    s=(np.arange(ROWS)+.5)[:,None]/ROWS*CYCLE_S
    tex=np.zeros((ROWS,TILE*FRAMES,4),np.uint8)
    for i in range(FRAMES):
        f=foam_field(d,s,PERIOD*i/FRAMES)
        # Alpha is a linear mask in both Blender and WebGL. RGB also gives a
        # valid first-frame emissive appearance to glTF-only applications.
        srgb=np.where(f<.0031308,12.92*f,1.055*np.maximum(f,0)**(1/2.4)-.055)
        band=tex[:,i*TILE:(i+1)*TILE]
        band[:,:,:3]=np.round(255*srgb)[:,:,None]
        band[:,:,3]=np.round(255*f)
    packed=BytesIO();Image.fromarray(tex).save(packed,format='PNG',compress_level=7)
    return packed.getvalue()


def foam_cells():
    # Cell walls retain hollows several tens of centimetres wide. Distorted
    # coordinates and nested populations make the lace irregular at the lip.
    from scipy.spatial import cKDTree
    n=256; yy,xx=np.mgrid[:n,:n]/n;tau=2*math.pi
    coords=np.column_stack(((xx+.023*np.sin(tau*(2*yy+xx))+.011*np.sin(tau*(4*xx-3*yy))+.008*np.cos(tau*(7*xx+5*yy))).ravel()%1,
                            (yy+.033*np.sin(tau*(xx-yy))+.014*np.cos(tau*(3*xx+yy))+.009*np.sin(tau*(5*xx+7*yy))).ravel()%1))
    rng=np.random.default_rng(497028)
    def rims(count,thickness):
        seeds=rng.random((count,2));ds=cKDTree(seeds,boxsize=1).query(coords,2)[0]
        diff=(ds[:,1]-ds[:,0]).reshape(n,n)
        return 1-smooth((diff-thickness*.28)/thickness)
    large=rims(111,.0105);small=rims(342,.0056)
    mix=.5+.5*np.sin(tau*(2*xx-yy)+.7*np.cos(tau*(3*xx+yy)))
    field=np.maximum(large,small*smooth((mix-.37)/.49)*.83)
    field=np.clip(field+.075*(.5+.5*np.sin(tau*(13*xx+17*yy)))**7,0,1)
    rgba=np.full((n,n,4),255,np.uint8);rgba[:,:,3]=np.uint8(field*255)
    out=BytesIO();Image.fromarray(rgba).save(out,format='PNG',optimize=True)
    return out.getvalue()


def embed_atlas(doc,raw,name,micro=False):
    while len(doc.raw)%4:doc.raw.append(0)
    bv=doc.doc['bufferViews'];im=doc.doc.setdefault('images',[]);textures=doc.doc.setdefault('textures',[]);sam=doc.doc.setdefault('samplers',[])
    bv.append({'buffer':0,'byteOffset':len(doc.raw),'byteLength':len(raw)})
    doc.raw.extend(raw)
    im.append({'name':name,'mimeType':'image/png','bufferView':len(bv)-1})
    # The last three texels of each tile are gutters. Use linear filtering
    # without smaller cross-frame mip levels bleeding into unrelated times.
    sam.append({'magFilter':9729,'minFilter':9987 if micro else 9729,'wrapS':10497 if micro else 33071,'wrapT':10497})
    textures.append({'source':len(im)-1,'sampler':len(sam)-1,'name':name})
    return len(textures)-1


def weights(t):
    h=np.asarray(HARMONICS)*2*np.pi*t/PERIOD
    return np.array([.5+.5*np.cos(h[0]),.5+.5*np.sin(h[0]),.5+.5*np.cos(h[1]),.5+.5*np.sin(h[1])])


def linear(a):
    a=a/255.
    return np.where(a<.04045,a/12.92,((a+.055)/1.055)**2.4)


class Surf:
    def __init__(self,waterfront):
        self.w=waterfront
        self.area=waterfront.shore.buffer(WIDTH,quad_segs=6).intersection(waterfront.ocean)

    def _geometry(self):
        w=self.w
        pitch=24
        x0,z0,x1,z1=self.area.bounds
        X,Z=np.meshgrid(np.arange(math.floor(x0/pitch)*pitch,x1,pitch),np.arange(math.floor(z0/pitch)*pitch,z1,pitch))
        tiles=box(X.flat[:],Z.flat[:],X.flat[:]+pitch,Z.flat[:]+pitch)
        from shapely import intersects,intersection
        tiles=tiles[intersects(tiles,self.area)]
        shape=Shape('波面三角网')
        radii=(.55,1.15,1.85,2.65,3.55,4.55,5.65,6.8,8.,9.3,10.7,12.2,13.85,15.65,17.6,19.7,22.2,25.2,29,34,41,51,65,84,WIDTH)
        previous=Polygon()
        for radius in radii:
            outline=w.shore.buffer(radius,quad_segs=6)
            band=outline.difference(previous).intersection(self.area)
            previous=outline
            cellparts=intersection(tiles[intersects(tiles,band)],band)
            length=6 if radius<20 else 13
            for geom in cellparts:
                face(shape,segmentize(geom,length),MATERIAL,0)
        v,_,idx=shape.parts[MATERIAL];xyz=np.array(v)
        # Welding the shared band edges is also important for stable swash motion.
        xz,inv=np.unique(np.round(xyz[:,[0,2]],5),axis=0,return_inverse=True)
        trilist=inv[np.asarray(idx,dtype=np.int32)].reshape(-1,3)
        # Independent polygon clips can leave a vertex partway along an opposing
        # edge. At changing water heights that otherwise opens a hairline crack.
        from scipy.spatial import cKDTree
        all_edges=np.stack((trilist[:,[0,1]],trilist[:,[1,2]],trilist[:,[2,0]]),axis=1).reshape(-1,2)
        unique=np.unique(np.sort(all_edges,axis=1),axis=0)
        a=xz[unique[:,0]];b=xz[unique[:,1]];v=b-a
        length=np.linalg.norm(v,axis=1);length2=np.maximum(1.e-12,length**2)
        nearby=cKDTree(xz).query_ball_point((a+b)*.5,length*.5+.0001,workers=-1)
        ei=np.repeat(np.arange(len(unique)),[len(ids) for ids in nearby]);vi=np.concatenate(nearby).astype(int)
        delta=xz[vi]-a[ei]
        order=np.sum(delta*v[ei],axis=1)/length2[ei]
        off=np.abs(delta[:,0]*v[ei,1]-delta[:,1]*v[ei,0])/np.maximum(length[ei],1.e-6)
        between=(off<.00004)&(order>1.e-5)&(order<.99999)
        split_edges={}
        for edge,vertex,t in zip(ei[between],vi[between],order[between]):
            split_edges.setdefault(tuple(unique[edge]),[]).append((t,vertex))
        if not split_edges:return xz,trilist.flatten()
        output=[];extra=[]
        for tri in trilist:
            expanded=[];changed=False
            for start,end in zip(tri,np.roll(tri,-1)):
                expanded.append(start);key=(start,end) if start<end else (end,start)
                if key in split_edges:
                    expanded.extend(item[1] for item in sorted(split_edges[key],reverse=start>end));changed=True
            if not changed:output.append(tuple(tri));continue
            mid=len(xz)+len(extra);extra.append(xz[tri].mean(axis=0))
            output.extend((mid,i,j) for i,j in zip(expanded,expanded[1:]+expanded[:1]) if i!=j)
        if extra:xz=np.vstack((xz,extra))
        return xz,np.asarray(output).flatten()

    def attributes(self,xz):
        w=self.w;shore=w.shore; xy=points(xz[:,0],xz[:,1]);d=distance(xy,shore)
        chain=line_locate_point(shore,xy)
        near=get_coordinates(line_interpolate_point(shore,chain))
        p=get_coordinates(line_interpolate_point(shore,np.maximum(0,chain-.5)))
        q=get_coordinates(line_interpolate_point(shore,np.minimum(shore.length,chain+.5)))
        tang=q-p
        # This line runs from south/east towards north; its right side is open
        # water. Pick the public-map interior for each direction at shore bends.
        n=np.column_stack((-tang[:,1],tang[:,0]))
        n/=np.maximum(1e-9,np.linalg.norm(n,axis=1)[:,None])
        from shapely import covers
        inside=covers(w.ocean,points(near[:,0]+n[:,0]*.45,near[:,1]+n[:,1]*.45))
        n[~inside]*=-1
        switch=d>.05
        n[switch]=(xz[switch]-near[switch])/np.maximum(d[switch,None],1e-8)
        s=chain+11*np.sin(chain/159)+6*np.cos(chain/92)
        phase=wave_phase(d,s);a=s*(2*np.pi/CYCLE_S)
        ends=smooth(np.minimum(chain,shore.length-chain)/45)
        shelter=1-.84*smooth((xz[:,1]+1865)/42)*smooth((-1650-xz[:,1])/42)
        fade=(1-smooth((d-30)/63))*ends*shelter
        shore_activity=(.72+.28*(.5+.5*np.sin(a*3+.4*np.sin(5*a))))
        taper=fade*shore_activity
        amps=[(.035+.098*np.exp(-((d-7)/10)**2)+.043*np.exp(-((d-25)/19)**2))*taper,
              (.012+.035*np.exp(-((d-9)/13)**2))*taper]
        offsets=[.52*(1-smooth(d/4.2))*taper,.09*(1-smooth(d/3.2))*taper]
        # Against the mapped quay only vertical motion is permissible.
        quay=smooth(np.minimum((xz[:,1]+1837)/19,(-1684-xz[:,1])/20))*smooth((585-xz[:,0])/16)
        poses=[];norms=[]
        for phi,amp,run,k in zip(phase,amps,offsets,(.68,.86)):
            for coef,gradient in [(np.sin(phi),np.cos(phi)),(np.cos(phi),-np.sin(phi))]:
                move=-run*coef*(1-quay)*2
                poses.append(np.column_stack((n[:,0]*move,2*amp*coef,n[:,1]*move)))
                grad=amp*k*gradient*2
                norms.append(np.column_stack((-n[:,0]*grad,np.zeros(len(xz)),-n[:,1]*grad)))
        uv=np.column_stack(((1.5+np.clip(d/FOAM_RANGE,0,1)*(TILE-3))/(FRAMES*TILE),s/CYCLE_S))
        shade=np.clip((.5+.5*np.sin(s/31)*np.cos(d/17))*.045,0,.045)
        stops=[0,2.3,8,21,46,79,WIDTH]
        pal=np.array([[132,131,111],[112,134,126],[83,127,130],[65,111,122],[58,105,119],[65,111,127],[67,113,131]])
        rgb=np.column_stack([np.interp(d,stops,pal[:,k]) for k in range(3)])
        rgb*=1+(shade-.022)[:,None]*(1-smooth(d/WIDTH))[:,None]
        rgb=linear(rgb)
        energy=taper*(1-smooth((d-18)/8))
        return d,chain,poses,norms,uv,rgb,energy

    def add(self,doc,level):
        xz,idx=self._geometry()
        d,chain,poses,norms,uv,rgb,energy=self.attributes(xz)
        flat=np.column_stack((xz[:,0],np.full(len(xz),level),xz[:,1]))
        pos=flat-.5*np.sum(poses,axis=0)
        up=np.zeros_like(pos);up[:,1]=1
        base=up-.5*np.sum(norms,axis=0);base/=np.linalg.norm(base,axis=1)[:,None]
        vec=lambda arr:doc.accessor(arr,'<f4','VEC3',5126,34962)
        attr={'POSITION':vec(pos),'NORMAL':vec(base),'COLOR_0':vec(rgb),
              'TEXCOORD_0':doc.accessor(uv,'<f4','VEC2',5126,34962),
              'TEXCOORD_1':doc.accessor(np.column_stack((energy,np.clip(d/WIDTH,0,1))),'<f4','VEC2',5126,34962)}
        m=doc.mat(MATERIAL);mat=doc.doc['materials'][m];pbr=mat['pbrMetallicRoughness']
        from qd_natural_finishes import apply_water
        apply_water(mat,'bay')
        cells=embed_atlas(doc,foam_cells(),'鳌山湾 · 泡孔细网',True)
        pbr.update(baseColorFactor=[1,1,1,1],baseColorTexture={'index':cells})
        texture=embed_atlas(doc,atlas_bytes(),IMAGE);mat.update(emissiveTexture={'index':texture},emissiveFactor=[.40,.43,.40])
        typ,dtype=(5123,'<u2') if len(pos)<=65535 else (5125,'<u4')
        targets=[{'POSITION':vec(o),'NORMAL':vec(n)} for o,n in zip(poses,norms)]
        prim={'attributes':attr,'indices':doc.accessor(idx,dtype,'SCALAR',typ,34963),'material':m,'targets':targets}
        name='鳌山湾 · 向岸浅浪';mi=len(doc.doc['meshes'])
        doc.doc['meshes'].append({'name':name,'primitives':[prim],'weights':weights(0).tolist(),
                                  'extras':{'targetNames':['主涌余弦','主涌正弦','交叉波余弦','交叉波正弦']}})
        doc.node(name,mesh=mi,kind='surfWater',surface='surf',period=PERIOD,frames=FRAMES,foamRange=FOAM_RANGE)
        node_index=len(doc.doc['nodes'])-1
        times=np.linspace(0,PERIOD,113)
        ta=doc.accessor(times,'<f4','SCALAR',5126,34962);doc.doc['accessors'][ta].update(min=[0],max=[PERIOD])
        wa=doc.accessor(np.array([weights(t) for t in times]).reshape(-1),'<f4','SCALAR',5126,34962)
        doc.doc.setdefault('animations',[]).append({'name':'鳌山湾向岸浅浪 · 11.2秒循环',
            'samplers':[{'input':ta,'output':wa,'interpolation':'LINEAR'}],'channels':[{'sampler':0,'target':{'node':node_index,'path':'weights'}}]})
        # Narrow sand bed beneath the moving contact line: retreat reveals damp
        # sediment; advancing water meets the existing beach at the same datum.
        bed=Shape('潮下沙底 · 涨落交界');lower=self.w.shore.buffer(1.15).intersection(self.area)
        face(bed,segmentize(lower,3),'#a99c81',lambda x,z:level-.003-.16*min(1.,self.w.shore.distance(Point(x,z))/1.15))
        doc.node(bed.name,shape=bed,kind='waterfrontShore',surface='subtidal')

