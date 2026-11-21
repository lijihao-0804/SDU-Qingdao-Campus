"""Entrance details in the four gates' local metre frames. See data/civic_sources.json."""
import json
import math
from functools import lru_cache
from pathlib import Path

import mapbox_earcut as ear
import numpy as np
from shapely.geometry import LineString


@lru_cache(maxsize=1)
def outlines():
    path = Path(__file__).resolve().parents[1] / 'data/校门标准书法轮廓.json'
    return json.loads(path.read_text('utf8'))['shapes']


class Frame:
    def __init__(self, scene, x=0., z=0., yaw=0.):
        self.scene, self.x, self.z, self.yaw = scene, x, z, yaw
        self.c, self.s = math.cos(yaw), math.sin(yaw)

    def pt(self, x, y, z):
        return self.x + self.c*x + self.s*z, y, self.z - self.s*x + self.c*z

    def box(self, name, x, y, z, w, h, d, mat):
        self.scene.box(name, *self.pt(x,y,z), w,h,d,mat,self.yaw)

    def mesh(self, name, verts, faces, mat):
        self.scene.mesh(name, [self.pt(*v) for v in verts], faces, mat)


def raised(frame, mark, name, x, y, front, width, height, depth, color):
    """Triangulate each filled outline with its holes and give the perimeter an edge."""
    for polygon in outlines()[mark]:
        points = [(x+(u-.5)*width,y+(v-.5)*height) for ring in polygon for u,v in ring]
        ends = np.cumsum([len(ring) for ring in polygon], dtype=np.uint32)
        triangles = ear.triangulate_float64(np.asarray(points), ends).reshape(-1,3)
        count = len(points)
        vertices = [(a,b,front) for a,b in points]+[(a,b,front-depth) for a,b in points]
        faces = [tuple(f) for f in triangles]
        faces.extend(tuple((count+i) for i in reversed(f)) for f in triangles)
        start = 0
        for ring,end in zip(polygon,ends.tolist()):
            # Normalize exterior/hole wall winding regardless of the source SVG winding.
            area = sum(ring[i-1][0]*p[1]-p[0]*ring[i-1][1] for i,p in enumerate(ring))
            reverse = (area < 0) == (start == 0)
            for a in range(start,end):
                b = start if a+1 == end else a+1
                quad = (a,a+count,b+count,b)
                faces.append(tuple(reversed(quad)) if reverse else quad)
            start = end
        frame.mesh(name,vertices,faces,color)


def nameplate(f, gate, x, y, z, width, height, ink):
    back = '#f4f2ea'
    f.box(gate+'·校名牌侧边',x,y,z-.048,width+.036,height+.036,.095,'#a5a195')
    f.box(gate+'·白釉校名牌',x,y,z-.022,width,height,.046,back)
    # The four independently bounded glyphs keep the unbalanced brushwork,
    # vertical spacing and alignment seen in the photo of the west gate pier.
    boxes = [(10,5,49,45),(16,54,45,106),(8,126,45,166),(10,177,47,233)]
    for letter,(l,t,r,b) in zip('山东大学',boxes):
        cx=x+((l+r)/114.-.5)*width*.85
        cy=y+(.5-(t+b)/484.)*height*.96
        raised(f,letter,gate+'·校名·'+letter,cx,cy,z+.019,
               (r-l)/57.*width*.85,(b-t)/242.*height*.96,.0185,ink)


def badge(f, gate, cx, cy, front, diameter, ink):
    # A pale circular carrier and a thin painted outline, both visible on the photographs.
    n=96;r=diameter/2+.025
    v=[(cx+r*math.cos(math.tau*i/n),cy+r*math.sin(math.tau*i/n),z)
       for z in (front-.067,front) for i in range(n)]
    faces=[tuple(range(n,2*n)),tuple(reversed(range(n)))]
    faces.extend((i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n))
    f.mesh(gate+'·圆徽底盘',v,faces,'#eae5d9')
    raised(f,'校徽',gate+'·圆徽环字山海与1901',cx,cy,front+.015,diameter,diameter,.0145,ink)


def west_sign(scene, x):
    f=Frame(scene,x)
    nameplate(f,'西门',0,11.30,4.125,1.81,6.82,'#192027')
    badge(f,'西门',0,15.72,4.12,1.69,'#8b2232')


def rounded_stack(f,name,w,d,chamfer,lo,hi,mat):
    a,b=w/2,d/2;c=chamfer
    rim=[(-a+c,-b),(a-c,-b),(a,-b+c),(a,b-c),(a-c,b),(-a+c,b),(-a,b-c),(-a,-b+c)]
    vs=[(x,y,z) for y in (lo,hi) for x,z in rim]
    faces=[(i,8+i,8+(i+1)%8,(i+1)%8) for i in range(8)]
    faces.extend([tuple(reversed(range(8,16))),tuple(range(8))])
    f.mesh(name,vs,faces,mat)


def round_arch(f,name,x,y,z,width,height,mat):
    r=width/2;spring=y+height-r
    rim=[(x-r,y,z),(x+r,y,z)]
    rim.extend((x+r*math.cos(math.pi*k/24),spring+r*math.sin(math.pi*k/24),z) for k in range(25))
    f.mesh(name,rim,[tuple(range(len(rim)))],mat)


def south_tower(scene):
    f=Frame(scene,-14.3,-2.5,-math.radians(17))
    body,trim,cut='#d0c4ad','#e3d9c5','#b6aa97'
    rounded_stack(f,'南门·宽石座',5.7,4.93,.30,-.03,.43,trim)
    rounded_stack(f,'南门·石座块缝底',5.40,4.68,.24,.42,5.40,cut)
    for layer in range(5):
        lo=.45+layer*.98
        rounded_stack(f,'南门·横砌石座',5.43,4.71,.26,lo,lo+.955,body)
    for yaw in [0.,math.pi/2]:
        j=Frame(scene,f.x,f.z,f.yaw+yaw)
        z=2.365 if yaw==0. else 2.725
        round_arch(j,'南门·拱券石套',0,.64,z+.018,1.26,3.42,trim)
        round_arch(j,'南门·拱券暗框',0,.67,z+.034,1.02,3.18,'#393c39')
        round_arch(j,'南门·高拱玻璃',0,.74,z+.042,.82,2.97,'#536674')
        j.box('南门·拱窗横档',0,2.38,z+.058,.80,.045,.032,'#39484a')
    rounded_stack(f,'南门·塔座上缘',5.50,4.77,.30,5.34,5.49,trim)
    rounded_stack(f,'南门·方塔石芯',4.30,3.89,.18,5.46,12.67,cut)
    for tier in range(7):
        lo=5.47+tier*1.00
        rounded_stack(f,'南门·平砌腰身',4.32,3.92,.19,lo,lo+.978,body)
    for hand in (-1,1):
        for side in (-1,1):
            f.box('南门·塔身转角扶壁',hand*1.84,8.98,side*1.66,.44,6.89,.62,trim)
        f.box('南门·额部纵槽底板',hand*1.10,10.49,2.005,.94,.70,.11,cut)
        for i in range(5):
            f.box('南门·额部短石肋',hand*1.10+(i-2)*.168,10.50,2.06,.11,.66,.080,trim)
    f.box('南门·白牌石背板',0,7.55,1.983,1.22,3.71,.088,trim)
    nameplate(f,'南门',0,7.54,2.035,.99,3.47,'#20282c')
    badge(f,'南门',0,10.50,2.052,.86,'#543e36')
    for y,w,d,h in [(12.42,4.55,4.08,.28),(12.66,4.68,4.16,.18),(12.84,4.26,3.90,.20)]:
        rounded_stack(f,'南门·檐口石层',w,d,.18,y-h/2,y+h/2,trim)
    roof=[(-2.20,12.94,-2.00),(2.20,12.94,-2.00),(2.20,12.94,2.00),(-2.20,12.94,2.00),(-.72,13.40,0),(.72,13.40,0)]
    f.mesh('南门·红瓦歇坡塔帽',roof,[(1,0,4,5),(2,1,5),(3,2,5,4),(0,3,4)],'#a26b55')


def north_tower(scene,x,layers):
    """Tapered running-bond granite and vertically slatted bay on the outer elevation."""
    def radius(y):
        return float(np.interp(y,[a for a,b in layers],[b for a,b in layers]))
    # Project the arch and muntins onto the actual taper. A flat decal at a single
    # radius sinks inside the shaft near the sill, hiding most of the opening.
    for azimuth in (-.72,0.,.72):
        def on_wall(u,y,offset):
            r=radius(y);angle=azimuth+u/r
            return x+(r+offset)*math.sin(angle),y,(r+offset)*math.cos(angle)
        def arch_face(name,y,width,height,offset,mat):
            r=width/2; spring=y+height-r
            perimeter=[(-r,y),(r,y)]
            perimeter += [(r*math.cos(math.pi*k/20),spring+r*math.sin(math.pi*k/20)) for k in range(21)]
            verts=[on_wall(0.,spring,offset)]+[on_wall(u,b,offset) for u,b in perimeter]
            faces=[(0,i+1,1+(i+1)%len(perimeter)) for i in range(len(perimeter))]
            scene.mesh(name,verts,faces,mat)
        arch_face('北门·基座拱券石套',.51,1.09,2.97,.091,'#d6cbb6')
        arch_face('北门·拱窗深框',.57,.85,2.77,.113,'#3c403d')
        arch_face('北门·深色拱窗玻璃',.63,.67,2.59,.140,'#46565a')
        for u0,u1,lo,hi in [(-.026,.026,.66,2.90),(-.32,.32,2.70,2.75)]:
            verts=[on_wall(u,y,.158) for u,y in ((u0,lo),(u1,lo),(u1,hi),(u0,hi))]
            scene.mesh('北门·拱窗分格',verts,[(0,1,2,3)],'#767771')
    # The radial shell is preserved behind a shallow, independently laid stone skin.
    for j in range(17):
        y0=5.14+j*.44;y1=y0+.412
        n=26
        for i in range(n):
            a=math.tau*(i+.5*(j%2))/n;b=a+math.tau/n
            def pt(t,y):
                r=radius(y)+.024
                return x+r*math.sin(t),y,r*math.cos(t)
            vs=[pt(a+.003,y0),pt(b-.003,y0),pt(b-.003,y1),pt(a+.003,y1)]
            scene.mesh('北门·错缝灰花岗石外皮',vs,[(0,1,2,3)],('#c4bdad','#c9c2b4','#c6bdae','#c0baad')[(j*3+i)%4])
    # Outer face slopes in with the tower. Slats attach to the backing plane along its full height.
    base,top=5.32,12.55
    def rect(name,left,right,lo,hi,offset,colour):
        p=[(x+u,y,radius(y)+offset) for u,y in ((left,lo),(right,lo),(right,hi),(left,hi))]
        scene.mesh(name,p,[(0,1,2,3)],colour)
    rect('北门·格栅暗槽',-.535,.535,base,top,.055,'#45342d')
    for i in range(7):
        c=(i-3)*.137
        rect('北门·棕色竖向格栅',c-.039,c+.039,base+.085,top-.085,.104,'#8a6552')
        rect('北门·木纹格栅明边',c-.039,c-.022,base+.085,top-.085,.106,'#ab8870')
    for side in (-1,1):
        c=.552*side
        rect('北门·窄槽框',c-.035,c+.035,base-.045,top+.04,.088,'#aa967c')
    for y in (base-.02,top+.015):
        rect('北门·格栅压边',-.575,.575,y-.057,y+.057,.11,'#af9f88')
    # The completion photograph resolves a subdued round impression over the slot.
    # Keep the tiny markings undeciphered instead of stamping a legible school seal.
    rect('北门·圆印底石',-.54,.54,12.65,13.75,.19,'#c9bfb0')
    cy=13.24; outer=.34;inner=.295
    for i in range(64):
        a,b=math.tau*i/64,math.tau*(i+1)/64
        ring=[(x+r*math.cos(theta),cy+r*math.sin(theta),radius(cy+r*math.sin(theta))+.197)
              for r,theta in ((inner,a),(outer,a),(outer,b),(inner,b))]
        scene.mesh('北门·淡棕圆印外缘',ring,[(0,1,2,3)],'#a49280')



def east_gate_arches(frame, label, face_z, centers, sill, width, height):
    for u in centers:
        round_arch(frame,label+'·浅石券边',u,sill,face_z+.045,width+.32,height+.16,'#d8d2c2')
        round_arch(frame,label+'·拱洞暗缘',u,sill+.04,face_z+.063,width,height,'#444c49')
        round_arch(frame,label+'·拱窗',u,sill+.11,face_z+.083,width-.15,height-.17,'#51616a')
        frame.box(label+'·石窗台',u,sill,face_z+.08,width+.34,.13,.22,'#c5bfae')


def east_gate_tower(scene, height):
    # From the library (west), the tall north pier stands left of the axial hedge.
    # The short roof, blank vertical stone field and three arches are visible in photo 3.
    from qd_civic import hip
    x,z=-2.75,-24.48
    f=Frame(scene,x,z,-math.pi/2)
    stone, trim='#c9c5b7','#ddd8c9'
    rounded_stack(f,'东门北塔·浅石基座',10.06,9.36,.28,-.18,.42,trim)
    rounded_stack(f,'东门北塔·三联拱基身',9.66,9.00,.28,.40,4.52,stone)
    for y,w,d,h in [(4.32,9.86,9.20,.21),(4.59,9.98,9.32,.27),(4.86,9.12,8.61,.30)]:
        rounded_stack(f,'东门北塔·分层台缘',w,d,.27,y-h/2,y+h/2,trim)
    rounded_stack(f,'东门北塔·长方形塔身',7.73,7.36,.21,4.99,height-1.38,stone)
    for u in (-3.44,3.44):
        for v in (-3.34,3.34):
            f.box('东门北塔·通高石角柱',u,9.94,v,.52,9.83,.76,trim)
    for hand in (-1,1):
        front=hand*3.681
        for side in (-1,1):
            f.box('东门北塔·中央竖石带',side*1.72,10.0,front,.28,9.86,.24,trim)
            f.box('东门北塔·竖带阴缝',side*1.53,9.96,front+hand*.018,.050,9.79,.039,'#a9a492')
        f.box('东门北塔·额部横带',0,height-2.42,front,7.51,.26,.28,trim)
    for y,w,d,h in [(height-1.46,8.03,7.68,.22),(height-1.24,8.20,7.84,.23)]:
        rounded_stack(f,'东门北塔·上檐',w,d,.21,y-h/2,y+h/2,trim)
    east_gate_arches(f,'东门北塔校内侧',4.50,(-2.23,0.,2.23),.52,1.13,2.57)
    road_frame=Frame(scene,x,z)
    east_gate_arches(road_frame,'东门北塔通道侧',4.83,(-1.4,1.4),.52,1.04,2.52)
    hip(scene,'东门北塔·灰色坡顶',x,z,7.72,8.18,height-1.12,1.12,1.55,'#807f7e')


def east_gate_pavilion(scene):
    # The low south pavilion ends in a broad cornice, sharing its entrance level
    # with the colonnade. These short walls do not continue into a tower shaft.
    from qd_civic import hip
    x,z=-3.1,20.70
    f=Frame(scene,x,z,-math.pi/2)
    stone,trim='#c9c5b7','#ddd8c9'
    rounded_stack(f,'东门南亭·方石基座',9.73,9.10,.18,-.18,.40,trim)
    rounded_stack(f,'东门南亭·浅石围护',9.24,8.61,.19,.39,5.67,stone)
    for face in (-1,1):
        for u in (-4.21,4.21):
            f.box('东门南亭·角部壁柱',u,3.11,face*4.18,.53,5.37,.44,trim)
    east_gate_arches(f,'东门南亭校内侧',4.305,(-2.30,0.,2.30),.52,1.35,2.73)
    to_lane=Frame(scene,x,z,math.pi)
    east_gate_arches(to_lane,'东门南亭通道侧',4.62,(-1.6,1.6),.52,1.12,2.62)
    for y,w,d,h in [(3.72,9.30,8.70,.17),(5.57,9.51,8.90,.26),(5.89,9.73,9.12,.31),(6.12,9.49,8.90,.15)]:
        rounded_stack(f,'东门南亭·环形石檐',w,d,.16,y-h/2,y+h/2,trim)
    hip(scene,'东门南亭·矮四坡灰顶',x,z,9.05,9.68,6.18,1.32,3.02,'#807f7e')


def east_details(scene,center,roof_top):
    from qd_residence_roofs import surface,walls
    bank=LineString([(-7.,.05),(18.8,.05)]).buffer(2.45,quad_segs=12)
    surface(scene,'东门·中分绿岛缘顶',bank,.265,'#c2bcaa')
    walls(scene,'东门·中分绿岛石边',bank,.08,.265,'#aaa896')
    turf=bank.buffer(-.21)
    surface(scene,'东门·轴线中分草坪',turf,.277,'#7d9163')
    hedge=bank.buffer(-.36)
    walls(scene,'东门·修剪绿岛侧缘',hedge,.275,.58,'#70864c')
    surface(scene,'东门·修剪绿岛冠面',hedge,.58,'#8b9c60')
    line=LineString(center)
    inset=line.buffer(1.64,cap_style=2,join_style=2)
    surface(scene,'东门·弧廊顶嵌面',inset,roof_top+.035,'#917768')
    for j,(x,z) in enumerate(center[1:],1):
        dx,dz=x-center[j-1][0],z-center[j-1][1]
        angle=math.atan2(dx,dz)
        scene.box('东门·弧廊顶石分带',x,roof_top+.04,z,3.78,.105,.19,'#c9c1b0',angle)
    x,z=center[-1]
    yaw=math.atan2(x-center[-2][0],z-center[-2][1])
    scene.box('东门·弧廊端部石基',x,.24,z,4.62,.46,2.40,'#bcb8a8',yaw)


def south_approach(x,z):
    """Gate approach aligned to the two real road junctions in the bundled map."""
    from shapely.affinity import rotate,translate
    from shapely.geometry import Polygon,box
    from shapely.ops import unary_union
    # Station centres use the campus road centreline. The jaw opens out into
    # Shanda South Road and reduces to the mapped width north of the junction.
    stations=[(-11.4,23.5,13.2),(-8.6,18.32,11.85),(-5.5,11.51,9.15),
              (0.,0.,7.85),(4.86,-10.46,7.42),(7.79,-16.78,6.78),
              (8.32,-29.35,5.70),(8.95,-43.1,3.95),(9.40,-53.3,2.65)]
    sides=[[],[]]
    for j,(cx,cz,half) in enumerate(stations):
        a,b=stations[max(0,j-1)],stations[min(len(stations)-1,j+1)]
        dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz)
        nx,nz=-dz/length,dx/length
        for i,hand in enumerate([-1,1]):
            sides[i].append((cx+hand*half*nx,cz+hand*half*nz))
    drive=Polygon(sides[0]+sides[1][::-1])
    # Pale stone aprons surrounding the tower and the kiosk. Both inner edges
    # extend into the road outline and will be clipped to its finished curb.
    tower=Polygon([(-27.4,.7),(-22.0,-4.9),(-18.7,-9.3),(-11.3,-8.9),
                   (-6.9,-5.8),(-2.0,-1.3),(-9.2,12.3),(-17.6,10.5),(-25.,6.9)])
    kiosk=Polygon([(3.2,-2.8),(10.,-1.0),(18.8,2.9),(21.2,7.5),
                   (17.5,13.),(17.4,17.6),(24.2,22.0),(22.8,26.4),
                   (8.2,21.6),(3.2,16.0),(-.5,7.3)])
    # Crosswalk stripes run parallel to traffic and connect the paved aprons
    # at the throat just inside the external junction, as in the overhead view.
    stripes=unary_union([box(u-.21,-1.7,u+.21,1.7) for u in np.arange(-7.6,7.61,.80)])
    stripes=translate(rotate(stripes,25.2,origin=(0,0)), -4.0,8.42)
    return tuple(translate(a,x,z) for a in (drive,tower.union(kiosk),stripes))


def kiosk_front(scene,x,z,angle):
    f=Frame(scene,x,z,angle)
    # In the 2016 oblique photograph a tall arched window faces the lane;
    # the long outside elevation sits in shade behind stone piers and cornice.
    west=Frame(scene,x,z,angle-math.pi/2)
    for fr,offset,depth in [(west,0.,3.95),(f,-2.22,1.565)]:
        round_arch(fr,'南门岗亭·拱窗石套',offset,.38,depth+.025,1.16,2.16,'#d6cbb6')
        round_arch(fr,'南门岗亭·石券暗边',offset,.42,depth+.044,.96,2.00,'#3c4341')
        round_arch(fr,'南门岗亭·深色玻璃',offset,.49,depth+.058,.77,1.83,'#536674')
        fr.box('南门岗亭·窄窗横梃',offset,1.70,depth+.068,.76,.045,.022,'#384747')
        fr.box('南门岗亭·石窗台',offset,.37,depth+.05,1.12,.10,.19,'#c4bba8')
    for px in (.28,2.23):
        f.box('南门岗亭·檐下凹进窗框',px,1.50,1.582,1.41,1.98,.058,'#5d5b50')
        f.box('南门岗亭·檐下玻璃',px,1.49,1.619,1.26,1.81,.038,'#56676c')
    for px in (-.69,1.26,3.26):
        f.box('南门岗亭·窄廊石柱',px,1.51,1.826,.26,2.52,.32,'#cbbeaa')
        f.box('南门岗亭·檐柱石础',px,.39,1.826,.35,.30,.40,'#d4c8b6')
    f.box('南门岗亭·檐下承托带',0,2.71,0,8.15,.20,3.90,'#cbbfab')
    f.box('南门岗亭·平直出檐线',0,2.87,0,8.52,.11,4.03,'#e0d3bf')
