"""Local campus grading. Subdivide only the college quadrangles, matching the original TIN at the seam."""
import numpy as np
from shapely import points, distance
from shapely.geometry import box, Point, LineString
from shapely.ops import unary_union,nearest_points
from qd_terrain import Terrain

def refine(terrain, footprints, transition=24):
    outlines=list(footprints); limit=unary_union(outlines).buffer(transition+3).bounds
    st=terrain.step; step=st/7
    left=terrain.x0+np.floor((limit[0]-terrain.x0)/st)*st
    top=terrain.z0+np.floor((limit[1]-terrain.z0)/st)*st
    right=terrain.x0+np.ceil((limit[2]-terrain.x0)/st)*st
    bottom=terrain.z0+np.ceil((limit[3]-terrain.z0)/st)*st
    region=box(left,top,right,bottom)
    grid=Terrain.__new__(Terrain)
    grid.x0=left;grid.z0=top;grid.step=step
    xs=np.arange(left,right+step*.5,step);zs=np.arange(top,bottom+step*.5,step)
    XX,ZZ=np.meshgrid(xs,zs); xy=points(XX,ZZ)
    orig_y=terrain.y;orig_skin=terrain.skin
    original=np.array([[orig_y(x,z) for x in xs] for z in zs])
    heights=original.copy();strongest=np.zeros_like(original)
    for p in outlines:
        d=distance(xy,p)
        valid=d<2
        level=float(np.median(original[valid])) if valid.any() else orig_y(*p.representative_point().coords[0])
        u=np.clip((transition-d)/(transition-10),0,1);weight=u*u*(3-2*u)
        use=weight>strongest
        heights[use]=original[use]*(1-weight[use])+level*weight[use]
        strongest[use]=weight[use]
    grid.heights=heights
    def elevation(x,z):
        return grid.y(x,z) if left<=x<right and top<=z<bottom else orig_y(x,z)
    def surface(shape,geom,material,lift=0):
        if not geom.intersects(region):return orig_skin(shape,geom,material,lift)
        grid.skin(shape,geom.intersection(region),material,lift)
        orig_skin(shape,geom.difference(region),material,lift)
    terrain.y=elevation;terrain.skin=surface
    return grid


def aprons(places, footprints, pavement, obstacles):
    """Bridge each modeled stair to the adjoining walking surface where geometry permits."""
    pieces=[]
    for loc in places:
        if loc.get('group')!='学院楼':continue
        door=loc['views']['entrance']['target'];nx,nz=loc['normal'];x,z=door[0],door[2]
        prev=Point(x+nx*1.2,z+nz*1.2); toe=Point(x+nx*8.5,z+nz*8.5)
        axis=LineString([prev,toe]); width=3.3
        near=nearest_points(toe,pavement)[1]
        if 0.5<near.distance(toe)<33 and (near.x-x)*nx+(near.y-z)*nz>6:
            segment=LineString([toe,near]);obstructed=obstacles.intersection(segment).length
            if obstructed<.1:axis=LineString([prev,toe,near])
        pieces.append(axis.buffer(width,cap_style=2,join_style=1))
    if not pieces:return None
    return unary_union(pieces).difference(pavement).difference(footprints)

