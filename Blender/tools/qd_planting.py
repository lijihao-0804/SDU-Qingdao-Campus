"""Deterministic campus planting; canopy families share editable glTF meshes."""
import math, random
import numpy as np
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from shapely.prepared import prep
from qd_geometry import Shape

def branch(s,p,q,r1,r2,material):
    p,q=np.array(p),np.array(q);axis=q-p;axis=axis/max(1e-8,np.linalg.norm(axis))
    u=np.cross(axis,[0,0,1] if abs(axis[2])<.85 else [1,0,0]);u/=np.linalg.norm(u);v=np.cross(axis,u)
    vv=[tuple(c+rr*(math.cos(i*math.pi/3)*u+math.sin(i*math.pi/3)*v)) for c,rr in [(p,r1),(q,r2)] for i in range(6)]
    s.mesh('树枝',vv,[(i,(i+1)%6,(i+1)%6+6,i+6) for i in range(6)],material)
def crown(s,c,rad,mat,rng):
    v,n,idx=s.parts[mat];off=len(v);rings,steps=6,11
    for j in range(rings+1):
        lat=math.pi*j/rings
        for i in range(steps):
            ang=i*math.tau/steps+.13*(j%2)
            axis=(math.sin(lat)*math.cos(ang),math.cos(lat),math.sin(lat)*math.sin(ang))
            jitter=1+rng.uniform(-.15,.13) if j and j<rings else 1
            v.append(tuple(c[k]+axis[k]*rad[k]*jitter for k in range(3)))
            vec=np.array(axis)/np.array(rad);vec/=np.linalg.norm(vec);n.append(tuple(vec))
    for j in range(rings):
        for i in range(steps):
            a=off+j*steps+i;b=off+j*steps+(i+1)%steps
            if j:idx.extend((a,b,a+steps))
            if j<rings-1:idx.extend((b,b+steps,a+steps))
def prototype(k,shrub=False):
    from qd_canopy import make
    return make(k,shrub)

def plant(doc,terrain,area,roads,excluded,parks,seed=1901,axis=None,axis_conflicts=None):
    rng=random.Random(seed); clear=prep(area.difference(excluded));park=prep(parks)
    trees=[doc.shape(prototype(k)) for k in range(5)];shrubs=[doc.shape(prototype(k,True)) for k in range(3)]
    cells={};placed=[0,0]
    if axis:
        sp,x0,z0=axis
        for side in (-1,1):
            for i in range(12):
                for outer in (False,True):
                    x=x0+(i-5.5)*sp['w']/12;z=z0+side*sp['d']*(.456 if outer else .395)
                    if axis_conflicts is not None and axis_conflicts.covers(Point(x,z)):
                        continue
                    sc=.67+.035*((i*7+side)%4);k=(i+int(outer))%5
                    doc.node('育贤广场行道树'+str(placed[0]+1),mesh=trees[k],at=(x,terrain.y(x,z)+.29,z),yaw=rng.uniform(0,math.tau),scale=(sc,sc,sc),kind='flora',species=k,shrub=False)
                    placed[0]+=1;cells.setdefault((math.floor(x/7),math.floor(z/7)),[]).append((x,z))
    def put(x,z,small=False):
        if not clear.contains(Point(x,z)):return
        ix,iz=math.floor(x/7),math.floor(z/7)
        limit=2.3 if small else 6.4
        for i in range(ix-1,ix+2):
            for j in range(iz-1,iz+2):
                if any((x-a)**2+(z-b)**2<limit*limit for a,b in cells.get((i,j),[])):return
        cells.setdefault((ix,iz),[]).append((x,z)); pool=shrubs if small else trees
        k=rng.randrange(len(pool));sc=rng.uniform(.78,1.24) if not small else rng.uniform(.7,1.65)
        name='灌木' if small else '乔木'
        doc.node(name+str(placed[int(small)]+1),mesh=pool[k],at=(x,terrain.y(x,z)-.05,z),yaw=rng.uniform(0,math.tau),scale=(sc,sc*rng.uniform(.9,1.12),sc),kind='flora',species=k,shrub=small)
        placed[int(small)]+=1
    for road in roads:
        ls=LineString(road['line']);w=road['width']
        if ls.length<20 or w<4.8 or road.get('tunnel'):continue
        for side in [-1,1]:
            for k in range(round(ls.length/12)):
                d=min(ls.length-.1,5+k*12+rng.uniform(-.8,.8))
                p=ls.interpolate(d);q=ls.interpolate(min(ls.length,d+.5));v=np.array([q.x-p.x,q.y-p.y]);norm=np.linalg.norm(v)
                if norm<.01:continue
                nx,nz=-v[1]/norm,v[0]/norm;gap=w*.5+rng.uniform(3.0,4.0)
                put(p.x+side*gap*nx,p.y+side*gap*nz)
    xmin,zmin,xmax,zmax=area.bounds
    for _ in range(int(area.area/520)):
        x=rng.uniform(xmin,xmax);z=rng.uniform(zmin,zmax)
        dense=park.contains(Point(x,z))
        if dense or rng.random()<.15:
            for j in range(rng.randint(3,8) if dense else rng.randint(2,5)):
                put(x+rng.gauss(0,8),z+rng.gauss(0,8))
        if dense or rng.random()<.4:
            length=rng.randrange(3,9);a=rng.uniform(0,math.tau)
            for j in range(length):put(x+math.cos(a)*j*1.9+rng.random(),z+math.sin(a)*j*1.9+rng.random(),True)
    return placed

