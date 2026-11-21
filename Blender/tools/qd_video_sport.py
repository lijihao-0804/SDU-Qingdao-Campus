"""Sports district geometry drawn from films V2 01:17–01:40 and V3 01:25–02:10."""
import math
import numpy as np
from shapely.geometry import Point,Polygon,box,LineString
from shapely.affinity import scale
from shapely.geometry.polygon import orient
from qd_terrain import face
from qd_geometry import Shape
from qd_residence_roofs import surface,walls

def arch_hall(s,w,d,h):
    # The western practice hall runs east/west. A barrel sits between blue
    # end frames. Narrow changes in skin colour follow the purlin bays.
    spring=6.15;end=w*.455;radius=d*.48
    def roof(x,t,extra=0):
        return x,spring+(h-spring+extra)*math.sin(t*math.pi),-radius*math.cos(t*math.pi)
    for i in range(16):
        a=-end+2*end*i/16;b=-end+2*end*(i+1)/16
        skin=('#cbbba9','#e4dbcd','#ded8d0','#c9b9ac')[i%4]
        for k in range(24):
            t=k/24;j=(k+1)/24
            s.mesh('训练馆弧形分幅屋皮',[roof(a,t),roof(a,j),roof(b,j),roof(b,t)],[(0,1,2,3)],skin)
            s.mesh('训练馆接缝盖条',[roof(a,t,.045),roof(a,j,.045),roof(a+.10,j,.045),roof(a+.10,t,.045)],[(0,1,2,3)],'#aaa9a5')
    for hand in (-1,1):
        z=hand*radius
        s.box('训练馆侧墙',0,2.87,z,w*.915,6.56,.42,'#97a7ac')
        for i in range(18):
            x=(i-8.5)*2*end/18
            s.box('侧面窄窗',x,4.0,z+hand*.23,2.64,1.60,.13,'#46616c')
            s.box('压型侧墙外柱',x-1.79,3.06,z+hand*.30,.19,6.2,.34,'#8198a6')
        x=hand*end
        loop=[(x,.02,-radius),(x,.02,radius)]+[roof(x,1-i/32) for i in range(33)]
        s.mesh('风雨操场蓝色山墙',loop,[tuple(range(len(loop))) if hand<0 else tuple(reversed(range(len(loop))))],'#769bb2')
        s.box('山墙入口侧翼',x+hand*1.02,2.7,0,2.05,5.4,13.8,'#8da2ad')
        for k in range(-2,3):s.box('侧翼卷门',x+hand*2.08,1.75,k*2.40,.13,3.5,2.14,'#495e66')
        for k in range(24):
            t=k/24;j=(k+1)/24
            s.mesh('端拱蓝色包边',[roof(x-hand*.37,t,.09),roof(x-hand*.37,j,.09),roof(x+hand*.19,j,.09),roof(x+hand*.19,t,.09)],[(0,1,2,3)],'#6691a9')
    return True

def arcade_skin(s,rows,roof_point):
    """A metal skin with individual diamond apertures, reveals and recessed blue glazing."""
    rz=np.array([r[0] for r in rows]);left=np.array([r[1] for r in rows])
    def surface_point(along,v,off=0):
        edge=np.interp(along,rz,left)
        x,h,z=roof_point(edge,along)
        lo=h*(.44+.045*math.sin((along-229)/221*math.pi))
        return (x+.75+off,lo+(h-.72-lo)*v,z)
    # Parametrised bands follow the curved top edge; the glazing ribbon tapers
    # into the grey cladding rather than ending with a square joint.
    zs=np.linspace(231.,448.,109)
    for col,(a,b) in enumerate(zip(zs,zs[1:])):
        for row in range(7):
            v0=row/7;v1=(row+1)/7
            u=(col+.5)/(len(zs)-1);v=(row+.5)/7
            amt=(.19+.77*math.exp(-((u-.28)/.28)**2-((v-.39)/.40)**2)+.18*math.cos(2*math.pi*(u+v*.39)))
            amt=max(.085,min(.83,amt))
            corners=[(0,0),(1,0),(1,1),(0,1)]
            diamonds=[(.5,.5-amt*.46),(.5+amt*.48,.5),(.5,.5+amt*.46),(.5-amt*.48,.5)]
            def pts(uv,depth):return [surface_point(a+(b-a)*t,v0+(v1-v0)*j,depth) for t,j in uv]
            if abs((a+b)/2-337.5)<13 and row in (3,4,5):
                s.mesh('馆名实心金属带',pts(corners,0),[(0,1,2,3)],'#e3e6e6')
                continue
            shell=pts(corners,0);lip=pts(diamonds,0);back=pts(diamonds,.20)
            skin=('#e3e6e6','#e6e8e7','#e2e5e4')[(row+2*col)%3]
            for k in range(4):
                # Join the four mid-side diamond vertices to their corners.
                edge=(k+1)%4;prev=(k-1)%4
                s.mesh('穿孔铝板折面', [shell[k],shell[edge],lip[k]],[(0,1,2)],skin)
                s.mesh('穿孔铝板折面',[shell[k],lip[k],lip[prev]],[(0,1,2)],skin)
                s.mesh('菱形窗四周折边',[lip[k],lip[edge],back[edge],back[k]],[(0,1,2,3)],'#a2abb2')
            s.mesh('凹入菱形深蓝窗',back,[(0,1,2,3)],'#354759')
        def point_at(z,dist,offset):
            x,h,p=surface_point(z,0,offset);return (x,h-dist,p)
        def slit(t):return .30+3.45*max(0,math.sin(math.pi*t))**.74
        ta=col/(len(zs)-1);tb=(col+1)/(len(zs)-1)
        s.mesh('横向收尖深蓝玻璃带',[point_at(a,slit(ta),.19),point_at(b,slit(tb),.19),point_at(b,0,.19),point_at(a,0,.19)],[(0,1,2,3)],'#384e65')
        s.mesh('低窗带下方金属裙边',[point_at(a,slit(ta)+1.15,0),point_at(b,slit(tb)+1.15,0),point_at(b,slit(tb),0),point_at(a,slit(ta),0)],[(0,1,2,3)],'#cdd2d4')
        # A recessed shadow joint subdivides the blue ribbon into individual lites.
        if col%2==0:
            s.mesh('窗带深色竖梃',[point_at(a,slit(ta),.14),point_at(a+.11,slit(ta),.14),point_at(a+.11,0,.14),point_at(a,0,.14)],[(0,1,2,3)],'#38434a')
    from qd_architecture import sign
    from qd_civic import SEAL_SHAPE,relief
    # Readable name and English inscription sit in the upper third of the
    # western metal facade, above the long dark ribbon, as in V2 01:18.5.
    x,y,z=surface_point(339,.68,-.20)
    sign(s,'宋君复体育馆外墙中文馆名','宋君复体育馆',x,y,z,14.6,2.30,'#252d36',-math.pi/2)
    sign(s,'宋君复体育馆英文馆名','SONG JUNFU GYMNASIUM',x,y-1.69,z,14.2,.69,'#252d36',-math.pi/2)
    class West:
        def mesh(self,name,vertices,faces,material):s.mesh(name,[(x-vz,y+vy,z-9.0+vx) for vx,vy,vz in vertices],faces,material)
    relief(West(),'馆名旁校徽',0,-.12,0,2.8,2.8,61,61,SEAL_SHAPE,'#252d36')

def podium():
    # World axes relative to the arena node. The concave orchard-side edge and
    # two inset light wells can be read from the overhead run in V2 01:26–01:34.
    outline=Polygon([(-43,-114),(-41,157),(-57,162),(-65,145),(-75,116),(-84,83),
                     (-89,59),(-98,43),(-103,30),(-104,12),(-103,-11),(-109,-24),
                     (-106,-38),(-93,-55),(-87,-78),(-77,-99),(-64,-112)])
    notch=scale(Point(-108,0).buffer(1,quad_segs=32),25,35)
    holes=[Polygon([(-79,67),(-66,108),(-57,125),(-61,79)]).buffer(2.8,join_style=1),
           Polygon([(-75,20),(-66,22),(-58,39),(-60,52),(-68,44)]).buffer(3.0,join_style=1)]
    return outline.difference(notch).difference(holes[0]).difference(holes[1])
def approach(s):
    deck=podium();hi=5.16;lo=4.62
    surface(s,'体育馆西侧高架平台',deck,hi,'#c6c4bc');surface(s,'平台与采光井檐底',deck,lo,'#b6b7b3',False)
    walls(s,'平台及采光井封边',deck,lo,hi,'#d6d6cf')
    from qd_civic import beam
    for ring in [deck.exterior,*deck.interiors]:
        line=LineString(ring.coords);ct=math.ceil(line.length/3.8)
        for j in range(ct):
            q=line.interpolate(j/ct,normalized=True);n=line.interpolate((j+1)/ct,normalized=True)
            s.cyl('平台护栏立柱',q.x,hi+.56,q.y,.052,1.12,'#929e9f',6)
            beam(s,'平台不锈钢扶手',(q.x,hi+1.12,q.y),(n.x,hi+1.12,n.y),.051,'#afb9ba',6)
            if j%5==0:s.cyl('平台承柱',q.x,lo/2,q.y,.34,lo,'#bdc4c1',10)
    # A fan of stone treads climbs from the orchard path to the raised deck.
    for i in range(27):
        u=i/26;level=hi*(i+1)/27
        x=-116+19*u;z=-51-12*u;width=27-4*u
        s.box('体育馆扇形台阶',x,level/2,z,1.12,level,width,'#c9c6bd',-.12-.22*u)
    island=scale(Point(-105,4).buffer(1,quad_segs=20),13.1,21.9)
    surface(s,'绿岛草坪',island,.38,'#7c9f66')
    for j in range(16):
        a=math.tau*j/16;b=math.tau*(j+1)/16
        # Low planting edge around the oval by the stair, grounded in its own lawn.
        p=(-105+13.2*math.cos(a),.4,4+22*math.sin(a));q=(-105+13.2*math.cos(b),.4,4+22*math.sin(b))
        beam(s,'弧形绿岛石收边',p,q,.19,'#b9b9ac')

