"""Exterior reconstruction of Huiwen's paired wings and the six Ganchang Court buildings.

Metres. Positive X points east, positive Z south. Each source footprint arrives translated
to its own centre. The surveyed door photographs and the inferred sides are distinguished
in data/huiwen_sources.json. Courtyard plaques use qd_signage's audit registry.
"""
from dataclasses import dataclass
import math

from shapely.geometry.polygon import orient

import qd_architecture  # Registers Shape.sign used by the plaque renderer.
from qd_geometry import Shape
from qd_signage import plaque
import qd_video_colleges as video
from qd_terrain import polygons
from qd_college_roofs import AcademicRoof, dormer_walls, pitched_cap


AERIAL = 'https://www.sdrj.sdu.edu.cn/info/1004/25361.htm'
NORTH_SOUTH = 'https://www.sdrj.sdu.edu.cn/info/1002/17675.htm'
ENV = 'https://www.huanke.sdu.edu.cn/info/1065/5655.htm'
MARINE = 'https://www.qdxq.sdu.edu.cn/info/1872/58724.htm'

WALL = '#ded4bf'
SILL = '#eee3ce'
SHADE = '#958b7b'
GLASS = '#405766'
FRAME = '#534f4c'
GRANITE = '#b1aaa0'
TILE = '#b65e4b'
TILE_DARK = '#9e513e'
ROOF_DECK = '#b3b2a5'
ZINC = '#91948b'


@dataclass(frozen=True)
class Design:
    osm: int
    name: str
    alias: tuple
    center: tuple
    door: tuple  # x, z, outward nx, nz; snapped to the mapped footprint on build
    kind: str
    eave: float
    pitch: float
    width: float
    bays: float
    cross: tuple  # Interior roof crossing locations, in direction of building length.
    long_x: bool = True

    @property
    def key(self):
        return 'way-' + str(self.osm)


DESIGNS = (
    Design(970257672, '会文北楼', ('会文楼北楼','H4'), (433.79,-131.13),
           (-44.5,20.3,0,1),'hui_n',15.8,2.9,11.2,4.55,(-68,-25,22,82)),
    Design(970257673, '会文南楼', ('会文楼南楼','H5'), (435.40,5.55),
           (18,20.3,0,1),'hui_s',15.8,2.9,11.8,4.70,(-67,-25,19,82)),
    Design(970257670, '淦昌苑A座', ('淦昌苑A区','K1','光热辐射研究中心'),
           (137.65,126.00),(8.9,0,1,0),'end_a',16.7,3.6,12.5,4.25,(-44,0,43),False),
    Design(1018848586, '淦昌苑B座', ('公共（创新）实验教学中心','K2'),
           (246.97,80.05),(-1.8,18.4,0,1),'bar_b',16.5,3.55,12,4.42,(-49,-2,48)),
    Design(970257667, '淦昌苑C座', ('海洋研究院','K3'),
           (386.30,77.27),(-2,9.25,0,1),'marine',16.8,3.65,12.5,4.25,(-47,-2,45)),
    Design(868015915, '淦昌苑D座', ('网络空间安全学院','K4'),
           (511.42,124.92),(-18.65,2.75,-1,0),'end_d',17.2,3.45,12,4.45,(-43,3,49),False),
    Design(970257669, '淦昌苑E座', ('环境科学与工程学院','K5'),
           (385.32,180.61),(-1.5,19.60,0,1),'environment',16.8,3.65,13,4.28,(-47,-2,45)),
    Design(970257668, '淦昌苑F座', ('淦昌苑F区','K6','环境研究院','国家糖工程技术研究中心'),
           (244.64,176.19),(-2,9.25,0,1),'bar_f',16.7,3.5,12.2,4.30,(-47,-2,45)),
)
BY_ID = {item.osm: item for item in DESIGNS}
SPECS = [dict(key=s.key, osm=s.osm, name=s.name, aliases=list(s.alias),
              x=s.center[0], z=s.center[1], h=s.eave+s.pitch+1.05, source=AERIAL)
         for s in DESIGNS]
VIEWS = {s.key: dict(target=[s.door[0],3.1,s.door[1]],
                     normal=list(s.door[2:])) for s in DESIGNS}


class Facade:
    """A wall coordinate u increases toward the right of a person facing the facade."""
    def __init__(self, shape, x, z, nx, nz):
        self.shape, self.x, self.z = shape, x, z
        self.nx, self.nz = nx, nz
        self.yaw = math.atan2(nx, nz)

    def pos(self, u, depth):
        return (self.x+u*self.nz+depth*self.nx,
                self.z-u*self.nx+depth*self.nz)

    def pt(self, u, y, depth):
        x,z = self.pos(u,depth)
        return x,y,z

    def box(self, name, u, y, depth, w, h, d, mat):
        x,z = self.pos(u,depth)
        self.shape.box(name,x,y,z,w,h,d,mat,self.yaw)

    def panel(self,name,u,y,depth,w,h,material):
        p=[self.pt(u-w/2,y-h/2,depth),self.pt(u+w/2,y-h/2,depth),
           self.pt(u+w/2,y+h/2,depth),self.pt(u-w/2,y+h/2,depth)]
        self.shape.mesh(name,p,[(0,1,2,3)],material)

    def gable(self,name,base,rise,half,front,back,mat):
        vertices=[self.pt(u,y,d) for d in (front,back)
                  for u,y in ((-half,base),(half,base),(0,base+rise))]
        self.shape.mesh(name,vertices,[(0,1,2),(5,4,3),(0,2,5,3),(2,1,4,5),(1,0,3,4)],mat)


def walls(shape,geom,bottom,top,material):
    for p in polygons(geom):
        p=orient(p,1)
        for ring in (p.exterior,*p.interiors):
            vertices=list(ring.coords)
            for (x,z),(xx,zz) in zip(vertices,vertices[1:]):
                shape.mesh('外墙',[(x,bottom,z),(xx,bottom,zz),(xx,top,zz),(x,top,z)],
                           [(0,3,2,1)],material)


def roof(shape,poly,s):
    AcademicRoof(poly,s.osm,s.eave,s.pitch,.58).build(shape,TILE,ROOF_DECK,SILL,ZINC)


def find_door(shape,poly,s):
    x,z,nx,nz=s.door
    winner=None
    for ring in (orient(poly,1).exterior,):
        cc=list(ring.coords)
        for (a,b),(c,d) in zip(cc,cc[1:]):
            dx,dz=c-a,d-b
            length=math.hypot(dx,dz)
            if length<s.width:continue
            fx,fz=dz/length,-dx/length
            if fx*nx+fz*nz<.85:continue
            span=max(0,min(length,((x-a)*dx+(z-b)*dz)/length))
            px,pz=a+span*dx/length,b+span*dz/length
            penalty=math.hypot(x-px,z-pz)
            if winner is None or penalty<winner[0]:
                winner=(penalty,Facade(shape,px,pz,fx,fz))
    if winner is None:raise ValueError('无法在足迹定位入口 '+s.name)
    return winner[1]


def dormer(f,u,s):
    roof_model=f.shape.college_roof
    if s.kind in ('bar_b','bar_f'):
        video.rounded_dormer(f.shape,f.pt,roof_model,u,TILE,SILL,GLASS)
        return
    x,z=f.pos(u,-1.35)
    y=roof_model.sheet.y(x,z)+.015
    vertices=[f.pt(u+a,y+b,d) for a,b,d in
              [(-1.15,0,-1.35),(1.15,0,-1.35),(0,.94,-1.35),
               (-1.15,.08,-2.15),(1.15,.08,-2.15),(0,1.02,-2.45)]]
    pitched_cap(f.shape,'老虎窗双坡盖瓦',vertices,[(0,2,5,3),(2,1,4,5)],.095,TILE_DARK,SILL)
    dormer_walls(f.shape,roof_model,[vertices[k] for k in (0,2,1)],
                 [vertices[k] for k in (3,5,4)],.037,SILL,WALL)
    f.panel('老虎窗玻璃',u,y+.21,-1.325,.83,.37,GLASS)


def pavilion(f,length,s):
    """Stone-framed end of a projecting wing facing the open side of a U plan."""
    facade_side={'marine':(0,1),'bar_f':(0,1),'environment':(0,-1),
                 'end_a':(1,0),'end_d':(-1,0)}.get(s.kind)
    if not facade_side or not 25<length<39:return
    if f.nx*facade_side[0]+f.nz*facade_side[1]<.92:return
    video.stepped_end(f.box,length,s.eave,WALL,SILL,GLASS)


def facade_windows(shape,poly,s,door):
    h=s.eave
    hui=s.kind.startswith('hui')
    cc=list(orient(poly,1).exterior.coords)
    for (a,b),(c,d) in zip(cc,cc[1:]):
        dx,dz=c-a,d-b
        length=math.hypot(dx,dz)
        if length<2:continue
        f=Facade(shape,(a+c)/2,(b+d)/2,dz/length,-dx/length)
        video.hui_west_gallery(f,s,length)
        plaza=video.plaza_canopy(f,s,length)
        n=max(1,int((length-.5)/s.bays))
        pitch=(length-.7)/n
        if length>=6:
            # Surveyed doors interrupt the wall datum. A continuous moulding would
            # visibly cut across the C/E doors and their photographed stonework.
            signed=(door.x-f.x)*f.nx+(door.z-f.z)*f.nz
            same=(door.nx*f.nx+door.nz*f.nz>.96 and abs(signed)<.8)
            pu=(door.x-f.x)*f.nz-(door.z-f.z)*f.nx
            gap=s.width/2+.25
            runs=[(-length/2,length/2)] if not same else [
                (-length/2,min(length/2,pu-gap)),(max(-length/2,pu+gap),length/2)]
            for left,right in runs:
                if right-left>.2:
                    f.box('石材基座压顶',(left+right)/2,3.65,.105,right-left,.21,.26,SILL)
        if length>=9:
            f.box('檐下浅色额枋',0,h-.72,.11,length,.34,.30,SILL)
        # A21 and V3 00:42.50 show the dormers to the left (west) of the foyer.
        # The shift of the lower entrance towards the east must not remove a window in the roof.
        west_wing=(s.kind=='hui_n' and f.nz>.94 and f.x<-50 and 68<length<76)
        if west_wing:
            for local_x in (-85.1,-57.8):
                dormer(f,(local_x-f.x)/f.nz,s)
        for k in range(n):
            u=(k+.5-n/2)*pitch
            xx,zz=f.pos(u,0)
            side=(xx-door.x)*door.nz-(zz-door.z)*door.nx
            front=(xx-door.x)*door.nx+(zz-door.z)*door.nz
            if abs(front)<.75 and abs(side)<s.width/2+1.1:
                continue
            if plaza and abs(u)<10.20:continue
            if length<3.6:continue
            terminal=length<27 and not hui
            width=min(3.6,pitch*(.50 if terminal else .67 if hui else .73))
            if not hui and not terminal:
                f.panel('层间窗带衬板',u,(h+3.7)/2-.25,.045,width+.17,h-4.15,'#8c8c80')
                if k%2==0:
                    f.box('贯层石质壁柱',u-pitch*.50,(h+3.7)/2-.25,.205,.35,h-4.12,.49,SILL)
            floor_height=(h-.5)/4
            for level in range(4):
                if level==0 and (length<7 or video.b_arcade(f,s,length,u,width)):continue
                cy=(level+.51)*floor_height+.12
                height=floor_height*(.60 if hui else .66)
                f.panel('窗洞阴影',u,cy,.102,width+.23,height+.22,SHADE)
                pane=['#465d69','#536773','#4a5f69','#45565f'][(k//2+level)%4]
                f.panel('灰蓝窗玻璃',u,cy,.134,width,height,pane)
                f.panel('上亮窗天光',u,cy+height*.34,.143,width-.05,height*.26,'#637883')
                f.panel('竖向窗梃',u,cy,.153,.075,height,'#7d817a')
                f.panel('横向窗梃',u,cy+height*.21,.158,width,.075,'#7d817a')
                if hui or terminal:
                    f.box('窗台石',u,cy-height*.5-.08,.11,width+.33,.13,.33,SILL)
            if not hui and length>35 and k%5==2 and k<n-1:
                dormer(f,u,s)
            elif hui and not west_wing and length>60 and k%7==3:
                dormer(f,u,s)
        pavilion(f,length,s)
        if 8<length<36 and not hui:
            f.box('端翼石材角墩',-length/2+.55,h*.51,.16,.72,h-.64,.38,SILL)


def stone_courses(f,left,right,low,high):
    """Staggered mortar joints around the marine institute's coarse stone sign wall."""
    for j in range(int((high-low)/.4)+1):
        y=low+j*.4
        f.panel('粗砌花岗石灰缝',.5*(left+right),y,.165,right-left,.027,'#8d8577')
        first=left+(.34 if j%2 else .70)
        joints=[left]
        x=first
        while x<right-.06:
            f.panel('粗砌花岗石竖缝',x,y+.19,.168,.025,.35,'#8d8577')
            joints.append(x)
            x+=.9
        joints.append(right)
        for k,(a,b) in enumerate(zip(joints,joints[1:])):
            if b-a<.13 or y+.33>high:continue
            a+=.024; b-=.025; t=y+.368; low_y=y+.024
            centre=(a+b)/2+(b-a)*(.09 if (j+k)%2 else -.14)
            verts=[f.pt(a,low_y,.17),f.pt(b,low_y,.17),f.pt(b,t,.17),f.pt(a,t,.17),
                   f.pt(centre,y+.19,.19+.01*((k+2*j)%3))]
            shades=['#b8ae98','#c3b9a3','#beb39c','#c0b5a0']
            f.shape.mesh('粗粒花岗岩劈裂面',verts,[(0,1,4),(1,2,4),(2,3,4),(3,0,4)],
                         shades[(j*7+k*3)%4])


def register(f,s,tag,text,u,y,w,h,source,year,carrier,depth,colour='#352f2c',note=''):
    x,z=f.pos(u,depth)
    plaque(f.shape,s.key,tag,text,x,y,z,w,h,f.yaw,source=source,year=year,
           carrier=carrier,colour=colour,background=None,note=note)


def portal(f,s):
    env=s.kind=='environment'
    marine=s.kind=='marine'
    hui=s.kind.startswith('hui')
    width=s.width
    eave=s.eave
    opening=4.35 if env else 4.85 if marine else width*.56
    glazing=3.35 if env else 4.25 if marine else 4.48
    # Wide steps and a continuous dark mullioned entrance; sign-height photography
    # gives the locally accurate ground floor of C and E.
    for step in range(4):
        top=.16*(step+1)
        bottom=-.55
        front=3.15-step*.54
        back=-.22
        f.box('入口花岗岩台阶',0,(top+bottom)/2,(front+back)/2,
              width+.9-step*.08,top-bottom,front-back,GRANITE)
    f.panel('通高玻璃门厅',0,.61+glazing/2,.085,opening,glazing,'#394745')
    if env or marine:
        f.panel('灰石门楣连续拉面',0,4.72,.080,width,1.52,'#b9b4aa')
        f.panel('入口上亮窗天空反光',0,.61+glazing-.48,.105,opening-.08,
                .80 if env else .91,'#738a92')
    for k in range(-2,3):
        f.box('门厅铝合金框',k*opening/5,.61+glazing/2,.16,.085,glazing,.14,FRAME)
    for y in (2.81,3.49) if env else (3.08,4.18):
        f.box('门厅横梁',0,y,.17,opening,.12,.16,FRAME)
    for left in (-1,1):
        f.box('双扇开启门',left*opening*.18,1.88,.225,opening*.33,2.50,.12,'#435452')
        f.box('开启门拉手',left*.135,1.80,.34,.044,.49,.061,'#c2c1ac')
    if env:
        for side in (-1,1):
            f.box('门套花岗石侧墙',side*(opening/2+1.82),2.80,.045,3.64,5.55,.13,'#bcb7af')
            f.box('外框内侧石质门套',side*(opening/2+.24),2.27,.45,.50,3.36,.75,GRANITE)
            x,z=f.pos(side*(opening/2-.15),.48)
            f.shape.cyl('圆柱石门框',x,2.27,z,.22,3.36,'#c7c1b7',20)
        f.box('灰石门洞上枋',0,3.96,.40,opening+.98,.38,.90,GRANITE)
        f.box('灰石门洞外框',0,4.24,.23,opening+1.60,.29,.72,'#c3bcb2')
        # Relative size and left/right placement from the college's 2024 photo.
        u=-(opening/2+1.33)
        f.box('左横向金属院牌',u,2.67,.217,1.12,.54,.10,'#c7c6b7')
        register(f,s,'gc-e-school','山东大学',u,2.81,.53,.080,ENV,2024,'门左金属横牌',.279,'#706457')
        register(f,s,'gc-e-college','环境科学与工程学院',u,2.66,1.02,.167,ENV,2024,'门左金属横牌',.281)
        register(f,s,'gc-e-en','SCHOOL OF ENVIRONMENTAL SCIENCE AND ENGINEERING',u,2.52,
                 1.01,.071,ENV,2024,'门左金属横牌',.281)
        u=opening/2+1.33
        f.box('右竖向楼座牌',u,2.72,.218,.76,1.08,.11,'#d5cbba')
        register(f,s,'gc-e-court','淦昌苑',u,2.83,.66,.17,ENV,2024,'门右竖牌',.285)
        register(f,s,'gc-e-court-en','GANCHANG COURTYARD',u,2.69,.65,.062,ENV,2024,'门右竖牌',.285)
        register(f,s,'gc-e-letter','E',u,2.51,.32,.24,ENV,2024,'门右竖牌',.285)
        for j in range(3):
            f.panel('楼座牌底饰线',u,2.30+.030*j,.284,.60,.014,'#685f54')
    elif marine:
        for side in (-1,1):
            a,b=(side*(opening/2),side*(width/2))
            f.box('粗面石门侧墙',(a+b)/2,2.75,.05,abs(b-a),5.45,.15,'#bcb29c')
            stone_courses(f,min(a,b),max(a,b),.2,5.48)
        f.box('石砌深门楣',0,5.31,.75,width,.57,1.73,'#c5bdab')
        u=-opening/2-1.28
        f.box('研究院横向金属铭牌',u,2.46,.235,1.18,.55,.12,'#d6d0b9')
        register(f,s,'gc-c-school','山东大学',u,2.615,.53,.085,MARINE,2024,'面向入口的左侧粗石墙金属横牌',.31,'#756354')
        register(f,s,'gc-c-institute','海洋研究院',u,2.45,1.01,.174,MARINE,2024,'面向入口的左侧粗石墙金属横牌',.31)
        register(f,s,'gc-c-en','INSTITUTE OF MARINE SCIENCE AND TECHNOLOGY',u,2.305,1.07,.071,
                 MARINE,2024,'面向入口的左侧粗石墙金属横牌',.31)
        for k in range(3):
            f.box('入口侧扶手立柱',-width*.48,1.07,1.1+k*.61,.065,1.1,.07,'#809096')
        f.box('入口侧钢扶手',-width*.48,1.62,1.70,.09,.09,1.30,'#809096')
    else:
        for side in (-1,1):
            f.box('门廊方石柱',side*(opening/2+.22),2.74,1.29,.74,4.30,.99,SILL)
        f.box('门廊挑檐',0,4.95,.94,width,.44,2.24,GRANITE)
    # Multi-storey foyer wings sit above the photographed stone floor.
    if hui:
        if video.hui_west_entry(f,s):return
        count=3
        for i in range(count):
            u=(i-(count-1)/2)*2.03
            f.panel('会文门厅上层竖窗',u,10.68,.16,1.36,7.62,'#50606a')
            for y in (8.55,10.67,12.63):
                f.panel('竖窗横梃',u,y,.19,1.37,.115,'#a39e8f')
        f.box('楼翼檐线',0,eave-.43,.21,width+1.4,.41,.56,SILL)
        return
    if video.ganchang_foyer(f,s):return
    for side in (-1,1):
        f.box('前厅侧石柱',side*(width/2-.5),(eave+5.6)/2,.48,.84,
              eave-5.5,1.02,SILL)
    f.panel('高窗玻璃厅',0,(5.52+eave)/2,.081,width-2.05,eave-5.52,'#465966')
    for j in range(-2,3):
        f.panel('高窗竖梃',j*(width-2.05)/5,(5.52+eave)/2,.122,.125,eave-5.52,'#858984')
    for j in range(1,4):
        f.panel('高窗横梃',0,5.52+j*(eave-5.52)/4,.130,width-2.05,.13,'#858984')
    if s.kind=='end_a':
        n=4 if s.kind=='end_a' else 3
        for j in range(n):
            f.box('端院门面通高浅色柱',(j-(n-1)/2)*(width-2.4)/n,
                  (5.52+eave)/2,.268,.38 if n==4 else .62,eave-5.52,.40,SILL)
        f.box('端院平直檐口',0,eave-.06,.29,width+.66,.62,.87,WALL)
        return
    f.gable('入口山花石包边',eave-.28,3.65,width*.56,.46,-6.0,SILL)
    f.gable('三角玻璃窗',eave-.12,2.97,width*.45,.482,.44,'#465966')
    f.gable('入口坡瓦盖脊',eave+3.31,.51,.75,-2.5,-6.55,TILE_DARK)
    # The wide red roof caps the projected gable. Thin fascia separates glazing and tile.
    v=[f.pt(u,y,d) for d in (.78,-8.15)
       for u,y in ((-width*.59,eave-.15),(0,eave+3.68),(width*.59,eave-.15))]
    pitched_cap(f.shape,'门厅红瓦双坡',v,[(0,1,4,3),(1,2,5,4)],.17,TILE,SILL)


def build(row,poly):
    raw=str(row.get('id') or row.get('key') or row.get('osm'))
    osm=int(raw.replace('way/','').replace('way-',''))
    s=BY_ID[osm]
    shape=Shape(s.name)
    poly=orient(poly,1)
    walls(shape,poly,-2,s.eave,WALL)
    walls(shape,poly.buffer(.075,join_style=2),-.12,3.61,GRANITE)
    door=find_door(shape,poly,s)
    roof(shape,poly,s)
    facade_windows(shape,poly,s,door)
    portal(door,s)
    return shape,s.eave+s.pitch+1.05
