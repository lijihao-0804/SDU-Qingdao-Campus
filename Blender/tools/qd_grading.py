"""Grade continuous landmark pads before triangulating the campus DEM.

Model coordinates are X east, Y up, Z south. Elevations within a pad are
engineering approximations based on the surrounding DEM. Each terrain grid
cell touched by the model has all four corners at the same target level.
"""
import math

import numpy as np
from scipy.ndimage import distance_transform_edt
from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep


GRADED = {'west_gate','north_gate','east_gate','south_gate','way-982199336','blue_track','east_track','song_arena',
          'yuxian','library','museum'}


def site_lift(key):
    """Node base relative to the graded terrain; positive Y is up."""
    if key in ('blue_track','east_track'):
        # The running surface has its own 14 cm base layer.
        return -.13
    from qd_teaching_courts import KEYS,FLOOR,ROAD_LIFT
    if key in KEYS:
        return ROAD_LIFT-FLOOR
    if key == 'yuxian':
        return .08
    if key in GRADED:
        return .005
    return .23


def _local_footprint(module, spec):
    w, d = spec['w'], spec['d']
    key = spec['key']
    if key in ('blue_track','east_track'):
        # Capsule perimeter has slight longitudinal flattening in qd_civic.pitch.
        radius, end_radius = w*.49, w*.48
        straight = d/2-end_radius
        outlined = [(radius*math.cos(t), z+end_radius*math.sin(t))
                    for z,start in ((straight,0),(-straight,math.pi))
                    for t in (start+i*math.pi/32 for i in range(33))]
        return Polygon(outlined)
    if key == 'song_arena' and hasattr(module,'ROOF'):
        # The OSM stadium outline includes unrelated open apron. Grade the
        # silhouette of the built canopy including the long north extension.
        sections=module.ROOF
        pts=[((l-181.5)*w/109,(z-269)*d/430) for z,l,r in sections]
        pts.extend(((r-181.5)*w/109,(z-269)*d/430) for z,l,r in reversed(sections))
        return Polygon(pts).buffer(3)
    # The step and sill edges project a few metres beyond the nominal walls.
    margin=4.5 if key in ('library','museum') else 1.5
    return box(-w/2-margin,-d/2-margin,w/2+margin,d/2+margin)


def _vertices_for_pad(terrain, poly):
    """Include all vertices needed by BOTH TIN triangles in each touched cell."""
    st=terrain.step
    shape=terrain.heights.shape
    xmin,zmin,xmax,zmax=poly.bounds
    i0=max(0,math.floor((xmin-terrain.x0)/st)-1)
    i1=min(shape[1]-1,math.ceil((xmax-terrain.x0)/st)+1)
    j0=max(0,math.floor((zmin-terrain.z0)/st)-1)
    j1=min(shape[0]-1,math.ceil((zmax-terrain.z0)/st)+1)
    core=np.zeros(shape,dtype=bool)
    test=prep(poly)
    for j in range(j0,j1):
        z=terrain.z0+j*st
        for i in range(i0,i1):
            x=terrain.x0+i*st
            if test.intersects(box(x,z,x+st,z+st)):
                core[j:j+2,i:i+2]=True
    return core


def _ordinary_pads(data, specs):
    # Apply the pre-existing grading to buildings, courts and water that are
    # independent of the source footprints superseded by the landmark models.
    ignored=set()
    excluded_names=set()
    for _,s,_,_,_ in specs:
        if s['key'] not in GRADED:
            continue
        for token in [s.get('osm',''), *s.get('replaces',())]:
            if token:
                ignored.add(str(token).split('/')[-1])
        excluded_names.update([s['name'],*s.get('aliases',())])
    pads=[]
    for category in ('buildings','pitches','water'):
        for row in data.get(category,()):
            if str(row['id']).split('/')[-1] in ignored or row.get('name') in excluded_names:
                continue
            shape=Polygon(row['poly'],row.get('holes',())).buffer(0)
            if shape.area>90:
                pads.append(shape)
    pads.extend(foot for _,spec,_,_,foot in specs if spec['key'] not in GRADED)
    return pads


def apply_grading(terrain,data,specs):
    """Replace the original general level_pads call; return JSON-safe pad metadata."""
    specs=list(specs)
    # Retain the local natural elevation before legacy building pads are applied.
    natural=terrain.heights.copy()
    ordinary=_ordinary_pads(data,specs)
    if ordinary:
        terrain.level_pads(ordinary)
    groups=[]
    for module,s,x,z,_ in specs:
        if s['key'] not in GRADED:
            continue
        local=_local_footprint(module,s)
        poly=translate(rotate(local,-math.degrees(s.get('yaw',0)),origin=(0,0)),x,z)
        support=_vertices_for_pad(terrain,poly.buffer(2.))
        if not support.any():
            continue
        # Sharing even one grid vertex would otherwise break flatness. Joined
        # objects (e.g. blue running track and canopy) get one surveyed-area proxy.
        shared=[g for g in groups if np.any(g['support'] & support)]
        keys=[s['key']]
        polygons=[poly]
        for g in shared:
            keys+=g['keys']
            polygons+=g['polygons']
            support|=g['support']
        groups=[g for g in groups if not any(g is other for other in shared)]
        groups.append(dict(keys=keys,polygons=polygons,support=support))
    if not groups:
        return []
    base=terrain.heights.copy()
    weighted=np.zeros_like(base)
    weight_sum=np.zeros_like(base)
    influence=np.zeros_like(base)
    reports=[]
    for group in groups:
        core=group['support']
        # Median of the original DEM under the actual footprint. Fall back to
        # supporting vertices for narrow gate pads with no grid point inside.
        geom=unary_union(group['polygons'])
        js,is_=np.nonzero(core)
        from shapely import intersects_xy
        valid=intersects_xy(geom,terrain.x0+is_*terrain.step,terrain.z0+js*terrain.step)
        samples=natural[js[valid],is_[valid]] if np.any(valid) else natural[core]
        elevation=float(np.median(samples))
        group['height']=elevation
        distances=distance_transform_edt(~core,sampling=terrain.step)
        t=np.clip(1.-distances/62.,0.,1.)
        weights=t*t*(3.-2.*t)
        weighted+=weights*elevation
        weight_sum+=weights
        influence=np.maximum(influence,weights)
        reports.append(dict(keys=group['keys'],height=elevation,terrainVertices=int(core.sum()),
                            transitionMetres=62))
    mix=np.divide(weighted,weight_sum,out=base.copy(),where=weight_sum>0)
    terrain.heights[:]=base*(1.-influence)+mix*influence
    for group in groups:
        terrain.heights[group['support']]=group['height']
    if any(s['key']=='song_arena' for _,s,_,_,_ in specs):
        from qd_arena_slope import install
        install(terrain,specs)
    return reports

