"""Pedestrian forecourt between the Innovation Centre and the Phoenix southern annex."""
import numpy as np
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.geometry.polygon import orient

from qd_geometry import Shape
from qd_terrain import polygons, sourcepolygon

KEY='innovation-forecourt'
PHOTO='实景参照/校园补拍/双创与凤凰居十一号.jpg'

# The east/west limits follow the two mapped buildings. The pointed planters
# turn from the north-south footways toward the open space at the clock.
# These small garden contours and heights are estimates from the oblique photo.
BED_PLANS=(
    (.47,[(294.3,1011.0),(301.3,1013.6),(307.4,1027.5),(294.8,1023.0)]),
    (.64,[(306.1,1008.8),(316.8,1012.2),(323.1,1026.3),(317.6,1024.4),(311.7,1018.9)]),
    (.53,[(294.6,1028.1),(300.2,1030.4),(308.8,1044.8),(309.8,1052.3),(295.2,1040.0)]),
    (.76,[(309.4,1033.2),(319.7,1036.0),(322.5,1040.6),(320.2,1049.7),(316.8,1048.0),(312.6,1043.6)]),
    (.47,[(294.3,1047.6),(304.3,1054.0),(308.8,1060.7),(308.8,1066.0),(303.3,1063.1),(294.2,1057.0)]),
    (.72,[(315.0,1056.4),(324.4,1054.0),(332.9,1058.4),(328.9,1062.0),(322.0,1064.4),(317.5,1063.0)]),
    (.52,[(295.0,1068.0),(302.1,1071.6),(311.8,1086.4),(312.4,1090.5),(302.4,1086.4),(295.2,1081.1)]),
    (.73,[(316.5,1073.1),(324.8,1069.0),(332.2,1071.0),(332.7,1079.7),(330.9,1084.8),(324.6,1085.0),(320.1,1081.4)]),
)


def sidewall(shape,terrain,name,foot,low,high,colour):
    for p in polygons(foot):
        p=orient(p,1)
        for ring in (p.exterior,*p.interiors):
            xy=list(ring.segmentize(1.4).coords)[:-1]
            count=len(xy)
            v=[(x,terrain.y(x,z)+height,z) for height in (low,high) for x,z in xy]
            shape.mesh(name,v,[(i,i+count,(i+1)%count+count,(i+1)%count) for i in range(count)],colour)


def add_numbered_annex(scene,terrain,annex,foot,records):
    """One photograph-facing sign set on the estimated northeastern low return."""
    import math
    from pathlib import Path
    import os
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    import mapbox_earcut as ear
    from qd_residence_roofs import walls,surface
    from qd_planting import branch
    roof=terrain.y(279.0,1013.0)+6.30
    body=Shape('凤凰居11号 · 前庭端低层平台')
    walls(body,'前庭端红色实墙',foot,terrain.y(279,1013)-1.0,roof,'#a46153')
    rim=foot.buffer(.10,join_style=2).difference(sourcepolygon(annex))
    walls(body,'深灰金属封檐',rim,roof-.15,roof+.12,'#535859')
    surface(body,'屋面检修铺面',rim,roof+.12,'#c6c2b4')
    green=foot.buffer(-.87).intersection(box(271,1007,278.7,1020))
    green=green.difference(box(270,1012.7,283,1013.25))
    walls(body,'种植屋面压边',green,roof+.12,roof+.25,'#adab9b')
    surface(body,'种植屋面',green,roof+.25,'#919269')
    rail=list(foot.buffer(-.12,join_style=2).exterior.coords)
    for a,b in zip(rail,rail[1:]):
        length=math.dist(a,b)
        if min(a[1],b[1])>1017.45:continue
        branch(body,(a[0],roof+.86,a[1]),(b[0],roof+.86,b[1]),.031,.031,'#505758')
        count=max(1,math.ceil(length/.94))
        for i in range(count):
            t=i/count;x=a[0]+t*(b[0]-a[0]);z=a[1]+t*(b[1]-a[1])
            body.cyl('平台细栏杆',x,roof+.49,z,.022,.74,'#505758',8)
    scene.node(body.name,shape=body,kind='plazaDetail',plazaKey=KEY,owner='way-982199358',
               approximate=True,source=PHOTO)
    # Photo wall is nearly frontal. The low extension abuts only the existing
    # north wall, with all letters on the opposite, north-facing exterior wall.
    a=np.array([283.90,1008.45]);b=np.array([274.25,1008.15])
    middle=(a+b)/2;u=(b-a)/np.linalg.norm(b-a);normal=np.array([-u[1],u[0]])
    def at(t,y,depth):
        x,z=middle+t*u+depth*normal
        return (float(x),float(y),float(z))
    fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    cn=FontProperties(fname=str(fonts/'msyh.ttc'))
    en=FontProperties(fname=str(fonts/'arial.ttf'))
    colour='#e7ddbd';shadow='#a79d85'
    def outlines(text,font):
        path=TextPath((0,0),text,prop=font,size=1)
        shape=Polygon()
        for contour in path.to_polygons():
            if len(contour)>3:shape=shape.symmetric_difference(Polygon(contour).buffer(0))
        return shape
    def emboss(mesh,geom,center,y,limit_w,limit_h,turned=False):
        left,bot,right,top=geom.bounds
        scale=min(limit_w/(right-left),limit_h/(top-bot))
        for p in getattr(geom,'geoms',[geom]):
            if p.geom_type!='Polygon' or p.area<1.e-6:continue
            loops=[list(r.coords)[:-1] for r in (p.exterior,*p.interiors)]
            uv=[]
            for loop in loops:
                for x0,y0 in loop:
                    xx=(x0-(left+right)/2)*scale;yy=(y0-(bot+top)/2)*scale
                    s,h=(yy,-xx) if turned else (xx,yy)
                    uv.append((center+s,y+h))
            ts=ear.triangulate_float64(np.asarray(uv,np.float64),np.cumsum([len(l) for l in loops],dtype=np.uint32)).reshape(-1,3)
            mesh.mesh('字面',[at(s,h,.045) for s,h in uv],ts,colour)
            start=0
            for loop in loops:
                vs=uv[start:start+len(loop)];start+=len(loop)
                for p0,p1 in zip(vs,vs[1:]+vs[:1]):
                    mesh.mesh('微凸字侧',[at(*p0,.045),at(*p1,.045),at(*p1,.002),at(*p0,.002)],[(0,1,2,3)],shadow)
    owner='way-982199358'
    def register(mesh,key,text,t,y,w,h):
        name='凤凰居11号 · '+text
        scene.node(name,shape=mesh,kind='signage',owner=owner,signId=key,text=text,
                   carrier='前庭端低层附属体外墙',source=PHOTO,facing=normal.tolist())
        if records is not None:
            pos=at(t,y,.045);cx,cz=annex['center'];cy=terrain.y(cx,cz)+.22
            records.append(dict(owner=owner,id=key,text=text,source=PHOTO,year=None,
                    carrier='前庭端低层附属体外墙',colour=colour,normal=normal.tolist(),
                    center=[pos[0]-cx,pos[1]-cy,pos[2]-cz],world=list(pos),width=w,height=h,
                    note='文字、竖排关系、圈号及平顶红墙均见照片。11至13号使用合并底图，附属体位置和尺寸按相对方位推定。'))
    center=-1.55
    chinese=Shape('竖排凤凰居')
    for j,ch in enumerate('凤凰居'):
        emboss(chinese,outlines(ch,cn),center,roof-.86-j*.79,.74,.70)
    register(chinese,'phoenix-11-zh','凤凰居',center,roof-1.65,.74,2.28)
    english=Shape('纵向英文')
    emboss(english,outlines('PHOENIX HALL',en),center-.69,roof-1.64,2.28,.265,True)
    register(english,'phoenix-11-en','PHOENIX HALL',center-.69,roof-1.64,.265,2.28)
    number=Shape('圈号11')
    circle=Point(0,0).buffer(.5,quad_segs=20).difference(Point(0,0).buffer(.469,quad_segs=20))
    emboss(number,circle,center-.23,roof-3.32,.89,.89)
    emboss(number,outlines('11',en),center-.23,roof-3.32,.54,.65)
    register(number,'phoenix-11-number','⑪',center-.23,roof-3.32,.89,.89)


class InnovationPlaza:
    def __init__(self,data,road,walk):
        rows={r['id']:r for r in data['buildings']}
        self.tower=rows['way/868015914']
        self.annex=rows['way/982199358']
        self.shells=unary_union([sourcepolygon(self.tower),sourcepolygon(self.annex)])
        # Join the surveyed northern wall from x=274 to its eastern end. The
        # return projects into the clear forecourt, well before the mapped walk.
        x0,z0=190.15,1015.21
        def north_edge(x):
            return z0+(x-x0)*(1018.12-z0)/(280.28-x0)
        self.return_plan=Polygon([(274.0,north_edge(274.0)),(280.28,1018.12),(284.0,1017.10),
                                  (283.90,1008.45),(274.25,1008.15)])
        if self.return_plan.intersection(self.shells).area>1.e-5 or self.return_plan.distance(walk)<2.0:
            raise ValueError('凤凰居低层平台与底图实楼或步道冲突')
        frontage=Polygon([(283.7,1005.2),(331.8,1006.1),(340.0,1016.9),(338.1,1053),
                          (351.0,1064.2),(338.5,1082.8),(334.8,1098.8),(318.6,1104.8),
                          (283.1,1087.5),(282.0,1058.4)])
        self.site=frontage.difference(self.return_plan.buffer(.12)).difference(self.shells.buffer(.48)).difference(road.buffer(.33)).difference(walk)
        photo_sight=Polygon([(277.2,987.8),(281.1,987.8),(298,1015),(273.5,1008.6)])
        self.plant_reserve=unary_union([frontage,self.return_plan.buffer(1.5),photo_sight]).difference(self.shells)
        self.beds=[]
        clearance=walk.buffer(.85).union(self.shells.buffer(1.6)).union(road.buffer(2.0))
        for height,coords in BED_PLANS:
            clipped=Polygon(coords).buffer(-.75).buffer(.75,quad_segs=6).intersection(self.site).difference(clearance)
            for bed in polygons(clipped):
                if bed.area>7:self.beds.append((height,bed))
        # Each short accessible route past the steps stays on the original
        # pedestrian network. Flights sit entirely beside it, up to small landings.
        self.steps=[]
        for z0,width in [(1027.6,5.8),(1045.9,5.3)]:
            for i in range(4):
                x0=330.0+i*.43
                x1=x0+.43 if i!=3 else 337.35
                foot=box(x0,z0-width*.5,x1,z0+width*.5).intersection(self.site)
                if foot.area>.07:self.steps.append((.16+(i+1)*.125,foot))
        solids=unary_union([p for _,p in self.beds+self.steps])
        self.paving=self.site.difference(solids)

    def build(self,scene,terrain,catalog,inscriptions=None):
        add_numbered_annex(scene,terrain,self.annex,self.return_plan,inscriptions)
        ground=Shape('双创前庭 · 浅灰铺地')
        terrain.skin(ground,self.paving,'#c3bfb1',.16)
        scene.node(ground.name,shape=ground,kind='ground',plazaKey=KEY)
        stone=Shape('双创前庭 · 叠级花池与便阶')
        shrubs=Shape('双创前庭 · 修剪矮篱')
        for high,foot in self.steps:
            terrain.skin(stone,foot,'#c9c5b7',high)
            sidewall(stone,terrain,'花岗岩踏步侧边',foot,.16,high,'#a39e91')
        spots=[]
        for j,(height,bed) in enumerate(self.beds):
            # Lower stone foot, setback wall, pale coping and planted inner lip.
            wall=bed.buffer(-.12)
            inside=wall.buffer(-.26)
            foot_top=.29
            top=.16+height
            sidewall(stone,terrain,'花池基座',bed,.16,foot_top,'#aaa79b')
            terrain.skin(stone,bed.difference(wall),'#c7c4b7',foot_top)
            sidewall(stone,terrain,'抬高花池侧面',wall,foot_top,top,'#aaa99d')
            terrain.skin(stone,wall.difference(inside),'#cecabd',top)
            terrain.skin(stone,inside,'#998868',top-.055)
            edge=inside.buffer(-.13)
            core=edge.buffer(-.60)
            hedge=edge.difference(core)
            sidewall(shrubs,terrain,'矮篱侧缘',hedge,top-.055,top+.28,'#828145')
            terrain.skin(shrubs,hedge,'#a0a650',top+.28)
            if not core.is_empty:
                patch=core.buffer(-.16)
                sidewall(shrubs,terrain,'内圈矮丛',patch,top-.055,top+.20,'#88764c')
                terrain.skin(shrubs,patch,'#9a865a' if j%3 else '#94945b',top+.20)
                planting=core.buffer(-.50)
                if not planting.is_empty:
                    pt=planting.representative_point()
                    spots.append((pt.x,pt.y,top-.055))
        scene.node(stone.name,shape=stone,kind='plazaDetail',plazaKey=KEY)
        scene.node(shrubs.name,shape=shrubs,kind='plazaPlanting',plazaKey=KEY)
        existing={m['name']:i for i,m in enumerate(scene.doc['meshes'])}
        from qd_planting import prototype
        fallback=None
        for j,(x,z,soil) in enumerate(spots):
            mesh=existing.get('乔木'+str(1+j%5))
            if mesh is None:
                if fallback is None:fallback=scene.shape(prototype(1))
                mesh=fallback
            sc=.57+.06*(j%3)
            scene.node('双创前庭 · 花池内乔木 '+str(j+1),mesh=mesh,at=(x,terrain.y(x,z)+soil,z),
                       scale=(sc,sc,sc),yaw=j*2.4,kind='flora',site=KEY,shrub=False)
        terrain_y=terrain.y(279.2,988.8)
        tower_x,tower_z=self.tower['center']
        tower_y=terrain.y(tower_x,tower_z)+.22
        eye=[279.2,terrain_y+9.3,988.8]
        target=[tower_x-43.45,tower_y+9.55,tower_z+24.0]
        viewpoint=dict(eye=eye,target=target,fov=46)
        roof=terrain.y(279,1013)+6.30
        sign_view=dict(eye=[280.75,roof-1.85,1001.6],target=[280.75,roof-2.0,1008.33],fov=42,
                       label='凤凰居11号竖排题字',hideMapLabels=True)
        catalog.append(dict(key=KEY,name='双创前庭 · 从凤凰居望钟楼',group='校园场地',
                            x=312,y=terrain.y(312,1051),z=1051,h=6,r=64,viewpoint=viewpoint,
                            views={'facade':dict(viewpoint,label='双创前庭与钟楼',hideMapLabels=True),'inscription':sign_view},
                            note='从凤凰居方向向东南看钟楼和前庭。分层花池、浅色石阶、内外两色矮篱据实拍，花池边线、标高与机位为近似。'))
        return dict(photo=PHOTO,pavingM2=round(self.paving.area,2),raisedBeds=len(self.beds),
                    flights=2,trees=len(spots),inscriptionLines=3,estimatedAnnexM2=round(self.return_plan.area,2),viewpoint=viewpoint)
