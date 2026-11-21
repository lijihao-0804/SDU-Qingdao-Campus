"""Phoenix Residence formal garden, X east / Z south, metres.

The April 2025 campus aerial resolves pale-trunked flowering standards, lower
pink and gold beds, clipped green outer edges and a second bronze-coloured hedge.
Rows, crown sizes and pigments below are estimates. No cultivar is assigned.
The original mapped walk network determines every large bed; crossings keep
their own widths and heights in build_campus. Photo and aerial use the same
northward axis and the small pavilion in the centre as registration points.
"""
import math
import random
from collections import Counter
from collections import defaultdict
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.prepared import prep

from qd_geometry import Shape
from qd_planting import branch
from qd_terrain import polygons
from qd_spring import _truss
from qd_petal_sprays import flowering_spur, leaf_blade

SOURCE='https://www.qdxq.sdu.edu.cn/info/1831/60590.htm'
PHOTO='实景参照/春日建筑/凤凰居-2025年中央花圃与两翼.jpg'
KEY='spring_phoenix_garden'
WALKS={f'way/{n}' for n in [548364991,982199359,*range(868015892,868015901)]}
# North to south: three calm forecourts alternate with the paired diagonal walks.
ZONES=('lawn','court','deep','gold','pale','court','deep','gold','pale','court','lawn')


def _layout(data):
    paths=[r for r in data['roads'] if r['id'] in WALKS]
    cores=unary_union([LineString(r['line']) for r in paths])
    sidewalks=unary_union([LineString(r['line']).buffer(r['width']*.5+.36,quad_segs=6) for r in paths])
    faces=sorted((p for p in polygonize(cores) if 296<p.centroid.x<324 and 637<p.centroid.y<1001),
                 key=lambda p:p.centroid.y)
    if len(faces)!=len(ZONES):
        raise ValueError('Expected eleven garden cells formed by Phoenix Residence walks, found '+str(len(faces)))
    layout=[]
    for mode,face in zip(ZONES,faces):
        # Rounded bed ends and a short grass shoulder occur between the hedge and curb.
        safe=face.difference(sidewalks)
        inset=safe.buffer(-2.05).buffer(1.83,quad_segs=6)
        layout.append((mode,inset))
    return layout


def reserve(data):
    """Only the mapped central islands are taken out of ordinary planting."""
    return unary_union([area for _,area in _layout(data)])


def _lobe(shape,p,rx,ry,rz,material,rng):
    x,y,z=p;angle=rng.random()*math.tau
    vert=[(x,y+ry,z),(x,y-ry*.83,z)]
    normal=[(0,1,0),(0,-1,0)]
    for j in range(7):
        a=angle+j*math.tau/7;v=rng.uniform(.81,1.07);offset=rng.uniform(-.18,.26)
        vert.append((x+rx*math.cos(a)*v,y+ry*offset,z+rz*math.sin(a)*v))
        normal.append((math.cos(a),offset,math.sin(a)))
    vv,nn,ii=shape.parts[material];off=len(vv);vv.extend(vert);nn.extend(normal)
    for j in range(7):
        k=2+j;l=2+(j+1)%7;ii.extend((off,off+l,off+k,off+1,off+k,off+l))


def _to(p,a,d,up):
    return (p[0]+math.cos(a)*d,p[1]+up,p[2]+math.sin(a)*d)


def _prototype(kind,variant):
    rng=random.Random(8136+variant*61+('pale','deep','gold','evergreen').index(kind)*305)
    shape=Shape('凤凰居 · '+{'pale':'浅粉小乔木','deep':'深粉花木','gold':'黄色花灌丛','evergreen':'常绿矮灌'}[kind]+str(variant+1))
    shape.uvs=defaultdict(list);shape.vertex_tints=defaultdict(list)
    flower_rng=random.Random(31900+variant*21)
    colors={'pale':('#e6bbcf','#eecbd8','#e1b4c4','#f0d7d9'),
            'deep':('#cf7da4','#d98db1','#e59eb6','#c7789e'),
            'gold':('#dcae2b','#e7bd3d','#cf9f24','#efc74d'),
            'evergreen':('#657d49','#72894c','#85944f','#788b4b')}[kind]
    tree=kind in ('pale','deep')
    if tree:
        fork=(rng.uniform(-.055,.055),rng.uniform(.92,1.13),rng.uniform(-.06,.06))
        wash=(fork[0]*.53,.65,fork[2]*.52)
        branch(shape,(0.,-.065,0.),wash,.064,.052,'#dad9ca')
        branch(shape,wash,fork,.052,.045,'#887565')
        arms=5
    else:
        fork=(0.,-.038,0.);arms=8
    phase=rng.random()*math.tau
    for j in range(arms):
        a=phase+(j+rng.uniform(-.18,.18))*math.tau/arms
        root=(fork[0],fork[1]-(j%3)*(.07 if tree else 0),fork[2])
        knot=_to(root,a,rng.uniform(.28,.48),rng.uniform(.28,.54) if tree else rng.uniform(.18,.34))
        branch(shape,root,knot,.034 if tree else .017,.018 if tree else .010,'#8a7965')
        for side in (-1,1):
            bearing=a+side*rng.uniform(.24,.79)
            tip=_to(knot,bearing,rng.uniform(.26,.54),rng.uniform(.13,.47) if tree else rng.uniform(.10,.31))
            branch(shape,knot,tip,.018 if tree else .011,.005,'#957e67')
            for k in range(3 if tree else 4):
                f=.18+k*(.37 if tree else .26)
                base=tuple(knot[t]+(tip[t]-knot[t])*f for t in range(3))
                tilt=bearing+rng.uniform(-1.0,1.0)
                p=_to(base,tilt,rng.uniform(.04,.13),rng.uniform(.01,.10))
                scale=rng.uniform(.115,.225) if tree else rng.uniform(.13,.22)
                if kind=='evergreen':scale*=1.22
                if kind=='evergreen':
                    _lobe(shape,p,scale,scale*.84,scale*.86,rng.choice(colors),rng)
                    continue
                branch(shape,base,p,.007,.003,'#957e67')
                _truss(shape,p,tilt,rng.uniform(.35,1.24),scale*1.45,rng.choice(colors),rng)
                leaf_blade(shape,p,tilt-.8,scale*.75,scale*.17,.05,
                      '#8b9256' if kind=='gold' else '#9a8868')
                if (tree and k==2) or (kind=='gold' and side==1 and k==3):
                    # Opaque outer blossoms give the silhouette physical depth.
                    flowering_spur(shape,p,tilt,scale,colors,flower_rng,
                                   count=3 if tree else 2,petals=5 if tree else 4)
            if kind=='gold' and side==1:
                for bearing in (a-.7,a+.5):
                    leaf_blade(shape,tip,bearing,.14,.030,.031,'#8f9253')
            if kind=='evergreen' and side==1:
                _lobe(shape,tip,.13,.10,.12,'#8f9253',rng)
    return shape


def _edge(shape,line,width,height,palette,terrain,rng):
    """A crown with vertical faces, chamfered shoulders, irregular leaf-scale relief."""
    steps=max(4,math.ceil(line.length/1.05))
    dist=line.length/steps
    cross=((-.49,.11),(-.51,.7),(-.38,.97),(-.16,1.015),(.16,1.025),(.38,.97),(.50,.70),(.48,.11))
    vv=[];faces=[[] for _ in range(3)]
    for i in range(steps):
        s=i*dist
        p=line.interpolate(s);before=line.interpolate((s-min(.14,.2*dist))%line.length)
        after=line.interpolate((s+min(.14,.2*dist))%line.length)
        dx,dz=after.x-before.x,after.y-before.y
        dl=max(.00001,math.hypot(dx,dz));nx,nz=-dz/dl,dx/dl
        jitter=rng.uniform(-.029,.029)
        for u,h in cross:
            x,z=p.x+nx*width*u,p.y+nz*width*u
            vv.append((x,terrain.y(x,z)+.045+height*h+jitter*h,z))
        sec=(i+1)%steps
        for j in range(len(cross)-1):
            cur=i*len(cross)+j;other=sec*len(cross)+j
            bucket=0 if j in (0,6) else 1 if j in (1,5) else 2
            faces[bucket].append((cur,cur+1,other+1,other))
        if i%2==0:
            x,z=p.x+nx*width*rng.uniform(-.26,.26),p.y+nz*width*rng.uniform(-.26,.26)
            _lobe(shape,(x,terrain.y(x,z)+height+.056,z),rng.uniform(.075,.16),.047,rng.uniform(.075,.16),palette[3],rng)
    for index,face_group in enumerate(faces):shape.mesh('绿篱冠',vv,face_group,palette[index])


GREEN=('#61753d','#748848','#82964b','#8b9a52')
BRONZE=('#705c43','#88714f','#9b8057','#a08660')


def _grid(poly,xstep,zstep,rng):
    xmin,zmin,xmax,zmax=poly.bounds
    line=0;z=zmin+zstep*.55
    while z<zmax:
        x=xmin+xstep*(.51+.43*(line%2))
        while x<xmax:
            xx=x+rng.uniform(-.14,.14)*xstep;zz=z+rng.uniform(-.13,.13)*zstep
            if poly.contains(Point(xx,zz)):yield xx,zz
            x+=xstep
        z+=zstep;line+=1


def build(scene,terrain,data,available,catalog):
    rng=random.Random(20250408)
    source=_layout(data);counts=Counter();colours=[]
    meshbank={}
    areas=[];clearances=[];crownMargins=[]
    reserve_area=unary_union([patch for _,patch in source])
    road_shapes=[]
    for road in data['roads']:
        line=LineString(road['line'])
        if not road.get('tunnel') and line.distance(reserve_area)<road['width']*.5+6:
            road_shapes.append(line.buffer(road['width']*.5,quad_segs=6))
    road_area=unary_union(road_shapes)
    def instance(kind,x,z,sc):
        variant=rng.randrange(2)
        if (kind,variant) not in meshbank:
            specimen=_prototype(kind,variant)
            radius=max(math.hypot(v[0],v[2]) for vv,_,_ in specimen.parts.values() for v in vv)
            meshbank[kind,variant]=(scene.shape(specimen),radius)
        mesh,radius=meshbank[kind,variant]
        crown_radius=radius*sc
        crownMargins.append(Point(x,z).distance(road_area)-crown_radius)
        name={'pale':'白干浅粉花木','deep':'深粉花木','gold':'黄花矮灌丛','evergreen':'常绿矮灌丛'}[kind]
        shrub=kind in ('gold','evergreen')
        scene.node('凤凰居 · '+name+str(counts[kind]+1),mesh=mesh,
                   at=(x,terrain.y(x,z)+.055,z),yaw=rng.random()*math.tau,
                   scale=(sc,sc*rng.uniform(.91,1.06),sc),kind='flora',site=KEY,
                   season='spring',shrub=shrub,species=name+'（种未定）',canopyRadius=round(crown_radius,4))
        counts[kind]+=1

    for number,(mode,footprint) in enumerate(source,1):
        zone=footprint.intersection(available)
        if zone.is_empty:continue
        areas.append(round(zone.area,2))
        clearances.append({'cell':number,'mode':mode,'edgeToRoadM':round(zone.distance(road_area),3)})
        ground=Shape('凤凰居花圃 '+str(number)+' · 花床与草肩')
        hedge=Shape('凤凰居花圃 '+str(number)+' · 绿篱与内缘')
        # Reserve the open central square at each transversal door approach.
        if mode=='court':
            c=footprint.centroid
            margin=footprint.difference(footprint.buffer(-3.05))
            openings=unary_union([LineString([(c.x,footprint.bounds[1]-2),(c.x,footprint.bounds[3]+2)]).buffer(2.9),
                                  LineString([(footprint.bounds[0]-3,c.y),(footprint.bounds[2]+3,c.y)]).buffer(3.5)])
            lengths=margin.difference(openings).intersection(zone).buffer(-.16)
            for corner in polygons(lengths):
                if corner.area<5:continue
                inner=corner.buffer(-.48)
                for component in polygons(inner):
                    _edge(hedge,component.exterior,.69,.44,GREEN,terrain,rng)
            # Forecourt gravel around the existing pavilion/approaches, inside its own cell.
            surface=zone.difference(margin)
            terrain.skin(ground,surface,'#bcaf94',.047)
        elif mode=='lawn':
            # Northern and southern margins read as a lawn with low evergreen planting.
            for p in polygons(zone.buffer(-2.0)):
                _edge(hedge,p.exterior,.74,.48,GREEN,terrain,rng)
                outer=p.difference(p.buffer(-3.00))
                for x,z in _grid(outer.buffer(-.67),2.6,2.3,rng):
                    instance('evergreen',x,z,rng.uniform(.66,.86))
            terrain.skin(ground,zone,'#91a275',.036)
        else:
            for p in polygons(zone):
                if p.area<35:continue
                # Outer grass margin, clipped evergreen hoop and warmer inner crown.
                terrain.skin(ground,p,'#91a275',.037)
                hedgeline=p.buffer(-.75)
                for c in polygons(hedgeline):_edge(hedge,c.exterior,1.10,.49,GREEN,terrain,rng)
                warmline=p.buffer(-1.76)
                for c in polygons(warmline):_edge(hedge,c.exterior,.83,.62,BRONZE,terrain,rng)
                soil=p.buffer(-2.19)
                if soil.is_empty:continue
                terrain.skin(ground,soil,'#b49c73' if mode=='pale' else '#a89166',.064)
                field=soil.buffer(-.77 if mode=='gold' else -1.00)
                if mode=='gold':
                    # The aerial shows a narrow east-west service strip bisecting the yellow group.
                    z=soil.centroid.y
                    lane=LineString([(soil.bounds[0]-2,z),(soil.bounds[2]+2,z-.35)]).buffer(.55)
                    clipped_lane=lane.intersection(soil)
                    terrain.skin(ground,clipped_lane,'#c6b99c',.081)
                    field=field.difference(lane.buffer(.43))
                if field.is_empty:continue
                spacing={'pale':(2.55,2.49),'deep':(2.43,2.38),'gold':(1.69,1.59)}[mode]
                for x,z in _grid(field,*spacing,rng):
                    sc=rng.uniform(.91,1.12) if mode!='deep' else rng.uniform(.84,1.04)
                    instance(mode,x,z,sc)
                colours.append(mode)
        if ground.parts:scene.node(ground.name,shape=ground,kind='ground',site=KEY)
        if hedge.parts:scene.node(hedge.name,shape=hedge,kind='landscape',site=KEY,season='spring',vegetation=True,species='修剪矮篱')
    eye=(310.,961.4);target=(311.,891.)
    viewpoint={'eye':[eye[0],round(terrain.y(*eye)+17.5,3),eye[1]],
               'target':[target[0],round(terrain.y(*target)+1.05,3),target[1]],'fov':44}
    catalog.append(dict(key=KEY,name='凤凰居中轴春季花圃',x=target[0],z=target[1],y=terrain.y(*target),
                        h=2.7,r=36,group='春日花木',viewpoint=viewpoint,
                        note='从南向北，沿原有斜向步道看粉花小乔木、黄花灌丛与常绿修剪篱。布局据2025年4月校方航拍，株数、花木品种和微地形为实景估计。'))
    return dict(cells=len(areas),cellAreas=areas,flowerBeds=len(colours),specimens=dict(counts),sharedSpecimenMeshes=len(meshbank),
                mappedRoadClearance=clearances,minCrownToRoadM=round(min(crownMargins,default=0.),3),
                reference=PHOTO,source=SOURCE,key=KEY,viewpoint=viewpoint)


def axis_pavilion(poly):
    """Mapped six-sided footprint; the November ground film resolves the open frame and lattice."""
    from shapely.geometry.polygon import orient
    from qd_geometry import Shape
    from qd_residence_roofs import surface, walls, eave
    from qd_planting import branch
    s=Shape('凤凰居中轴花园六角亭')
    plan=orient(poly,sign=1)
    rim=plan.buffer(.34,join_style=2)
    stone='#b6aaa0';metal='#52615d';tiles='#996b58'
    surface(s,'亭台石材铺装',plan,.21,stone)
    walls(s,'六角亭石台侧边',plan,-.28,.21,'#a69b92')
    eave(s,plan,rim,4.18,4.30,metal)
    surface(s,'亭内木色吊顶',plan,4.035,'#897c6a',up=False)
    cx,cz=plan.centroid.coords[0]
    corners=list(orient(rim,sign=1).exterior.coords)[:-1]
    edge=lambda p,f:(cx+(p[0]-cx)*f,cz+(p[1]-cz)*f)
    for i,p in enumerate(corners):
        q=corners[(i+1)%len(corners)]
        a,b=edge(p,.82),edge(q,.82)
        s.cyl('亭角钢柱',a[0],2.16,a[1],.16,3.90,metal,12)
        s.cyl('亭柱石础',a[0],.44,a[1],.245,.46,stone,12)
        branch(s,(a[0],3.64,a[1]),(b[0],3.64,b[1]),.074,.074,metal)
        branch(s,(a[0],4.05,a[1]),(b[0],4.05,b[1]),.085,.085,metal)
        def lerp(t,h):return (a[0]+t*(b[0]-a[0]),h,a[1]+t*(b[1]-a[1]))
        for j in range(9):
            branch(s,lerp(j/9,3.64),lerp((j+.5)/9,4.05),.026,.026,metal)
            branch(s,lerp((j+.5)/9,4.05),lerp((j+1)/9,3.64),.026,.026,metal)
        # Each roof sector bends slightly at its middle and closes around the central cap.
        ring=[(1.,4.30),(.60,4.81),(.12,5.98)]
        for (f,hy),(g,gy) in zip(ring,ring[1:]):
            v=[(*edge(p,f),hy),(*edge(p,g),gy),(*edge(q,g),gy),(*edge(q,f),hy)]
            s.mesh('铺瓦坡面',[(x,y,z) for x,z,y in v],[(0,1,2,3)],tiles)
        x,z=edge(p,.12);ex,ez=edge(q,.12)
        s.mesh('瓦脊收口',[(x,5.98,z),(cx,6.09,cz),(ex,5.98,ez)],[(0,1,2)],tiles)
        branch(s,(p[0],4.32,p[1]),(edge(p,.60)[0],4.84,edge(p,.60)[1]),.055,.05,'#7a685d')
    # The oblique axis photograph resolves the small windowed lantern above the tile roof.
    lower=[edge(p,.19) for p in corners]
    upper=[edge(p,.23) for p in corners]
    for i,(px,pz) in enumerate(lower):
        j=(i+1)%len(lower);qx,qz=lower[j]
        s.mesh('亭顶采光小楼',[(px,5.77,pz),(px,6.96,pz),(qx,6.96,qz),(qx,5.77,qz)],[(0,1,2,3)],'#ad785f')
        dx,dz=qx-px,qz-pz;nx,nz=dz,-dx
        ln=(nx*nx+nz*nz)**.5;nx,nz=nx/ln,nz/ln
        def arc(t,h,d):return (px+t*dx+nx*d,h,pz+t*dz+nz*d)
        for w,base,peak,offset,mat in [(.31,5.91,6.79,.021,'#dac7a5'),(.23,5.96,6.70,.033,'#4f514b')]:
            opening=[arc(.5-w,base,offset),arc(.5+w,base,offset)]+[arc(.5+w*math.cos(k*math.pi/10),peak-.22+.22*math.sin(k*math.pi/10),offset) for k in range(11)]
            s.mesh('亭顶小拱窗',opening,[tuple(range(len(opening)))],mat)
        a,b=upper[i],upper[j]
        s.mesh('铺瓦坡面',[(a[0],6.99,a[1]),(cx,7.64,cz),(b[0],6.99,b[1])],[(0,1,2)],'#a36d50')
    return s,7.64
