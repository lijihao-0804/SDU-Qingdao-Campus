"""Spring flowering garden immediately south of the library, west of the curved drive."""
import math
import random
from collections import defaultdict
from shapely.geometry import box, Point
from shapely.ops import unary_union
import numpy as np
from PIL import Image, ImageDraw
from qd_spring_surfaces import add_image
from qd_geometry import Shape
from qd_planting import branch
from qd_phoenix_garden import _edge, _lobe
from qd_spring import _truss
from qd_petal_sprays import flowering_spur, leaf_blade

AREA=box(111.7,6.9,157.5,32.1)
# Registered against the garden squares and two paths in Wayback image release 3692.
X_SPANS=[(113.0,120.5),(122.2,131.25),(132.98,142.34),(144.03,155.65)]
Z_SPANS=[(8.0,17.35),(19.30,30.45)]
BEDS=[box(a,c,b,d).buffer(-.48,join_style=1).buffer(.48,quad_segs=3)
      for a,b in X_SPANS for c,d in Z_SPANS]
HEDGE=('图书馆方篱·侧面','图书馆方篱·肩部','图书馆方篱·顶面','图书馆方篱·嫩叶')
BLOOM=('#d78299','#e6a3ad','#eab2b5','#dc92aa','#c77689')
TWIG='#70665e'
SPROUT='图书馆方篱·对生嫩梢'


def hedge_shoots(shape, line, terrain, seed):
    """Paired leaves on short shoots inside the clipped footprint of each hedge."""
    from qd_geometry import lin
    rng=random.Random(47620+seed)
    vv,nn,ii=shape.parts[SPROUT]
    tints=shape.vertex_tints.setdefault(SPROUT,[])
    def append(pts, norms, tris, cols):
        off=len(vv);vv.extend(map(tuple,pts));nn.extend(map(tuple,norms))
        ii.extend(off+i for tri in tris for i in tri)
        tints.extend(tuple(lin(c/255) for c in rgb) for rgb in cols)
    count=0
    for s in np.arange(.13,line.length-.10,.31):
        p=line.interpolate(s)
        a=line.interpolate(max(0.,s-.08));b=line.interpolate(min(line.length,s+.08))
        tangent=np.array([b.x-a.x,0.,b.y-a.y])
        tangent/=max(np.linalg.norm(tangent),.001)
        side=np.array([-tangent[2],0.,tangent[0]])
        direction=rng.choice((-1,1));setback=rng.uniform(.15,.29)*direction
        root=np.array([p.x,0.,p.y])+side*setback
        root[1]=terrain.y(root[0],root[2])+rng.uniform(.694,.711)
        top=root+tangent*rng.uniform(-.029,.045)+side*direction*.023+[0,rng.uniform(.075,.118),0]
        append([root-side*.002,root+side*.002,top],[(0,1,0)]*3,[(0,1,2)],[(104,116,58)]*3)
        for tier,frac in enumerate((.45,.86)):
            base=root+(top-root)*frac
            for handed in (-1,1):
                forward=tangent*handed+side*direction*rng.uniform(-.37,.52)
                forward/=np.linalg.norm(forward)
                cross=np.array([-forward[2],0.,forward[0]])
                length=rng.uniform(.039,.068)*(1.-tier*.21)
                width=length*rng.uniform(.19,.27)
                mid=base+forward*length*.52+[0,.016,0]
                tip=base+forward*length+[0,rng.uniform(.016,.039),0]
                midrib=mid+[0,width*.32,0]
                cols=((95,120,57),(111,137,61),(141,160,77),
                      (120,146,68),(150,167,81)) if tier else (
                      (79,104,50),(97,121,55),(119,141,65),(106,130,59),(123,145,68))
                crossnorm=cross*.33
                append([base,mid-cross*width,midrib,mid+cross*width,tip],
                       [(0,1,0),tuple(-crossnorm+[0,.944,0]),(0,1,0),
                        tuple(crossnorm+[0,.944,0]),(0,1,0)],
                       [(0,2,1),(0,3,2),(1,2,4),(2,3,4)],cols)
                count+=1
    return count


def flowering_tree(variant):
    rng=random.Random(1274+437*variant)
    s=Shape('图书馆花木 · 多干重瓣粉花 '+str(variant+1))
    s.uvs=defaultdict(list);s.vertex_tints=defaultdict(list)
    flower_rng=random.Random(81245+43*variant)
    def pushed(pt,angle,length,rise):
        return (pt[0]+math.cos(angle)*length, pt[1]+rise,pt[2]+math.sin(angle)*length)
    def blossom(p,scale,angle,exposed):
        _truss(s,p,angle,flower_rng.uniform(.40,1.34),scale*1.48,
               flower_rng.choice(BLOOM),flower_rng)
        if exposed:
            flowering_spur(s,p,angle+.9,scale,BLOOM,flower_rng,count=4,double=True)
            leaf_blade(s,p,angle-.74,scale*.65,scale*.14,.048,'#a18b69')
        else:
            # Deeper buds are smaller and darker than the open outer flowers.
            _lobe(s,p,scale*.24,scale*.31,scale*.23,BLOOM[-1],flower_rng)
    origin=(0,-.07,0)
    fork=(rng.uniform(-.11,.11),.83,rng.uniform(-.13,.13))
    branch(s,origin,fork,.126,.103,'#d9d9c9')
    for j in range(5):
        a=(j+rng.uniform(-.23,.23))*math.tau/5
        knuckle=pushed(fork,a,rng.uniform(.28,.52),rng.uniform(.57,.92))
        branch(s,fork,knuckle,.076,.053,'#9a9686')
        elbow=pushed(knuckle,a,rng.uniform(.32,.64),rng.uniform(.52,.93))
        branch(s,knuckle,elbow,.055,.039,TWIG)
        for side in (-1,1):
            # A short lateral flowering branch breaks up the bare zone below
            # the three longer, upright extensions at the end of the scaffold.
            t=flower_rng.uniform(.45,.85)
            base=tuple(x+t*(y-x) for x,y in zip(knuckle,elbow))
            bearing=a+side*flower_rng.uniform(.59,1.35)
            shoot=pushed(base,bearing,flower_rng.uniform(.27,.50),flower_rng.uniform(.30,.55))
            branch(s,base,shoot,.020,.008,TWIG)
            fork_tip=pushed(shoot,bearing+.5,.14,.17)
            branch(s,shoot,fork_tip,.008,.003,TWIG)
            blossom(shoot,.16,bearing,True)
            blossom(fork_tip,.19,bearing+.7,True)
        for k in range(3):
            angle=a+rng.uniform(-1.1,1.1)
            tip=pushed(elbow,angle,rng.uniform(.27,.68),rng.uniform(.57,1.13))
            branch(s,elbow,tip,.038,.017,TWIG)
            for l in range(3):
                theta=angle+rng.uniform(-1.3,1.3)
                u=.32+.28*l
                start=tuple(elbow[q]+u*(tip[q]-elbow[q]) for q in range(3))
                twig=pushed(start,theta,rng.uniform(.17,.34),rng.uniform(.21,.43))
                branch(s,start,twig,.018,.005,'#887165')
                for frac in (.41,.72,1.0):
                    c=tuple(start[q]+frac*(twig[q]-start[q]) for q in range(3))
                    blossom(c,rng.uniform(.15,.21),theta+frac*2.1,frac!=.41)
                spur=pushed(start,theta+.76,.20,.16)
                branch(s,start,spur,.012,.004,'#91786d')
                blossom(spur,rng.uniform(.17,.23),theta-.70,True)
                if l!=1:
                    leaf_blade(s,twig,theta,.15,.033,.038,rng.choice(('#a4845e','#9e8860','#a79764')))
    return s


def hedge_finish(scene,shape):
    # A physical hedge still has its cross-section and torn leaf tips at the silhouette.
    # Map smaller overlapping leaves on vertical faces as well as the top.
    rng=np.random.default_rng(28126);size=384
    a=np.empty((size,size,3),dtype=np.uint8)
    a[:]=[100,130,63]
    im=Image.fromarray(a);draw=ImageDraw.Draw(im)
    for _ in range(7200):
        x,y=rng.integers(0,size,2)
        rx,ry=rng.uniform(2.0,5.0,2)
        theta=rng.uniform(0,math.tau)
        v=(rx*math.cos(theta),rx*math.sin(theta))
        w=(-.56*ry*math.sin(theta),.56*ry*math.cos(theta))
        c=rng.normal(0,13)
        tint=tuple(np.clip(np.array([118,146,66])+np.array([1,.86,.50])*c,0,255).astype(int))
        for xx in [x]+([x+size] if x<7 else [x-size] if x>size-7 else []):
            for yy in [y]+([y+size] if y<7 else [y-size] if y>size-7 else []):
                points=[(xx+v[0],yy+v[1]),(xx+w[0],yy+w[1]),(xx-v[0],yy-v[1]),(xx-w[0],yy-w[1])]
                draw.polygon(points,fill=tint)
    tex=add_image(scene,'图书馆方篱 · 近距叶片',im,'JPEG',True)
    shape.uvs={}
    for key,factor in zip(HEDGE,(.70,.85,.98,1.06)):
        verts,norms,_=shape.parts[key]
        uv=[]
        for (x,y,z),(nx,ny,nz) in zip(verts,norms):
            if abs(ny)>max(abs(nx),abs(nz)):
                q=(x/.92,z/.92)
            elif abs(nz)>abs(nx):q=(x/.92,y/.92)
            else:q=(z/.92,y/.92)
            uv.append(q)
        shape.uvs[key]=uv
        mat=scene.doc['materials'][scene.mat(key)]['pbrMetallicRoughness']
        mat.update(baseColorTexture=tex,baseColorFactor=[min(1,factor)]*3+[1],roughnessFactor=.91)


def build(scene,terrain,catalog):
    rng=random.Random(713)
    bedshape=Shape('图书馆南侧花园 · 修剪矮篱')
    bedshape.vertex_tints={}
    leaf_count=0
    ground=Shape('图书馆南侧花园 · 灰石园路与种植土')
    terrain.skin(ground,AREA.difference(unary_union(BEDS)),'#bbb9ad',.105)
    meshes=[scene.shape(flowering_tree(i)) for i in range(3)]
    count=0
    for i,bed in enumerate(BEDS):
        terrain.skin(ground,bed,'#a69c79',.072)
        border=bed.buffer(-.45).exterior
        _edge(bedshape,border,.88,.69,HEDGE,terrain,rng)
        leaf_count+=hedge_shoots(bedshape,border,terrain,i)
        a,c,b,d=bed.bounds
        for shift,delta in ((.27,.32),(.71,.30),(.52,.73)):
            x=a+shift*(b-a)+rng.uniform(-.25,.25);z=c+delta*(d-c)+rng.uniform(-.18,.18)
            sc=rng.uniform(.98,1.18)
            scene.node('图书馆南侧粉花树 '+str(count+1),mesh=meshes[(i+count)%3],
                       at=(x,terrain.y(x,z)+.06,z),yaw=rng.random()*math.tau,
                       scale=(sc,sc*rng.uniform(.90,1.07),sc),kind='flora',site='library-flower-court',
                       species='粉花小乔木（品种未定）',season='spring',canopyRadius=2.08*sc)
            assert bed.buffer(-1).contains(Point(x,z))
            count+=1
    scene.node(ground.name,shape=ground,kind='ground',site='library-flower-court')
    hedge_finish(scene,bedshape)
    scene.doc['materials'][scene.mat(SPROUT)]['pbrMetallicRoughness'].update(
        baseColorFactor=[1.,1.,1.,1.],roughnessFactor=.91,metallicFactor=0.)
    scene.node(bedshape.name,shape=bedshape,kind='landscape',vegetation=True,site='library-flower-court',
               pairedHedgeLeaves=leaf_count)
    def camera(x,z,h):
        return [x,round(terrain.y(x,z)+h,3),z]
    eye=camera(132.08,35.45,1.70); target=camera(132.08,14.0,1.93)
    catalog.append(dict(key='library-flower-court',name='图书馆南侧 · 粉花方格园',group='校园场地',aliases=['图书馆花园','图书馆花树','方格矮篱'],
                        x=133,y=terrain.y(133,19),z=19,h=4,r=24,
                        viewpoint=dict(eye=eye,target=target,fov=50),
                        views={'facade':dict(eye=[134,10,-5],target=[133,-.1,23],fov=52,label='图书馆南望花园'),
                               'path':dict(eye=eye,target=target,fov=50,label='沿方篱小径看花',hideMapLabels=True)},
                        note='由图书馆南面走进花园。多干粉花树种在矮篱格内，横纵石径从中穿过。花色据两张四月实拍，格网依据航片。'))
    return dict(beds=len(BEDS),trees=count,areaM2=round(AREA.area,1),
                narrowestInternalWalkM=round(min(b[0]-a[1] for a,b in zip(X_SPANS,X_SPANS[1:])),2),
                reference='https://livingatlas.arcgis.com/wayback/#active=3692&mapCenter=120.68353%2C36.36542%2C19')
