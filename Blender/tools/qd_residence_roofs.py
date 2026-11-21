"""Footprint roof shells with positive top normals, outward fascias and measured overhangs."""
import math

import mapbox_earcut as ear
import numpy as np
from shapely.geometry import Point, box
from shapely.geometry.polygon import orient

from qd_terrain import polygons


def surface(shape,name,geometry,level,material,up=True):
    for polygon in polygons(geometry):
        p=orient(polygon,1)
        rings=[list(r.coords)[:-1] for r in (p.exterior,*p.interiors)]
        xy=np.asarray([v for r in rings for v in r],np.float64)
        tri=ear.triangulate_float64(xy,np.cumsum([len(r) for r in rings],dtype=np.uint32)).reshape(-1,3)
        vertices=[(x,level(x,z) if callable(level) else level,z) for x,z in xy]
        shape.mesh(name,vertices,tri[:,::-1] if up else tri,material)


def walls(shape,name,geometry,bottom,top,material,inward=False):
    for polygon in polygons(geometry):
        p=orient(polygon,1)
        for ring in (p.exterior,*p.interiors):
            points=list(ring.coords)[:-1]
            n=len(points)
            vs=[(x,y,z) for y in (bottom,top) for x,z in points]
            quads=[(i,n+i,n+(i+1)%n,(i+1)%n) for i in range(n)]
            shape.mesh(name,vs,[q[::-1] for q in quads] if inward else quads,material)


def eave(shape,footprint,rim,wall_h,top,material):
    bottom=wall_h-.14
    walls(shape,'外檐封边',rim,bottom,top,material)
    surface(shape,'檐下封底',rim.difference(footprint),bottom,material,up=False)


def terrace(shape,footprint,h,material,curb=None,abuts=None):
    surface(shape,'平屋面',footprint,h,material)
    if not curb:
        return
    # The protective parapet occupies a narrow strip. Its middle remains a usable deck.
    inside=footprint.buffer(-.18,join_style=2)
    if inside.is_empty:
        return
    ring=footprint.difference(inside)
    if abuts is not None:
        ring=ring.difference(abuts.buffer(.205,join_style=2))
    walls(shape,'露台女儿墙内外面',ring,h,h+.42,curb)
    surface(shape,'女儿墙压顶',ring,h+.42,curb)


def inradius(p):
    x0,z0,x1,z1=p.bounds
    lo,hi=0.,min(x1-x0,z1-z0)/2
    for _ in range(16):
        mid=(lo+hi)/2
        if p.buffer(-mid,join_style=2).is_empty:hi=mid
        else:lo=mid
    return lo


def slope_band(shape,band,active,inner,low,high,material):
    from shapely import covers, delaunay_triangles, get_parts, intersection, intersects
    outer_edge,inner_edge=active.boundary,inner.boundary
    verts=[];faces=[]
    height_cache={}
    def height(x,z):
        key=(x,z)
        if key not in height_cache:
            point=Point(x,z)
            a,b=outer_edge.distance(point),inner_edge.distance(point)
            height_cache[key]=low+(high-low)*a/max(a+b,1.e-12)
        return height_cache[key]
    for p in polygons(band):
        tiled=get_parts(delaunay_triangles(p.segmentize(2.40)))
        # GEOS 3.11 can raise NumPy divide warnings inside otherwise valid predicates
        # on coincident curved-offset endpoints. Retain all the clipped polygon pieces.
        with np.errstate(divide='ignore',invalid='ignore'):
            fully=covers(p,tiled)
            chunks=list(tiled[fully])
            partial=tiled[~fully]
            if len(partial):
                for geom in intersection(partial[intersects(p,partial)],p):
                    if geom.is_empty:continue
                    for part in get_parts(geom):
                        if part.geom_type=='Polygon' and part.area>1.e-10:
                            chunks.append(part)
        for part in chunks:
            ring=list(part.exterior.coords)[:-1]
            if len(ring)<3:continue
            if len(ring)==3:
                ids=[(0,1,2)] if not part.exterior.is_ccw else [(2,1,0)]
            else:
                if part.exterior.is_ccw:ring.reverse()
                rs=[ring]+[list(h.coords)[:-1] for h in part.interiors]
                ring=[v for points in rs for v in points]
                ids=ear.triangulate_float64(np.asarray(ring),np.cumsum([len(v) for v in rs],dtype=np.uint32)).reshape(-1,3)[:,::-1]
            off=len(verts)
            verts.extend((x,height(x,z),z) for x,z in ring)
            faces.extend(tuple(off+int(v) for v in ids_) for ids_ in ids)
    shape.mesh('铺瓦坡面',verts,faces,material)


def graded_slopes(shape,rim,h,run,gradient,material):
    """Nested contour strips keep concave hips watertight and the pitch continuous."""
    active=rim
    count=max(1,math.ceil(run/1.5))
    for i in range(1,count+1):
        d=i*run/count
        inner=rim.buffer(-d,join_style=2)
        low=h+(i-1)*run/count*gradient
        if inner.is_empty:
            surface(shape,'铺瓦坡面',active,low,material)
        else:
            slope_band(shape,active.difference(inner),active,inner,low,h+d*gradient,material)
        active=inner
        if active.is_empty:break
    return active


def full_hip(shape,footprint,h,tile,fascia):
    for p in polygons(footprint):
        rim=p.buffer(.42,join_style=2)
        eave(shape,p,rim,h,h+.075,fascia)
        # Leave a narrow sealed ridge roll even on the widest local junction.
        run=max(.17,inradius(rim)-.105)
        ridge=graded_slopes(shape,rim,h+.075,run,.355,tile)
        surface(shape,'瓦脊收口',ridge,h+.075+run*.355,tile)


def pitched_deck(shape,footprint,h,width,rise,tile,deck,fascia,drop):
    """Use one shared inner contour for the tiled collar, inward reveal and deck."""
    wells=[]
    for p in polygons(footprint):
        rim=p.buffer(.42,join_style=2)
        run=min(width,max(.12,inradius(rim)*.86))
        eave(shape,p,rim,h,h+.075,fascia)
        inner=graded_slopes(shape,rim,h+.075,run,rise/run,tile)
        if inner.is_empty:continue
        crest=h+.075+rise
        floor=crest-drop
        if drop>.001:
            walls(shape,'设备平台内侧泛水',inner,floor,crest,'#997968',inward=True)
        surface(shape,'屋顶平台防水层',inner,floor,deck)
        wells.append((inner,floor,crest))
    return wells


def phoenix_tips(p):
    # The six open-ended U plans face the central flower axis in mirrored rows.
    x0,z0,x1,z1=p.bounds
    east=p.centroid.x<(x0+x1)/2
    length=6.25
    strip=box(x1-length,z0-1,x1+1,z1+1) if east else box(x0-1,z0-1,x0+length,z1+1)
    return p.difference(strip),p.intersection(strip)


def expert_equipment(shape,deck,level,key):
    """Low roof strips and curb-mounted service housings seen on the eight expert apartments."""
    from shapely.geometry import Polygon
    panel_roofs={'way/970257688','way/970257687','way/970257686','s2/south-t6','s2/south-t7'}
    for p in polygons(deck):
        corners=list(p.minimum_rotated_rectangle.exterior.coords)
        (x0,z0),(x1,z1)=max(zip(corners,corners[1:]),key=lambda pair:math.dist(*pair))
        length=math.hypot(x1-x0,z1-z0)
        ux,uz=(x1-x0)/length,(z1-z0)/length
        if ux<0:ux,uz=-ux,-uz
        cx,cz=p.centroid.coords[0]
        yaw=-math.atan2(uz,ux)
        def point(u,v):
            return cx+u*ux-v*uz,cz+u*uz+v*ux
        cross=[(x-cx)*(-uz)+(z-cz)*ux for x,z in corners[:-1]]
        mid=(max(cross)+min(cross))/2
        if key in panel_roofs:
            rows=2 if max(cross)-min(cross)>7.8 else 1
            for j in range(rows):
                v=mid+(j-(rows-1)/2)*2.40
                for i,u in enumerate(np.arange(-.45*length,.45*length,3.10)):
                    if i%9==8:continue
                    footprint=Polygon([point(u+a,v+b) for a,b in
                                       [(-1.44,-.98),(-1.44,.98),(1.44,.98),(1.44,-.98)]])
                    if not p.covers(footprint):continue
                    x,z=point(u,v)
                    shape.box('公寓屋顶组件基座',x,level+.14,z,.76,.28,1.37,'#858986',yaw)
                    shape.box('公寓中央屋面板件',x,level+.305,z,2.88,.07,1.96,'#52626a',yaw)
                    shape.box('公寓板件中缝',x,level+.351,z,.045,.020,1.96,'#99a3a0',yaw)
        else:
            for u in (-.36*length,-.12*length,.12*length,.36*length):
                footprint=Polygon([point(u+a,mid+b) for a,b in [(-2.6,-1.2),(-2.6,1.2),(2.6,1.2),(2.6,-1.2)]])
                if not p.covers(footprint):continue
                x,z=point(u,mid)
                shape.box('公寓平顶设备基座',x,level+.10,z,5.18,.20,2.40,'#898b85',yaw)
                shape.box('公寓浅色机房盖板',x,level+.51,z,4.80,.64,2.03,'#c2bdb0',yaw)
                shape.box('公寓机房压顶',x,level+.87,z,4.98,.09,2.19,'#a4a69f',yaw)


def exact_top(shape):
    return max(v[1] for vs,_,_ in shape.parts.values() for v in vs)

