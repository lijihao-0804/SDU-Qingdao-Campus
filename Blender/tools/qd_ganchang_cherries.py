"""Four white-flowering cherry rows in the western Ganchang garden, as seen in user photos 3/4."""
import math
import random
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString,Point
from shapely.ops import substring,unary_union

from qd_geometry import Shape
from qd_spring import BLOSSOM,_truss,_twig,_leaf,_move,_curve
from qd_petal_sprays import flowering_spur
from qd_terrain import sourcepolygon

LANES=(('north','北','way/868015911'),('south','南','way/868015912'))
BRICK='#a98f78'
BARK='#77756e'
TWIG='#655950'
WHITEWASH='#c7c7bc'
PETALS=('#f5ede9','#f6ebe7','#ecd9dc','#eee1df','#f9f1e8')
GREEN=('#789457','#a0a969')


@dataclass(frozen=True)
class RowTree:
    lane: str
    side: int
    x: float
    z: float
    variant: int
    scale: float
    yaw: float


class Layout:
    """Only the west segment between the A building and the middle crossing is resurfaced."""
    def __init__(self,data):
        rows={r['id']:r for r in data['roads']}
        buildings=unary_union([sourcepolygon(r) for r in data['buildings']])
        branches=unary_union([LineString(r['line']).buffer(r['width']/2+.65)
                               for r in data['roads'] if r['id'] not in {lane[2] for lane in LANES}
                               and not r.get('tunnel') and len(r['line'])>1])
        self.lines={};self.half={};self.trees=[];pads=[]
        rng=random.Random(130431)
        for lane,_,rid in LANES:
            source=rows[rid]
            # Each OSM line has a vertex on the central cross street between gardens.
            full=LineString(source['line'][:2])
            line=substring(full,3.02,full.length-3.02)
            self.lines[lane]=line;self.half[lane]=source['width']/2.
            pad=line.buffer(self.half[lane],cap_style=2)
            pads.append(pad)
            for side in (-1,1):
                for j,distance in enumerate(np.arange(5.15,line.length-4.5,6.95)):
                    p=line.interpolate(distance+rng.uniform(-.18,.18))
                    q=line.interpolate(distance+.8)
                    dx,dz=q.x-p.x,q.y-p.y;length=math.hypot(dx,dz)
                    offset=side*(self.half[lane]+rng.uniform(1.30,1.65))
                    x=p.x-offset*dz/length;z=p.y+offset*dx/length
                    if 238.5 < x < 252.3:continue  # crosswise entrance walk opposite B/F
                    tree=Point(x,z)
                    if tree.distance(buildings)<3.8 or branches.covers(tree):continue
                    self.trees.append(RowTree(lane,side,x,z,j%3,rng.uniform(.90,1.075),rng.uniform(0,math.tau)))
        self.pavement=unary_union(pads)
        # Suppress pre-existing random road-edge trees and the generated sidewalk in
        # the two strips. Transverse streets and the central garden stay outside this reserve.
        self.reserve=unary_union([line.buffer(self.half[k]+6.50,cap_style=2)
                                  for k,line in self.lines.items()]).difference(branches)
        # C and E face the east half of the same pair of streets. Both rows
        # sit inside the median garden, behind the existing 2.65 m sidewalks.
        by_id={r['id']:sourcepolygon(r) for r in data['buildings']}
        c,e=(by_id[key].centroid for key in ('way/970257667','way/970257669'))
        self.ce_axis=LineString([c,e])
        self.ce_lines={}
        self.ce=[]
        self.ce_hard=unary_union([buildings,*[
            LineString(r['line']).buffer(r['width']/2+2.65)
            for r in data['roads'] if len(r['line'])>1 and not r.get('tunnel')]])
        ce_rng=random.Random(62239)
        for lane,_,rid in LANES:
            line=LineString(rows[rid]['line'][1:])
            self.ce_lines[lane]=line
            side=1 if lane=='north' else -1
            for j,d in enumerate(np.arange(14.,line.length-12.,8.4)):
                along=d+ce_rng.uniform(-.35,.35)
                p=line.interpolate(along);q=line.interpolate(along+.8)
                dx,dz=q.x-p.x,q.y-p.y
                offset=side*(rows[rid]['width']/2+2.65+ce_rng.uniform(3.65,4.4))
                x,z=p.x-dz/.8*offset,p.y+dx/.8*offset
                point=Point(x,z)
                if self.ce_axis.distance(point)<11.5 or self.ce_hard.distance(point)<3.4:
                    continue
                self.ce.append(RowTree(lane,side,x,z,j%3,ce_rng.uniform(.90,1.035),ce_rng.uniform(0,math.tau)))
        reserved=unary_union([Point(t.x,t.z).buffer(6.2) for t in self.ce])
        self.reserve=self.reserve.union(reserved.difference(self.ce_hard))


def _flowering_cherry(variant):
    """Light-grey scaffold limbs fork off a short whitewashed trunk."""
    rng=random.Random(42960+variant*117)
    flowers=random.Random(82290+variant*83)
    inner=random.Random(7816+variant*37)
    shape=Shape(f'淦昌粉白樱 · 分叉与花序 {variant+1}')
    shape.uvs=defaultdict(list);shape.vertex_tints=defaultdict(list)
    base=(0.,-.055,0.);step=(.028,1.02,-.025)
    fork=(rng.uniform(-.1,.1),1.43+rng.uniform(-.10,.10),rng.uniform(-.10,.13))
    _twig(shape,base,step,.129,.107,WHITEWASH);_twig(shape,step,fork,.107,.095,BARK)
    phi=rng.random()*math.tau
    for j in range(7):
        angle=phi+j*2.39996+rng.uniform(-.23,.24)
        start=_curve(step,fork,.48+.45*((j+1)%4)/3)
        low=_move(start,angle,.30+rng.random()*.19,rng.uniform(.68,.88))
        elbow=_move(low,angle+.13,rng.uniform(.36,.63),rng.uniform(.56,.82))
        crown=_move(elbow,angle-.11,rng.uniform(.27,.67),rng.uniform(.53,.89))
        _twig(shape,start,low,.078 if j<4 else .054,.054,BARK)
        _twig(shape,low,elbow,.057,.037,BARK);_twig(shape,elbow,crown,.038,.020,BARK)
        for k in range(6):
            origin=_curve(low,elbow,.33+.24*k) if k<3 else _curve(elbow,crown,.26+.28*(k-3))
            fan=angle+(1 if k%2 else -1)*rng.uniform(.62,1.32)
            shoulder=_move(origin,fan,rng.uniform(.39,.69),rng.uniform(.27,.68))
            _twig(shape,origin,shoulder,.026,.012,BARK)
            # Short flowering spurs on the older scaffold fill portions of the
            # inner crown. The longer terminal shoots still leave open windows.
            for u in ((.43,.78) if (j+k)%3 else (.60,)):
                joint=_curve(origin,shoulder,u)
                heading=fan+inner.choice((-.82,.71))
                spur=_move(joint,heading,inner.uniform(.055,.12),inner.uniform(.06,.14))
                _twig(shape,joint,spur,.0055,.0021,TWIG)
                _truss(shape,spur,heading,.88,inner.uniform(.16,.21),inner.choice(PETALS),inner)
                if (j+k)%2==0:
                    flowering_spur(shape,spur,heading+.38,.16,PETALS,inner,count=2)
            for zeta in (-.64,.03,.69):
                theta=fan+zeta+rng.uniform(-.16,.15)
                tip=_move(shoulder,theta,rng.uniform(.36,.66),rng.uniform(.20,.64))
                _twig(shape,shoulder,tip,.013,.0034,TWIG)
                # Several pale sprays grow along each short twig. Crossing trusses
                # retain mass at a distance and separation of the individual petals nearby.
                for f in (.24,.51,.74,.96):
                    joint=_curve(shoulder,tip,f);a=theta+rng.uniform(-1.48,1.48)
                    shoot=_move(joint,a,rng.uniform(.035,.11),rng.uniform(.01,.09))
                    _twig(shape,joint,shoot,.0035,.0016,TWIG)
                    size=rng.uniform(.17,.27)
                    _truss(shape,shoot,a,rng.uniform(.52,1.34),size,rng.choice(PETALS),rng)
                    _truss(shape,shoot,a+rng.uniform(.97,1.86),rng.uniform(.34,1.33),
                           size*rng.uniform(.74,.97),rng.choice(PETALS),rng)
                    # An opaque outer spray keeps a continuous silhouette against
                    # the sky, with downward and lateral blossoms on separate stalks.
                    if f in (.51,.96):
                        flowering_spur(shape,shoot,a+.9,size*.86,PETALS,flowers,
                                       count=3 if f==.96 else 2,pendulous=True)
                    if rng.random()<.29:
                        _leaf(shape,shoot,a+.7,rng.uniform(.095,.15),.027,rng.uniform(.01,.085),rng.choice(GREEN))
    return shape


def _brick_texture(scene):
    from PIL import Image
    from qd_spring_surfaces import add_image
    rng=np.random.default_rng(40721)
    # A seamless running bond. The UV repeat is 1.20 by 1.20 metres (four by eight
    # .30 x .15 m brick stretchers and their neighbours rather than metre-wide "bricks").
    q=256;yy,xx=np.mgrid[:q,:q];row=yy//32;u=(xx+32*(row%2))%64
    edge=np.minimum(np.minimum(u,64-u),np.minimum(yy%32,32-yy%32))
    joints=np.clip(1.-edge/2.0,0,1)
    cells=rng.uniform(-6,6,(8,4))[row,((xx+32*(row%2))//64)%4]
    shade=np.clip(239+cells+rng.normal(0,2.0,(q,q))-joints*26,185,255).astype(np.uint8)
    tile=Image.fromarray(np.repeat(shade[:,:,None],3,axis=2))
    tex=add_image(scene,'淦昌花径 · 错缝棕砖',tile,'PNG',True)
    pbr=scene.doc['materials'][scene.colors[BRICK]]['pbrMetallicRoughness']
    pbr.update(baseColorTexture=tex,roughnessFactor=.94,metallicFactor=0.)


def _pavement(scene,terrain,layout):
    ground=Shape('淦昌苑 · 两条棕砖花径')
    for key,line in layout.lines.items():
        width=layout.half[key]
        out=line.buffer(width,cap_style=2);dark=line.buffer(width-.20,cap_style=2)
        buff=line.buffer(width-.43,cap_style=2);middle=line.buffer(width-.55,cap_style=2)
        terrain.skin(ground,out.difference(dark),'#d5c4a4',.228)
        terrain.skin(ground,dark.difference(buff),'#756e66',.228)
        terrain.skin(ground,buff.difference(middle),'#c8b395',.228)
        bars=[]
        for d in np.arange(7.2,line.length-4.,8.2):
            a,b=line.interpolate(d),line.interpolate(d+.1)
            dx,dz=b.x-a.x,b.y-a.y;ln=math.hypot(dx,dz);nx,nz=-dz/ln,dx/ln
            bars.append(LineString([(a.x+nx*width,a.y+nz*width),(a.x-nx*width,a.y-nz*width)]).buffer(.047,cap_style=2))
        joints=unary_union(bars).intersection(middle)
        terrain.skin(ground,joints,'#c9b79f',.228)
        terrain.skin(ground,middle.difference(joints),BRICK,.228)
    ground.uvs={BRICK:[(x/1.2,z/1.2) for x,y,z in ground.parts[BRICK][0]]}
    scene.node(ground.name,shape=ground,kind='ground',site='ganchang-cherries')
    _brick_texture(scene)


def build(scene,terrain,catalog,layout):
    _pavement(scene,terrain,layout)
    meshes=[];bounds=[]
    for i in range(3):
        tree=_flowering_cherry(i)
        verts=np.asarray([pt for v,n,idx in tree.parts.values() for pt in v])
        bounds.append((float(np.linalg.norm(verts[:,[0,2]],axis=1).max()),float(verts[:,1].max())))
        meshes.append(scene.shape(tree))
    counts=defaultdict(int)
    for t in layout.trees:
        counts[t.lane,t.side]+=1
        lane_name='北' if t.lane=='north' else '南';side_name='南侧' if t.side==1 else '北侧'
        key='ganchang-cherry-walk' if t.lane=='north' else 'ganchang-cherry-south'
        scene.node(f'淦昌苑{lane_name}花径 · {side_name}樱花 {counts[t.lane,t.side]}',
                   mesh=meshes[t.variant],at=(t.x,terrain.y(t.x,t.z)+.015,t.z),yaw=t.yaw,
                   scale=(t.scale,t.scale,t.scale),kind='flora',species='浅粉白樱花',shrub=False,
                   site=key,row=side_name,season='spring',canopyRadius=round(bounds[t.variant][0]*t.scale,3))
    ce_key='ganchang-ce-cherries'
    ce_counts=defaultdict(int)
    for t in layout.ce:
        ce_counts[t.lane]+=1
        side='C座侧' if t.lane=='north' else 'E座侧'
        scene.node(f'淦昌苑C、E座间 · {side}樱花 {ce_counts[t.lane]}',
                   mesh=meshes[t.variant],at=(t.x,terrain.y(t.x,t.z)+.015,t.z),yaw=t.yaw,
                   scale=(t.scale,)*3,kind='flora',species='浅粉白樱花',shrub=False,site=ce_key,
                   row=side,season='spring',canopyRadius=round(bounds[t.variant][0]*t.scale,3))
    # Bind once if the caller runs this module before or apart from qd_spring.build.
    atlas=scene.doc['materials'][scene.colors[BLOSSOM]]
    if 'baseColorTexture' not in atlas['pbrMetallicRoughness']:
        from qd_spring import _blossom_texture
        _blossom_texture(scene)
    for key,label,_ in LANES:
        line=layout.lines[key]
        def point(at,lateral=0.,height=0.):
            a=line.interpolate(at);b=line.interpolate(at+.1);dx,dz=b.x-a.x,b.y-a.y;ln=math.hypot(dx,dz)
            x,z=a.x-lateral*dz/ln,a.y+lateral*dx/ln
            return [round(x,3),round(terrain.y(x,z)+height,3),round(z,3)]
        eye=point(9.,-.20,1.88);look=point(42.,0.,1.98)
        near=point(13.,.55,1.95)
        subject=min((t for t in layout.trees if t.lane==key and t.side==1),
                    key=lambda t:abs(line.project(Point(t.x,t.z))-20.))
        target=[round(subject.x,3),round(terrain.y(subject.x,subject.z)+3.25*subject.scale,3),round(subject.z,3)]
        cx,cy,cz=point(36.)
        location='ganchang-cherry-south'
        title=f'淦昌苑樱花{label}径'
        caption='沿花径望去'
        if key=='north':
            # Looking west from just east of the middle intersection, both parallel
            # lanes flank the planted court. A ground-level position hides the far row.
            north_end=layout.lines['north'].coords[-1];south_end=layout.lines['south'].coords[-1]
            aim_x=(north_end[0]+south_end[0])/2-72.;aim_z=(north_end[1]+south_end[1])/2
            ex=(north_end[0]+south_end[0])/2+13.;ez=aim_z
            eye=[round(ex,3),round(terrain.y(ex,ez)+13.8,3),round(ez,3)]
            look=[round(aim_x,3),round(terrain.y(aim_x,aim_z)+1.9,3),round(aim_z,3)]
            cx,cy,cz=(aim_x,terrain.y(aim_x,aim_z),aim_z)
            location='ganchang-cherry-walk';title='淦昌苑樱花径';caption='两径四行樱花'
        catalog.append(dict(key=location,name=title,
                   aliases=[f'淦昌苑{label}侧樱花小路','淦昌苑A/B座樱花','淦昌苑樱花'],
                   x=cx,y=cy,z=cz,h=4.8,r=28,group='春日花木',
                   note='按现场照片复原浅粉白花簇、浅色树干及棕砖园路；两条路各有两排樱花。单株位置与树高按照片和开放地图估计。',
                   viewpoint=dict(eye=eye,target=look,fov=53),
                   views={'facade':dict(label=caption,eye=eye,target=look,fov=53,hideMapLabels=True),
                          'detail':dict(label='近看樱花与分枝',eye=near,target=target,fov=41,hideMapLabels=True)}))
    def ce_camera(x,z,height):
        return [round(x,3),round(terrain.y(x,z)+height,3),round(z,3)]
    court=layout.ce_axis.interpolate(.5,normalized=True)
    street=layout.ce_lines['north'].interpolate(18.)
    subject=min((t for t in layout.ce if t.lane=='north'),key=lambda t:abs(t.x-street.x-18.))
    target=ce_camera(court.x,court.y,1.8)
    overview=dict(eye=ce_camera(455.,court.y+5.,17.),target=target,fov=49,
                  label='俯看C、E两座之间的樱花',hideMapLabels=True)
    path=dict(eye=ce_camera(street.x,street.y+4.3,1.84),target=ce_camera(subject.x,subject.z,2.65),
              fov=48,label='沿C座侧人行道看花',hideMapLabels=True)
    catalog.append(dict(key=ce_key,name='淦昌苑C、E座间樱花庭院',group='春日花木',
                        aliases=['淦昌苑CE之间樱花','C座与E座之间的樱花','淦昌苑东庭樱花'],
                        x=court.x,y=terrain.y(court.x,court.y),z=court.y,h=4.8,r=30,
                        note='据现场补充，C座与E座之间有樱花。树位、株数和行距为按楼宇、路网和入口留白估计的情景复原。',
                        viewpoint=path,views={'facade':overview,'path':path}))
    ce_gaps=[layout.ce_hard.distance(Point(t.x,t.z))-bounds[t.variant][0]*t.scale for t in layout.ce]
    return dict(rows={f'{k}-{"south" if s==1 else "north"}':counts[k,s] for k,_,_ in LANES for s in (-1,1)},
                trees=len(layout.trees),pavement_m2=round(layout.pavement.area,2),
                ce_court=dict(site=ce_key,trees=len(layout.ce),rows=dict(ce_counts),
                              minimum_crown_to_road_walk_or_building_m=round(min(ce_gaps),3),
                              minimum_root_to_entrance_axis_m=round(min(layout.ce_axis.distance(Point(t.x,t.z)) for t in layout.ce),3),
                              placement_basis='用户确认两座之间有樱花，逐株位置、数量与行距为估计。'),
                minimum_trunk_to_pavement_m=round(min(Point(t.x,t.z).distance(layout.pavement) for t in layout.trees),3),
                prototype_height_m=[round(h,2) for _,h in bounds],prototype_radius_m=[round(rad,2) for rad,_ in bounds])
