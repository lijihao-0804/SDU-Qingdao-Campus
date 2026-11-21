"""Photo-referenced brick residences, arcades and Chenyuan Hall in Qingdao.

Footprints are supplied in local coordinates (metres, X east, Z south).
Archive keys and the photo / estimate distinction are in architecture_spring_sources.json.
"""
import math

import mapbox_earcut as ear
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from qd_geometry import Shape
import qd_video_colleges as video
from qd_terrain import face, polygons

PHOENIX = {f'way/{k}' for k in range(970257676,970257682)}
ARCADES = {f'way/{k}' for k in range(970257682,970257686)}
SOUTH_END = 'way/982199358'
NORTH_U = {'s2/b1','s2/b9'}
NORTH_BAR = {'s2/b2','s2/b5','s2/b10'}
MORNING = 's2/b6'
SOURCE_MORNING = 'https://www.qdxq.sdu.edu.cn/info/1819/57064.htm'

BRICK_S='#b77261'
BRICK_N='#b2644c'
BRICK_D='#a45b48'
CREAM='#dac8ae'
DARK='#3e4a50'
GLAZE='#516671'
SKY='#687b83'
REVEAL='#79584c'
TILE_S='#c87958'
TILE_N='#b96e52'
COURT='#b2ada0'
STEEL='#697478'
PV='#516779'


class Facade:
    def __init__(self,shape,a,b):
        dx,dz=b[0]-a[0],b[1]-a[1]
        self.length=math.hypot(dx,dz)
        self.x=(a[0]+b[0])/2
        self.z=(a[1]+b[1])/2
        self.nx,self.nz=dz/self.length,-dx/self.length
        self.s=shape
        self.yaw=math.atan2(self.nx,self.nz)

    def at(self,u,y,t):
        return self.x+u*self.nz+t*self.nx,y,self.z-u*self.nx+t*self.nz

    def pane(self,name,loop,t,colour):
        v=[self.at(u,y,t) for u,y in loop]
        self.s.mesh(name,v,[(0,i,i+1) for i in range(1,len(v)-1)],colour)

    def rect(self,name,u,y,t,w,h,colour):
        self.pane(name,rectangle(u,y,w,h),t,colour)

    def block(self,name,u,y,t,w,h,d,colour):
        self.s.box(name,*self.at(u,y,t),w,h,d,colour,self.yaw)

    def cut_wall(self,holes,top,material,base=-1.15,offset=0):
        width=self.length/2
        loops=[[(-width,base),(width,base),(width,top),(-width,top)]]
        loops += [list(reversed(loop)) for loop in holes]
        # Each opening is a hole in the masonry, with its glazing physically recessed.
        uv=np.array([uv for loop in loops for uv in loop],np.float64)
        ends=np.cumsum([len(loop) for loop in loops],dtype=np.uint32)
        faces=ear.triangulate_float64(uv,ends).reshape(-1,3)
        self.s.mesh('砌体外墙开洞',[self.at(u,y,offset) for u,y in uv],faces,material)


def rectangle(u,y,width,height):
    return [(u-width/2,y-height/2),(u+width/2,y-height/2),
            (u+width/2,y+height/2),(u-width/2,y+height/2)]


def arch_loop(u,low,width,spring,rise):
    # Elliptical rather than semicircular: the court's ground-floor arches are shallow.
    half=width/2
    return [(u-half,low),(u+half,low)]+[(u+half*math.cos(a*math.pi/12),
            spring+rise*math.sin(a*math.pi/12)) for a in range(13)]


def reveal(frame,loop,depth,arch=False):
    surface=[frame.at(u,y,0) for u,y in loop]+[frame.at(u,y,-depth) for u,y in loop]
    n=len(loop)
    frame.s.mesh('砖券洞口内口' if arch else '窗洞侧壁',surface,
                 [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],REVEAL)


def opening(frame,holes,u,y,w,h,row,kind):
    loop=rectangle(u,y,w,h)
    holes.append(loop)
    recess=.235 if kind in ('north_u','north_bar') else .20
    reveal(frame,loop,recess)
    frame.pane('内退玻璃',loop,-recess,GLAZE if row%3 else SKY)
    frame.rect('窗扇竖梃',u,y,-recess+.016,.066,h,DARK)
    frame.rect('上亮窗横梃',u,y+h*.17,-recess+.022,w,.072,DARK)
    # In photographs some glass is screened from below by a dark opaque panel.
    if kind in ('north_u','north_bar') and row>0:
        frame.rect('深色栏板',u,y-h*.34,-.12,w,.30,DARK)
        frame.rect('栏顶细带',u,y-h*.27,-.095,w,.055,STEEL)


def arcade(frame,holes,u,w,top,walkthrough=False,depth=.60):
    spring=top-w*.135
    loop=arch_loop(u,-1.13 if walkthrough else .085,w,spring,w*.135);holes.append(loop)
    reveal(frame,loop,depth,True)
    if walkthrough:
        return
    frame.pane('拱廊后窗',loop,.02-depth,GLAZE)
    frame.rect('拱廊后窗横梃',u,top*.58,.055-depth,w,.13,DARK)
    frame.rect('拱廊后窗中梃',u,(top+.08)/2,.065-depth,.095,top-.15,DARK)
    if top>5:
        frame.rect('夹层栏板',u,top*.54,.37-depth,w,.47,DARK)
        frame.rect('夹层扶手',u,top*.60,.39-depth,w,.075,STEEL)
    # A narrow raised brick arch band follows the inside profile.
    inner=loop[2:];outer=[(u+(x-u)*(1+.22/w),v+.105) for x,v in inner]
    frame.s.mesh('拱券压线',[frame.at(x,v,.036) for x,v in inner+outer],
                 [(i,i+1,i+1+len(inner),i+len(inner)) for i in range(len(inner)-1)],BRICK_D)


def chenyuan_windows(fr,eave,width):
    """Six tall openings, including three lower side-hung lights seen open in the photo."""
    lo,hi=eave-3.26,eave-.17
    pitch,ww=width*.144,width*.088
    windows=[]
    for index,angle in enumerate((31,-55,28,0,0,0)):
        u=(index-2.5)*pitch
        loop=rectangle(u,(hi+lo)/2,ww,hi-lo)
        windows.append(loop)
        reveal(fr,loop,.275)
        fr.rect('窄窗后方阴影',u,(lo+hi)/2,-.37,ww,hi-lo,'#313c40')
        for hand in (-1,1):
            fr.block('晨园窄窗砖质侧框',u+hand*(ww/2+.064),(lo+hi)/2,.029,.125,hi-lo+.045,.100,BRICK_N)
            fr.block('窗框立边',u+hand*(ww/2-.030),(lo+hi)/2,-.205,.061,hi-lo,.086,DARK)
        fr.block('窗头突出过梁',u,hi+.064,.055,ww+.30,.126,.15,BRICK_N)
        fr.block('窗台滴水边',u,lo-.036,.030,ww+.22,.090,.19,BRICK_D)
        joints=[lo+.047,lo+1.07,lo+2.37,hi-.045]
        for lower,upper in zip(joints[1:],joints[2:]):
            fr.rect('晨园固定高窗玻璃',u,(lower+upper)/2,-.238,ww-.112,upper-lower,
                    SKY if upper==joints[-1] else GLAZE)
        for yy in joints:
            fr.block('黑色实心窗横框',u,yy,-.181,ww-.055,.064,.093,DARK)
        lower,upper=joints[:2]
        half=(ww-.11)/2
        fr.rect('下亮固定半扇',u+half/2,(lower+upper)/2,-.231,half-.04,upper-lower-.045,GLAZE)
        fr.block('下亮立梃',u,(lower+upper)/2,-.172,.047,upper-lower,.086,DARK)
        span=half-.035
        left,right=u-half+.012,u-.022
        radians=math.radians(abs(angle))
        reach=span*math.sin(radians);flat=span*math.cos(radians)
        if angle < 0:
            pleft,pright=fr.at(right-flat,0,-.15+reach),fr.at(right,0,-.15)
        else:
            pleft,pright=fr.at(left,0,-.15),fr.at(left+flat,0,-.15+reach)
        sash=Facade(fr.s,pright[::2],pleft[::2])
        sash.rect('晨园外开扇玻璃',0,(lower+upper)/2,0,span-.057,upper-lower-.11,SKY if angle else GLAZE)
        for edge in (-1,1):
            sash.block('外开扇立边',edge*(span/2-.018),(lower+upper)/2,.002,.037,upper-lower-.042,.045,DARK)
        for y in (lower+.039,upper-.039):
            sash.block('外开扇上下边',0,y,.002,span,.055,.045,DARK)
    return windows


def chenyuan_arch(fr,u,width,spring,rise):
    """Stepped concentric brick reveals and a deep, unobstructed archway."""
    start=.02
    def contour(add):
        rw=width/2+add
        return [(u+rw,start)]+[(u+rw*math.cos(j*math.pi/28),
                 spring+(rise+add)*math.sin(j*math.pi/28)) for j in range(29)]+[(u-rw,start)]
    profile=[(.31,0),(.28,.031),(.228,.031),(.20,-.044),(.145,-.044),
             (.125,-.103),(.072,-.103),(.045,-.166),(0,-.175),(0,-.82)]
    previous=None
    for k,(radius,depth) in enumerate(profile):
        rim=[fr.at(x,y,depth) for x,y in contour(radius)]
        if previous is not None:
            n=len(rim)
            fr.s.mesh('晨园三重券边' if k<len(profile)-1 else '晨园拱内桶形顶和侧壁',
                      previous+rim,[(i,i+1,i+1+n,i+n) for i in range(n-1)],
                      BRICK_N if k in (1,2,4,6,8) else BRICK_D if k<9 else '#665046')
        previous=rim
    outline=contour(profile[0][0])
    return [(u-width/2-profile[0][0],start)]+outline[:-1]


def chenyuan_portal(frame,backing_holes,width,eave):
    edge=width/2
    fr=Facade(frame.s,frame.at(edge,0,.87)[::2],frame.at(-edge,0,.87)[::2])
    # One clear opening in the main wall sits behind the projecting entrance pavilion.
    backing_holes.append(rectangle(0,(eave-.20-.51)/2,width-.15,eave-.20+.51))
    windows=chenyuan_windows(fr,eave,width)
    arches=[chenyuan_arch(fr,0,4.90,2.87,1.08)]
    arches += [chenyuan_arch(fr,side*4.31,1.43,2.69,.80) for side in (-1,1)]
    fr.cut_wall(windows+arches,eave,BRICK_N)
    for side in (-1,1):
        fr.block('红色山墙的侧面返墙',side*(edge-.08),eave/2,-.425,.16,eave,.85,BRICK_N)
        fr.block('入口转角叠涩',side*(edge-.18),4.42,.023,.36,.27,.18,BRICK_N)
    fr.block('高窗下通长砖枋',0,4.39,.08,width+.09,.26,.25,BRICK_N)
    fr.block('砖枋底侧细滴水',0,4.257,.045,width+.075,.043,.18,BRICK_D)
    # The three exterior arches open into one sheltered lobby with doors set at its rear.
    fr.block('门廊顶板',0,4.35,-2.08,width-.13,.15,4.08,'#53463d')
    fr.block('门廊石质地面',0,.012,-1.96,width-.16,.070,3.91,'#8f8578')
    for side in (-1,1):
        fr.block('门廊内侧墙',side*(edge-.17),2.15,-2.05,.23,4.34,3.94,'#786154')
    rear=Facade(fr.s,fr.at(edge-.15,0,-4.05)[::2],fr.at(-edge+.15,0,-4.05)[::2])
    door_w,door_h=3.12,2.70
    rear.cut_wall([rectangle(0,door_h/2+.05,door_w,door_h)],4.28,'#51473e',base=-.19)
    rear.rect('门框背后暗槽',0,1.40,-.16,door_w+.16,door_h+.14,'#323a38')
    rear.block('内门框顶梁',0,door_h+.036,-.042,door_w+.02,.083,.10,DARK)
    for side in (-1,1):
        rear.block('内门框立边',side*(door_w/2-.024),1.39,-.046,.065,door_h,.09,DARK)
        u=side*door_w/4
        rear.rect('退入门廊的双扇门',u,1.38,-.105,door_w/2-.040,2.64,'#354449')
        for yy in (.28,1.03,2.56):
            rear.block('内部门扇横档',u,yy,-.070,door_w/2-.030,.075,.060,DARK)
        rear.block('内部门扇拉手',side*.10,1.07,-.014,.032,.47,.075,STEEL)
    rear.block('内门中梃',0,1.39,-.069,.066,2.74,.061,DARK)


def gable(frame,width,eave,entrance_y,kind):
    """Projecting curtain wall over the vaulted door, with an actual transverse roof."""
    u=width/2; ridge=eave+(2.3 if kind=='dining' else 2.75)
    if kind=='dining':
        outline=[(-u,eave-.015),(u,eave-.015),(0,ridge)]
        circle=[(2.90+.39*math.cos(q*math.tau/32),eave+.56+.39*math.sin(q*math.tau/32)) for q in range(32)]
        uv=np.array(outline+circle[::-1],np.float64)
        ts=ear.triangulate_float64(uv,np.array([3,len(uv)],np.uint32)).reshape(-1,3)
        frame.s.mesh('晨园山墙圆窗口', [frame.at(x,y,.87) for x,y in uv],ts,BRICK_N)
        back=[frame.at(x,y,.63) for x,y in circle]
        front=[frame.at(x,y,.87) for x,y in circle]
        n=len(circle)
        frame.s.mesh('圆窗砖壁',front+back,[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],BRICK_D)
        frame.pane('圆窗蓝灰玻璃',circle,.625,SKY)
    else:
        frame.block('山墙中段的玻璃幕墙',0,(eave+entrance_y)/2,.26,width,eave-entrance_y,.65,DARK)
        frame.pane('玻璃山尖',[(-u,eave-.01),(u,eave-.01),(0,ridge-.31)],.61,GLAZE)
        frame.rect('中央连续玻璃',0,(eave+entrance_y)/2,.611,width-.62,eave-entrance_y-.18,GLAZE)
        if kind.startswith('north'):
            palette=('#5d7078','#607780','#53636d','#6a7e86')
            span=eave-entrance_y
            courses=max(2,round(span/3.0))
            for j in range(courses):
                for k in range(4):
                    frame.rect('幕墙分格玻璃',(k-1.5)*width*.222,
                               entrance_y+(j+.58)*span/courses,.634,width*.199,span/courses*.64,
                               palette[(j+3*k)%len(palette)])
                frame.rect('楼板深色扎带',0,entrance_y+j*span/courses+.19,.669,width-.36,.48,DARK)
        for i in range(-2,3):
            x=i*width*.148
            head=ridge-.32-abs(x)*2.77/u
            frame.rect('高窗竖梃',x,(head+entrance_y)/2,.69,.12,head-entrance_y,DARK)
        yy=entrance_y+1.75
        while yy<eave-.15:
            frame.rect('幕墙横楣',0,yy,.68,width-.28,.19,DARK);yy+=2.92
        for edge in (-1,1):
            frame.block('中央红砖壁柱',edge*(u+.14),(entrance_y+eave-1.6)/2,.36,
                        .94 if 'north' in kind else .52,eave-1.6-entrance_y,1.04,BRICK_N if 'north' in kind else BRICK_S)
    t=.98 if kind=='dining' else .85
    frame.pane('交叉山墙后端封山',[(u+.29,eave-.07),(-u-.29,eave-.07),(0,ridge+.17)],-4.39,
               BRICK_N if kind.startswith('north') or kind=='dining' else BRICK_S)
    for side in (-1,1):
        pts=[frame.at(side*(u+.29),eave-.07,t+.32),frame.at(0,ridge+.17,t+.32),
             frame.at(0,ridge+.17,-4.4),frame.at(side*(u+.29),eave-.07,-4.4)]
        frame.s.mesh('过街山墙坡瓦',pts,[(0,1,2,3) if side < 0 else (3,2,1,0)],TILE_N if kind!='south' else TILE_S)
        wall_face=.87 if kind=='dining' else .59
        soffit=[frame.at(side*(u+.30),eave-.36,t+.34),frame.at(0,ridge-.12,t+.34),
                frame.at(0,ridge-.12,wall_face),frame.at(side*(u+.30),eave-.36,wall_face)]
        frame.s.mesh('斜檐封底',soffit,[(0,1,2,3) if side>0 else (3,2,1,0)],DARK if kind!='south' else CREAM)
        frame.s.mesh('三角山花檐边',[frame.at(side*(u+.30),eave-.12,t+.34),
            frame.at(0,ridge+.13,t+.34),frame.at(0,ridge-.12,t+.34),
            frame.at(side*(u+.30),eave-.36,t+.34)],[(0,1,2,3) if side > 0 else (3,2,1,0)],DARK if kind!='south' else CREAM)


def dormer(frame,u,eave,north,phoenix=False):
    if phoenix:
        video.phoenix_dormer(frame,u,eave,TILE_S,CREAM,DARK)
        return
    wide=1.56 if north else 2.08
    t=-1.15; low=eave+.53
    if north:
        window=[(u-wide/2,low),(u+wide/2,low),(u,low+.81)]
    else:
        window=arch_loop(u,low,wide,low+.11,.64)
    frame.pane('屋顶老虎窗外框',window,t,CREAM)
    inner=[(u+(x-u)*.72,low+(y-low)*.72+.015) for x,y in window]
    frame.pane('老虎窗暗玻璃',inner,t+.032,DARK)
    if north:
        for side in (-1,1):
            ps=[frame.at(u+side*wide*.56,low-.025,t+.15),frame.at(u,low+.91,t+.15),
                frame.at(u,low+.91,t-1.22),frame.at(u+side*wide*.56,low-.025,t-1.6)]
            frame.s.mesh('小山花红瓦',ps,[(0,1,2,3) if side < 0 else (3,2,1,0)],TILE_N)
    else:
        arc=window[2:]
        v=[frame.at(x,y,t) for x,y in arc]+[frame.at(x,y+.09,t-1.56) for x,y in arc]
        l=len(arc)
        frame.s.mesh('半圆形老虎窗雨罩',v,[(i+l,i+1+l,i+1,i) for i in range(l-1)],CREAM)


def modules_for_wall(fr,kind,levels,h,tip_side=0,owner=None):
    length=fr.length
    north=kind.startswith('north')
    islink=kind=='arcade'
    meal=kind=='dining'
    end=kind=='south_end'
    # The east-facing enclosed residential court, and both faces of the street block,
    # have glazed gables. The short end walls instead have one very tall recessed arch.
    central=(kind in ('south','north_u') and abs(fr.nx)>.92 and length>36)
    central|=(kind=='north_bar' and abs(fr.nx)>.92 and length>38)
    central|=meal and fr.nx>.86 and length>35
    central|=end and length>62
    blind_end=(kind in ('north_u','south') and abs(fr.nx)>.91 and 15<length<28)
    holes=[]
    if length<2.4:
        fr.cut_wall([],h,BRICK_N if (north or meal) else BRICK_S)
        return
    crownline=h-(2.65 if not islink else 1.02)
    if islink:
        # Both long sides are open between the structural brick piers.
        if length>15:
            count=max(2,round(length/5.3));pitch=(length-.8)/count
            for i in range(count):
                arcade(fr,holes,(i-(count-1)/2)*pitch,pitch*.81,4.65,True)
        else:
            arcade(fr,holes,0,min(6.4,length*.65),4.65,True)
        fr.cut_wall(holes,h,BRICK_S)
        fr.block('廊檐',0,h-.07,.13,length+.18,.25,.34,CREAM)
        return
    if blind_end:
        margin=max(1.1,length*.11)
        opwidth=length*.44
        arcade(fr,holes,0,opwidth, h-3.8)
        for side in (-1,1):
            ct=side*(length/2-margin*1.1)
            opening(fr,holes,ct,(h-3.78)/2+1.20,min(1.05,margin*.51),h-7.1,2,kind)
        if kind=='south':
            video.phoenix_projection(fr,opwidth,h,BRICK_S,CREAM,owner)
        fr.cut_wall(holes,h,BRICK_N if north else BRICK_S)
        fr.block('端楼两级檐',0,h-.20,.12,length+.16,.33,.34,DARK if north else CREAM)
        return
    opening_width=9.2 if meal else (8.0 if north else 8.5)
    if central and meal:
        chenyuan_portal(fr,holes,opening_width+2.65,h)
        gable(fr,opening_width+2.65,h,4.37,kind)
    elif central:
        arch_top=5.75 if kind=='north_u' else 3.89
        arcade(fr,holes,0,opening_width*.78,arch_top,depth=1.85 if north else .82)
        if kind=='north_u':
            fr.block('入口钢框雨棚',0,2.86,.50,opening_width*.95,.22,2.20,DARK)
            for sign in (-1,1):
                fr.block('入口通廊支柱',sign*opening_width*.43,1.40,1.32,.16,2.80,.16,STEEL)
        gable(fr,opening_width,h,arch_top+.22,kind)
    if central:
        reserve=opening_width/2+(1.75 if meal else .69)
        segments=[(-length/2+.55,-reserve),(reserve,length/2-.55)]
    else:
        segments=[(-length/2+.55,length/2-.55)]
    if tip_side:
        margin=video.phoenix_slots(fr,holes,tip_side,crownline,h,opening,kind)
        segments=[(max(a,-length/2+margin) if tip_side<0 else a,
                   min(b,length/2-margin) if tip_side>0 else b) for a,b in segments]
    # The lower 2-storey order is prominent on the taller northern residence.
    arcade_top=5.9 if kind=='north_u' else (3.56 if meal else 3.38)
    brick=BRICK_N if north or meal else BRICK_S
    for start,stop in segments:
        run=stop-start
        if run<1.65:continue
        count=max(1,round(run/(4.0 if meal else 3.72 if kind=='south' else 3.40)))
        pitch=run/count
        arcade_count=max(1,round(run/(6.1 if meal else 6.35)))
        apitch=run/arcade_count
        for i in range(arcade_count):
            u=start+(i+.5)*apitch
            arcade(fr,holes,u,min(apitch*.75,5.35),arcade_top)
        if meal:
            for i in range(count):
                u=start+(i+.5)*pitch
                opening(fr,holes,u,5.36,min(2.1,pitch*.57),2.6,1,kind)
            continue
        rows=4 if kind=='north_u' else max(1,levels-2)
        lo=arcade_top+.39;hi=crownline-.48
        for j in range(rows):
            cy=lo+(j+.5)*(hi-lo)/rows
            wh=(hi-lo)/rows*.74
            for i in range(count):
                u=start+(i+.5)*pitch;ww=pitch*.69
                opening(fr,holes,u,cy,ww,wh,j,kind)
        for i in range(count):
            u=start+(i+.5)*pitch
            opening(fr,holes,u,h-1.43,pitch*.70,1.52,0,kind)
        for i in range(2,count,4):
            u=start+i*pitch
            fr.block('窗列间立面竖肋',u,(arcade_top+crownline)/2,.086,.28,
                     crownline-arcade_top,.22,brick)
        if run>13:
            nd=max(1,round(run/(17.8 if kind=='south' else 11.5 if north else 13.2)))
            for i in range(nd):
                dormer(fr,start+(i+.5)*run/nd,h,north,kind=='south')
    fr.cut_wall(holes,h,brick)
    if north:
        attic=[loop for loop in holes if min(y for _,y in loop)>crownline]
        fr.cut_wall(attic,h,'#53585b',base=crownline,offset=.018)
    fr.block('檐口金属收边',0,h-.09,.12,length+.12,.20,.36,DARK if north or meal else CREAM)
    if not meal:
        # The top storey on north campus is a continuous charcoal band.
        for start,stop in segments:
            if stop-start<=.8:continue
            for yy in (crownline+.02,h-.45):
                fr.block('连贯檐带',.5*(start+stop),yy,.11,stop-start,.25,.34,DARK if north else CREAM)


def roof(shape,poly,h,kind,owner=None):
    import qd_residence_roofs as roofs
    if kind=='arcade':
        rim=poly.buffer(.24,join_style=2)
        roofs.eave(shape,poly,rim,h,h+.12,CREAM)
        # The 2025 axis photo distinguishes an open, flat axis-side gallery
        # and a narrow, raised tiled bay behind the gallery.
        x0,z0,x1,z1=poly.bounds
        west=owner in ('way/970257682','way/970257684')
        split=x0+(x1-x0)*(.60 if west else .40)
        mask=box(x0-1,z0-1,split,z1+1) if west else box(split,z0-1,x1+1,z1+1)
        back=poly.intersection(mask)
        roofs.terrace(shape,rim.difference(back),h+.12,COURT,BRICK_S,abuts=back)
        roofs.walls(shape,'连廊后跨屋座',back,h-.04,h+1.38,BRICK_S)
        roofs.full_hip(shape,back,h+1.38,TILE_S,CREAM)
        return
    if kind=='south':
        body,tip=roofs.phoenix_tips(poly)
        roofs.full_hip(shape,body,h,TILE_S,CREAM)
        roofs.terrace(shape,tip,h+.005,COURT,BRICK_S,abuts=body)
        # The pitch carries the collectors directly above the long window elevations.
        for p in polygons(body):
            roof_edge=p.buffer(.42,join_style=2).boundary
            coords=list(orient(p,1).exterior.coords)
            for a,b in zip(coords,coords[1:]):
                fr=Facade(shape,a,b)
                if fr.length<53 or fr.nz<.80:continue
                for side in (-1,1):
                    span=fr.length*.34;centre=side*fr.length*.245
                    count=max(2,round(span/2.45))
                    for i in range(count):
                        u=centre+(i-(count-1)/2)*(span/count)
                        half=(span/count-.09)/2
                        pts=[]
                        for du,d in [(-half,.64),(half,.64),(half,1.68),(-half,1.68)]:
                            x,_,z=fr.at(u+du,0,-d)
                            y=h+.075+.355*roof_edge.distance(Point(x,z))+.054
                            pts.append((x,y,z))
                        shape.mesh('南区坡屋面集热板',pts,[(0,1,2,3)],PV)
        return
    if kind=='south_end':
        roofs.full_hip(shape,poly,h,TILE_S,CREAM)
        return
    meal=kind=='dining'
    wells=roofs.pitched_deck(shape,poly,h,4.60 if meal else 3.65,2.45 if meal else 2.10,
                             TILE_N,COURT,DARK,1.75 if meal else 1.70)
    for inner,deck,crest in wells:
        arrays(shape,inner,deck,crest,kind)


def arrays(shape,inner,deck,crest,kind):
    """Alternating collectors and service lanes, steel supports anchored on the roof."""
    safe=inner.buffer(-.42,join_style=2)
    for p in polygons(safe):
        x0,z0,x1,z1=p.bounds
        for j,z in enumerate(np.arange(z0+1.15,z1-1.0,2.43)):
            for i,x in enumerate(np.arange(x0+1.84,x1-1.65,3.79)):
                if not p.covers(box(x-1.80,z-1.08,x+1.80,z+1.08)):continue
                if kind=='dining':
                    if z<(z0+z1)/2+1 or i%5==4:continue
                elif (j%7==4 if (z1-z0)>(x1-x0) else i%6==3):continue
                top=crest+.04 if kind!='dining' else deck+.76
                bottom=top-.32
                for dz,plate in ((-.78,top-.04),(.78,bottom+.04)):
                    height=plate-deck
                    shape.box('屋顶集热架落地钢柱',x,deck+height/2,z+dz,.105,height,.105,STEEL)
                    shape.box('集热架钢横担',x,plate-.028,z+dz,3.38,.056,.086,STEEL)
                pts=[(x-1.79,top,z-1.04),(x-1.79,bottom,z+1.04),
                     (x+1.79,bottom,z+1.04),(x+1.79,top,z-1.04)]
                shape.mesh('屋顶集热或光伏组件',pts,[(0,1,2,3)],PV)
                shape.mesh('集热板背面',[(xx,yy-.044,zz) for xx,yy,zz in pts],[(3,2,1,0)],'#79868a')
                for k in range(4):
                    l=(k+1)%4
                    a,b=pts[k],pts[l]
                    shape.mesh('集热板金属包边',[a,b,(b[0],b[1]-.044,b[2]),(a[0],a[1]-.044,a[2])],
                               [(0,3,2,1)],'#859394')
                mid=[(x-.048,top+.008,z-1.04),(x-.048,bottom+.008,z+1.04),
                     (x+.048,bottom+.008,z+1.04),(x+.048,top+.008,z-1.04)]
                shape.mesh('组件分隔框',mid,[(0,1,2,3)],'#a3acaa')
        if kind=='dining':
            for i in range(4):
                x=(x0+x1)/2+(i%2-.5)*6.6;z=(z0+z1)/2-7.0-(i//2)*3.9
                if p.covers(box(x-2.2,z-1.2,x+2.2,z+1.2)):
                    shape.box('晨园屋顶设备',x,deck+.61,z,4.4,1.22,2.4,'#a5a69e')
                    for j in (-1,1):
                        shape.cyl('圆形风机罩',x+j*1.06,deck+1.32,z,.58,.20,'#697678',14)


def hall_label(shape,frame,h):
    from qd_signage import plaque
    carrier='晨园东侧主门红色山墙'
    fr=frame
    for id_,word,u,y,w,hh in [('zh','晨园',-.84,h+.60,2.40,.78),
                              ('en1','DINING',1.36,h+.78,1.34,.27),('en2','HALL',1.36,h+.37,1.05,.27)]:
        plaque(shape,'s2-b6','chenyuan-'+id_,word,*fr.at(u,y,.928),w,hh,fr.yaw,
               source=SOURCE_MORNING,year=2022,carrier=carrier,colour='#dfded7',
               note='校方2022开学照片可辨；结合承建方航拍，面向东侧通行道路。')


def yuehai_one_end(fr,h):
    """Photographed east end of B1's north arm, opposite the north end of B2."""
    from qd_signage import plaque
    from qd_architecture import letters
    cap=h-2.65
    span=fr.length*.51
    outer=arch_loop(0,-.04,span,cap-7.05,2.03)
    fr.cut_wall([outer],cap,BRICK_N)
    reveal(fr,outer,1.24,True)
    fr.pane('高拱内退玻璃',outer,-1.23,GLAZE)
    for u in (-span*.29,0,span*.29):
        fr.rect('落地玻璃竖框',u,7.23,-1.19,.16,14.32,DARK)
    # The dark projecting secondary portal sits within the red wall's taller arch.
    edge=span*.445
    portal=Facade(fr.s,fr.at(edge,0,.22)[::2],fr.at(-edge,0,.22)[::2])
    lower=arch_loop(0,.04,span*.49,5.48,1.64)
    portal.cut_wall([lower],9.20,'#48535a')
    reveal(portal,lower,1.12,True)
    portal.pane('嵌入底部门厅的玻璃',lower,-1.11,'#3d5058')
    portal.block('内拱帽檐',0,9.22,-.32,portal.length+.16,.26,.95,'#626c70')
    fr.rect('从拱顶通往金属檐的竖缝',0,(cap+15.82)/2,.018,.31,cap-15.82,DARK)
    fr.block('东端连续深色顶层',0,(h+cap)/2,.045,fr.length+.12,h-cap,.25,'#4f565b')
    for yy in (cap+.10,h-.33):
        fr.block('金属压顶折边',0,yy,.17,fr.length+.30,.20,.34,DARK)
    for u in (-fr.length*.36,fr.length*.36):
        for yy in (3.32,6.65,10.02,13.35,16.70):
            fr.rect('红色外墙侧部板缝',u,yy,.015,fr.length*.24,.027,'#a36753')
    word_u=fr.length*.303
    carrier='阅海居1号楼北翼东端高拱外侧红墙，靠北角、深色顶层以下'
    note='2025校区街拍读字；2022中建五局从东侧的航拍可在同一北翼端墙上读到圈号①，另一翼同位无字。'
    for label,word,u,y,w,hh in [('zh','阅海居①',word_u,cap-1.58,5.90,1.38),
                                ('en','YUEHAI HALL',word_u-.66,cap-2.73,4.50,.53)]:
        mesh=plaque(fr.s,'s2-b1','yuehai-one-'+label,word,*fr.at(u,y,.021),w,hh,fr.yaw,
                      source='https://www.qdxq.sdu.edu.cn/info/1831/60590.htm',year=2025,
                      carrier=carrier,colour='#ece8dc',note=note)
        # The letter returns join the bright raised face directly to the rendered wall.
        outlines=letters(word)
        l,b,r,t=outlines.bounds
        sc=min(w/(r-l),hh/(t-b))
        for poly in polygons(outlines):
            poly=orient(poly,1)
            for contour in (poly.exterior,*poly.interiors):
                xy=[(u+(x-(l+r)/2)*sc,y+(v-(b+t)/2)*sc) for x,v in list(contour.coords)[:-1]]
                n=len(xy)
                points=[fr.at(x,v,depth) for depth in (.033,.000) for x,v in xy]
                sides=[((i+1)%n,i,i+n,(i+1)%n+n) for i in range(n)]
                mesh.mesh('立体墙字侧壁',points,sides,'#a9a597')


def shell(shape,poly,kind,levels,h,owner=None):
    for p in polygons(poly):
        plan=orient(p,1)
        for ring in (plan.exterior,*plan.interiors):
            points=list(ring.coords)
            for a,b in zip(points,points[1:]):
                if math.dist(a,b)<.15:continue
                fr=Facade(shape,a,b)
                if owner=='s2/b1' and fr.nx>.99 and fr.z<0 and 18<fr.length<24:
                    yuehai_one_end(fr,h)
                else:
                    tip_side=0
                    if kind=='south' and abs(fr.nz)>.91 and fr.length>48:
                        # The two open wing heads are east on the western row and mirrored across the garden.
                        xmin,_,xmax,_=plan.bounds
                        tip=xmax if plan.centroid.x<(xmin+xmax)/2 else xmin
                        for side in (-1,1):
                            if abs(fr.at(side*fr.length/2,0,0)[0]-tip)<1.1:tip_side=side
                    modules_for_wall(fr,kind,levels,h,tip_side,owner)
                if kind=='dining' and fr.nx>.86 and fr.length>35:
                    hall_label(shape,fr,h)
    roof(shape,poly,h,kind,owner)


def south_annex(shape,poly):
    # The cadastral outline includes the lower green terrace behind the street wing.
    ring=list(orient(poly,1).exterior.coords)
    longest=max(zip(ring,ring[1:]),key=lambda pair:math.dist(*pair))
    bar=poly.intersection(LineString(longest).buffer(16.4,cap_style=3))
    other=poly.intersection(box(poly.bounds[2]-10,poly.bounds[1]-1,poly.bounds[2]+1,poly.bounds[3]+1))
    podium=poly.difference(unary_union([bar,other]))
    for p in polygons(podium):
        from qd_residence_roofs import surface
        green=p.buffer(-1.5,join_style=2)
        surface(shape,'裙房露台铺面',p.difference(green),3.22,'#bcbaa5')
        surface(shape,'裙房屋顶绿化',green,3.22,'#83916e')
        coords=list(orient(p,1).exterior.coords)
        for a,b in zip(coords,coords[1:]):
            if math.dist(a,b)<.18:continue
            Facade(shape,a,b).cut_wall([],3.22,BRICK_S)
    for p in polygons(other.difference(bar)):
        shell(shape,p,'south_end',4,12.95)
    for p in polygons(bar):
        shell(shape,p,'south_end',5,16.75)
    return 19.55


def build_if_known(row,poly):
    id_=row.get('id','')
    if id_ in PHOENIX:kind,levels,h='south',6,19.55
    elif id_ in ARCADES:kind,levels,h='arcade',2,5.85
    elif id_ in NORTH_U:kind,levels,h='north_u',7,23.50
    elif id_ in NORTH_BAR:kind,levels,h='north_bar',4,14.70
    elif id_==MORNING:kind,levels,h='dining',2,7.85
    elif id_==SOUTH_END:
        shape=Shape(row['name'])
        south_annex(shape,poly)
        from qd_residence_roofs import exact_top
        return shape,exact_top(shape)
    else:return None
    shape=Shape(row['name'] or '凤凰居连廊')
    shell(shape,poly,kind,levels,h,id_)
    if kind=='arcade':
        from qd_phoenix_arcades import add_returns
        add_returns(shape,row,h)
    from qd_residence_roofs import exact_top
    return shape,exact_top(shape)

