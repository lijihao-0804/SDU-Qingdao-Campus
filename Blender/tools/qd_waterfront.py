"""Editable coastal terrain, park paths and furniture in the campus metre frame.

The OSM centre-lines control layout. The inner tidal bay uses the bundled
10-m Sentinel mask where the old mapped shoreline bridges the inlet.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import json
import math
import random

import numpy as np
from PIL import Image
from shapely import segmentize, distance, points
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, substring, unary_union
from shapely.prepared import prep

from qd_geometry import Shape
from qd_terrain import face, polygons

ROOT = Path(__file__).resolve().parents[1]
MAIN = 982447347
BRANCH = 982447348
OSM_PARK = 548365000


def smooth(t):
    t = max(0., min(1., t))
    return t*t*(3.-2.*t)


def combine(parts):
    return unary_union([p for p in parts if not p.is_empty])


def smooth_points(points, rounds=2):
    for _ in range(rounds):
        out = [points[0]]
        for a,b in zip(points,points[1:]):
            out.extend([(a[0]*.75+b[0]*.25,a[1]*.75+b[1]*.25),
                        (a[0]*.25+b[0]*.75,a[1]*.25+b[1]*.75)])
        points = out+[points[-1]]
    return points


def surface(shape, geom, mat, y, pitch=24):
    if geom.is_empty:
        return
    xmin,zmin,xmax,zmax = geom.bounds
    prepared = prep(geom)
    for iz in range(math.floor(zmin/pitch), math.ceil(zmax/pitch)):
        z=iz*pitch
        for ix in range(math.floor(xmin/pitch), math.ceil(xmax/pitch)):
            x=ix*pitch
            cell=box(x,z,x+pitch,z+pitch)
            if prepared.covers(cell):
                verts=[(a,y(a,b),b) for a,b in ((x,z),(x+pitch,z),(x,z+pitch),(x+pitch,z+pitch))]
                shape.mesh('地面',verts,[(0,2,1),(3,1,2)],mat)
            elif prepared.intersects(cell):
                face(shape,segmentize(geom.intersection(cell),max_segment_length=pitch*.7),mat,y)


def line_pose(line, s):
    s=max(0.,min(line.length,s))
    p=line.interpolate(s)
    a=line.interpolate(max(0.,s-.65)); b=line.interpolate(min(line.length,s+.65))
    dx,dz=b.x-a.x,b.y-a.y
    length=math.hypot(dx,dz) or 1.
    return p.x,p.y,dx/length,dz/length


def oval(shape,name,x,y,z,rx,ry,rz,mat):
    vertices=[]
    for j in range(9):
        lat=-math.pi/2+math.pi*j/8
        for k in range(14):
            lon=k*math.tau/14
            vertices.append((x+rx*math.cos(lat)*math.cos(lon),y+ry*math.sin(lat),z+rz*math.cos(lat)*math.sin(lon)))
    faces=[]
    for j in range(8):
        for k in range(14):
            i=j*14+k; b=j*14+(k+1)%14
            faces.append((i,b,b+14,i+14))
    shape.mesh(name,vertices,faces,mat)


def railing_beam(shape, a,b, radius,mat):
    from qd_planting import branch
    branch(shape, a,b,radius,radius,mat)


def sand_surface_appearance(xyz, shore):
    """Return vertex tint, UVs and the matte sand colour map for these existing surface positions."""
    x,z=xyz[:,0],xyz[:,2]
    d=distance(points(x,z),shore)
    spread=22+3.9*np.sin(z/94+x/140)+2.1*np.sin(z/34-x/72)
    u=np.minimum(1.,d/spread)
    u=.40*u+.60*u*u*(3-2*u)
    stations=np.array([0,.22,.55,1.])
    pigment=np.array([[119,112,99],[153,137,117],[199,172,134],[219,196,156]],dtype=float)
    # The dry/wet hue is shared between the editable vertex attribute and a
    # soft image ramp, so Blender's texture-only solid view also shows it.
    tint=np.array([[181,171,151],[191,177,153],[216,198,164],[231,216,183]],dtype=float)
    def rgb_table(t,table):
        return np.column_stack([np.interp(t,stations,table[:,j]) for j in range(3)])
    def linear(values):
        srgb=values/255
        return np.where(srgb<=.04045,srgb/12.92,((srgb+.055)/1.055)**2.4)
    variation=1+.011*np.sin(x/4.6+z/8.9)+.008*np.sin(z/3.7-x/8)
    vertex=np.clip(linear(rgb_table(u,pigment))/linear(rgb_table(u,tint))*variation[:,None],0,1)
    # The repeating second UV direction adds a very light grain near the
    # eye. No duplicate face or transparent overlay is used at the tide line.
    # Moisture stops changing on the dry upper beach, but texture space must
    # continue inland. Otherwise whole triangles read a single column of pixels.
    across = u + np.maximum(0, d-spread)/22.
    extent = max(1., math.ceil(float(across.max())*4)/4)
    texture_width, texture_height = 4096, 1024
    alongshore = (z*.78+x*.31+1.35*np.sin(z/15+x/22)+.34*np.sin(z/3.9))/15.3
    uv = np.column_stack(((.5+(texture_width-1)*across/extent)/texture_width, alongshore))
    # Keep tide channels and ripples at their authored metre scale. A second,
    # finer sampling grid holds the pigment flecks visible at beach level.
    width,height=round(384*extent),512
    from scipy.ndimage import gaussian_filter
    rng=np.random.default_rng(462)
    fine=rng.normal(0,1,(height,width));coarse=gaussian_filter(fine,3,mode='wrap')
    # Slightly darker streaks left by receding spring tides are strongest
    # on damp sand. The tide line and all ground elevations remain shared.
    moisture=np.linspace(0,extent,width)[None,:];along=np.arange(height)[:,None]/height*math.tau
    # Small shallow streams fan across exposed sand. The ridge field is
    # periodic alongshore and bends/splits on the sloping tidal surface.
    v=along/math.tau
    wet=(1-np.minimum(1,moisture/.83)**1.7)
    ditch=np.zeros((height,width));fork=np.zeros_like(ditch)
    for n,(mouth,drift,phase) in enumerate(((.08,.28,1.2),(.31,-.22,2.4),(.54,.12,4.1),(.77,-.21,5.7),(.91,.19,3.2))):
        bed=mouth+drift*moisture+.031*np.sin(8.6*moisture+phase)+.014*np.sin(15.1*moisture+phase*.66)
        cross=(v-bed+.5)%1-.5
        breadth=.0029+.0021*(.5+.5*np.sin(9*moisture+phase))
        trunk=np.exp(-.5*(cross/breadth)**2)
        reach=np.clip((.34+.085*(n%4)-moisture)/.13,0,1)
        ditch=np.maximum(ditch,trunk*reach*(.72+.28*np.sin(11*moisture+phase)))
        joint=.12+.028*n
        branchbed=bed+np.maximum(0,moisture-joint)*(-.68 if n%2 else .56)
        arm=np.exp(-.5*(((v-branchbed+.5)%1-.5)/.0027)**2)
        fork=np.maximum(fork,arm*reach*np.clip((moisture-joint)/.07,0,1))
    # Spring flats also show streaked mineral deposits and fine, broken
    # corrugations between the channels, especially below the last high tide.
    cloud=gaussian_filter(rng.normal(size=(height,width)),(3.5,2.3),mode='wrap')
    patches=np.clip((cloud-.008)*6.9,0,1)
    clusters=np.clip((gaussian_filter(fine,.78,mode='wrap')-.18)*2.4,0,1)
    ripple=(np.sin(51*along+157*moisture+3*np.sin(5*along+12*moisture))*.5+.5)**5
    tide_stain=wet*(19*ditch+12*fork+13*patches+5*clusters*patches+3.6*ripple)
    grains=fine*.65+coarse*12.5-tide_stain
    base=rgb_table(np.linspace(0,extent,width),tint)[None,:,:]
    tex=np.uint8(np.clip(base+grains[:,:,None],0,255))
    pigment_map=Image.fromarray(tex).resize((texture_width,texture_height),Image.Resampling.BICUBIC)
    fine_sand=rng.standard_normal((texture_height,texture_width),dtype=np.float32)
    flecks=gaussian_filter(fine_sand,.45,mode='wrap')*3.6
    rgb=np.clip(np.asarray(pigment_map,dtype=np.float32)+flecks[:,:,None],0,255)
    stream=BytesIO()
    Image.fromarray(rgb.astype(np.uint8)).save(stream,format='PNG',compress_level=6)
    return vertex,uv,stream.getvalue()


class Waterfront:
    def __init__(self,data):
        self.data=data
        m=data['metadata']['metres_per_degree']
        self.xz=lambda lon,lat: ((lon-120.68204)*m['longitude'],(36.36559-lat)*m['latitude'])
        elements=json.loads((ROOT/'data/map/osm-source.json').read_text('utf8'))['elements']
        nodes={n['id']:self.xz(n['lon'],n['lat']) for n in elements if n['type']=='node'}
        ways={w['id']:w for w in elements if w['type']=='way'}
        def raw(i):return [nodes[n] for n in ways[i]['nodes']]
        extra=json.loads((ROOT/'data/map/waterfront-osm.json').read_text('utf8'))
        self.outer=box(-1100,-2000,1800,1500)
        clipped=LineString(raw(258503874)).intersection(self.outer)
        source=list(clipped.coords)
        if source[0][1]<source[-1][1]:
            source.reverse()
        baseline=LineString(source)
        mask=np.asarray(Image.open(ROOT/'assets/海陆掩膜.png').convert('L'))
        xrow=np.arange(465,646,10)
        def shoreline_x(z):
            hit=baseline.intersection(LineString([(300,z),(800,z)]))
            return hit.x
        calibrated=[]
        for z in range(-1660,-1851,-5):
            old=shoreline_x(z)
            candidates=xrow[mask[int((z+10000)/10),(xrow+10000)//10]>127]
            obs=old if not len(candidates) else min(old,float(candidates[0]-5))
            calibrated.append(obs)
        filtered=np.convolve(np.pad(calibrated,(2,2),mode='edge'),[.1,.2,.4,.2,.1],mode='valid')
        revised=[]
        for j,z in enumerate(range(-1660,-1851,-5)):
            original=shoreline_x(z)
            blend=smooth(min((-1660-z)/25,(z+1850)/24))
            revised.append((original*(1-blend)+filtered[j]*blend,z))
        mapped=LineString([p for p in source if p[1]>-1660]+revised+[p for p in source if p[1]<-1850])
        # The survey controls the bay shape. On the exposed sandy reach the
        # instantaneous tide edge has metre-scale cusps below the map resolution.
        from shapely import get_coordinates, line_interpolate_point
        original=np.array(mapped.coords); chain=np.r_[0,np.cumsum(np.linalg.norm(np.diff(original,axis=0),axis=1))]
        along=np.unique(np.r_[chain,np.arange(0,mapped.length,3.15)])
        def at(s):
            return get_coordinates(line_interpolate_point(mapped,np.clip(s,0,mapped.length)))
        xy=at(along); active=np.clip((-185-xy[:,1])/125,0,1)*np.clip((xy[:,1]+1610)/125,0,1)
        corridor=LineString(raw(MAIN))
        clearance=distance(points(xy[:,0],xy[:,1]),corridor)
        active*=np.clip((clearance-9)/8,0,1)
        active=active**2*(3-2*active)
        end=at(along+2)-at(along-2); normal=np.column_stack((-end[:,1],end[:,0]))
        normal/=np.maximum(1.e-8,np.linalg.norm(normal,axis=1))[:,None]
        bend=(1.24*np.sin(along/12.2+.57*np.sin(along/26))+.46*np.sin(along/5.8+.72)+.27*np.sin(along/3.4+1.5))
        rounded=(at(along-9)+at(along+9)-2*xy)*.21
        xy+=(normal*bend[:,None]+rounded)*active[:,None]
        keep=(active>.0001)|np.isin(along,chain)
        self.shore=LineString(xy[keep])
        if not self.shore.is_simple:raise ValueError('The tidal shoreline must stay continuous and simple.')
        pieces=split(self.outer,self.shore)
        self.ocean=next(p for p in pieces.geoms if p.covers(Point(1380,-700)))
        self.land=self.outer.difference(self.ocean)
        self.park=Polygon(raw(OSM_PARK)).buffer(0).intersection(self.land)
        self.main=LineString(raw(MAIN)); self.branch=LineString(raw(BRANCH))
        self.north=LineString([self.xz(*p) for p in extra['1022936686']['lonlat']])
        self.north_end=LineString([self.xz(*p) for p in extra['1022936687']['lonlat']])
        self.bridge=LineString(list(self.north.coords)+list(self.north_end.coords)[1:])
        self.bridge_start=self.bridge.project(Point(568,-1652))
        self.bridge_deck=substring(self.bridge,self.bridge_start,self.bridge.length)
        self.approach=substring(self.bridge,0,self.bridge_start)
        self.entrance=LineString(smooth_points([(660,-57.3),(697,-56),(729,-50),(757,-58),(785,-76),(818,-82),(842,-101),self.main.coords[0]]))
        self.path_geom=combine([self.main.buffer(2.8),self.branch.buffer(1.8),self.approach.buffer(4.4),self.entrance.buffer(3.5)])
        self.paths=[self.main,self.branch,self.approach,self.entrance,self.bridge_deck]
        self.carriageways=[LineString(raw(i)).intersection(self.outer) for i in (659714388,659714390)]
        self.street=combine([ln.buffer(4.5) for ln in self.carriageways])
        self.entry_plaza=Polygon(smooth_points([(685,-61),(710,-70),(744,-67),(766,-59),(752,-47),(717,-40),(693,-49),(685,-61)]))
        self.bridge_plaza=Polygon(smooth_points([(507,-1628),(527,-1645),(548,-1655),(570,-1658),(559,-1643),(541,-1630),(523,-1622),(507,-1628)]))
        self.plazas=combine([self.entry_plaza,self.bridge_plaza]).intersection(self.land)
        self.strand=self.shore.buffer(66,quad_segs=6).intersection(self.land)
        self.substrate=combine([self.park,self.strand,self.entrance.buffer(10),self.plazas,self.street.buffer(2).intersection(self.park.buffer(12))]).intersection(self.land)
        natural=Polygon(raw(739121633)).buffer(0).intersection(self.land)
        # The 10 m image and the mapped beach both show a narrow backshore. The
        # dry side stops at the signed promenade, including its concave bends.
        seaward_bank=LineString(list(self.main.coords)+[(760,-1960),(1100,-1500),(1600,-600),(1150,250),self.main.coords[0]])
        seaward=Polygon(seaward_bank).buffer(0)
        wet_domain=self.shore.buffer(9).intersection(self.land)
        back_beach=natural.union(self.shore.buffer(30).intersection(seaward)).intersection(self.substrate)
        self.beach=combine([back_beach,wet_domain]).difference(self.path_geom.buffer(.2)).intersection(self.strand)
        self.plant_exclusion=combine([self.park,self.strand,self.entrance.buffer(9),self.street.buffer(2)])
        from qd_surf import Surf
        self.surf=Surf(self)
        self.extras=[]
    def grade(self, terrain):
        self.terrain=terrain; self.level=-terrain.datum-.02
        raw=terrain.y
        xmin,zmin,xmax,zmax=self.strand.bounds
        coast=self.shore
        @lru_cache(maxsize=140000)
        def local(x,z):
            native=raw(x,z)
            if x<xmin-2 or x>xmax+2 or z<zmin-2 or z>zmax+2:return native
            dist=coast.distance(Point(x,z))
            if dist>=66:return native
            rise=max(1.15,min(3.3,native-self.level))
            h=self.level+rise*(min(dist,40)/40)**.98
            # A low quay is visible along the inside of the observation bridge.
            weight=self.wall_weight(x,z)
            h+=1.12*weight*(1-smooth(dist/22))
            w=smooth((dist-40)/26)
            return h*(1-w)+native*w
        terrain.y=local
    @staticmethod
    def wall_weight(x,z):
        return smooth(min((z+1837)/19,(-1684-z)/20))*smooth((585-x)/16)
    def _emit(self,doc,shape,kind,**props):
        doc.node(shape.name,shape=shape,kind=kind,**props)
    def _sand_mesh(self,doc,shape,material):
        # The same world point gets the same linear colour on either side of a
        # triangulation ring. glTF interpolates both moisture and tint per face.
        mesh=doc.shape(shape)
        primitive=doc.doc['meshes'][mesh]['primitives'][0]
        xyz=np.asarray(shape.parts[material][0],dtype=np.float64)
        vertex,uv,raw=sand_surface_appearance(xyz,self.shore)
        primitive['attributes']['COLOR_0']=doc.accessor(vertex,'<f4','VEC3',5126,34962)
        primitive['attributes']['TEXCOORD_0']=doc.accessor(uv,'<f4','VEC2',5126,34962)
        while len(doc.raw)%4:doc.raw.append(0)
        view=len(doc.doc['bufferViews'])
        doc.doc['bufferViews'].append({'buffer':0,'byteOffset':len(doc.raw),'byteLength':len(raw)})
        doc.raw.extend(raw)
        images=doc.doc.setdefault('images',[]); samplers=doc.doc.setdefault('samplers',[]);textures=doc.doc.setdefault('textures',[])
        images.append({'name':'鳌山湾 · 沙色与细砂','mimeType':'image/png','bufferView':view})
        samplers.append({'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':10497})
        textures.append({'source':len(images)-1,'sampler':len(samplers)-1,'name':'沙滩连续色阶'})
        mat=doc.doc['materials'][primitive['material']]
        mat['pbrMetallicRoughness'].update(baseColorFactor=[1,1,1,1],baseColorTexture={'index':len(textures)-1})
        from qd_coast_cleanup import set_matte_sand
        set_matte_sand(doc.doc,mat)
        doc.node(shape.name,mesh=mesh,kind='waterfrontShore',surface='sand')

    def _shore(self,doc):
        soil=Shape('滨海公园 · 绿带与岸上地形'); f=self.terrain.y
        bands=Shape('鳌山湾 · 干湿沙滩与潮间带')
        distance_bands=(0,1.7,5,11,20,34,51,68)
        sand_material='鳌山湾 · 湿沙至干沙'
        pens=[self.shore.buffer(d,quad_segs=6) if d else Polygon() for d in distance_bands]
        for lo,hi in zip(pens,pens[1:]):
            part=hi.difference(lo).intersection(self.beach)
            surface(bands,part,sand_material,f,12)
        inland=self.substrate.difference(self.beach)
        # Share profile breaklines with the sand mesh. The fine interface also
        # keeps independent surfaces from rising through the gentle upper beach.
        for lo,hi in zip(pens,pens[1:]):
            surface(soil,hi.difference(lo).intersection(inland),'grass',f,23)
        surface(soil,inland.difference(pens[-1]),'grass',f,32)
        self._emit(doc,soil,'waterfrontShore',surface='land')
        self._sand_mesh(doc,bands,sand_material)
        wall=Shape('北段潮汐湾 · 护岸立面与护脚')
        line=segmentize(self.shore,4)
        for p,q in zip(line.coords,list(line.coords)[1:]):
            w0=self.wall_weight(*p);w1=self.wall_weight(*q)
            if max(w0,w1)<.002:continue
            a=self.level-.17;b=self.level-.17
            wall.mesh('压顶下护岸',[(p[0],a,p[1]),(q[0],b,q[1]),(q[0],f(*q),q[1]),(p[0],f(*p),p[1])],[(0,1,2,3)],'#948e80')
        self._emit(doc,wall,'waterfrontShore',surface='wall')
    def _paved(self,doc):
        f=self.terrain.y
        shape=Shape('蓝谷人才公园 · 海滨步道及入园游线')
        surfaces=[(self.main,2.8),(self.branch,1.8),(self.approach,4.4),(self.entrance,3.5)]
        inner=combine([line.buffer(w-.20) for line,w in surfaces]).intersection(self.land).difference(self.street)
        border=self.path_geom.difference(inner).intersection(self.land).difference(self.street)
        surface(shape,border,'#aeaa9f',lambda x,z:f(x,z)+.085,12)
        surface(shape,inner,'#d3c8ae',lambda x,z:f(x,z)+.09,12)
        surface(shape,self.plazas.difference(self.path_geom),'#cec4b1',lambda x,z:f(x,z)+.065,14)
        self._emit(doc,shape,'waterfront',surface='walk',key='waterfront-promenade')
        road=Shape('听海路 · 公园侧道路延续')
        mapped=combine([LineString(r['line']).buffer(r['width']/2+.55) for r in self.data['roads'] if r.get('kind')=='secondary'])
        extra=self.street.intersection(self.park.buffer(16)).difference(mapped)
        surface(road,extra,'asphalt',lambda x,z:f(x,z)+.19,18)
        self._emit(doc,road,'waterfront',surface='road')
        self._beach_access(doc)
    def access_layout(self,s,width):
        x,z,dx,dz=line_pose(self.main,s);nx,nz=-dz,dx
        land=Point(x,z);coast=self.shore.interpolate(self.shore.project(land))
        if (coast.x-x)*nx+(coast.y-z)*nz<0:nx,nz=-nx,-nz
        reach=min(10,max(4,land.distance(coast)*.34))
        start=(x+nx*2.7,z+nz*2.7);end=(x+nx*(2.7+reach),z+nz*(2.7+reach))
        ra=(start[0]+dx*(width/2+2),start[1]+dz*(width/2+2))
        rb=(end[0]+dx*(width/2+13),end[1]+dz*(width/2+13))
        return x,z,dx,dz,nx,nz,reach,start,end,ra,rb

    def east_gate_walk(self):
        # Pick the south gate leaf and its connected, mapped service lane.
        # The approach continues across the shared road junction. The exact
        # pedestrian marking is unverified; no traffic signal or stripe is implied.
        road_ids=['way/982199363','way/982199365']
        lanes=[LineString(next(r['line'] for r in self.data['roads'] if r['id']==i)) for i in road_ids]
        lane=substring(lanes[0],lanes[0].project(Point(587.24,-51.60)),lanes[0].length)
        approach=substring(self.main,0,47)
        *_,ra,rb=self.access_layout(40,10)
        shore=self.shore.interpolate(self.shore.project(Point(rb)))
        dx=shore.x-rb[0];dz=shore.y-rb[1];length=math.hypot(dx,dz)
        target=(shore.x-dx/length*.35,shore.y-dz/length*.35)
        return LineString(list(lane.coords)+list(lanes[1].coords)[1:]+list(self.entrance.coords)[1:]+list(approach.coords)[1:]+[ra,rb,target])

    def _beach_access(self,doc):
        f=self.terrain.y;shape=Shape('亲水设施 · 台阶坐凳、下滩坡道')
        reserve=[]
        for number,s in enumerate((40,305,614,924,1210,1492)):
            width=15 if number%2 else 10
            x,z,dx,dz,nx,nz,reach,start,end,ra,rb=self.access_layout(s,width)
            center=(x+nx*(3+reach/2),z+nz*(3+reach/2))
            high=f(*start)+.085;low=min(high-.16,f(*end)+.04)
            count=max(2,min(7,round((high-low)/.15)))
            def pt(rad,lat,hh):return (x+nx*rad+dx*lat,hh,z+nz*rad+dz*lat)
            for i in range(count):
                a=2.7+reach*i/count;b=2.7+reach*(i+1)/count
                h=high+(low-high)*i/count;h2=high+(low-high)*(i+1)/count
                shape.mesh('看海坐阶',[pt(a,-width/2,h),pt(a,width/2,h),pt(b,width/2,h),pt(b,-width/2,h)],[(0,1,2,3)],'#b8afa0')
                shape.mesh('台阶立板',[pt(b,-width/2,h),pt(b,width/2,h),pt(b,width/2,h2),pt(b,-width/2,h2)],[(0,1,2,3)],'#9e978b')
            # An oblique run reaches the same back-beach with a gentler pitch.
            ramp=LineString([ra,rb]);ramp_poly=ramp.buffer(1.25,cap_style=2)
            def ry(xx,zz,r=ramp,a=high,b=f(*rb)+.035):
                return a+(b-a)*min(1,max(0,r.project(Point(xx,zz))/r.length))
            surface(shape,ramp_poly,'#c4bbab',ry,5)
            reserve.append(Point(*center).buffer(width+12))
        from qd_public_roofs import coastal_reserve
        self.furniture_reserve=combine(reserve).union(coastal_reserve())
        self._emit(doc,shape,'waterfront',surface='steps')
    def _bridge(self,doc):
        f=self.terrain.y;line=self.bridge_deck; length=line.length
        shape=Shape('北段实景 · 白色弧形观海廊桥')
        width=5.4
        def deck_y(s):
            x,z,_,_=line_pose(line,s)
            a=smooth(min(s/30,(length-s)/27))
            return (f(x,z)+.10)*(1-a)+(self.level+3.10)*a
        rows=[]
        for s in np.linspace(0,length,math.ceil(length/2.5)+1):
            x,z,dx,dz=line_pose(line,s);n=(-dz,dx);h=deck_y(s)
            def at(w,dy=0):return (x+n[0]*w,h+dy,z+n[1]*w)
            rows.append((s,at(-width/2),at(-.15),at(width/2),at(-width/2,-.38),at(width/2,-.38),at(-width/2,1.1),at(width/2,1.1)))
        for a,b in zip(rows,rows[1:]):
            for left,right,mat in ((1,2,'#a46e5c'),(2,3,'#779690'),(4,1,'#e0e0d3'),(3,5,'#e0e0d3'),(5,4,'#b7b9ad')):
                shape.mesh('弧形连续桥面',[a[left],a[right],b[right],b[left]],[(0,1,2,3)],mat)
            for bottom,top in ((1,6),(3,7)):
                railing_beam(shape,a[top],b[top],.075,'#e6e4d9')
                railing_beam(shape,a[bottom],a[top],.045,'#deded3')
                mid_a=tuple(p*.48+q*.52 for p,q in zip(a[bottom],a[top]))
                mid_b=tuple(p*.48+q*.52 for p,q in zip(b[bottom],b[top]))
                railing_beam(shape,mid_a,mid_b,.035,'#deded3')
        for s in np.arange(17,length-9,16):
            x,z,_,_=line_pose(line,s); top=deck_y(s)-.28;bottom=self.level-.34
            shape.cyl('圆形桥墩',x,(top+bottom)/2,z,.48,top-bottom,'#a6a797',12)
        self._emit(doc,shape,'waterfront',key='waterfront-overlook',surface='bridge')
    def _spring_gardens(self,doc):
        """Low planted pockets on the park side, clear of ramps and sea views."""
        from shapely.affinity import rotate,scale
        f=self.terrain.y
        avoid=combine([self.path_geom.buffer(3.2),self.bridge_deck.buffer(5),self.plazas.buffer(1.3),self.street.buffer(5),self.furniture_reserve,self.beach.buffer(2)])
        free=self.park.difference(avoid)
        plots=[];beds=Shape('园内春日草本 · 低矮曲线花境')
        for station in (106,265,474,747,1006,1373,1640,1890):
            x,z,dx,dz=line_pose(self.main,station);x+=dz*11.4;z-=dx*11.4
            eye=Point(x,z)
            patch=scale(eye.buffer(1,quad_segs=18),10,2.6).buffer(0)
            patch=rotate(patch,math.degrees(math.atan2(dz,dx)),origin=(x,z)).intersection(free)
            if patch.area<32:continue
            plots.append(patch)
            surface(beds,patch,'#8b9971',lambda x,z:f(x,z)+.036,4)
            surface(beds,patch.buffer(.19).difference(patch),'#b0ad97',lambda x,z:f(x,z)+.047,4)
        self.garden_mask=combine(plots)
        self._emit(doc,beds,'waterfront',surface='plantingBed')
        if not plots:return
        rng=random.Random(1453)
        clump=Shape('低海风草丛 · 嫩叶与旧叶')
        for j in range(22):
            a=rng.random()*math.tau;h=rng.uniform(.22,.51);rad=rng.uniform(.09,.23);dx,dz=math.cos(a),math.sin(a);w=rng.uniform(.015,.038)
            base=(rng.uniform(-.065,.065),rng.uniform(-.065,.065));leaves=[]
            for along,elev,width in ((0,0,w*.45),(rad*.38,h*.7,w),(rad,h,w*.1)):
                for sign in (-1,1):
                    leaves.append((base[0]+dx*along-dz*width*sign,elev,base[1]+dz*along+dx*width*sign))
            clump.mesh('海风草叶',leaves,[(0,1,3,2),(2,3,5,4)],rng.choice(('#82935e','#a0ae73','#849c65','#a9ac80')))
        mi=doc.shape(clump);i=0
        for p in plots:
            xmin,zmin,xmax,zmax=p.bounds
            for _ in range(100):
                x,z=rng.uniform(xmin,xmax),rng.uniform(zmin,zmax)
                if not p.contains(Point(x,z)):continue
                sz=rng.uniform(.8,1.38);i+=1
                doc.node('滨海春草 '+str(i),mesh=mi,at=(x,f(x,z)+.04,z),scale=(sz,sz,sz),yaw=rng.random()*math.tau,kind='waterfrontFurniture')

    def _details(self,doc):
        f=self.terrain.y
        lamp=Shape('实景样式 · 球头滨海灯')
        lamp.cyl('细杆',0,2.20,0,.074,4.4,'#d2d3c4',10);lamp.cyl('灯座',0,.19,0,.15,.38,'#9d9e8d',10)
        oval(lamp,'乳白灯罩',0,4.54,0,.205,.26,.205,'#e9e2bd')
        lm=doc.shape(lamp)
        bench=Shape('实景样式 · 木面石座')
        for off in [-.19,-.095,0,.095,.19]:bench.box('木条',0,.49,off,2.05,.075,.08,'#9c8163')
        for x in [-.68,.68]:bench.box('石座',x,.23,0,.25,.45,.48,'#a8a498')
        bm=doc.shape(bench)
        for k,s in enumerate(np.arange(12,self.main.length-3,38.7)):
            x,z,dx,dz=line_pose(self.main,s);nx,nz=dz,-dx
            xx,zz=x+nx*3.85,z+nz*3.85
            doc.node(f'滨海球头灯 {k+1:02d}',mesh=lm,at=(xx,f(xx,zz)+.015,zz),kind='waterfrontFurniture')
            if k%2:continue
            xx,zz=x+nx*4.1+dx*6,z+nz*4.1+dz*6
            doc.node(f'向海坐凳 {k//2+1:02d}',mesh=bm,at=(xx,f(xx,zz)+.04,zz),yaw=-math.atan2(dz,dx),kind='waterfrontFurniture')
        # Plant the landward belt in modest irregular clusters. The mapped
        # entrance, promenade, bridge and access ramps remain unobstructed.
        protected=combine([self.path_geom.buffer(5),self.bridge_deck.buffer(6),self.plazas.buffer(2),self.street.buffer(6),self.furniture_reserve,self.garden_mask.buffer(1),self.beach.buffer(1),self.shore.buffer(10)])
        gate_view=Polygon([(657,-65),(826,-104),(866,-113),(816,-77),(655,-49)])
        open_ground=self.park.difference(protected).difference(gate_view)
        allowed=prep(open_ground);rng=random.Random(67321)
        from qd_planting import prototype
        existing={m['name']:i for i,m in enumerate(doc.doc['meshes'])}
        trees=[existing.get('乔木'+str(i+1)) for i in range(3)];shrubs=[existing.get('灌丛'+str(i+1)) for i in range(2)]
        trees=[v if v is not None else doc.shape(prototype(i)) for i,v in enumerate(trees)]
        shrubs=[v if v is not None else doc.shape(prototype(i,True)) for i,v in enumerate(shrubs)]
        used=set();i=0
        xmin,zmin,xmax,zmax=self.park.bounds
        for _ in range(1050):
            x,z=rng.uniform(xmin,xmax),rng.uniform(zmin,zmax)
            if not allowed.contains(Point(x,z)):continue
            for _ in range(rng.randint(2,6)):
                xx,zz=x+rng.gauss(0,8),z+rng.gauss(0,9)
                cell=(int(xx//6),int(zz//6))
                if cell in used or not allowed.contains(Point(xx,zz)):continue
                used.add(cell);i+=1;small=rng.random()<.36
                pool=shrubs if small else trees;scale=rng.uniform(.61,1.1)
                doc.node(('滨海灌丛 ' if small else '滨海绿带 ')+str(i),mesh=rng.choice(pool),at=(xx,f(xx,zz)-.05,zz),
                         yaw=rng.random()*math.tau,scale=(scale,scale,scale),kind='flora',shrub=small)
    def _ripples(self,doc):
        self.surf.add(doc,self.level)

    def build(self,doc,terrain,catalog):
        self._shore(doc);self._paved(doc);self._bridge(doc);self._spring_gardens(doc);self._details(doc);self._ripples(doc)
        source=json.loads((ROOT/'data/waterfront_sources.json').read_text('utf8'))
        views={v['key']:{k:v[k] for k in ('eye','target','fov')} for v in source['viewpoints']}
        for key,name,x,z,h,r,note in LOCATIONS:
            yy=self.level+3.1 if key=='waterfront-overlook' else terrain.y(x,z)
            pose=views[key];anchor=(x,yy,z)
            absolute={k:[round(a+b,5) for a,b in zip(anchor,pose[k])] for k in ('eye','target')}
            absolute['fov']=pose['fov']
            catalog.append(dict(key=key,name=name,x=x,y=yy,z=z,h=h,r=r,group='滨海公园',note=note,viewpoint=absolute))


LOCATIONS=[
 ('waterfront-entrance','东门与听海路入园口',712,-57,3,65,'从会文广场东门经听海路进入临海绿地。道路节点来自开放街图，园内入口支线按影像概化。'),
 ('waterfront-promenade','青岛蓝谷人才公园 · 滨海步道',504,-684,3,95,'临校沿海连续步道据开放街图完整轨迹，园内灯凳与铺装参考现场照片。'),
 ('waterfront-beach','鳌山湾 · 岸阶与潮滩',455,-972,2,75,'面向鳌山湾的湿沙、干沙与亲水坐阶，模型表现单一潮位。'),
 ('waterfront-overlook','北段弧形观海廊桥',604,-1719,5,95,'开放街图弧线、卫星潮汐湾轮廓与航拍交叉定位，桥面高度、栏杆和墩距为概化值。')
]

