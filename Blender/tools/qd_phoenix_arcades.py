"""Covered returns between the four Phoenix Garden arcades and six residential wings."""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from qd_terrain import sourcepolygon

ROOT=Path(__file__).resolve().parents[1]
# Hosts are ordered from the north end to the south end of each gallery.
HOSTS={
    'way/970257682':('way/970257676','way/970257677'),
    'way/970257683':('way/970257679','way/970257680'),
    'way/970257684':('way/970257677','way/970257678'),
    'way/970257685':('way/970257680','way/970257681'),
}
KEY='phoenix-connected-arcades'
GROUND='凤凰居四廊 · 通廊下透水铺地'

@lru_cache(maxsize=1)
def buildings():
    data=json.loads((ROOT/'data/map/campus.json').read_text('utf-8-sig'))
    return {r['id']:r for r in data['buildings']}

@lru_cache(maxsize=4)
def links(key):
    rows=buildings()
    core=sourcepolygon(rows[key])
    corners=sorted(core.exterior.coords[:-1],key=lambda pt:pt[1])
    ends=[]
    for sign,edge,host_id in zip((-1,1),(corners[:2],corners[2:]),HOSTS[key]):
        a,b=np.array(sorted(edge))
        u=(b-a)/np.linalg.norm(b-a)
        outward=sign*np.array([-u[1],u[0]])
        start=(a+b)*.5-outward*.42
        # Pick the actual long wall opposite this end, rather than a projecting
        # balcony or the remote bounding rectangle of the U-shaped building.
        host=sourcepolygon(rows[host_id])
        ring=list(host.exterior.coords)
        long_edges=[LineString((p,q)) for p,q in zip(ring,ring[1:]) if abs(q[0]-p[0])>30]
        edge_line=min(long_edges,key=lambda line:line.distance(LineString((a,b))))
        c,d=np.array(sorted(edge_line.coords))
        wall_unit=(d-c)/np.linalg.norm(d-c)
        inside=sign*np.array([-wall_unit[1],wall_unit[0]])
        width=7.4
        # The west 9th residence is staggered: its gallery returns inland far
        # enough for the entire end section to land on the masonry wall.
        station=np.clip((start-c)@wall_unit,width/2+1.0,np.linalg.norm(d-c)-width/2-1.0)
        end=c+station*wall_unit+inside*.85
        ring=[start-u*width/2,start+u*width/2,end+wall_unit*width/2,end-wall_unit*width/2]
        ends.append((host_id,Polygon(ring),core.distance(host)))
    return tuple(ends)

def cover_plan(key):
    return unary_union([sourcepolygon(buildings()[key]),*(p for _,p,_ in links(key))])

def add_returns(shape,row,h):
    from qd_arch_spring import Facade, arch_loop, reveal, BRICK_S, CREAM, COURT
    from qd_residence_roofs import surface, walls
    x,z=row['center']
    for host_id,world,_ in links(row['id']):
        poly=translate(world,-x,-z)
        corners=list(poly.exterior.coords)
        # Only the two longitudinal sides carry piers. The end sections are
        # open at the existing arcade entrance and concealed inside the host.
        for p,q in ((corners[1],corners[2]),(corners[3],corners[0])):
            if not poly.exterior.is_ccw:p,q=q,p
            fr=Facade(shape,p,q)
            count=max(1,round(fr.length/5.4))
            pitch=fr.length/count
            holes=[]
            for i in range(count):
                clear=pitch-.72
                loop=arch_loop((i+.5)*pitch-fr.length/2,-2.2,clear,4.42-clear*.13,clear*.13)
                holes.append(loop)
                reveal(fr,loop,.35,True)
            fr.cut_wall(holes,h-.22,BRICK_S,base=-2.24)
        rim=poly.buffer(.13,join_style='mitre')
        walls(shape,'接翼连廊 · 浅色檐边',rim,h-.37,h-.20,CREAM)
        surface(shape,'接翼连廊 · 廊顶内底',rim,h-.37,CREAM,up=False)
        surface(shape,'平屋面',rim,h-.20,COURT)
        for p,q in ((corners[1],corners[2]),(corners[3],corners[0])):
            fr=Facade(shape,p,q)
            fr.block('接翼连廊 · 砖面压顶',0,h-.08,0.,fr.length,.24,.22,BRICK_S)

def add_view(catalog,terrain):
    eye=(309.,882.);target=(274.,892.)
    pose={'eye':[eye[0],terrain.y(*eye)+15.5,eye[1]],
          'target':[target[0],terrain.y(*target)+4.6,target[1]],'fov':63}
    catalog.append(dict(key=KEY,name='凤凰居 · 五号楼与九号楼接翼拱廊',
                        x=target[0],y=terrain.y(*target),z=target[1],r=25,h=8,
                        group='院楼与生活区',viewpoint=pose,
                        note='低层平顶回廊由中段红瓦屋体接到两侧宿舍翼楼，柱间保留穿行拱洞。'))
    eye=(276.5,894.8);target=(273.6,870.5)
    pose={'eye':[eye[0],terrain.y(*eye)+1.81,eye[1]],
          'target':[target[0],terrain.y(*target)+2.15,target[1]],'fov':69}
    catalog.append(dict(key='phoenix-arcade-walk',name='凤凰居 · 廊下望五号楼',
                        x=target[0],y=terrain.y(*target),z=target[1],r=16,h=5,
                        group='院楼与生活区',viewpoint=pose,
                        note='在中段拱廊下向北看，开敞券洞和低平檐一直延伸至五号楼。'))
