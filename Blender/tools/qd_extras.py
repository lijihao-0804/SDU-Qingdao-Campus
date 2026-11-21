"""Ancillary landscape furnishings and the satellite-traced north assembly hall."""
import math
from shapely.geometry import Point
from qd_geometry import Shape
def assembly(row,p):
    # The georeferenced orthophoto separates three unequal sectors and the
    # established tree court. The delivered horizontal plan is an estimate at
    # roof level. The source image shows construction and does not prove opening.
    s=Shape(row['name'])
    outer_x,outer_z=80.1,82.0
    inner_x,inner_z=60.7,60.0
    boundaries=(-140.,-16.,129.,220.)
    for wing,(start,stop) in enumerate(zip(boundaries,boundaries[1:])):
        stations=max(32,math.ceil((stop-start)/2.1));across=10
        verts=[];faces=[]
        def ring(t,q):
            ang=math.radians(start+1.75+(stop-start-3.50)*t)
            width=math.sin(math.pi*t)**1.2
            rx=inner_x+q*(outer_x-inner_x)*(1+.05*width)
            rz=inner_z+q*(outer_z-inner_z)*(1+.05*width)
            y=12.4+(7.6,10.3,6.7)[wing]*width+(1.4+2.6*width)*math.sin(q*math.pi)
            return rx*math.cos(ang),y,rz*math.sin(ang)
        for j in range(stations+1):
            t=j/stations
            verts.extend(ring(t,k/across) for k in range(across+1))
        stride=across+1
        for j in range(stations):
            for k in range(across):
                n=j*stride+k
                faces.append((n,n+stride,n+stride+1,n+1))
        s.mesh('贝壳薄壳顶 · '+str(wing+1),verts,faces,'#d4d4c9')
        for q in (0.,1.):
            edge=[ring(j/stations,q) for j in range(stations+1)]
            for j,(u,v) in enumerate(zip(edge,edge[1:])):
                upper=[u,v,(v[0],v[1]-.45,v[2]),(u[0],u[1]-.45,u[2])]
                s.mesh('贝壳檐口封边',upper,[(0,1,2,3)],'#c1c4bd')
                # Continuous roof meets both the exterior wall and the inner
                # facade. Radial access slots between the shells remain open.
                for low,high,col in ((.0,.24,'#89968c'),(.24,.68,'#809194'),(.68,1.,'#d2d2c6')):
                    quad=[(u[0],(u[1]-.45)*low,u[2]),(v[0],(v[1]-.45)*low,v[2]),
                          (v[0],(v[1]-.45)*high,v[2]),(u[0],(u[1]-.45)*high,u[2])]
                    s.mesh('环庭与外侧围护',quad,[(0,1,2,3)],col)
                if j%2==0:
                    s.box('环庭分隔竖挺',u[0],u[1]*.43,u[2],.24,u[1]*.84,.24,'#c4c8bc')
        for t in (0.,1.):
            for k in range(across):
                u=ring(t,k/across);v=ring(t,(k+1)/across)
                s.mesh('三处分翼端部封板',[(u[0],.0,u[2]),(v[0],.0,v[2]),v,u],[(0,1,2,3)],'#cccbbd')
    return s,26.8

def detail_plaza(scene,terrain,r,p):
    x,z=r['center'];s=Shape(r['name'])
    for k in range(1,9):
        xx=p.bounds[0]+(p.bounds[2]-p.bounds[0])*k/10
        for zz in (p.bounds[1]+2.2,p.bounds[3]-2.2):
            if not p.contains(Point(xx,zz)):continue
            y=terrain.y(xx,zz)+.13
            s.box('长凳',xx,y+.44,zz,3.35,.16,.7,'#88725b')
            for q in [-1.15,1.15]:s.box('凳脚',xx+q,y+.22,zz,.32,.44,.59,'#aaa598')
            if k%2==0:
                s.cyl('灯柱',xx+2.7,y+2.3,zz,.095,4.6,'#667170',10)
                s.cyl('灯罩',xx+2.7,y+4.6,zz,.38,.17,'#e2d9bf',12)
    scene.node(r['name']+' · 坐凳与庭院灯',shape=s,kind='landscape')

