"""Photographic reconstruction of the Innovation and Entrepreneurship Centre on its surveyed plan."""
import math
from shapely.geometry import box
from shapely.geometry.polygon import orient
from qd_geometry import Shape
from qd_residence_roofs import walls, eave, terrace, full_hip, exact_top
from qd_terrain import polygons

PLUM='#915f57'
STONE='#dbceb5'
TILE='#976c5b'
FRAME='#666d68'
TRIM='#c9b99d'


def panel(s, origin, tangent, normal, width, bottom, spring, depth, name):
    """Arched glass and its separate raised stone archivolt."""
    x,z=origin
    tx,tz=tangent
    nx,nz=normal
    def vertex(a,b,d):
        return (x+a*tx+d*nx,b,z+a*tz+d*nz)
    radius=width/2
    def profile(r):
        return [(-r,bottom), *[(r*math.cos(a*math.pi/18),spring+.69*r*math.sin(a*math.pi/18))
                              for a in range(18,-1,-1)], (r,bottom)]
    outer,inner=profile(radius+.20),profile(radius)
    inside=[vertex(a,b,depth) for a,b in inner]
    s.mesh(name+'玻璃',inside,[list(range(len(inside)))],'glass')
    for i in range(len(inner)-1):
        v=[vertex(*outer[i],depth+.14),vertex(*outer[i+1],depth+.14),
           vertex(*inner[i+1],depth+.14),vertex(*inner[i],depth+.14)]
        s.mesh(name+'石券与窗套',v,[(0,1,2,3)],TRIM)
    yaw=-math.atan2(tz,tx)
    s.box(name+'中梃',x+nx*(depth+.04),(bottom+spring)/2,z+nz*(depth+.04),
          .075,spring-bottom,.08,FRAME,yaw)
    s.box(name+'横梃',x+nx*(depth+.05),spring-.15,z+nz*(depth+.05),
          width,.085,.09,FRAME,yaw)


def clock(s,cx,cz):
    width=8.15
    s.box('钟塔石台',cx,.15,cz,width+.9,.9,width+.9,TRIM)
    s.box('绛红钟塔塔身',cx,14.4,cz,width,28.65,width,PLUM)
    for y,w,h in [(1.0,8.5,.3),(6.7,8.55,.29),(28.5,8.48,.28),(28.81,8.82,.24)]:
        s.box('钟塔水平石带',cx,y,cz,w,h,w,TRIM)
    for tx,tz,nx,nz in [(1,0,0,1),(-1,0,0,-1),(0,-1,1,0),(0,1,-1,0)]:
        x,z=cx+nx*width/2,cz+nz*width/2
        panel(s,(x,z),(tx,tz),(nx,nz),2.15,.62,4.6,.035,'塔底拱门')
        panel(s,(x,z),(tx,tz),(nx,nz),1.62,8.05,15.0,.035,'塔身长拱窗')
        panel(s,(x,z),(tx,tz),(nx,nz),2.05,18.65,21.85,.035,'钟面下拱窗')
        def facept(a,b,d):
            return (x+tx*a+nx*d,25.5+b,z+tz*a+nz*d)
        for r,d,mat in [(1.37,.12,FRAME),(1.21,.14,'#e3dabc')]:
            ring=[facept(r*math.sin(i*math.tau/48),r*math.cos(i*math.tau/48),d) for i in range(48)]
            s.mesh('独立圆形钟盘',ring,[tuple(range(48))],mat)
        def stroke(a,b,c,e,th,depth):
            dx,dy=c-a,e-b
            length=math.hypot(dx,dy)
            vx,vy=-dy*th/length/2,dx*th/length/2
            s.mesh('钟盘刻度与指针',[facept(u,v,depth) for u,v in
                   [(a+vx,b+vy),(c+vx,e+vy),(c-vx,e-vy),(a-vx,b-vy)]],[(0,1,2,3)],'#414b48')
        for i in range(12):
            a=i*math.tau/12
            stroke(.97*math.sin(a),.97*math.cos(a),1.13*math.sin(a),1.13*math.cos(a),.066,.17)
        stroke(0,0,-.54,.32,.095,.185)
        stroke(0,0,.79,.46,.07,.19)
    corners=[(cx+a,28.95,cz+b) for a,b in [(-4.53,-4.53),(-4.53,4.53),(4.53,4.53),(4.53,-4.53)]]
    s.mesh('铺瓦坡面',corners+[(cx,36.4,cz)],[(i,(i+1)%4,4) for i in range(4)],'#805953')
    s.cyl('尖顶铜饰',cx,36.92,cz,.087,1.08,'#625950',10)


def build(foot):
    s=Shape('创新创业中心 · 钟塔、拱廊与屋面群')
    foot=orient(foot,1)
    # Offices span the footprint at the base. The upper wings step back from open terraces.
    h=8.48
    walls(s,'下层陶色基座',foot,-2,h,PLUM)
    rim=foot.buffer(.38,join_style=2)
    eave(s,foot,rim,h,h+.12,TRIM)
    terrace(s,rim,h+.12,'#b6b1a4')
    lo,bot,hi,top=foot.bounds
    # The north and south wings upper walls meet a recessed east link. Gaps are the terraces.
    clips=(box(lo-1,bot-1,hi+1,bot+25),box(lo-1,top-33,hi+1,top+1),box(hi-24,bot+28,hi+1,top-36))
    sections=[]
    for cut in clips:
        for p in polygons(foot.buffer(-.65,join_style=2).intersection(cut)):
            if p.area<35:continue
            sections.append(orient(p,1))
    def glazing(p,upper):
        for (a,b),(c,d) in zip(p.exterior.coords,list(p.exterior.coords)[1:]):
            length=math.hypot(c-a,d-b)
            if length<4:continue
            tx,tz=(c-a)/length,(d-b)/length
            nx,nz=tz,-tx
            angle=-math.atan2(tz,tx)
            n=max(1,round(length/(4.3 if upper else 5.45)));pitch=length/n
            for j in range(n):
                t=(j+.5)*pitch;x,z=a+t*tx,b+t*tz
                if upper:
                    s.box('砂岩窗套',x+nx*.06,11.21,z+nz*.06,pitch*.58,2.98,.15,TRIM,angle)
                    s.box('上层窄窗',x+nx*.17,11.21,z+nz*.17,pitch*.51,2.72,.11,'glass',angle)
                    s.box('上层中梃',x+nx*.25,11.21,z+nz*.25,.075,2.72,.08,FRAME,angle)
                else:
                    panel(s,(x,z),(tx,tz),(nx,nz),min(3.85,pitch*.74),.5,3.55,.06,'基座拱窗')
                    s.box('露台层玻璃',x+nx*.095,6.95,z+nz*.095,pitch*.61,1.81,.21,'glass',angle)
            if not upper:
                s.box('层间浅色压顶',(a+c)/2+nx*.07,5.18,(b+d)/2+nz*.07,length,.26,.28,TRIM,angle)
    glazing(foot,False)
    for p in sections:
        walls(s,'米色上层侧翼',p,8.60,13.68,STONE)
        glazing(p,True)
        full_hip(s,p,13.68,TILE,STONE)
    # Guard rails follow the actual uncovered terrace edge only.
    from shapely.ops import unary_union
    guard=foot.exterior.difference(unary_union(sections).buffer(1.25))
    from qd_planting import branch
    for line in getattr(guard,'geoms',[guard]):
        pts=list(line.coords)
        for (a,b),(c,d) in zip(pts,pts[1:]):
            length=math.hypot(c-a,d-b)
            if length<.7:continue
            for y in (8.95,9.6):branch(s,(a,y,b),(c,y,d),.055,.055,FRAME)
            n=max(1,math.ceil(length/2.8))
            for j in range(n):
                t=j/n;s.cyl('露台栏杆立柱',a+(c-a)*t,9.1,b+(d-b)*t,.055,1.0,FRAME,8)
    clock(s,-43.45,24.0)
    return s,exact_top(s)
