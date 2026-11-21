"""Reconstruction of the six courtyards' academic blocks in local metres (X east, Z south).

The roof terraces and the positions of the entrance axes come from the aerial view.
The reference register records the dates and limits for each photographed plate.
"""
import math

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

import qd_architecture  # Registers Shape.sign for the audited plaque routine.
from qd_geometry import Shape
from qd_signage import plaque
import qd_video_colleges as video
from qd_terrain import polygons
from qd_college_roofs import AcademicRoof, dormer_walls, pitched_cap

IDS = {'A': 868015919, 'B': 868015920, 'C': 868015918,
       'D': 868015916, 'E': 970257671, 'F': 868015921}
DIRECTORY = {
    'A': (['第周苑A', 'N1', '微生物技术研究院', '微生物改造技术全国重点实验室', '微生物技术国家重点实验室'], '研究院办公楼。2023年两侧入口铭牌有旧照，2024年实验室重组；旧牌对应哪一面仍待确认。'),
    'B': (['第周苑B','N2','生命科学学院北楼','生命科学学院','微生物技术研究院','微生物改造技术全国重点实验室'], '2026年正照核对半圆拱、楼牌及生命学院上牌。与微生物技术研究院共享。'),
    'C': (['第周苑C','N3','计算机科学与技术学院'], '南向凹院与入口轴，左院名牌、右楼牌均据正面照片。'),
    'D': (['第周苑D','N5','信息科学与工程学院'], '西侧深门廊，正射影像西台阶方框交叉标线与两次返校照片的黄色线相符。'),
    'E': (['第周苑E','N7','前沿交叉科学青岛研究院','信息科学与工程学院','光学高等研究中心'], '2024年正面合影核对左侧三块院所牌与右侧楼牌。'),
    'F': (['第周苑F','N8','生命科学学院南楼','生命科学学院','微生物技术研究院','微生物改造技术全国重点实验室'], '南立面玻璃山墙见2021年航拍，与研究院共享。入口牌文字待核。'),
}
SPECS = [{'key': f'way-{osm}', 'osm': osm, 'name': f'第周苑{letter}座',
          'aliases': DIRECTORY[letter][0], 'note': DIRECTORY[letter][1]}
         for letter, osm in IDS.items()]
KEYS = {s['key']: letter for s, letter in zip(SPECS, IDS)}
SOURCES = {
    'A': ('https://www.jgb.sdu.edu.cn/jsj/info/1015/1063.htm', 2023),
    'B': ('https://lifesci.sdu.edu.cn/info/1021/13447.htm', 2026),
    'C': ('https://www.cs.sdu.edu.cn/info/1055/5898.htm', 2023),
    'D': ('https://www.ise.sdu.edu.cn/info/1075/16921.htm', 2026),
    'E': ('https://www.qdxq.sdu.edu.cn/info/1820/59304.htm', 2024),
}
# Face centres of the traced entrance walls, with the viewing vector pointing outdoors.
AXES = {'A': (12.12, -1.45, 1, .010), 'B': (-.12, 20.95, -.0056, 1),
        'C': (.82, 9.00, -.004, 1), 'D': (-15.16, 2.10, -1, .014),
        'E': (.44, 21.30, -.0077, 1), 'F': (-.15, 17.55, -.014, 1)}
VIEWS = {f'way-{IDS[k]}': {'target': [x+nx*1.8, 3.15, z+nz*1.8], 'normal': [nx, nz]}
         for k,(x,z,nx,nz) in AXES.items()}
# Wall/eave heights, portal width and depth, roof break locations on the long axis.
PROFILES = {
    'A': (17.6, 14.5, 3.05, (-43, 39)), 'B': (17.5, 16.0, 3.20, (-42, 42)),
    'C': (17.8, 14.0, 2.70, (-38, 38)), 'D': (18.25, 16.3, 3.8, (-42, 41)),
    'E': (17.65, 14.4, 2.75, (-39, 39)), 'F': (17.15, 13.0, 2.40, (-47, 46)),
}
STONE = '#d9cbb7'
PALE = '#e2d9c9'
DARK = '#435461'
GLASS = '#3c6072'
SPANDREL = '#647581'
TILE = '#bd684f'
ROOF = '#a3a49a'
METAL = '#78878a'


class Front:
    """Place details relative to an outward facing wall: u right, v up, t out."""
    def __init__(self, shape, x, z, nx, nz):
        self.s = shape
        length = math.hypot(nx, nz)
        self.x, self.z, self.nx, self.nz = x, z, nx/length, nz/length
        self.yaw = math.atan2(self.nx, self.nz)

    def at(self, u, v, t):
        return (self.x+u*self.nz+t*self.nx, v, self.z-u*self.nx+t*self.nz)

    def block(self, label, u, v, t, w, h, d, colour):
        self.s.box(label, *self.at(u, v, t), w, h, d, colour, self.yaw)

    def panel(self, label, coords, t, colour):
        self.s.mesh(label, [self.at(u,v,t) for u,v in coords], [tuple(range(len(coords)))], colour)


def walls(s, poly, bottom, top, colour):
    for p in polygons(poly):
        p = orient(p, 1)
        for ring in (p.exterior, *p.interiors):
            edge = list(ring.coords)
            for (x,z), (xx,zz) in zip(edge,edge[1:]):
                s.mesh('石材外墙', [(x,bottom,z),(x,top,z),(xx,top,zz),(xx,bottom,zz)],
                       [(0,1,2,3)], colour)


def crown(s, poly, h, letter):
    AcademicRoof(poly,IDS[letter],h,2.77,.47).build(s,TILE,ROOF,PALE,METAL)


def facade(s, poly, portal, h, letter):
    """Tall stone pilasters divide groups of dark spandrels and three stacked windows."""
    for p in polygons(poly):
        pts = list(orient(p,1).exterior.coords)
        for (x,z),(xx,zz) in zip(pts,pts[1:]):
            dx,dz = xx-x,zz-z
            length = math.hypot(dx,dz)
            if length < 2:
                continue
            frame = Front(s,(x+xx)/2,(z+zz)/2,dz,-dx)
            frame.block('下层勒脚',0,.50,.09,length,.29,.20,'#b9b1a3')
            frame.block('浅石冠带',0,h-3.0,.18,length,.55,.42,PALE)
            frame.block('窗上压线',0,h-.16,.14,length,.24,.32,'#d2c3ae')
            normal={'A':(1,0),'C':(0,1),'D':(-1,0)}.get(letter)
            fronting=normal and frame.nx*normal[0]+frame.nz*normal[1]>.94 and 26<length<40
            if fronting:
                video.stepped_end(frame.block,length,h,STONE,PALE,GLASS)
            if length < 4.0:
                continue
            count = max(1,round((length-.7)/(5.65 if letter in 'AF' else 5.8)))
            step = (length-.86)/count
            same = frame.nx*portal.nx+frame.nz*portal.nz>.92
            for k in range(count):
                u = -length/2+.43+(k+.5)*step
                px,_,pz=frame.at(u,0,0)
                if same and abs((px-portal.x)*portal.nz-(pz-portal.z)*portal.nx) < PROFILES[letter][1]/2+1.4 and abs((px-portal.x)*portal.nx+(pz-portal.z)*portal.nz)<4.1:
                    continue
                w = min(step*.71,4.15)
                if w < 1.4:
                    continue
                # A recessed dark strip with pale jambs matches the photographed vertical bays.
                frame.block('石窗洞边框',u,7.70,.10,w+.38,12.75,.23,'#cabeae')
                frame.block('竖向深色窗带',u,7.70,.25,w,12.45,.095,SPANDREL)
                for floor in range(3):
                    cy = 3.05+floor*4.04
                    frame.block('落地窗组',u,cy,.32,w-.16,2.78,.11,GLASS)
                    frame.block('两扇中梃',u,cy,.397,.085,2.78,.05,DARK)
                    frame.block('开启窗横档',u,cy+.61,.405,w-.12,.075,.06,DARK)
                frame.block('顶层退窗',u,h-1.59,.095,w*.77,1.52,.18,'#40586a')
                if length>24 and k%3==1:
                    frame.block('石柱竖棱',u-step*.46,8.0,.20,.36,13.20,.44,PALE)
                if length>32 and k%3==1:
                    if letter=='B':
                        video.rounded_dormer(frame.s,frame.at,frame.s.college_roof,u,TILE,PALE,GLASS)
                    else:
                        dormer(frame,u,h)


def dormer(w,u,h):
    # Small triangular dormer faces on the edge of the roof, with a tile hood.
    z = -.92
    x,_,zz=w.at(u,0,z)
    roof_model=w.s.college_roof
    h=roof_model.sheet.y(x,zz)-.49+.015
    w.panel('小老虎窗玻璃',[(u-.72,h+.58),(u+.72,h+.58),(u,h+1.34)],z+.023,GLASS)
    pts = [w.at(u+dx,y,t) for dx,y,t in [(-1.12,h+.49,z+.16),(0,h+1.70,z+.16),
             (1.12,h+.49,z+.16),(-1.12,h+.49,z-1.90),(0,h+1.70,z-1.15),(1.12,h+.49,z-1.90)]]
    pitched_cap(w.s,'红瓦小坡顶',pts,[(0,1,4,3),(1,2,5,4)],.095,TILE,PALE)
    dormer_walls(w.s,roof_model,pts[:3],pts[3:],.20,PALE,STONE)


def entry_glazing(frame, width, arch):
    ground,base= .60,2.95 if arch else 4.40
    radius=width/2
    frame.block('门厅深色玻璃',0,(base+ground)/2,-1.24,width,base-ground,.18,GLASS)
    if arch:
        half = [(radius*math.cos(a*math.pi/28),base+radius*math.sin(a*math.pi/28)) for a in range(29)]
        frame.panel('半圆拱窗',[(0,base),*half],-1.11,GLASS)
        for i in range(28):
            a,b=i*math.pi/28,(i+1)*math.pi/28
            frame.panel('圆拱石窗套',[(r*math.cos(t),base+r*math.sin(t)) for r,t in
                [(radius,a),(radius+.20,a),(radius+.20,b),(radius,b)]],-1.045,'#b9a991')
    for u in [-radius, -radius*.62, -radius*.23, 0, radius*.23, radius*.62, radius]:
        top = base+math.sqrt(max(0,radius**2-u**2)) if arch else base
        frame.block('门厅立梃',u,(ground+top)/2,-1.008,.075,top-ground,.10,DARK)
    frame.block('门厅横档',0,2.92,-.98,width,.10,.10,DARK)
    frame.block('双扇门顶',0,2.67,-.96,width*.46,.10,.08,'#a5a29d')
    for u in (-.20,.20):
        frame.block('门拉手',u,1.66,-.92,.045,.55,.055,'#c3b8a2')


def triangle_head(fr, h, width, depth, letter):
    """Stone-framed blue gable over entrance, as seen on C, D, E and F."""
    top = h+2.7
    base = h-3.45
    eave = h+.15
    u=width/2
    setback=depth*.38
    fr.block('中央竖向玻璃',0,(5.72+base)/2,setback,width-.95,base-5.72,.20,GLASS)
    wallshape=[(-u,base-.02),(u,base-.02),(u,eave),(0,top),(-u,eave)]
    fr.panel('灰白三角山墙框',wallshape,setback+.08,PALE)
    fr.panel('三角玻璃冠', [(-u+.62,base+.15),(u-.62,base+.15),(u-.62,eave-.30),
                        (0,top-.65),(-u+.62,eave-.30)],setback+.118,GLASS)
    for side in (-1,1):
        fr.block('中央山墙边柱',side*(u-.15),(5.64+eave)/2,setback+.22,.58,eave-5.64,.55,STONE)
    for i in range(-3,4):
        ux=i*(u-.65)/3
        upper=top-.67-(top-eave)*abs(ux)/(u-.65)
        fr.block('山墙窗金属立梃',ux,(upper+5.7)/2,setback+.16,.09,upper-5.7,.08,DARK)
    for v in (7.45,11.30,base,16.25):
        fr.block('山墙玻璃横梁',0,v,setback+.18,width-1.08,.11,.10,DARK)
    p=[fr.at(ux,v,t) for ux,v,t in [(-u-.38,eave+.02,setback+.57),(0,top+.25,setback+.57),
          (u+.38,eave+.02,setback+.57),(-u-.38,eave+.02,-6.5),(0,top+.25,-6.5),(u+.38,eave+.02,-6.5)]]
    pitched_cap(fr.s,'中央横向红瓦屋脊',p,[(0,3,4,1),(1,4,5,2)],.18,TILE,PALE)


def raised_portal(s, letter, fr, h):
    width,depth=PROFILES[letter][1:3]
    arch = letter=='B'
    inner_w = width*(.51 if arch else .57)
    top = 7.52 if arch else 5.56
    entry_glazing(fr,inner_w,arch)
    for i in range(5):
        leading=depth+1.25+(4-i)*.37
        level=.12*(i+1)
        fr.block('花岗岩踏步',0,level/2,(leading-1.5)/2,width+1.25,level,leading+1.5,'#b9b6ac')
    edge_t=depth-.29
    side_at=width*.395
    for side in (-1,1):
        fr.block('门廊石墙及铭牌背衬',side*side_at,(top+.56)/2,depth/2-.32,
                 width*.218,top-.56,depth+.09,STONE if letter in 'ABF' else '#d0cbc1')
    # Rain porch is a horizontal slab with a stepped moulding; its soffit is visible.
    fr.block('门廊顶板',0,top+.05,depth/2-.25,width+.17,.71,depth+1.2,STONE)
    fr.block('叠涩檐口',0,top+.40,depth/2-.23,width+.54,.18,depth+1.54,PALE)
    fr.block('檐口压顶',0,top+.57,depth/2-.21,width+.78,.17,depth+1.80,STONE)
    if letter in 'ACEF':
        for side in (-1,1):
            px,py,pz=fr.at(side*inner_w*.414,(top+.59)/2,depth-.85)
            s.cyl('灰白石圆柱',px,py,pz,.42,top-.59,'#c9c5bc',20)
            s.cyl('柱础',px,.77,pz,.48,.34,'#c4bfb3',20)
    if letter in 'CE':
        fr.panel('门廊中央梯形拱心石',[(-.35,top-.17),(.35,top-.17),(.59,top+.64),(-.59,top+.64)],
                 depth+.76,'#b4ad9d')
        fr.block('拱心石顶',0,top+.70,depth+.72,1.31,.15,.33,PALE)
    if letter in 'AB':
        for i in range(19):
            fr.block('门楣细齿饰',(i-9)*width/20,top+.09,depth+.43,.16,.47,.18,'#e6d9c2')
    if letter == 'B':
        for side in (-1,1):
            u = side*(width*.54)
            fr.block('B座门厅竖塔',u,(h+.73)/2,.94,2.36,h+.73,2.55,PALE)
            for k in (-1,0,1):
                fr.block('塔柱狭长窗口',u+k*.49,12.60,2.24,.23,6.45,.08,GLASS)
                fr.block('塔柱底部窄窗',u+k*.49,4.00,2.24,.23,4.05,.08,GLASS)
            fr.block('竖塔薄压顶',u,h+.80,.94,2.55,.22,2.74,STONE)
        for i in range(-2,3):
            fr.block('B门厅二层竖窗',i*1.07,11.52,.22,.72,3.14,.25,GLASS)
    elif letter in 'CDEF':
        triangle_head(fr,h,width*.91,depth,letter)
    else:
        # A contains a long clerestory and a shallow central court roof, with no glass gable here.
        for i in range(-3,4):
            fr.block('A门厅上层玻璃',i*1.52,11.46,.21,1.32,6.34,.20,GLASS)
        for i in range(-2,3):
            fr.block('A入口两端粗石带',-width*.57,i*.80+3.55,.64,1.12,.75,1.46,'#bbb4a6')
            fr.block('A入口两端粗石带',width*.57,i*.80+3.55,.64,1.12,.75,1.46,'#bbb4a6')
    if letter=='D':
        # The white/yellow rectangle and its diagonal cross identify this entry in both views.
        front = depth+2.85
        w,d = 9.85,4.95
        fr.block('西门石前场',0,-.080,front+d*.52,w+2.35,.24,d+1.28,'#aba89b')
        strip = .063
        colour = '#d4bb54'
        def paint(a,b):
            dx,dt=b[0]-a[0],b[1]-a[1]
            half=strip/(2*math.hypot(dx,dt))
            wx,wt=-dt*half,dx*half
            verts=[fr.at(u,.047,t) for u,t in [(a[0]+wx,a[1]+wt),(b[0]+wx,b[1]+wt),
                    (b[0]-wx,b[1]-wt),(a[0]-wx,a[1]-wt)]]
            fr.s.mesh('禁停标线',verts,[(0,1,2,3)],colour)
        corners=[(-w/2,front),(w/2,front),(w/2,front+d),(-w/2,front+d)]
        for k in range(4): paint(corners[k],corners[(k+1)%4])
        paint(corners[0],corners[2])
        paint(corners[1],corners[3])
    return side_at, edge_t


def attach_plates(fr, letter, side_at, depth):
    if letter=='A':
        # Both photographed A entrances carried these boards historically. The replacement status
        # and side of the old inscriptions are unresolved. Hold both faces without writing.
        for name,offset,width,height in [('左侧金属横牌',-side_at,2.10,.84),('右侧金属立牌',side_at,1.52,2.10)]:
            fr.block(name,offset,3.0,depth+.055,width,height,.105,'#d8d5c7')
        return
    if letter=='F':
        return
    key=f'way-{IDS[letter]}'
    src,year=SOURCES[letter]
    dark='#302c29'
    # This face is beyond every portal back wall and remains readable from the outdoors.
    front_depth=depth+.055
    def line(board,part,label,u,y,w,h,carrier,note=''):
        plaque(fr.s,key,f'{letter}-{board}-{part}',label,*fr.at(u,y,front_depth+.075),w,h,fr.yaw,
               source=src,year=year,carrier=carrier,colour=dark,background=None,note=note)
    def board(u,v,w,h,carrier):
        fr.block(carrier+' 金属底板',u,v,front_depth,w,h,.105,'#d8d5c7')
        fr.block(carrier+' 下缘',u,v-h/2+.045,front_depth+.063,w-.06,.035,.027,'#88887a')
    right = '入口右侧楼栋金属牌'
    u=side_at
    centre=3.02
    board(u,centre,1.52,2.10,right)
    # The circular crest on the right plaque is represented by a relief ring without invented type.
    for i in range(36):
        a,b=i*2*math.pi/36,(i+1)*2*math.pi/36
        fr.panel('楼牌圆徽轮廓',[(u+r*math.cos(t),centre+.72+r*math.sin(t)) for r,t in
                                  [(.135,a),(.153,a),(.153,b),(.135,b)]],front_depth+.072,'#806e66')
    line('R','zh','第周苑',u,centre+.22,1.25,.35,right)
    line('R','en','DIZHOU COURTYARD',u,centre-.054,1.31,.125,right)
    line('R','letter',letter,u,centre-.40,.65,.49,right)
    for i in range(3):
        fr.block('楼牌下部细格',u,centre-.72-i*.045,front_depth+.062,1.22,.02,.016,'#77776d')
    if letter=='B':
        rows=[('生命科学学院','SCHOOL OF LIFE SCIENCES'),('','')]
    elif letter=='C':
        rows=[('计算机科学与技术学院','SCHOOL OF COMPUTER SCIENCE AND TECHNOLOGY')]
    elif letter=='D':
        rows=[('信息科学与工程学院','SCHOOL OF INFORMATION SCIENCE AND ENGINEERING')]
    else:
        rows=[('前沿交叉科学青岛研究院','INSTITUTE OF FRONTIER AND INTERDISCIPLINARY SCIENCE'),
              ('信息科学与工程学院','SCHOOL OF INFORMATION SCIENCE AND ENGINEERING'),
              ('光学高等研究中心','CENTER FOR OPTICS RESEARCH AND ENGINEERING')]
    for i,(ch,en) in enumerate(rows):
        v=3.0+(.92*(len(rows)-1)/2)-i*.92
        carrier=f'入口左侧第{i+1}块金属横牌'
        board(-side_at,v,2.10,.84,carrier)
        if not ch:
            continue  # Second B plaque exists, but people hide part of its inscription.
        note = ''
        line(f'L{i+1}','sdu','山东大学',-side_at,v+.251,.68,.102,carrier,note)
        line(f'L{i+1}','zh',ch,-side_at,v+.001,1.92,.25,carrier,note)
        line(f'L{i+1}','en',en,-side_at,v-.23,1.96,.090,carrier,note)


def build(row, poly):
    key=str(row.get('id') or row.get('key')).replace('/','-')
    letter=KEYS[key]
    s=Shape('第周苑'+letter+'座')
    x,z,nx,nz=AXES[letter]
    fr=Front(s,x,z,nx,nz)
    h,width,depth,_=PROFILES[letter]
    recess=Polygon([(pt[0],pt[2]) for pt in [fr.at(u,0,t) for u,t in
                    [(-width*.32,-1.55),(width*.32,-1.55),(width*.32,3.5),(-width*.32,3.5)]]])
    lintel=7.48 if letter=='B' else 5.60
    walls(s,poly.difference(recess),-.33,lintel,STONE)
    walls(s,poly,lintel,h,STONE)
    crown(s,poly,h,letter)
    facade(s,poly,fr,h,letter)
    side_at,edge=raised_portal(s,letter,fr,h)
    attach_plates(fr,letter,side_at,edge)
    return s,h+3.0

