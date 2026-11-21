"""Photo-registered weather surfaces for 14 Qingdao campus academic buildings.

Values are local metres on the footprint centre. The ESRI orthophoto resolves
the plan of the grey service roofs and glazed bands; school/photographer obliques
distinguish roofs from the courts open to ground. Height and flashings are inferred.
All actual faces, soffits and local gaps remain inspectable in componentRanges.
"""
from dataclasses import dataclass
from functools import lru_cache
import math

import mapbox_earcut as earcut
import numpy as np
from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
import qd_video_colleges as video

def polygons(geometry):
    # The terrain iterator omits sub-0.04 m² flecks. A clipped corner of a
    # weather skin must survive even when it is smaller than a lawn triangle.
    if geometry.is_empty:return
    if geometry.geom_type=='Polygon':
        if geometry.area>1.e-10:yield geometry
    elif hasattr(geometry,'geoms'):
        for part in geometry.geoms:yield from polygons(part)


# id: (name, long axis, roof valley splits, photographed service rectangles,
#      transverse ridges, pale-blue roof panels by rectangle, lower flat connectors)
PLANS={
    868015915: ["淦昌苑D座","z",[-34,39],[[-18,-50,8,-41],[-0.8,-23,10.5,28],[-18,49,8,57]],[[2,1.1]],{},[]],
    868015916: ["第周苑D座","z",[-42,41],[[-22,-64,12,-54],[-4,-32,15,33],[-23,52,12,63]],[],{0:["x",1],1:["z",2],2:["x",1]},[]],
    868015918: ["第周苑C座","x",[-36.8,35],[[-53,4,-40,19],[-32,-16,-6,-3],[4,-16,29,-3],[40,4,52,20]],[[-1.5,1.1]],{1:["x",1],2:["x",1]},[]],
    868015919: ["第周苑A座","z",[-43,40],[[-10,-62,17,-53],[-16,-35,-1,34],[-10,54,16,63]],[],{1:["z",2]},[]],
    868015920: ["第周苑B座","x",[-38,35.5],[[-53,-18,-44,-1],[-28,1,27,12],[43,-16,52,-0.5]],[],{},[]],
    868015921: ["第周苑F座","x",[-45,41],[[-40,-5,-7,8],[4,-5,36,8]],[[-0.8,1.1]],{0:["x",1],1:["x",1]},[]],
    970257667: ["淦昌苑C座","x",[-39,-6.5,5.5,35.5],[[-55,2,-45,17],[-32,-14,-11,-2],[7,-14,28,-2],[42,2,51,17]],[],{},[2]],
    970257668: ["淦昌苑F座","x",[-39,35.5],[[-54,0.8,-45,17],[-32,-14,28,-3],[42,1,51,17]],[],{},[]],
    970257669: ["淦昌苑E座","x",[-39,34],[[-55,-18,-45,-2],[-33,0.3,-7,11],[4,0.7,27,11],[42,-17,51,-1]],[[-1.2,1.1]],{},[]],
    970257670: ["淦昌苑A座","z",[-38,37],[[-14,-55,14,-46],[-16,-26,-4,26],[-12,47,15,56]],[[0,1.8]],{},[]],
    970257671: ["第周苑E座","x",[-38,34.5],[[-54,-20,-42,-2],[-33,0,-6,12],[2,0,28,12],[39,-19,51,-1]],[[-2,1]],{1:["x",1],2:["x",1]},[]],
    970257672: ["会文北楼","x",[-49,-33,66,72],[[-94,-3,-52,12],[-25,-15,61,-1],[77,-7,90,7]],[[14,4]],{},[1,3]],
    970257673: ["会文南楼","x",[-49,-34,63.5,69.5],[[-94,-16,-54,-1],[-29,-2,57,13],[75,-12,88,1]],[[19,4]],{},[1,3]],
    1018848586: ["淦昌苑B座","x",[-50,-10,4,39],[[-58,-10,-53,5],[-45,-8,-17,4],[-6,-9,0,6],[9,-9,34,4],[46,-9,56,7]],[],{},[]],
}


def _triangles(poly):
    p=orient(poly,1)
    rr=[list(r.coords)[:-1] for r in (p.exterior,*p.interiors)]
    points=[a for ring in rr for a in ring]
    ends=np.cumsum([len(ring) for ring in rr],dtype=np.uint32)
    tt=earcut.triangulate_float64(np.asarray(points,dtype=np.float64),ends).reshape(-1,3)
    return points,tt


def _face(shape,label,geom,mat,y,down=False,weather_mesh=None):
    for p in polygons(geom):
        if p.area<1.e-6:continue
        xy,tt=_triangles(p)
        vv=[(x,y(x,z) if callable(y) else y,z) for x,z in xy]
        shape.mesh(label,vv,[tuple(t if down else reversed(t)) for t in tt],mat)
        if weather_mesh is not None:
            weather_mesh.extend(tuple(vv[i] for i in t) for t in tt)


def _sides(shape,label,geom,low,high,mat,inside=False):
    for p in polygons(geom):
        p=orient(p,1)
        for ring in (p.exterior,*p.interiors):
            xy=list(ring.coords)
            for (x,z),(xx,zz) in zip(xy,xy[1:]):
                vv=[(x,low,z),(x,high,z),(xx,high,zz),(xx,low,zz)]
                shape.mesh(label,vv,[(3,2,1,0) if inside else (0,1,2,3)],mat)


def _grid(geom,step=3.8):
    """Split long or re-entrant surfaces before interpolating elevation."""
    for poly in polygons(geom):
        x0,z0,x1,z1=poly.bounds
        xx=math.floor(x0/step)*step
        while xx<x1:
            zz=math.floor(z0/step)*step
            while zz<z1:
                tile=box(xx,zz,xx+step,zz+step)
                if poly.intersects(tile):
                    yield poly.intersection(tile)
                zz+=step
            xx+=step


def _axis_angle(poly,along_x):
    coords=list(poly.exterior.coords)
    choices=[]
    for (x,z),(xx,zz) in zip(coords,coords[1:]):
        dx,dz=xx-x,zz-z
        a=(math.degrees(math.atan2(dz,dx))+(90 if along_x else 0))%180-90
        if abs(a)<3.0:choices.append((math.hypot(dx,dz),a))
    return max(choices,default=(0,0))[1]


@dataclass
class Section:
    area: object
    decks: list
    crest: object
    low: float
    high: float
    connector: bool


class AcademicRoof:
    def __init__(self,poly,osm,h,pitch,overhang):
        name,axis,breaks,rectangles,ridges,lights,connectors=PLANS[osm]
        self.title=name;self.id=osm;self.height=h;self.overhang=overhang
        self.support=poly.buffer(0)
        self.outer=poly.buffer(overhang,join_style=2)
        self.angle=_axis_angle(poly,axis=='x')
        self.axis=axis;self.lights=lights;self.sections=[];self.decks=[]
        self.pitch=pitch
        self.light_zones=[];self.equipment_feet=[]
        def to_world(g):return rotate(g,self.angle,origin=(0,0))
        self.to_world=to_world
        full=rotate(self.outer,-self.angle,origin=(0,0))
        allow=self.outer.buffer(-1.20,join_style=2)
        for rect in rectangles:
            self.decks.append(to_world(box(*rect)).intersection(allow))
        for i,(a,b) in enumerate(zip((-400,*breaks),(*breaks,400))):
            stripe=box(a,-400,b,400) if axis=='x' else box(-400,a,400,b)
            unit=to_world(full.intersection(stripe)).intersection(self.outer)
            if unit.is_empty:continue
            connector=i in connectors
            # End and inner wings have separately hipped tops and shared low valleys.
            # A flat connecting roof sits at the existing wall crown between paired Huiwen wings.
            plate_list=[]
            inner_limit=unit.buffer(-.55,join_style=2)
            for ix,plane in enumerate(self.decks):
                gg=plane.intersection(inner_limit)
                if gg.area>.50:plate_list.append((ix,gg))
            crest_lines=[]
            for pos,_ in ridges:
                if not a+.1<pos<b-.1:continue
                line=LineString([(pos,-400),(pos,400)]) if axis=='x' else LineString([(-400,pos),(400,pos)])
                clip=to_world(line).intersection(unit.buffer(-5.,join_style=2))
                if not clip.is_empty:crest_lines.append(clip)
            if not plate_list and not connector:
                # A fully tiled pavilion has a short, genuine hip ridge instead of a terraced lid.
                mid=rotate(unit,-self.angle,origin=(0,0))
                x0,z0,x1,z1=mid.bounds; mx,mz=mid.representative_point().coords[0]
                line=(LineString([(x0,mz),(x1,mz)]) if x1-x0>z1-z0 else LineString([(mx,z0),(mx,z1)]))
                cut=to_world(line).intersection(unit.buffer(-min(x1-x0,z1-z0)*.29,join_style=2))
                if not cut.is_empty:crest_lines.append(cut)
            if not plate_list and not crest_lines and not connector:crest_lines.append(unit.representative_point())
            ref=unary_union([g for _,g in plate_list]+crest_lines)
            high=h+(.56 if connector else pitch*(.94 if i in (0,len(breaks)) else 1.0))+.08
            self.sections.append(Section(unit,plate_list,ref,h+.055,high,connector))

    @staticmethod
    def _interpolator(unit):
        bound=unit.area.boundary
        @lru_cache(maxsize=None)
        def yy(x,z):
            p=Point(x,z)
            outer=bound.distance(p);inner=unit.crest.distance(p)
            return unit.low+(unit.high-unit.low)*outer/max(.00001,outer+inner)
        return yy

    def y(self,x,z):
        q=Point(x,z)
        unit=min(self.sections,key=lambda u:u.area.distance(q))
        if unit.connector:return unit.high
        if any(g.covers(q) for _,g in unit.decks):return unit.high-.23
        return self._interpolator(unit)(x,z)

    def build(self,shape,tile,flat,fascia,metal):
        h=self.height
        surface_triangles=[]
        # The continuous slab is contained in the actual exterior and courtyard boundaries.
        _face(shape,'承重楼板上盖',self.support,fascia,h-.145)
        _face(shape,'承重楼板底面',self.support,fascia,h-.31,True)
        _sides(shape,'屋盖封边',self.support,h-.31,h-.145,fascia)
        _face(shape,'外挑檐底',self.outer.difference(self.support.buffer(-.015)),fascia,h-.22,True)
        _sides(shape,'外檐封板',self.outer,h-.22,h+.055,fascia)
        for u in self.sections:
            if u.connector:
                # Three physically distinct surfaces keep the flat connector, its edge,
                # and the adjacent taller hipped wings readable in oblique views.
                _sides(shape,'连接翼实体屋面侧边',u.area,u.low,u.high,fascia)
                _face(shape,'连接翼防水顶面',u.area,flat,u.high,weather_mesh=surface_triangles)
                inner=u.area.buffer(-.19,join_style=2)
                rim=u.area.difference(inner)
                _sides(shape,'连接翼女儿墙外侧',u.area,u.high,u.high+.16,fascia)
                _sides(shape,'连接翼女儿墙内侧',inner,u.high,u.high+.16,fascia,True)
                _face(shape,'连接翼金属压顶',rim,metal,u.high+.16)
                continue
            terraces=unary_union([g for _,g in u.decks]) if u.decks else Polygon()
            roof=u.area.difference(terraces)
            elev=self._interpolator(u)
            for cell in _grid(roof):
                _face(shape,'主瓦坡外表面',cell,tile,elev,weather_mesh=surface_triangles)
            self._hip_caps(shape,u,terraces,elev,tile)
            for ix,deck in u.decks:
                rim_inside=deck.buffer(-.20,join_style=2)
                _face(shape,'平台周缘金属泛水',deck.difference(rim_inside),metal,u.high,weather_mesh=surface_triangles)
                _sides(shape,'平台内侧收口',rim_inside,u.high-.23,u.high,metal,True)
                _face(shape,'有支撑的设备平台防水面',rim_inside,flat,u.high-.23,weather_mesh=surface_triangles)
                if ix in self.lights:
                    direction,count=self.lights[ix]
                    self._lights(shape,rim_inside,direction,count,u.high-.23,metal)
                video.service_deck(self,shape,rim_inside,u.high-.23,metal,ix)
        self.sheet=RoofSheet(surface_triangles)
        self.dormer_strip_counts=[]
        shape.college_roof=self

    def _hip_caps(self,shape,unit,terraces,elev,tile):
        corners=[tuple(c) for _,g in unit.decks for p in polygons(g) for c in list(p.exterior.coords)[:-1]]
        if not corners:return
        skin=unit.area.buffer(-.12).difference(terraces.buffer(.12))
        for shell in polygons(unit.area):
            ring=list(orient(shell,1).exterior.coords)[:-1]
            for i,(x,z) in enumerate(ring):
                px,pz=ring[i-1];qx,qz=ring[(i+1)%len(ring)]
                ax,az=x-px,z-pz;bx,bz=qx-x,qz-z
                if ax*bz-az*bx<.37*math.hypot(ax,az)*math.hypot(bx,bz):continue
                tx,tz=min(corners,key=lambda p:(p[0]-x)**2+(p[1]-z)**2)
                line=LineString([(x,z),(tx,tz)])
                if not 2.4<line.length<24:continue
                segment=line.intersection(skin)
                if segment.geom_type!='LineString' or segment.length<1.2:continue
                dx,dz=(tx-x)/line.length,(tz-z)/line.length
                verts=[];faces=[];n=max(2,math.ceil(segment.length/.82))
                for j in range(n+1):
                    pos=segment.interpolate(segment.length*j/n)
                    for u,rise in ((-.12,.022),(0.,.124),(.12,.022)):
                        xx,zz=pos.x-u*dz,pos.y+u*dx
                        verts.append((xx,elev(xx,zz)+rise,zz))
                    if j:
                        k=j*3
                        faces.extend([(k-3,k-2,k+1,k),(k-2,k-1,k+2,k+1)])
                shape.mesh('红瓦斜脊压瓦',verts,faces,tile)

    def _lights(self,shape,deck,direction,count,base,metal):
        local=rotate(deck,-self.angle,origin=(0,0))
        x0,z0,x1,z1=local.bounds;cx,cz=local.representative_point().coords[0]
        along_x=direction=='x'
        long=(x1-x0) if along_x else (z1-z0);short=(z1-z0) if along_x else (x1-x0)
        run=min(27.7,long*(.77 if count==1 else .40));span=min(7.4,short*.52)
        if min(run,span)<.75:return
        ca,sa=math.cos(math.radians(self.angle)),math.sin(math.radians(self.angle))
        def block(tag,x,z,w,d,yy,hh,mat):
            shape.box(tag,x*ca-z*sa,yy,x*sa+z*ca,w,hh,d,mat,-math.radians(self.angle))
        for j in range(count):
            d=(j-(count-1)/2)*long*.49
            x=(x0+x1)/2+d if along_x else cx;z=cz if along_x else (z0+z1)/2+d
            w,dep=(run,span) if along_x else (span,run)
            pl=box(x-w/2-.16,z-dep/2-.16,x+w/2+.16,z+dep/2+.16)
            if not local.covers(pl):continue
            self.light_zones.append(pl.buffer(.25,join_style=2))
            block('屋面带状构件支座',x,z,w+.30,dep+.30,base+.17,.34,metal)
            if self.id in (868015919,868015916,970257671,868015921):
                video.raised_light(shape,x,z,run,span,direction,self.angle,base,metal)
                continue
            block('浅灰蓝色带状屋面板',x,z,w,dep,base+.37,.12,'#839b9a')
            bars=max(2,round(run/2.35))
            for k in range(1,bars):
                t=k/bars-.5
                block('带状屋面板压条',x+(run*t if along_x else 0),z+(0 if along_x else run*t),
                      .075 if along_x else w,.075 if not along_x else dep,base+.45,.06,metal)

    def _vents(self,shape,deck,base,metal,ix):
        # Only faint, low service projections on the larger visible equipment decks.
        if deck.area<135:return
        p=rotate(deck,-self.angle,origin=(0,0));x0,z0,x1,z1=p.bounds
        for j in range(2 if deck.area>290 else 1):
            x=x0+(x1-x0)*(.24+.44*j);z=z0+(z1-z0)*(.33+.10*(ix%3))
            c=self.to_world(Point(x,z))
            if deck.covers(c.buffer(1.5)):
                shape.box('设备平台矮罩',c.x,base+.27,c.y,1.60,.54,1.02,metal,-math.radians(self.angle))


class RoofSheet:
    """Height and edge crossings of the actual triangulated weather skin, in local X/Z."""
    def __init__(self,triangles):
        from shapely import STRtree
        self.faces=[];self.planes=[]
        for a,b,c in triangles:
            den=(b[0]-a[0])*(c[2]-a[2])-(c[0]-a[0])*(b[2]-a[2])
            if abs(den)<1.e-10:continue
            sx=((b[1]-a[1])*(c[2]-a[2])-(c[1]-a[1])*(b[2]-a[2]))/den
            sz=((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/den
            self.faces.append(Polygon([(v[0],v[2]) for v in (a,b,c)]))
            self.planes.append((sx,sz,a[1]-sx*a[0]-sz*a[2]))
        self.index=STRtree(self.faces)

    def y(self,x,z):
        q=Point(x,z)
        ids=self.index.query(q,predicate='intersects')
        if not len(ids):return None
        return min(self.planes[i][0]*x+self.planes[i][1]*z+self.planes[i][2] for i in ids)

    def spans(self,a,b):
        x,z=a[0],a[2];dx,dz=b[0]-x,b[2]-z
        d2=dx*dx+dz*dz
        line=LineString([(x,z),(b[0],b[2])]);cuts={0.,1.};coverage=[]
        # Exact intersections catch narrow valleys which uniformly spaced samples can straddle.
        for i in self.index.query(line,predicate='intersects'):
            hit=self.faces[i].intersection(line)
            if hit.geom_type!='LineString' or hit.length<1.e-8:continue
            e=list(hit.coords)
            ts=sorted(max(0.,min(1.,((qx-x)*dx+(qz-z)*dz)/d2)) for qx,qz in (e[0],e[-1]))
            cuts.update(round(t,10) for t in ts);coverage.append((ts[0],ts[1],self.planes[i]))
        steps=max(1,math.ceil(math.sqrt(d2)/.12))
        cuts.update(k/steps for k in range(1,steps));cuts=sorted(cuts)
        for t,u in zip(cuts,cuts[1:]):
            if u-t<1.e-8:continue
            mid=(t+u)/2;mx=x+dx*mid;mz=z+dz*mid
            planes=[pl for low,high,pl in coverage if low-1.e-8<=mid<=high+1.e-8]
            if not planes:
                raise ValueError('Dormer edge escaped the triangulated weather roof at '+str((mx,mz)))
            plane=min(planes,key=lambda v:v[0]*mx+v[1]*mz+v[2])
            yield t,u,plane


def dormer_walls(shape,roof,front,back,front_setback,stone,side_stone):
    """Six connected wall runs, from the actual cap soffit into the exact supporting triangles."""
    def move(p,q,distance):
        frac=distance/max(.001,math.hypot(q[0]-p[0],q[2]-p[2]))
        return tuple(p[k]+(q[k]-p[k])*frac for k in range(3))
    def inset(row,other,distance):
        a,mid,b=[move(p,q,distance) for p,q in zip(row,other)]
        hor=(move(a,mid,.046),mid,move(b,mid,.046))
        return [(x,y-.082,z) for x,y,z in hor]
    front,back=inset(front,back,front_setback),inset(back,front,.038)
    boundary=[('前',front[0],front[1]),('前',front[1],front[2]),
              ('侧',front[2],back[2]),('后',back[2],back[1]),
              ('后',back[1],back[0]),('侧',back[0],front[0])]
    counts={'前':0,'后':0,'侧':0}
    for tag,a,b in boundary:
        vertices=[];faces=[]
        for t,u,plane in roof.sheet.spans(a,b):
            off=len(vertices)
            ends=[tuple(a[k]+(b[k]-a[k])*v for k in range(3)) for v in (t,u)]
            bottom=[]
            for xx,yy,zz in ends:
                roof_y=plane[0]*xx+plane[1]*zz+plane[2]
                bottom.append((xx,min(yy-.038,roof_y-.085),zz))
            vertices.extend([*ends,bottom[1],bottom[0]])
            faces.append((off+3,off+2,off+1,off))
            counts[tag]+=1
        shape.mesh('老虎窗'+tag+'墙贴坡封板',vertices,faces,stone if tag=='前' else side_stone)
    roof.dormer_strip_counts.append(counts)


def pitched_cap(shape,label,vertices,faces,thickness,tile,fascia):
    """Build upward facing top faces and seal only the true perimeter, not its shared ridge."""
    points=list(vertices)+[(x,y-thickness,z) for x,y,z in vertices]
    count=len(vertices);sides={};top=[]
    for ring in faces:
        a,b,c=(points[i] for i in ring[:3])
        ny=(b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2])
        ring=tuple(ring if ny>0 else reversed(ring));top.append(ring)
        for i,j in zip(ring,ring[1:]+ring[:1]):
            key=tuple(sorted((i,j)))
            if key in sides:sides.pop(key)
            else:sides[key]=(i,j)
    shape.mesh(label,points,top,tile)
    shape.mesh(label+'檐底',points,[tuple(i+count for i in reversed(face)) for face in top],fascia)
    shape.mesh(label+'封檐',points,[(j,i,i+count,j+count) for i,j in sides.values()],fascia)
