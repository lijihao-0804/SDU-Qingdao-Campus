"""Exterior forms traced against the user's second campus flight (116.31 seconds)."""
import json
import math
import random
from pathlib import Path

import mapbox_earcut as ear
import numpy as np

STONE='#D2B89B'
LIGHT='#E6D2B5'
TRIM='#F0DEC0'
SHADE='#AE937B'
GLASS='#526D78'
METAL='#455354'
TILE='#974E45'
RED='#A45E53'
WHITE='#E6E4DA'


def rectangle(x,y,w,h):
    return [(x-w/2,y-h/2),(x+w/2,y-h/2),(x+w/2,y+h/2),(x-w/2,y+h/2)]


def perforated(b,name,material,outer,holes,xyz,reverse=False):
    rings=[outer]+holes
    uv=[pt for loop in rings for pt in loop]
    idx=ear.triangulate_float64(np.asarray(uv,np.float64),np.cumsum([len(r) for r in rings],dtype=np.uint32)).reshape(-1,3)
    for tri in idx:
        seq=tri[::-1] if reverse else tri
        b.poly(name,material,[xyz(*uv[j]) for j in seq])


def jambs(b,name,loop,front,back,material):
    for k,a in enumerate(loop):
        c=loop[(k+1)%len(loop)]
        b.poly(name,material,[front(*a),front(*c),back(*c),back(*a)])


def arch_loop(x,half,sill,spring,rise,samples=26):
    return [(x-half,sill),(x+half,sill)]+[(x+half*math.cos(j*math.pi/samples),spring+rise*math.sin(j*math.pi/samples)) for j in range(samples+1)]


def library_front(b,side):
    """A wall with continuous real negative spaces for the five portals and recessed stacks."""
    from qd_landmarks import glass
    z,back=39.55,36.94
    sill=3.92 if side==0 else 1.52
    arches=[arch_loop(x,2.55,sill,8.38 if side==0 else 7.2,2.52) for x in (-18,-9,0,9,18)]
    recesses=[rectangle(x,26.80,7.0,29.05) for x in (-18,-9,0,9,18)]
    to=lambda depth:lambda x,y:(x,y,depth)
    perforated(b,'实切五拱与五个落地深窗间',STONE,rectangle(0,22.98,63.6,46.20),arches+recesses,to(z))
    for hole in arches:
        jambs(b,'图书馆拱口石质券筒',hole,to(z),to(back),SHADE)
        perforated(b,'图书馆内退入口玻璃','#384748',hole,[],to(back-.02))
        x=(hole[0][0]+hole[1][0])/2
        for dx in (-1.35,0,1.35):
            b.cube('拱门青灰竖框',METAL,x+dx,(hole[1][1]+8.15)/2,back+.04,.105,8.15-hole[1][1],.13)
        b.cube('拱门横框',METAL,x,7.45,back+.055,5.0,.15,.13)
    for hole in recesses:
        x=(hole[0][0]+hole[1][0])/2
        jambs(b,'深窗间石材侧壁',hole,to(z),to(back),SHADE)
        b.rect('深窗间后墙',STONE,x,26.8,back,7.0,29.05)
        for j in range(6):
            cy=14.48+j*4.48
            glass(b,'内退双扇阅览窗',x,cy,back+.055,4.78,2.77,2,2)
            b.cube('石窗台',TRIM,x,cy-1.44,back+.105,5.1,.17,.30)
    # Real mortar lines stop at each arched recess.
    from shapely.geometry import Polygon,LineString
    lower=Polygon(rectangle(0,5.88,63.6,11.76),arches)
    for row in range(1,14):
        yy=row*.84
        seg=lower.intersection(LineString([(-31.8,yy),(31.8,yy)]))
        for ln in getattr(seg,'geoms',[seg]):
            if ln.geom_type=='LineString' and ln.length>.1:
                left,right=sorted((ln.coords[0][0],ln.coords[-1][0]))
                b.rect('入口勒脚水平石缝',SHADE,(left+right)/2,yy,z+.012,right-left,.035)
        for i in range(-16,17):
            xx=2.03*i+(.98 if row%2 else 0)
            seg=lower.intersection(LineString([(xx,yy-.80),(xx,yy-.04)]))
            for ln in getattr(seg,'geoms',[seg]):
                if ln.geom_type=='LineString' and ln.length>.10:
                    b.rect('入口错缝石块',SHADE,xx,(ln.coords[0][1]+ln.coords[-1][1])/2,z+.013,.031,ln.length)


def library_steps(b):
    # Three flights, their landings and side undercroft portals are visible at 20.1/31.3 s.
    landing=3.90;start=58.8;count=24;rise=landing/count
    for i in range(count):
        depth=.51+(.95 if i in (7,15) else 0)
        top=(i+1)*rise
        b.cube('图书馆三级台段踏步','#D5CBB8',0,top/2,start-depth/2,30.5,top,depth+.017)
        start-=depth
    b.cube('图书馆入口平台','#D5CBB8',0,landing/2,(start+39.32)/2,30.5,landing,start-39.32+.025)
    for side in (-1,1):
        for z,lo,hi in [(56.0,0,1.35),(51.3,1.28,2.6),(46.6,2.55,3.91)]:
            b.cube('阶梯实心侧颊',STONE,side*15.43,(lo+hi+.36)/2,z,.68,hi+.36-lo,4.65)
            b.cube('台阶白石扶墙压顶',TRIM,side*15.43,hi+.37,z,.87,.16,4.70)
        for dx in (-2.4,2.4):
            b.cube('侧厅门廊石柱',STONE,side*18.65+dx,1.52,44.15,1.0,3.04,3.16)
        b.cube('侧厅挡雨石顶',TRIM,side*18.65,3.36,44.28,6.36,.50,4.10)
        b.rect('侧厅内退地下入口','#34413e',side*18.65,1.49,42.55,3.88,2.97)
    # World X=62 lies 114.256 m west of the library origin.
    podium_z=114.256
    b.cube('三旗台石基','#babcb3',0,.43,podium_z,13.8,.43,5.05)
    b.cube('三旗台浅石压顶','#d1d1c5',0,.69,podium_z,14.03,.17,5.22)
    for j in range(3):
        top=.40+.115*j
        b.cube('旗台轴线小台阶','#c6c8be',0,(.20+top)/2,podium_z+3.81-j*.44,5.5,top-.20,.47)
    for x in (-4.32,0,4.32):
        height=17.25 if x==0 else 16.95
        ring=[(x+.087*math.cos(j*math.tau/12),podium_z+.087*math.sin(j*math.tau/12)) for j in range(12)]
        for j,(px,pz) in enumerate(ring):
            qx,qz=ring[(j+1)%len(ring)]
            b.poly('轴线不锈钢旗杆','#ADB4AF',[(px,.78,pz),(px,height,pz),(qx,height,qz),(qx,.78,qz)])


def library_crown(b):
    for yaw,span,edge in ((0,77.4,37.55),(math.pi,77.4,37.55),
                          (math.pi/2,75.1,38.7),(-math.pi/2,75.1,38.7)):
        b.frame(0,0,yaw)
        lo,hi,inset=57.02,66.3,8.35
        top=edge-inset
        outline=[(-span/2,0),(span/2,0),(span/2-inset,1),(-span/2+inset,1)]
        cuts=[rectangle(i*1.55,.758,1.075,.193) for i in range(-5,6)]
        xyz=lambda x,t:(x,lo+(hi-lo)*t,edge-inset*t)
        rear=lambda x,t:(x,lo+(hi-lo)*t-.095,edge-inset*t-.17)
        perforated(b,'馆顶砖红坡面实开十一孔',TILE,outline,cuts,xyz)
        perforated(b,'馆顶有孔内衬','#93564a',outline,cuts,rear,True)
        for hole in cuts:jambs(b,'通风采光孔翻边',hole,xyz,rear,'#875145')
        jambs(b,'坡顶四边金属封边',outline,xyz,rear,TILE)
        clear=span-2*inset
        b.cube('屋冠内围红钢下槛','#a36752',0,58.40,top,clear,.53,.65)
        for yy in (60.43,63.02,66.09):
            b.cube('屋冠内围三道主梁','#9e5c4b',0,yy,top,clear+.35,.46,.74)
        for j in range(9):
            x=(j/8-.5)*(clear-.50)
            b.cube('屋冠承重红框柱','#a3634e',x,62.10,top,.51,8.05,.67)
            b.cube('屋冠径向支撑','#986052',x,65.79,top-.94,.28,.32,2.22)
        for j in range(21):
            x=(j/20-.5)*(clear-1.30)
            b.cube('内环检修次梁','#a06855',x,61.44,top+1.54,.14,.21,3.13)
    b.frame(0,0,0)


def museum_mark(b):
    """The emblem and Chinese calligraphy are vector outlines of the 74.7-s film frame."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    from qd_terrain import polygons
    from os import environ
    path=Path(__file__).resolve().parents[1]/'data/v5_video_landmarks.json'
    outlines=json.loads(path.read_text('utf-8-sig'))['museumLettering']['contours']
    # All surfaces start at the white tower wall and end on the embossed ink face.
    def solid(rings):
        perforated(b,'北立面墙上馆名与标识','#34383a',rings[0],rings[1:],lambda x,y:(x,y,29.496))
        for loop in rings:
            jambs(b,'北立面实体文字侧边',loop,lambda x,y:(x,y,29.496),lambda x,y:(x,y,29.45),'#666767')
    ux=lambda x:-15.20+(x-52)*.040
    yy=lambda y:38.17-(y-11)*.040
    for rings in outlines:
        top=min(pt[1] for pt in rings[0]);mid=sum(pt[0] for pt in rings[0])/len(rings[0])
        if top>86 and mid<39:continue
        solid([[(ux(x),yy(y)) for x,y in ring] for ring in rings])
    font=FontProperties(fname=str(Path(environ.get('WINDIR','C:/Windows'))/'Fonts/arialbd.ttf'))
    glyph=TextPath((0,0),'SHANDONG UNIVERSITY MUSEUM',size=1,prop=font)
    merged=Polygon()
    for ring in glyph.to_polygons():
        if len(ring)>3:merged=merged.symmetric_difference(Polygon(ring).buffer(0))
    x0,y0,x1,y1=merged.bounds;scale=12.55/(x1-x0)
    for p in polygons(merged):
        p=orient(p,1)
        rs=[[(ux(25)+(y-y0)*scale,yy(97)-(x-x0)*scale) for x,y in ring.coords[:-1]]
            for ring in (p.exterior,*p.interiors)]
        solid(rs)


def museum_north(b):
    # One white screen carries the name; the copper slip screen faces north on the other box.
    b.cube('馆名所在白石悬挑墙',WHITE,-21.2,29.62,18.95,20.90,23.40,21.0)
    for row in range(17):
        y=18.35+row*1.32
        b.rect('白石板水平细缝','#c2c4bd',-21.2,y,29.459,20.75,.039)
        for k in range(-5,6):
            x=-21.2+k*2.25+(1.12 if row%2 else 0)
            if -31.5<x<-10.92:b.rect('白石错缝立缝','#c2c4bd',x,y+.65,29.463,.032,1.27)
    museum_mark(b)
    # Behind the projecting curtain box a blue lower wall remains visible on both sides.
    b.cube('中央幕墙后衬','#243958',0,20.04,27.08,26.0,34.2,.53)
    for j in range(14):
        for k in range(8):
            b.rect('蓝玻璃入口背衬','#385680' if (j+2*k)%5 else '#6688ae',
                   (j-6.5)*1.85,5.26+k*4.08,27.37,1.75,3.96)
    left,right=-10.0,10.0;bottom,top=8.05,37.56
    for s in (-1,1):
        b.cube('宝蓝玻璃框侧面',WHITE,s*10.16,(top+bottom)/2,29.47,.35,top-bottom+.41,3.94)
    for y in (bottom,top):
        b.cube('悬挑幕墙上下石边',WHITE,0,y,29.48,20.66,.39,3.98)
    palette=('#274781','#315997','#2a4b84','#426bb0')
    for i in range(17):
        x=left+(i+.5)*(right-left)/17
        width=(right-left)/17-.075
        intervals=[bottom+.22,13.50+(i%3)*.72,19.7+((i*3)%5)*.78,27.2+((i*7)%5)*.84,top-.22]
        for j,(lo,hi) in enumerate(zip(intervals,intervals[1:])):
            z=31.02+(.14 if (i+2*j)%5<=1 else 0)
            b.rect('北门不等高宝蓝玻璃',palette[(i*3+j+i//4)%4],x,(lo+hi)/2,z,width,hi-lo-.095)
            b.cube('幕墙短横压线','#243958',x,lo,z+.05,width,.085,.10)
        b.cube('幕墙窄竖肋','#263c56',x-width/2-.035,(top+bottom)/2,31.09,.069,top-bottom-.38,.27)
    for i in range(-3,4):
        x=i*1.29
        b.rect('隐在玻璃后的北门扇','#2d4049',x,6.68,28.0,1.20,3.72)
        b.cube('北门推拉把手','#969da0',x+.46,6.15,28.16,.062,.52,.10)
    b.cube('北门入口上方窄雨棚','#333f46',0,8.70,28.34,13.6,.18,1.40)
    b.cube('北门口上平台','#c4c3b8',0,2.41,34.65,39.7,4.82,12.85)


def bronze(b,cx):
    b.rect('竹简屏内凹背衬','#384b49',cx,33.81,29.48,19.43,14.54)
    shades=('#657970','#72867c','#667d75','#779085')
    for i in range(20):
        x=cx+(i-9.5)*.957
        cuts=[26.64,30.55+(i*7%5)*.77,35.58+(i*3%5)*.51,40.98]
        for j,(lo,hi) in enumerate(zip(cuts,cuts[1:])):
            b.cube('错缝竹简直立铜片',shades[(i+3*j)%4],x,(lo+hi)/2,29.57,.884,hi-lo-.110,.165)



def court_tree(b,x,z,h,r,conifer,rng):
    b.cube('中庭乔木树干','#665a4b',x,h*.31,z,.22,h*.62,.22)
    n=9
    if conifer:
        layers=[(.34,.68),(.50,1.0),(.69,.70),(.84,.42),(.99,.035)]
        colours=('#455f46','#4e684e','#547158')
    else:
        layers=[(.41,.17),(.52,.77),(.71,1),(.88,.80),(.99,.12)]
        colours=('#62774f','#657f54','#72915c','#78945d')
    angle=rng.random()*2
    radii=[.85+rng.random()*.25 for j in range(n)]
    rings=[[(x+math.cos(angle+j*math.tau/n)*r*rr*radii[j],h*hh,
             z+math.sin(angle+j*math.tau/n)*r*rr*radii[j]) for j in range(n)] for hh,rr in layers]
    if not conifer and h>3.5:
        # Broadleaf tree crowns in the teaching courts overlap unevenly above clear trunks.
        for k in range(3):
            phase=angle+k*math.tau/3+rng.uniform(-.23,.23)
            dx=r*.45*math.cos(phase);dz=r*.45*math.sin(phase)
            cy=h*rng.uniform(.64,.82);rr=r*rng.uniform(.45,.61)
            twig=[(x+dx+rr*math.cos(phase+j*math.tau/7),
                   cy+(.15*r if j%3==0 else 0),z+dz+rr*math.sin(phase+j*math.tau/7)) for j in range(7)]
            for j in range(7):
                n2=(j+1)%7
                mat=colours[(k+j//3+int(h))%len(colours)]
                b.poly('落叶乔木侧生团冠',mat,[twig[j],(x+dx,cy+rr*.77,z+dz),twig[n2]])
                b.poly('落叶乔木侧生团冠',mat,[twig[n2],(x+dx,cy-rr*.68,z+dz),twig[j]])
    for a,c in zip(rings,rings[1:]):
        for j in range(n):
            k=(j+1)%n
            b.poly('庭植针叶乔木' if conifer else '庭院落叶树冠',colours[(j//3+int(h))%len(colours)],
                   [a[j],c[j],c[k],a[k]])


def court_garden(b,key,ix,iz):
    from qd_teaching_courts import FLOOR,PAVING
    hu=key=='huagang'
    rng=random.Random(104 if hu else 191)
    # Match the width of the four portals all the way through the garden.
    side=4.40 if hu else 4.25
    x0,x1=side,ix-(3.60 if hu else 2.5)
    z0,z1=side,iz-3.5
    bw,bd=x1-x0,z1-z0
    cross_x,cross_z=x0+.50*bw,z0+.55*bd
    xs=[(x0,cross_x-.68),(cross_x+.68,x1)] if hu else [(x0,x1)]
    zs=[(z0,cross_z-.72),(cross_z+.72,z1)] if hu else [(z0,z1)]
    beds=[]
    for sx in (-1,1):
        for sz in (-1,1):
            for xa,xb in xs:
                for za,zb in zs:
                    cx,cz=sx*(xa+xb)/2,sz*(za+zb)/2
                    rw,rd=xb-xa,zb-za
                    outer=rectangle(cx,cz,rw,rd)
                    lawn=rectangle(cx,cz,rw-.32,rd-.32)
                    beds.append(outer)
                    at=lambda y:lambda x,z:(x,y,z)
                    perforated(b,'庭院草地石边', '#b9b7a7',outer,[lawn],at(.23),True)
                    jambs(b,'花池外缘',outer,at(.23),at(FLOOR),'#b9b7a7')
                    jambs(b,'花池内缘',lawn,at(.20),at(.23),'#b9b7a7')
                    b.poly('庭院草地','#83925d',[(x,.20,z) for x,z in reversed(lawn)])
                    if za==z0:
                        b.cube('草缘修剪矮篱','#61794e',cx,.46,sz*(za+.5),rw-.9,.50,.62)
                    if xa==x0:
                        b.cube('草缘修剪矮篱','#61794e',sx*(xa+.48),.46,cz,.66,.50,rd-.9)
            # Mature planting is staggered within beds. The trunk and shrubs keep
            # clear of both the main cross and Huagang's secondary paths.
            def on_bed(v,cross):
                if not hu or abs(v-cross)>=1.65:
                    return v
                return cross+(-1.65 if v<cross else 1.65)
            for j in range(12 if hu else 13):
                rx=(j%3+.21+rng.random()*.59)/3
                rz=(j//3+.24+rng.random()*.53)/(4 if hu else 5)
                x=sx*on_bed(x0+2.0+(bw-4)*rx,cross_x)
                z=sz*on_bed(z0+2.1+(bd-4.3)*rz,cross_z)
                h=rng.uniform(5.45,10.15) if hu else rng.uniform(7.1,12.45)
                pointed=(j%5==2) if hu else (j%4==0)
                court_tree(b,x,z,h,h*(.255 if pointed else (.438 if hu else .462)),pointed,rng)
            for j in range(4):
                x=sx*on_bed(x0+1.9+(j+.6)*(bw-4)/4,cross_x)
                z=sz*(z0+1.7+(j%2)*1.6)
                court_tree(b,x,z,rng.uniform(1.22,1.80),rng.uniform(.72,1.22),False,rng)
    perforated(b,'中庭十字与环形步道',PAVING,rectangle(0,0,2*ix,2*iz),beds,
               lambda x,z:(x,FLOOR,z),True)


def passage_shell(b,group,length,height,inn,out,arched,material=LIGHT,back=True):
    """Extrude the actual opening in the wing's cross section; open at floor level."""
    from qd_teaching_courts import HALF_PASSAGE
    half=HALF_PASSAGE
    if arched:
        crown=[(half*math.cos(t*math.pi/24),2.13+2.92*math.sin(t*math.pi/24))
               for t in range(24,-1,-1)]
    else:
        crown=[(-half,4.70),(half,4.70)]
    reveal=[(-half,0),*crown,(half,0)]
    outer=[(-length/2,0),*reveal,(length/2,0),(length/2,height),(-length/2,height)]
    at=lambda depth:lambda x,y:(x,y,depth)
    perforated(b,group+' 门洞外墙',material,outer,[],at(out))
    if back:
        perforated(b,group+' 门洞庭院墙',material,outer,[],at(inn),True)
    for i,(a,c) in enumerate(zip(outer,outer[1:]+outer[:1])):
        lining=1<=i<len(reveal)
        b.poly(group+(' 门洞贯通内壁' if lining else ' 翼楼外缘'),
               '#a09580' if lining else material,
               [at(out)(*a),at(inn)(*a),at(inn)(*c),at(out)(*c)])


def court_wing(b,group,length,wallh,inn,out,arched):
    from qd_teaching_courts import FLOOR,HALF_PASSAGE,PAVING
    from qd_wing_junctions import END_BAY,end_pavilions
    core=length-2*END_BAY if arched else length
    passage_shell(b,group,core,wallh,inn,out,arched)
    if arched:
        end_pavilions(b,group,length/2,inn,out,wallh)
    for s in (-1,1):
        wide=core/2-HALF_PASSAGE
        # Project the exposed end cap as well as the two long faces. The wing
        # slot exposes this return at eye level, so a flush cap would z-fight.
        lip=.055
        b.cube(group+' 门洞两侧勒脚',SHADE,s*(HALF_PASSAGE+(wide+lip)/2),.48,(out+inn)/2,wide+lip,.96,out-inn+.26)
    b.poly(group+' 贯通门洞铺地',PAVING,[(-HALF_PASSAGE,FLOOR,inn),(-HALF_PASSAGE,FLOOR,out),
                             (HALF_PASSAGE,FLOOR,out),(HALF_PASSAGE,FLOOR,inn)])


def bridge_face(b,group,z,wallh):
    from qd_landmarks import glass
    from qd_teaching_courts import HALF_PASSAGE
    for sign in (-1,1):
        b.cube(group+' 平过梁边柱',TRIM,sign*(HALF_PASSAGE+.31),2.35,z+.16,.62,4.70,.32)
    b.cube(group+' 平过梁',TRIM,0,4.93,z+.16,2*HALF_PASSAGE+1.24,.46,.32)
    for row in range(3):
        y=6.95+row*3.48
        for col in (-1,0,1):
            glass(b,group+' 连廊上层窗',col*3.03,y,z+.056,2.72,2.33,2,1)
    b.cube(group+' 连廊上檐石带',TRIM,0,wallh-.67,z+.12,10.35,.24,.24)


def open_portal(b,group,z,back):
    half=4.28;spring=2.13;rise=2.90
    for s in (-1,1):
        b.cube(group+' 拱门厚岸柱',LIGHT,s*4.95,2.49,(z+back)/2,1.34,4.98,z-back)
    for j in range(24):
        t=j*math.pi/24;c=(j+1)*math.pi/24
        a=(half*math.cos(t),spring+rise*math.sin(t))
        e=(half*math.cos(c),spring+rise*math.sin(c))
        A=((half+.54)*math.cos(t),spring+(rise+.54)*math.sin(t))
        E=((half+.54)*math.cos(c),spring+(rise+.54)*math.sin(c))
        pts=[(a[0],a[1],z),(A[0],A[1],z),(E[0],E[1],z),(e[0],e[1],z)]
        b.poly(group+' 拱券正面',TRIM,pts)
        b.poly(group+' 拱下石券筒',SHADE,[(e[0],e[1],z),(e[0],e[1],back),(a[0],a[1],back),(a[0],a[1],z)])
    for s in (-1,1):
        b.cube(group+' 券脚',TRIM,s*4.58,spring/2,z-.3,.64,spring,.82)


def court_roof(b,key,group,side,length,center,depth,wallh,h,L,D):
    z0,z1=center-depth/2-.45,center+depth/2+.45
    zl,zr=center-D/2,center+D/2;ridge=h-.60
    outer=[(-length/2-.4,wallh+.14,z0),(length/2+.4,wallh+.14,z0),
           (length/2+.4,wallh+.14,z1),(-length/2-.4,wallh+.14,z1)]
    lip=[(-L/2,ridge,zl),(L/2,ridge,zl),(L/2,ridge,zr),(-L/2,ridge,zr)]
    lower=[(x,y-.65,z) for x,y,z in lip]
    for j in range(4):
        k=(j+1)%4
        b.poly(group+' 红瓦四面坡',RED,[outer[j],lip[j],lip[k],outer[k]])
        b.poly(group+' 屋顶设备槽内立缘','#aa9485',[lip[j],lower[j],lower[k],lip[k]])
    dark=key=='zhensheng' and side in (0,2)
    b.poly(group+' 设备槽内防水面','#65686a' if dark else '#aaa99e',lower[::-1])
    for s in (-1,1):
        b.cube(group+' 瓦顶细压边','#ad7b67',0,ridge+.02,center+s*D/2,L+.02,.12,.19)
    y=ridge-.65
    if key=='huagang' or side in (1,3):
        for j in range(11 if key=='huagang' else 6):
            n=11 if key=='huagang' else 6
            x=(j-(n-1)/2)*(L-7)/n;z=center+(-.76 if j%3 else .95)
            b.cube(group+' 风冷热泵基座','#777a76',x,y+.13,z,2.27,.26,1.63)
            b.cube(group+' 风冷热泵箱体','#b6b9b3',x,y+.57,z,2.10,.78,1.53)
            for dx in (-.51,.51):
                top=[(x+dx+.355*math.cos(a*math.tau/12),y+.970,z+.355*math.sin(a*math.tau/12)) for a in range(12)]
                b.poly(group+' 风机顶圆格栅','#626965',top[::-1])
            for a in (-.40,-.15,.10,.35):
                b.rect(group+' 机组侧格栅','#6e7673',x+.04,y+.57+a*.67,z+.775,1.64,.065)
    elif side==2:
        for j in range(5):
            x=(j-2)*2.35-L*.25
            for s in (-1,1):
                pts=[(x-1.14,y+.15,center+s*1.42),(x+1.14,y+.15,center+s*1.42),
                     (x+1.14,y+.87,center),(x-1.14,y+.87,center)]
                b.poly('振声北翼玻璃采光带','#82969b',pts if s>0 else pts[::-1])


def lunette(b,group,x,z,width,base,rise,depth):
    r=width/2;low=[]
    for j in range(21):
        a=j*math.pi/20
        low.append((x+r*math.cos(a),base+rise*math.sin(a),z))
    for p,q in zip(low,low[1:]):
        b.poly(group+' 扇窗玻璃','#537584',[(x,base,z),p,q])
        xx,yy,_=p;xx2,yy2,_=q
        A=(x+(xx-x)*1.05,base+(yy-base)*1.10+.14,z+.04)
        E=(x+(xx2-x)*1.05,base+(yy2-base)*1.10+.14,z+.04)
        b.poly(group+' 弧形窗券',TRIM,[p,A,E,q])
        b.poly(group+' 弧形窗顶外壳',RED,[A,(A[0],A[1],z-depth),(E[0],E[1],z-depth),E])
    for i in range(-3,4):
        dx=i*width/8.2
        hh=rise*math.sqrt(1-(dx/r)**2)
        b.cube(group+' 弧窗直框',METAL,x+dx,base+hh/2,z+.045,.115,hh,.12)
    b.cube(group+' 弧窗下槛',TRIM,x,base+.05,z,width+.42,.22,.52)


def court_inside(b,key,group,side,inn,out,wallh,arched):
    from qd_landmarks import curtain
    z=-inn
    if arched:
        low,high=5.40,wallh-.55
        curtain(b,group+' 庭院拱上整幅玻璃',0,(low+high)/2,z+.155,14.25,high-low,8,4)
        open_portal(b,group+' 内庭',z+1.01,z)
    else:
        bridge_face(b,group+' 内庭',z,wallh)
    if key=='zhensheng' and side==0:
        arc=[(6.1*math.cos(t*math.pi/24),z+5.15*math.sin(t*math.pi/24)) for t in range(25)]
        y=5.64
        b.poly('振声内庭半圆阳台底',TRIM,[(x,y,zz) for x,zz in arc])
        b.poly('振声内庭半圆阳台顶',LIGHT,[(x,y+.26,zz) for x,zz in arc][::-1])
        for a,c in zip(arc,arc[1:]):
            b.poly('振声弧形石栏板',TRIM,[(a[0],y,a[1]),(a[0],y+1.02,a[1]),(c[0],y+1.02,c[1]),(c[0],y,c[1])])
    if key=='zhensheng' and side==1:
        lunette(b,'振声内庭东翼中央',0,z-.60,15.30,wallh+.62,3.78,4.65)
        for x in (-29,-21,-13,13,21,29):
            lunette(b,'振声内庭东翼侧窗',x,z-1.30,3.45,wallh+1.01,1.36,2.62)
    if key=='huagang' and side in (0,2):
        for x in (-29.6,-19.0,-8.8,8.8,19.0,29.6):
            court_facing_dormer(b,group,x,-inn-2.48,wallh+1.04)
        ridge=(out+inn)/2
        for x in (-43.4,-21.25,0,21.25,43.4):
            b.cube(group+' 方形屋面排气道',SHADE,x,wallh+4.22,-ridge,.76,2.28,.86)
            b.cube(group+' 排气道压帽',LIGHT,x,wallh+5.38,-ridge,.96,.16,1.05)
        for wx in (-30,-21,-12,12,21,30):
            b.cube(group+' 庭院窗间石柱',LIGHT,wx,wallh*.50,z+.13,.48,wallh-.96,.30)
        b.cube(group+' 庭院上层石带',TRIM,0,wallh-1.91,z+.13,71.7,.20,.39)
        for sign in (-1,1):
            b.cube(group+' 门洞两侧石带',TRIM,sign*20.75,1.06,z+.13,30.2,.20,.39)


def museum_north_supports(b):
    # The museum's own oblique view and the film show a narrower stone foot below the left overhang.
    for sx,cx,width,front,top in ((-1,-19.40,17.30,26.0,16.18),(1,21.20,19.80,29.32,25.84)):
        bottom=4.80
        b.cube('北面悬盒下部白石支承',WHITE,cx,(bottom+top)/2,(3.8+front)/2,width,top-bottom,front-3.8)
        y=bottom+.81
        while y<top:
            b.rect('北墙下部横向石缝','#c2c4bd',cx,y,front+.009,width-.025,.035)
            for k in range(-5,6):
                xx=cx+k*2.25+(1.12 if int((y-bottom)/1.32)%2 else 0)
                if abs(xx-cx)<width/2-.05:
                    hh=min(1.28,top-y)
                    if hh>.04:b.rect('北墙下部竖向石缝','#c2c4bd',xx,y+hh/2,front+.013,.031,hh)
            y+=1.32


def register_north_towers(b):
    # Shift complete joined components including their submeshes and fitted roof, preserving the east/other wings.
    roof={'四角方盒下凹银灰盖板','方盒屋面正交构架','白石周边压顶'}
    left={'馆名所在白石悬挑墙','白石板水平细缝','白石错缝立缝','北立面墙上馆名与标识','北立面实体文字侧边'}
    right={'Cantilevered upper galleries','竹简屏内凹背衬','错缝竹简直立铜片'}
    sx,sy,sz=b.scales
    for (name,mat),(verts,faces) in b.parts.items():
        if name not in roof|left|right:continue
        for i,(x,y,z) in enumerate(verts):
            if z<=0:continue
            if x<0 and (name in left or name in roof):
                verts[i]=(x,y-1.75*sy,z-3.45*sz)
            elif x>0 and (name in right or name in roof):
                verts[i]=(x,y,z+5.20*sz)


def court_facing_dormer(b,group,x,z,eave):
    # Small upper lights sit on the *inner* north/south hip, immediately above the court window course.
    width=3.85;apex=eave+1.51
    pts=[(x-width/2,eave,z),(x+width/2,eave,z),(x,apex,z)]
    b.poly(group+' 庭院向三角窗墙',TRIM,pts)
    b.poly(group+' 庭院向三角窗玻璃','#455a59',[(x-1.43,eave+.13,z+.025),(x+1.43,eave+.13,z+.025),(x,apex-.30,z+.025)])
    for sign in (-1,1):
        pts=[(x+sign*2.06,eave-.04,z+.23),(x,apex+.16,z+.23),
             (x,apex+.16,z-2.94),(x+sign*2.06,eave-.04,z-2.94)]
        b.poly(group+' 庭院向三角窗瓦盖',RED,pts if sign<0 else pts[::-1])
    b.cube(group+' 庭院向三角窗底边',TRIM,x,eave,z,3.93,.18,.40)



def barrel_surface(x):
    # Circular section between two side sills; 3.38 m crown across the 30.8 m clear span.
    half,rise=15.4,3.38
    radius=(half*half+rise*rise)/(2*rise)
    return 57.99+math.sqrt(radius*radius-x*x)-(radius-rise)


def lantern_member(b,begin,end,width=.28):
    # An extruded gasket, two sloping edge profiles and an exposed silver cap form a complete mullion.
    x0,z0=begin;x1,z1=end
    length=math.hypot(x1-x0,z1-z0)
    nx,nz=(z0-z1)/length,(x1-x0)/length
    sections=max(1,math.ceil(length/1.05))
    def section(t):
        x=x0+t*(x1-x0);z=z0+t*(z1-z0);y=barrel_surface(x)
        return [(x+nx*offset,y+dy,z+nz*offset) for offset,dy in
                [(width*.57,.018),(width*.57,.202),(width*.36,.329),
                 (-width*.36,.329),(-width*.57,.202),(-width*.57,.018)]]
    for i in range(sections):
        a=section(i/sections);c=section((i+1)/sections)
        for j,mat in enumerate(('#4a575a','#95a9ac','#d6e1de','#b5c5c5','#475459','#475459')):
            k=(j+1)%len(a)
            b.poly('采光顶斜交钢格外露压条' if j==2 else '斜交框实体侧缘和防水胶条',mat,[a[j],c[j],c[k],a[k]])
    b.poly('斜交钢格端口','#899a9b',section(0))
    b.poly('斜交钢格端口','#899a9b',section(1)[::-1])


def skylight_equipment(b):
    # At the back two paired tan enclosures flank the lantern. The fanbank is on the right when facing east.
    for s in (-1,1):
        for off,w,h in ((0,3.30,5.68),(3.10,2.80,4.50)):
            x=s*(21.85-off);z=-17.35+off*.32;y=57.27
            b.cube('图书馆采光顶后方设备基座','#8c8c7f',x,y+.19,z,w+.38,.38,3.75)
            b.cube('图书馆屋面成组浅米机柜','#cabda6',x,y+h/2+.30,z,w,h,3.38)
            for layer in range(12):
                cy=y+.61+(h-.65)*layer/12
                b.rect('浅米机柜百叶阴影','#8d8778',x,cy,z+1.703,w-.41,.067)
            for side in (-1,1):
                b.cube('浅米机柜角框','#d4c8b0',x+side*(w/2-.08),y+h/2+.30,z+1.70,.14,h,.16)
            b.cube('设备箱顶边','#d8cbb5',x,y+h+.34,z,w+.19,.15,3.6)
        lx=s*24.48
        for d in (-.27,.27):
            b.cube('机房外侧检修梯', '#817f73',lx+d,60.00,-16.03,.088,5.15,.13)
        for j in range(11):
            b.cube('机房外侧检修梯', '#817f73',lx,57.7+j*.45,-16.03,.64,.061,.13)
    for j in range(7):
        x,z=18.35,-11.65+3.42*j;floor=57.30
        b.cube('东向画面右侧连续机组基座','#757b78',x,floor+.23,z,3.0,.46,3.23)
        b.cube('采光顶右侧列置风机箱','#b9b9ae',x,floor+1.46,z,2.94,2.22,3.19)
        b.cube('风机浅灰上盖','#d3d2c4',x,floor+2.62,z,3.13,.16,3.36)
        # Vertical discharge grilles stay visible from the aerial view; louvres remain visible in the roof walk.
        for dz in (-.72,.72):
            rim=[(x+.61*math.cos(t*math.tau/20),floor+2.721,z+dz+.61*math.sin(t*math.tau/20)) for t in range(20)]
            b.poly('屋顶风机圆形出风口','#616b6b',rim[::-1])
            for k in (-.35,-.12,.12,.35):
                half=math.sqrt(.59**2-k*k)
                b.cube('风机顶防护格','#939b96',x,floor+2.745,z+dz+k,half*2,.045,.061)
        for k in range(7):
            b.rect('屋面设备竖百叶','#6e7470',x-1.12+k*.37,floor+1.46,z+1.608,.13,1.56)
    for x,z in [(-18.9,-7.7),(-19.35,4.3)]:
        b.cube('左侧设备箱','#aaa99c',x,58.25,z,3.18,1.92,5.0)
        b.cube('左侧设备箱顶边','#cccabc',x,59.26,z,3.32,.19,5.12)


def library_lantern(b):
    from shapely.geometry import Polygon,box
    b.frame(0,0,0)
    half_w,half_d=15.4,15.6
    domain=box(-half_w,-half_d,half_w,half_d)
    hx,hz=1.69,1.82
    shades=('#274b61','#30596c','#39697d','#244b60')
    edges=set()
    for row in range(-11,12):
        for col in range(-6,7):
            x=(2*col+(row%2))*hx;z=row*hz
            points=[(x-hx,z),(x,z+hz),(x+hx,z),(x,z-hz)]
            pane=Polygon(points).intersection(domain)
            if pane.geom_type!='Polygon' or pane.area<.0001:continue
            corners=list(pane.exterior.coords)[:-1]
            # The convex glazed facet is triangulated from a crown-aligned centre to keep the rise visible.
            cx,cz=pane.centroid.coords[0]
            color=shades[(col*3+row//2+(1 if row%5==1 else 0))%4]
            for pt,qt in zip(corners,corners[1:]+corners[:1]):
                tri=[(cx,barrel_surface(cx),cz),(pt[0],barrel_surface(pt[0]),pt[1]),(qt[0],barrel_surface(qt[0]),qt[1])]
                if (pt[0]-cx)*(qt[1]-cz)-(pt[1]-cz)*(qt[0]-cx)>0:tri.reverse()
                b.poly('拱面分片蓝色菱形玻璃',color,tri)
                a=tuple(round(v,5) for v in pt);c=tuple(round(v,5) for v in qt)
                edges.add(tuple(sorted((a,c))))
    for a,c in sorted(edges):
        boundary=(a[0]==c[0] and abs(a[0])==half_w) or (a[1]==c[1] and abs(a[1])==half_d)
        lantern_member(b,a,c,.34 if boundary else .285)
    for s in (-1,1):
        b.cube('蓝玻璃采光顶侧基座','#adae9f',s*(half_w+.21),57.57,0,.45,.83,2*half_d+.82)
        b.cube('蓝玻璃采光顶端基座','#adae9f',0,57.57,s*(half_d+.19),2*half_w+.86,.83,.43)
        z=s*half_d
        for j in range(22):
            x0=half_w*(j/11-1);x1=half_w*((j+1)/11-1)
            pts=[(x0,57.84,z),(x1,57.84,z),(x1,barrel_surface(x1),z),(x0,barrel_surface(x0),z)]
            b.poly('端墙下部深蓝玻璃','#325364',pts if s>0 else pts[::-1])
    skylight_equipment(b)

