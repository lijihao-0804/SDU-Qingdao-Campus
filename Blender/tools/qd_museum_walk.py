"""Phoenix-to-laboratory walk beside the museum, based on the supplied ground photo."""
import math
import random

import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

from qd_geometry import Shape
from qd_planting import branch
from qd_terrain import sourcepolygon

KEY = 'museum-north-walk'
SOURCE_WAY = 'way/868002332'
PAVERS = '博物馆步道·窄缝灰色方砖'


def solar_lamp():
    s=Shape('博物馆步道 · 单臂太阳能灯')
    dark='#333839'
    s.cyl('铸铁柱脚',0,.18,0,.112,.36,dark,12)
    branch(s,(0,.34,0),(0,3.65,0),.071,.046,dark)
    for a,b in [((0,2.68,0),(.16,2.95,0)),((.16,2.95,0),(.44,3.03,0)),
                ((.44,3.03,0),(.84,3.03,0)),((.84,3.03,0),(.84,2.88,0))]:
        branch(s,a,b,.026,.023,dark)
    s.cyl('遮光灯罩',.84,2.85,0,.208,.084,dark,16)
    s.cyl('乳白色灯盘',.84,2.804,0,.17,.018,'#dcdccf',16)
    # Fixed south-facing photovoltaic cells. The silver rim and dark cells
    # have different extents and a shallow recess between them.
    def panel(x,z,lift=0):
        return (x,3.72-z*.56+lift,z)
    def plate(name,x0,z0,x1,z1,col,lift):
        pts=[panel(x0,z0,lift),panel(x0,z1,lift),panel(x1,z1,lift),panel(x1,z0,lift)]
        s.mesh(name,pts,[(0,1,2,3)],col)
    plate('铝合金板框',-.43,-.25,.43,.25,'#c6cac7',0)
    plate('光伏背板',-.404,-.224,.404,.224,'#b0b6ba',.006)
    for col in range(8):
        for row in range(5):
            x=-.397+col*.0995;z=-.219+row*.0878
            plate('蓝色电池片',x,z,x+.095,z+.082,'#384e69' if (row+col)%4 else '#4a5e77',.009)
    return s


def whitewashed_tree(variant):
    rng=random.Random(4930+variant)
    s=Shape('博物馆步道 · 白干落叶乔木 '+str(variant+1))
    bark='#696256'
    base=(0,-.03,0);paint_top=(.055,1.26,-.04)
    branch(s,base,paint_top,.128,.102,'#deded0')
    stem=paint_top
    for j in range(5):
        angle=rng.uniform(0,math.tau)
        next_stem=(stem[0]+.22*math.sin(angle),stem[1]+.87,stem[2]+.22*math.cos(angle))
        branch(s,stem,next_stem,.104-.017*j,.09-.017*j,bark)
        for k in range(2):
            hd=(j*2+k)*2.4+rng.uniform(-.25,.25)
            radius=rng.uniform(1.10,1.85)*(1-.11*j)
            knee=(stem[0]+.60*radius*math.sin(hd),stem[1]+.68,stem[2]+.60*radius*math.cos(hd))
            branch(s,stem,knee,.059-.006*j,.034-.003*j,bark)
            for hand in (-1,1):
                a=hd+hand*.47
                tip=(knee[0]+.53*radius*math.sin(a),knee[1]+rng.uniform(.65,1.17),knee[2]+.53*radius*math.cos(a))
                branch(s,knee,tip,.032-.003*j,.014,bark)
                for t in (-1,1):
                    az=a+t*.7
                    end=(tip[0]+.40*math.sin(az),tip[1]+rng.uniform(.37,.76),tip[2]+.40*math.cos(az))
                    branch(s,tip,end,.012,.0035,'#776f60')
        stem=next_stem
    return s


def grey_pavers(scene):
    rng=np.random.default_rng(6903)
    n=256
    yy,xx=np.mgrid[:n,:n]
    row=yy//64
    cellx=(xx+32*(row%2))%n
    field=rng.normal(0,2.2,(n,n))+np.array([[0,2,-3,1],[-2,2,0,3],[1,-2,2,0],[1,0,-2,2]])[row,cellx//64]
    seam=np.minimum(np.minimum(cellx%64,63-cellx%64),np.minimum(yy%64,63-yy%64))
    field-=np.where(seam==0,15,np.where(seam==1,6,0))
    rgb=np.stack((157+field,155+field,147+field),axis=2)
    from qd_spring_surfaces import add_image
    tex=add_image(scene,'博物馆步道 · 灰色步道砖',Image.fromarray(np.uint8(np.clip(rgb,0,255))),'PNG',True)
    mat=scene.doc['materials'][scene.colors[PAVERS]]['pbrMetallicRoughness']
    mat.update(baseColorFactor=[1,1,1,1],baseColorTexture=tex,roughnessFactor=.88)


class MuseumWalk:
    def __init__(self,data,road,walk):
        path=next(r for r in data['roads'] if r['id']==SOURCE_WAY)
        mapped=LineString(path['line'])
        if mapped.coords[0][1] > mapped.coords[-1][1]:
            mapped=LineString(list(mapped.coords)[::-1])
        self.line=substring(mapped,6,104)
        self.half=path['width']/2
        x,z=self.line.coords[0];a,b=self.line.coords[-1]
        self.forward=np.array([a-x,b-z])/self.line.length
        self.right=np.array([self.forward[1],-self.forward[0]])
        self.pavement=self.line.buffer(self.half,cap_style='flat').intersection(walk)
        self.plant_reserve=self.line.buffer(8.0,cap_style='flat')
        import qd_v6_alumni
        areas=qd_v6_alumni.layout(data)
        other=[sourcepolygon(r) for cat in ('buildings','parking','water') for r in data[cat]]
        self.blocked=unary_union([road,walk,areas['paths'],*other])

    def at(self,distance,lateral=0):
        p=self.line.interpolate(distance)
        x,z=np.array([p.x,p.y])+self.right*lateral
        return float(x),float(z)

    def build(self,scene,terrain,catalog):
        surf=Shape('博物馆北侧步道 · 灰砖与浅色路沿')
        inner=self.pavement.intersection(self.line.buffer(self.half-.12,cap_style='square'))
        terrain.skin(surf,inner,PAVERS,.17)
        terrain.skin(surf,self.pavement.difference(inner),'#c1c1b5',.17)
        verts=np.asarray(surf.parts[PAVERS][0])[:,[0,2]]
        surf.uvs={PAVERS:list(zip(verts@self.right/1.38,verts@self.forward/2.42))}
        scene.node(surf.name,shape=surf,kind='ground',walkKey=KEY,sourceWay=SOURCE_WAY)
        grey_pavers(scene)

        lamp=scene.shape(solar_lamp());trees=[scene.shape(whitewashed_tree(i)) for i in range(3)]
        neighbourhood=self.plant_reserve.buffer(4)
        occupied=[Point(n['translation'][0],n['translation'][2]) for n in scene.doc['nodes']
                  if n.get('extras',{}).get('kind')=='flora' and not n['extras'].get('shrub')
                  and neighbourhood.covers(Point(n['translation'][0],n['translation'][2]))]
        lamp_points=[];tree_points=[]
        for d in np.arange(6.,self.line.length-2,13.4):
            x,z=self.at(d,-self.half-.78)
            p=Point(x,z)
            if self.blocked.distance(p)<.22:continue
            lamp_points.append(p)
            scene.node('博物馆北侧步道 · 西列太阳能灯 '+str(len(lamp_points)),mesh=lamp,
                       at=(x,terrain.y(x,z)+.06,z),kind='walkFurniture',walkKey=KEY)
        for side in (-1,1):
            for j,d in enumerate(np.arange(4.+2.8*(side==1),self.line.length-1,7.2)):
                x,z=self.at(d,side*(4.60+.57*math.sin(j*.85+side)))
                p=Point(x,z)
                if self.blocked.distance(p)<1.15 or any(p.distance(q)<2.85 for q in occupied):continue
                sc=.87+.07*((j*7+side)%5)
                tree_points.append(p);occupied.append(p)
                scene.node('博物馆北侧步道 · 涂白行道树 '+str(len(tree_points)),mesh=trees[(j+side)%3],
                           at=(x,terrain.y(x,z)+.076,z),yaw=j*2.399,scale=(sc,sc,sc),
                           kind='flora',site=KEY,shrub=False)
        hedge=Shape('博物馆北侧步道 · 临路低篱')
        paint=('#88864f','#81804c','#93905a')
        length=self.line.length
        for j,d in enumerate(np.arange(.45,length-1.6,1.55)):
            edge=-self.half-.20
            footprint=Polygon([self.at(at,side) for at,side in
                               ((d,edge),(d,edge-1.30),(d+1.53,edge-1.30),(d+1.53,edge))])
            if footprint.intersects(self.blocked) or any(footprint.distance(p)<.14 for p in lamp_points):continue
            base=list(footprint.exterior.coords)[:-1]
            upper=[self.at(at,side) for at,side in ((d+.06,edge-.12),(d+.06,edge-1.14),
                                                   (d+1.47,edge-1.14),(d+1.47,edge-.12))]
            low=[(x,terrain.y(x,z)+.045,z) for x,z in base]
            high=[(x,terrain.y(x,z)+.47+.028*math.sin(j*.73+i),z) for i,(x,z) in enumerate(upper)]
            hedge.mesh('短修剪篱段',low+high,[(4,5,6,7)]+[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)],paint[j%3])
        scene.node(hedge.name,shape=hedge,kind='walkPlanting',walkKey=KEY)

        x,z=self.at(self.line.length-3)
        tx,tz=self.at(self.line.length-32,1.2)
        view=dict(eye=[x,terrain.y(x,z)+.17+1.62,z],
                  target=[tx,terrain.y(tx,tz)+1.80,tz],fov=43)
        catalog.append(dict(key=KEY,name='博物馆北侧步道 · 从凤凰居向实验楼',
                            x=x,y=terrain.y(x,z),z=z,h=5,r=49,group='校园场地',viewpoint=view,
                            note='沿校友广场西沿向北看，左侧太阳能路灯与修剪树篱随步道延伸。灰砖、灰白树干与灯具形制据补拍照片，拍摄点、株距和灯距为近似。'))
        return dict(sourceWay=SOURCE_WAY,photo='实景参照/校园补拍/博物馆北侧步道.jpg',
                    lengthMetres=round(self.line.length,2),pavedAreaM2=round(self.pavement.area,2),
                    lamps=len(lamp_points),whitewashedTrees=len(tree_points),viewpoint=view)
