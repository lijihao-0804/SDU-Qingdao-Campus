"""Stripe and furnish only mapped parking pads. All details share their draped base."""
import math
import random
import numpy as np
from shapely.geometry import Polygon
from qd_geometry import Shape
from qd_terrain import sourcepolygon

def body(s,colour):
    def shell(name,sections,mat):
        vs=[(x,y,z) for z,hw,y0,y1 in sections for x,y in [(-hw,y0),(hw,y0),(hw,y1),(-hw,y1)]]
        fs=[(0,1,2,3)]+[(i*4+k,(i+1)*4+k,(i+1)*4+(k+1)%4,i*4+(k+1)%4) for i in range(len(sections)-1) for k in range(4)]
        fs.append(tuple(range(len(vs)-1,len(vs)-5,-1)));s.mesh(name,vs,fs,mat)
    shell('车身',[(-2.18,.75,.39,.80),(-1.67,.89,.31,.94),(.8,.88,.31,1.00),(2.12,.76,.39,.76)],colour)
    shell('侧窗与前后风挡',[(-1.32,.79,.90,.95),(-.69,.68,.94,1.50),(.53,.66,.94,1.53),(1.30,.79,.90,.96)],'#364653')
    s.box('车顶',0,1.52,-.08,1.36,.055,1.20,colour)
    for h in (-1,1):
        s.box('车窗中柱',h*.711,1.21,-.12,.072,.53,.115,'#323b3e')
        for z in (-1.35,1.32):
            v=[(h*x,.37+math.sin(t*math.tau/12)*.31,z+math.cos(t*math.tau/12)*.31) for x in (.78,.899) for t in range(12)]
            s.mesh('轮胎',v,[(t,(t+1)%12,12+(t+1)%12,12+t) for t in range(12)]+[tuple(range(12,24))],'#303232')
            hub=[(h*.902,.37+math.sin(t*math.tau/12)*.17,z+math.cos(t*math.tau/12)*.17) for t in range(12)]
            s.mesh('轮毂',hub,[tuple(range(12))],'#a0a5a5')
        for z,c in [(-2.19,'#973f36'),(2.13,'#d9ded3')]:
            s.box('灯',h*.59,.70,z,.25,.115,.022,c)
    return s

class ParkingSurface:
    """Clip paint and islands to the actual exported triangles underneath."""
    def __init__(self,scene):
        from shapely.strtree import STRtree
        node=next(n for n in scene.doc['nodes'] if n['name']=='停车铺面')
        assert node['translation']==[0,0,0] and node['scale']==[1,1,1] and node['rotation']==[0,0.0,0,1.0]
        def array(idx):
            a=scene.doc['accessors'][idx]
            view=scene.doc['bufferViews'][a['bufferView']]
            dims=3 if a['type']=='VEC3' else 1
            dtype={5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
            return np.frombuffer(scene.raw,dtype=dtype,count=a['count']*dims,
                                 offset=view['byteOffset']).reshape(-1,dims).copy()
        triangles=[]
        for part in scene.doc['meshes'][node['mesh']]['primitives']:
            verts=array(part['attributes']['POSITION'])
            triangles.extend(verts[array(part['indices']).reshape(-1,3)].astype(float))
        self.faces=[]
        self.planes=[]
        for tri in triangles:
            xz=tri[:,[0,2]]
            p=Polygon(xz)
            if p.area<1e-8:
                continue
            self.faces.append(p)
            self.planes.append(np.linalg.solve(np.column_stack((xz,np.ones(3))),tri[:,1]))
        self.index=STRtree(self.faces)

    def slab(self,shape,footprint,name,colour,offset):
        count=0
        for idx in self.index.query(footprint,predicate='intersects'):
            poly=footprint.intersection(self.faces[idx])
            if poly.geom_type!='Polygon' or poly.area<1e-7:
                continue
            xz=np.asarray(poly.exterior.coords)[:-1]
            plane=self.planes[idx]
            y=xz@plane[:2]+plane[2]+offset
            xyz=np.column_stack((xz[:,0],y,xz[:,1]))
            # GEOS may keep a collinear point, so discard each degenerate fan ear.
            for k in range(1,len(xyz)-1):
                a,b=xz[k]-xz[0],xz[k+1]-xz[0]
                signed=a[0]*b[1]-a[1]*b[0]
                if abs(signed)<1e-9:
                    continue
                face=(0,k+1,k) if signed>0 else (0,k,k+1)
                shape.mesh(name,xyz,[face],colour)
                count+=1
        return count

def build(scene,terrain,data,obstacle):
    substrate=ParkingSurface(scene)
    rng=random.Random(62026)
    cars=[scene.shape(body(Shape('停车区车辆'),c)) for c in ('#c9ccca','#818e95','#34454d','#f0efea','#5b7185','#924f44')]
    parking=[]
    for row in data['parking']:
        poly=sourcepolygon(row);area=poly.buffer(-.12).difference(obstacle)
        c=list(poly.minimum_rotated_rectangle.exterior.coords);a,b,d=np.array(c[:3])
        u=(b-a) if np.linalg.norm(b-a)>np.linalg.norm(d-b) else (d-b)
        u=u/np.linalg.norm(u);v=np.array([-u[1],u[0]]);center=np.array(poly.centroid.coords[0])
        local=np.array(poly.exterior.coords)-center;lo,hi=(local@u).min(),(local@u).max()
        bottom,top=(local@v).min(),(local@v).max();span=top-bottom
        nrow=max(1,int((span+5.5)//(5.20+3.5)))
        if span<17.:nrow=1
        if nrow>=2:nrow-=nrow%2
        if nrow==1:rows=[(top+bottom)/2]
        else:
            groups=nrow//2
            start=(top+bottom)/2-(groups-1)*8.30
            rows=[start+group*16.60+offset for group in range(groups) for offset in (-5.65,5.65)]
        sh=Shape('停车分区');spots=vehicles=islands=0
        stripes={'#dfdbbd':[],'#dad8c4':[]}
        def at(i,j):return center+u*i+v*j
        def rect(i,j,w,h):
            return Polygon([at(i+x*w*.5,j+y*h*.5) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]])
        def slab(i,j,w,h,name,col,level):
            # The base pad is at DEM +.09. Only a 5 mm relief is needed for paint.
            offset=.005 if col in stripes else level-.09
            count=substrate.slab(sh,rect(i,j,w,h),name,col,offset)
            if col in stripes:
                if not count:raise ValueError(('车位标线下无铺面',row['id'],i,j))
                stripes[col].append(count)
        for ri,nominal in enumerate(rows):
            direction=1 if ri%2 else -1
            for k,i in enumerate(np.arange(lo+1.6,hi-1.23,2.67)):
                depth=4.88 if span<7 else 5.12
                j=next((nominal+shift for shift in (0,.16,-.16,.32,-.32,.48,-.48,.64,-.64,.80,-.80)
                        if area.covers(rect(i,nominal+shift,2.63,depth+.06))),None)
                if j is None:continue
                if nrow>1 and k%21 in (0,1):continue
                if nrow>1 and k%21==2:
                    slab(i,j,2.26,4.70,'岛头压边','#b8b5a6',.146)
                    slab(i,j,1.95,4.37,'修剪地被岛','#71845d',.21)
                    islands+=1
                    continue
                for side in (-1,1):slab(i+side*1.29,j,.082,depth,'车位分隔漆线','#dfdbbd',.125)
                slab(i,j+direction*(depth/2-.05),2.55,.10,'车位端线','#dad8c4',.126)
                spots+=1
                if rng.random()<.23:
                    x,z=at(i,j);yaw=math.atan2(v[0],v[1])+(math.pi if direction<0 else 0)
                    # Tilt the shared mesh onto the same terrain plane as its four tyre contacts.
                    gx=(terrain.y(x+.5,z)-terrain.y(x-.5,z));gz=(terrain.y(x,z+.5)-terrain.y(x,z-.5))
                    from scipy.spatial.transform import Rotation
                    n=np.array([-gx,1.,-gz]);n/=np.linalg.norm(n)
                    f=np.array([math.sin(yaw),0,math.cos(yaw)]);f-=n*(f@n);f/=np.linalg.norm(f)
                    rot=Rotation.from_matrix(np.column_stack((np.cross(n,f),n,f))).as_quat().tolist()
                    scene.node('停放车辆',mesh=rng.choice(cars),at=(x,terrain.y(x,z)+.063,z),kind='parkingVehicle')
                    scene.doc['nodes'][-1]['rotation']=rot;vehicles+=1
        if sh.parts:scene.node('停车位与绿岛 · '+row['id'],shape=sh,kind='parkingDetail',sourceID=row['id'],stalls=spots,vehicles=vehicles,paintTriangleCounts=stripes)
        parking.append(dict(id=row['id'],area=round(poly.area),stalls=spots,vehicles=vehicles,islands=islands))
    return parking

