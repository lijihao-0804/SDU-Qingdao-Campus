"""Measured plan of Huiwen Square: the paired academic wings share its garden forecourt.

Local WGS84-derived campus metres (X east, Z south). OSM way/981132251 is the
outer polygon. The 2019 Zhou Qingxian aerial in 实景参照/会文与淦昌 and the campus
OSM paths give the cross axis, oval and garden edges. The garden dimensions
and species/crown count are inferred. The later library photograph also resolves
the two bands of central turf and the hue and curvature of the western oval.
"""
import math

from shapely.affinity import scale
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import qd_huiwen_axis as axis
from qd_geometry import Shape
from qd_planting import prototype
from qd_terrain import polygons


OSM_ID = 'way/981132251'
AXIS_X, AXIS_Z = 454.7, -62.0


def ellipse(x,z,rx,rz):
    return scale(Point(x,z).buffer(1,quad_segs=26),rx,rz,origin=(x,z))


class HuiwenSquare:
    def __init__(self, footprint, mapped_walks, roads):
        self.site=footprint.union(axis.WEST_FORECOURT).difference(roads.buffer(.02))
        mapped_walks=mapped_walks.intersection(self.site.buffer(1.0))
        gardens=self.site.buffer(-3.1,join_style=2)
        self.crossing=box(AXIS_X-18.4,AXIS_Z-12.1,AXIS_X+18.4,AXIS_Z+12.1)
        west_approach=axis.OVAL_WALK
        western_arc=LineString([(323.5,-83.0),(334,-82.1),(342,-80.7),(350,-77.9),
                                (357,-74.8),(362.5,-70.8),(366.8,-66.3),(369.2,-62),
                                (367.2,-55.6),(363.2,-50.3),(358,-46.4),(351,-42.8),
                                (342,-39.9),(333,-38.3),(324,-37.9)]).buffer(.82)
        western_bed=ellipse(354.1,AXIS_Z,8.5,8.9).intersection(box(354.1,-75,367,-47))
        east_approach=Polygon([(528,-74),(548,-79),(548,-44),(528,-49)])
        east_west=box(310,AXIS_Z-7.9,548,AXIS_Z+7.9)
        north_south=box(AXIS_X-5.8,-111,AXIS_X+5.8,-14)
        north_entry=box(365.8,-111,375.9,-87)
        crossing_west=box(372.7,-106,377.2,-16)
        self.routes=unary_union([mapped_walks.buffer(.18),west_approach,western_arc,east_approach,
                                 east_west,north_south,north_entry,crossing_west,axis.WEST_PATHS,
                                 self.crossing]).intersection(self.site)
        # The large lawns are separately clipped to every surveyed oval/diagonal
        # path. This makes the path graph continuous through all four quadrants.
        self.lawns=gardens.difference(self.routes)
        self.lawns=unary_union([p for p in polygons(self.lawns) if p.area>3.2]+[western_bed])
        plant_rows=[]
        for left,right in ((249.9,282.9),(368.0,436.0),(473.7,528.0)):
            for side in (-1,1):
                z=AXIS_Z+side*6.65
                plant_rows.append(box(left,z-.69,right,z+.69))
        # The crossing is a paved rectangle, with low corner beds and central inlay.
        for dx in (-1,1):
            for dz in (-1,1):
                x,z=AXIS_X+13.0*dx,AXIS_Z+7.4*dz
                plant_rows.append(box(x-1.9,z-.46,x+1.9,z+.46))
                plant_rows.append(box(x+1.54*dx-.36,z-.94,x+1.54*dx+.36,z+.94))
        for dz in (-4.3,0,4.3):
            plant_rows.append(ellipse(359.65,AXIS_Z+dz,1.05,.98))
        raw_rows=unary_union(plant_rows).intersection(self.site)
        self.hedges=raw_rows.difference(mapped_walks.buffer(.28)).difference(crossing_west).difference(axis.WEST_CROSS)
        self.axial_lawns=axis.axial_lawns(mapped_walks).intersection(self.site)
        self.lawns=self.lawns.union(self.axial_lawns).difference(self.hedges)
        self.islands=unary_union([self.lawns,self.hedges])
        self.paved=self.site.difference(self.islands)
        self.inlay=box(AXIS_X-8.15,AXIS_Z-2.05,AXIS_X+8.15,AXIS_Z+2.05)
        self.tree_count=0

    def tree_sites(self,door_corridors):
        # A trunk is planted only where the entire estimated canopy clears a path.
        keep_clear=self.lawns.buffer(-3.8)
        if door_corridors:
            keep_clear=keep_clear.difference(unary_union(door_corridors).buffer(1.6))
        sites=[]
        for band,z in enumerate((-91.5,-81.8,-41.3,-31.5)):
            for col in range(-5,14):
                x=332+(col*15.4)+(3.5 if band%2 else 0)
                px=x+1.4*math.sin(col*3.2+band)
                pz=z+1.3*math.cos(col+band*2.1)
                if keep_clear.covers(Point(px,pz)):
                    sites.append((px,pz,(col+2*band)%3))
        return sites

    def build(self,scene,terrain,door_corridors):
        ground=Shape('会文广场 · 园路铺装')
        inset=self.inlay.intersection(self.paved)
        frame=self.crossing.boundary.buffer(.29,cap_style=2,join_style=2).intersection(self.paved)
        # A small change of paving tone defines the central crossing and the east-west route.
        axial=box(315,AXIS_Z-5.15,549,AXIS_Z+5.15).intersection(self.paved)
        oval_finish=axis.BLUE_OVAL.buffer(.38).intersection(self.paved)
        main=self.paved.difference(frame).difference(inset).difference(oval_finish)
        axis.draw_oval(ground,terrain,self.paved)
        terrain.skin(ground,main.difference(axial),'#c3beb0',.17)
        terrain.skin(ground,main.intersection(axial),'#beb59f',.17)
        terrain.skin(ground,frame,'#9d9b8c',.17)
        thin=inset.boundary.buffer(.13,cap_style=2,join_style=2).intersection(inset)
        terrain.skin(ground,inset.difference(thin),'#aaa994',.17)
        terrain.skin(ground,thin,'#c3bfa9',.17)
        scene.node('会文广场 · 十字步道与中心铺石',shape=ground,kind='ground')

        soft=Shape('会文广场 · 园圃')
        turf=self.lawns.buffer(-.24,join_style=2)
        terrain.skin(soft,self.lawns.difference(turf),'#a7aa8b',.19)
        trees=self.tree_sites(door_corridors)
        pits=[box(x-1.22,z-1.22,x+1.22,z+1.22) for i,(x,z,k) in enumerate(trees) if i%3==0]
        self.sward=turf.difference(unary_union(pits))
        terrain.skin(soft,self.sward,'#87a173',.185)
        # Raised hedge tops and sides follow the same TIN as the adjoining paving.
        terrain.skin(soft,self.hedges,'#73875b',.655)
        for p in polygons(self.hedges):
            for ring in (p.exterior,*p.interiors):
                points=list(ring.coords)
                for a,b in zip(points,points[1:]):
                    n=max(1,math.ceil(math.dist(a,b)/2.4))
                    for i in range(n):
                        t0,t1=i/n,(i+1)/n
                        x,z=a[0]+(b[0]-a[0])*t0,a[1]+(b[1]-a[1])*t0
                        xx,zz=a[0]+(b[0]-a[0])*t1,a[1]+(b[1]-a[1])*t1
                        y,yy=terrain.y(x,z),terrain.y(xx,zz)
                        soft.mesh('整形低篱侧面',[(x,y+.145,z),(xx,yy+.145,zz),
                                  (xx,yy+.655,zz),(x,y+.655,z)],[(0,3,2,1)],'#697e57')
        for i,(x,z,k) in enumerate(trees):
            if i%3==0:
                pit=box(x-1.22,z-1.22,x+1.22,z+1.22)
                soil=box(x-1.07,z-1.07,x+1.07,z+1.07)
                terrain.skin(soft,pit.difference(soil),'#a3a28c',.215)
                terrain.skin(soft,soil,'#857c65',.205)
        scene.node('会文广场 · 园块与修剪绿篱',shape=soft,kind='ground')
        choices=[scene.shape(prototype(k)) for k in (0,1,2)]
        for i,(x,z,k) in enumerate(trees):
            sc=.56+.04*((i*7)%4)
            scene.node('会文广场园圃小乔木 '+str(i+1),mesh=choices[k],
                       at=(x,terrain.y(x,z)+.176,z),yaw=(i*2.399)%math.tau,
                       scale=(sc*.88,sc,sc*.88),kind='flora',species=k,shrub=False)
        self.tree_count=len(trees)
        return self.tree_count
