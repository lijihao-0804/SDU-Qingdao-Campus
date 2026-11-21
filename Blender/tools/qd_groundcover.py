"""Near-ground planting, in metre units, for the Qingdao campus scene.

Tufts share a small set of meshes. Each patch lies on the local DEM facet,
or on the known top surface of a raised, modelled lawn at Yuxian Square.
"""
import math
import random

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

from qd_geometry import Shape


def prototype(family, variant):
    rng = random.Random(46171 + 231 * family + variant)
    shape = Shape(('草坪草', '疏草', '林缘地被')[family] + str(variant + 1))
    palettes = [
        ('#7e9a61', '#97ac6d'),
        ('#758c59', '#a7ac73'),
        ('#71875c', '#8e9f6b'),
    ]
    colors = palettes[family]
    radius = (1.65, 3.10, 3.30)[family]
    tuft_count = (60, 61, 51)[family]
    blades = 0
    leaves = 0
    for tuft in range(tuft_count):
        angle = rng.uniform(0, math.tau)
        r = radius * math.sqrt(rng.random())
        cx, cz = math.cos(angle) * r, math.sin(angle) * r
        tuft_scale = rng.uniform(.76, 1.25)
        height = (.115, .24, .32)[family] * tuft_scale
        for blade in range(rng.randrange(5, 8)):
            a = angle + blade * 2.39996 + rng.uniform(-.8, .8)
            vx, vz = math.cos(a), math.sin(a)
            h = height * rng.uniform(.60, 1.29)
            bend = h * rng.uniform(.32, 1.04)
            spread = rng.uniform(.007, .055)
            x, z = cx + spread * vx, cz + spread * vz
            width = (.012, .018, .024)[family] * rng.uniform(.47, 1.04)
            dx, dz = -vz * width / 2, vx * width / 2
            # A curved tapered strip; the root runs slightly into the host lawn.
            v = [(x-dx, -.028, z-dz), (x+dx, -.028, z+dz),
                 (x+vx*bend*.31+dx*.71, h*.62, z+vz*bend*.31+dz*.71),
                 (x+vx*bend*.31-dx*.71, h*.62, z+vz*bend*.31-dz*.71),
                 (x+vx*bend, h, z+vz*bend)]
            shape.mesh('弯曲叶片', v, [(0,1,2,3),(3,2,4)], colors[(tuft+blade//3)%2])
            blades += 1
        if family == 2 and tuft % 2 == 0:
            # Low, spreading broadleaves with a raised midrib, beneath the grasses.
            for k in range(4):
                a = k * math.pi / 2 + angle + rng.uniform(-.3,.3)
                vx, vz = math.cos(a), math.sin(a)
                span, hw = rng.uniform(.105,.18), rng.uniform(.024,.048)
                mx, mz = cx+vx*span*.54, cz+vz*span*.54
                h = rng.uniform(.03,.075)
                v = [(cx,.002,cz),(mx-vz*hw,h*.75,mz+vx*hw),
                     (mx,h,mz),(mx+vz*hw,h*.70,mz-vx*hw),
                     (cx+vx*span,h*.65,cz+vz*span)]
                shape.mesh('地被叶中脊',v,[(0,1,2),(0,2,3),(1,4,2),(2,4,3)],colors[k%2])
                leaves += 1
    triangles = sum(len(indices)//3 for _,_,indices in shape.parts.values())
    extent = max(math.hypot(x,z) for vertices,_,_ in shape.parts.values() for x,_,z in vertices)
    return shape, blades, leaves, triangles, extent


def square_lawns(data):
    """Planted beds only, using the same dimensions as qd_civic.plaza."""
    from qd_civic import SPECS
    spec = next((s for s in SPECS if s['key'] == 'yuxian'), None)
    if not spec or not any(r.get('name') == '育贤广场' for r in data.get('plazas',[])):
        return None
    metadata = data['metadata']
    origin, m = metadata['origin'], metadata['metres_per_degree']
    x = (spec['lon'] - origin['lon']) * m['longitude']
    z = (origin['lat'] - spec['lat']) * m['latitude']
    w, d = spec['w'], spec['d']
    lawn = unary_union([box(x+w*left,z-d*.27,x+w*right,z+d*.27)
                        for left,right in ((-.485,-.23),(-.207,.045),(.067,.292),(.313,.484))])
    stone_clearance = box(x-w*.34-1.7, z-7.6, x-w*.34+1.7, z+7.6)
    return x, z, lawn.difference(stone_clearance)


def terrain_rotation(dx, dz, yaw):
    """Quaternion for local up onto the normal (-dx,1,-dz), followed by local yaw."""
    length = math.sqrt(1. + dx*dx + dz*dz)
    nx, ny, nz = -dx/length, 1./length, -dz/length
    t = math.sqrt(2.*(1.+ny))
    qx, qz, qw = nz/t, -nx/t, t/2.
    sy, cy = math.sin(yaw/2), math.cos(yaw/2)
    return [qx*cy-qz*sy, qw*sy, qz*cy+qx*sy, qw*cy]


def add(doc, terrain, data, available, spots, garden=None):
    """Place grouped grass meshes in clear planting polygons; return assembly counts."""
    rng = random.Random(7291901)
    stats = dict(patches=0, grassBlades=0, groundcoverLeaves=0, triangles=0, sharedMeshes=0,
                 squarePatches=0, mappedGrassPatches=0, landmarkPatches=0, understoryPatches=0, meadowPatches=0, huiwenPatches=0)
    pool = {}
    occupied = {}
    def plant(x, z, family, mode, flat_height=None):
        cell = math.floor(x/4), math.floor(z/4)
        cell_items = [v for a in range(cell[0]-1,cell[0]+2) for b in range(cell[1]-1,cell[1]+2)
                      for v in occupied.get((a,b),())]
        if any((x-u)**2+(z-v)**2 < (2.55 if family==0 else 3.8)**2 for u,v in cell_items):
            return False
        variant = rng.randrange(3)
        key = (family, variant)
        if key not in pool:
            shape, blades, leaves, triangles, radius = prototype(*key)
            pool[key] = (doc.shape(shape), blades, leaves, triangles, radius)
        mesh, blades, leaves, triangles, radius = pool[key]
        scale = rng.uniform(.83,1.08)
        yaw = rng.uniform(0,math.tau)
        dx = dz = 0.
        if flat_height is None or callable(flat_height):
            height = terrain.y(x,z) if flat_height is None else flat_height(x,z)
            dx = (terrain.y(x+.4,z)-terrain.y(x-.4,z))/.8
            dz = (terrain.y(x,z+.4)-terrain.y(x,z-.4))/.8
            # Reject patches straddling a sharp terrain facet break.
            for i in range(8):
                a=math.tau*i/8
                xx,zz=radius*scale*math.cos(a),radius*scale*math.sin(a)
                if abs((flat_height(x+xx,z+zz) if callable(flat_height) else terrain.y(x+xx,z+zz))-height-dx*xx-dz*zz)>.026:
                    return False
        else:
            height = flat_height(x,z) if callable(flat_height) else flat_height
        idx = len(doc.doc['nodes'])
        doc.node('草叶地被 '+str(stats['patches']+1),mesh=mesh,at=(x,height-.003,z),
                       yaw=yaw,scale=(scale,scale,scale),kind='groundcover',
                       family=('草坪','散生细草','林缘地被')[family])
        if (flat_height is None or callable(flat_height)) and (dx or dz):
            doc.doc['nodes'][idx]['rotation'] = terrain_rotation(dx,dz,yaw)
        occupied.setdefault(cell,[]).append((x,z))
        stats['patches'] += 1
        stats[mode] += 1
        stats['grassBlades'] += blades
        stats['groundcoverLeaves'] += leaves
        stats['triangles'] += triangles
        return True

    def scatter(area, limit, family, mode, flat_height=None):
        if area.is_empty or limit < 1:
            return
        clearance=(2.2,4.05,4.5)[family]
        interior=area.buffer(-clearance,quad_segs=2)
        if interior.is_empty:
            return
        pieces=[interior] if interior.geom_type=='Polygon' else [p for p in interior.geoms if p.geom_type=='Polygon']
        if not pieces:
            return
        # Weight by planted area, then sample inside the selected component.
        prep_pieces=[prep(p) for p in pieces]
        weights=[p.area for p in pieces]
        bounds=[p.bounds for p in pieces]
        count=0
        for i in rng.choices(range(len(pieces)),weights=weights,k=max(120,limit*28)):
            xmin,zmin,xmax,zmax=bounds[i]
            x=rng.uniform(xmin,xmax);z=rng.uniform(zmin,zmax)
            if prep_pieces[i].contains(Point(x,z)):
                count+=plant(x,z,family,mode,flat_height)
                if count>=limit:
                    break

    square=square_lawns(data)
    if square:
        x,z,lawn=square
        from qd_grading import site_lift
        # Match the exact graded plaza origin and the top of its 0.14 m turf slab.
        scatter(lawn,92,0,'squarePatches',terrain.y(x,z)+site_lift('yuxian')+.21)
    if garden is not None:
        scatter(garden,160,0,'huiwenPatches',lambda x,z:terrain.y(x,z)+.185)
    if not available.is_empty:
        grass, wooded = [], []
        for row in data.get('greens',[]):
            poly=Polygon(row['poly'],row.get('holes',[])).buffer(0)
            if poly.is_empty:
                continue
            (grass if row.get('kind')=='grass' else wooded).append(poly)
        if grass:
            scatter(available.intersection(unary_union(grass)),240,0,'mappedGrassPatches')
        if spots:
            circles=unary_union([Point(float(x),float(z)).buffer(84,quad_segs=9) for x,z in spots])
            scatter(available.intersection(circles),310,1,'landmarkPatches')
        if wooded:
            scatter(available.intersection(unary_union(wooded)),155,2,'understoryPatches')
        scatter(available,480,0,'meadowPatches')
    stats['sharedMeshes']=len(pool)
    return stats

