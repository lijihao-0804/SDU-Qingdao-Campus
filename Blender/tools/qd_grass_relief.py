"""Editable, instanced curved grass leaves for the Qingdao campus.

Coordinates are east/up/south, in metres. The caller supplies the final
plantable area, which includes all custom buildings, paving and garden reserves.
"""
import math
from collections import Counter

import numpy as np
from scipy.spatial import cKDTree
from shapely import contains_xy, prepare
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from qd_geometry import Shape, lin
from qd_groundcover import terrain_rotation
from qd_terrain import sourcepolygon
from qd_v6_planting import nursery_rows


MATERIAL = "校园春草 · 叶鞘与渐浅叶尖"
# Radius, tuft count, height range, maximum blade width and base colours.
FORMS = {
    "field": (5.1, 40, (.18, .40), .036, ("#547848", "#78924f", "#909657")),
    "verge": (2.05, 27, (.17, .37), .029, ("#4c744c", "#678e53", "#8c985e")),
    "detail": (1.24, 55, (.12, .27), .023, ("#547849", "#79994f", "#9ba35d")),
}
DISTRICTS = ("北区", "科研及生态区", "图书馆与学院区", "运动与生活区")
SUNLIT_GARDEN = box(-155, -160, 103, -105)


def _linear(rgb):
    return tuple(lin(float(np.clip(channel, 0, 255)) / 255) for channel in rgb)


def _prototype(scene, form, variant):
    radius, tufts, height_range, width, colours = FORMS[form]
    rng = np.random.default_rng(347910 + 47 * variant + 313 * tuple(FORMS).index(form))
    shape = Shape("春草 · " + {"field": "空地疏草", "verge": "路边长草", "detail": "近景短草"}[form] + str(variant+1))
    verts, normals, indices = shape.parts[MATERIAL]
    tints = []
    shape.vertex_tints = {MATERIAL: tints}
    shape.uvs = {MATERIAL: []}
    blade_uv=((.12,1.),(.88,1.),(.01,.41),(.99,.41),(.5,0.))
    palette = [np.array([int(c[k:k+2], 16) for k in (1, 3, 5)]) for c in colours]
    roots = []
    # Localised, overlapping families of tillers create patches of growth.
    # Fully opaque tapered strips remain visible edge-on from another angle.
    centres = rng.uniform(-.55, .55, (4, 2)) * radius
    blades = 0
    for k in range(tufts):
        if k % 3 == 0:
            angle = rng.uniform(0, math.tau)
            spread = radius * math.sqrt(rng.random())
            x, z = spread * math.cos(angle), spread * math.sin(angle)
        else:
            x, z = centres[k % 4] + rng.normal(0, radius * .24, 2)
            distance = math.hypot(x, z)
            if distance > radius:
                x, z = x*radius/distance, z*radius/distance
        roots.append((x, z))
        fan = rng.uniform(0, math.tau)
        h = rng.uniform(*height_range)
        main = palette[int(rng.choice(3, p=(.37, .48, .15)))]
        for leaf in range(int(rng.integers(5, 9))):
            a = fan + leaf*2.399963 + rng.uniform(-.33, .33)
            vx, vz = math.cos(a), math.sin(a)
            side = np.array([-vz, 0., vx])
            height = h * rng.uniform(.72, 1.20)
            lean = height * rng.uniform(.35, 1.09)
            half = width * rng.uniform(.39, .70)
            origin = np.array([x + vx*.029, -.032, z + vz*.029])
            knee = origin + [vx*lean*.27, height*.69, vz*lean*.27]
            tip = origin + [vx*lean, height, vz*lean]
            # Very slight twist, with a darker sheath and brighter growing tip.
            twist = side * rng.uniform(-.15, .15) * lean
            off = len(verts)
            verts.extend(tuple(p) for p in (origin-side*half*.58, origin+side*half*.58,
                         knee-side*half*.82, knee+side*half*.82, tip+twist))
            def norm(up):
                length = math.hypot(1., up)
                return (-vx/length, up/length, -vz/length)
            normals.extend([norm(.35)]*2 + [norm(.71)]*2 + [norm(1.9)])
            # Winding faces slightly upward on blades bending away from the root.
            indices.extend(off+i for i in (0,1,3, 0,3,2, 2,3,4))
            rgb = main + rng.uniform(-4, 4)
            base = _linear(rgb * (.72, .76, .72))
            middle = _linear(rgb + (0, 4, -1))
            tip_color = _linear(rgb + (16, 15, 3))
            tints.extend((base, base, middle, middle, tip_color))
            shape.uvs[MATERIAL].extend(blade_uv)
            blades += 1
            if (form=='detail' and leaf in (1,4)) or (form=='verge' and leaf==2):
                # A narrow younger tiller springs from the same tuft below the
                # mature blade. Keep the open-field tier free of subpixel blades.
                az=a+(.63 if leaf%2 else -.71)
                along=np.array([math.cos(az),0.,math.sin(az)])
                cross=np.array([-math.sin(az),0.,math.cos(az)])
                root=origin+along*.006
                neck=root+along*lean*.13+[0,height*.42,0]
                young_tip=root+along*lean*.49+cross*half*.40+[0,height*.61,0]
                off=len(verts)
                verts.extend(tuple(pt) for pt in (root-cross*half*.27,root+cross*half*.27,
                             neck-cross*half*.40,neck+cross*half*.34,young_tip))
                for up in (.39,.39,.76,.76,1.6):
                    normals.append(tuple((-along+[0,up,0])/math.hypot(1.,up)))
                indices.extend(off+i for i in (0,1,3,0,3,2,2,3,4))
                tints.extend((base,base,middle,middle,tip_color))
                shape.uvs[MATERIAL].extend(blade_uv)
                blades+=1
    vertices = np.array(verts)
    # Use a 3D sphere for clearance, valid for every yaw and slope rotation.
    reach = float(np.max(np.linalg.norm(vertices, axis=1)))
    return dict(mesh=scene.shape(shape), radius=reach, blades=blades, tufts=tufts,
                triangles=len(indices)//3, roots=roots,
                height=float(vertices[:, 1].max()))


def _grid(area, pitch, rng):
    if area.is_empty:
        return []
    x0,z0,x1,z1 = area.bounds
    xx,zz = np.meshgrid(np.arange(x0, x1, pitch), np.arange(z0, z1, pitch))
    xx = xx.ravel() + rng.uniform(.04, .96, xx.size)*pitch
    zz = zz.ravel() + rng.uniform(.04, .96, zz.size)*pitch
    prepare(area)
    inside = contains_xy(area, xx, zz)
    return list(zip(xx[inside], zz[inside]))


def _camera_center(lawn, scene, terrain):
    # The north garden has the library beyond its open grass. Preserve a short
    # clear sightline through its tree groups for a genuinely low grass view.
    candidates = _grid(lawn.intersection(SUNLIT_GARDEN).buffer(-3.1), 1.8, np.random.default_rng(731))
    if not candidates:
        return None
    plants = [n["translation"][::2] for n in scene.doc["nodes"] if n.get("extras", {}).get("kind") == "flora"]
    tree = cKDTree(plants) if plants else None
    def score(p):
        x,z = p
        gap = min(18., float(tree.query(p)[0])) if tree is not None else 18.
        return gap - .065*math.hypot(x-41,z+141)
    return max(candidates, key=score)


def _view(terrain, x, z):
    # Look east-southeast. At a 0.82 m eye height the foremost blades reach
    # well above the lower image edge, with the trees readable behind them.
    dx, dz = .88, .475
    ex, ez = x-2.6*dx, z-2.6*dz
    return {"eye": [ex, terrain.y(ex,ez)+.82, ez],
            "target": [x+1.3*dx, terrain.y(x,z)+.30, z+1.3*dz], "fov": 54}


def build(scene, terrain, data, catalog, plantable, square_lawns):
    """Add the new layers and a close viewpoint. The return value is JSON-safe."""
    rng = np.random.default_rng(6108791)
    campus = Polygon(data["boundary"]).buffer(0)
    # The woody row nursery has intentionally exposed soil. Existing running
    # tracks, playing fields and all mapped lakes remain completely clear.
    excluded = unary_union([sourcepolygon(r) for group in ("pitches","water","beaches")
                            for r in data[group]] + [nursery_rows(data)])
    site = campus.intersection(plantable.union(square_lawns)).difference(excluded)
    woods = unary_union([sourcepolygon(r) for r in data["greens"] if r["kind"] == "forest"])
    prepare(woods)
    pool = {(form,k): _prototype(scene,form,k) for form in FORMS for k in range(2)}
    material = scene.doc["materials"][scene.mat(MATERIAL)]
    material["pbrMetallicRoughness"].update(baseColorFactor=[1,1,1,1], roughnessFactor=.97)
    material["doubleSided"] = True
    edge = {}
    max_reach = {}
    for form in FORMS:
        max_reach[form] = 1.04*max(pool[form,k]["radius"] for k in range(2)) + .05
        edge[form] = site.buffer(-max_reach[form], quad_segs=12)
        prepare(edge[form])
    hero = _camera_center(square_lawns, scene, terrain)
    targets = [(x,z) for x,z in ((-50,-1030),(155,-565),(250,-262),
               (300,169),(90,397),(120,638),(-350,655))]
    if hero is not None:
        targets.append(hero)
    fans = unary_union([Point(x,z).buffer(13 if hero is not None and (x,z)==hero else 11,
                        quad_segs=12) for x,z in targets])
    detail = edge["detail"].intersection(fans)
    # Thin grass bands on the inside of pedestrian and road clearances. A
    # broader, sparser layer covers the body of a lawn and open grasslands.
    verges = edge["verge"].difference(site.buffer(-9, quad_segs=5))
    counts, districts = Counter(), Counter()
    blades = tufts = triangles = 0
    max_ground_error = 0.
    used = set()
    planted = []
    for form, region, pitch in (("field",edge["field"],14.2), ("verge",verges,8.1),
                                 ("detail",detail,1.82)):
        for x,z in _grid(region,pitch,rng):
            if form=="field" and contains_xy(woods,x,z) and rng.random()<.48:
                continue
            k = int(rng.integers(0,2))
            proto = pool[form,k]
            scale = float(rng.uniform(.83,1.04))
            yaw = float(rng.uniform(0, math.tau))
            y = terrain.y(x,z)
            dx = (terrain.y(x+.25,z)-terrain.y(x-.25,z))/.50
            dz = (terrain.y(x,z+.25)-terrain.y(x,z-.25))/.50
            # Reject patches on sharp TIN breaks. Check the actual transformed
            # tiller roots, so a lawn crossing a fold cannot float on one side.
            qx,qy,qz,qw = terrain_rotation(dx,dz,yaw)
            a,b,c,d = 1-2*(qy*qy+qz*qz), 2*(qx*qz+qw*qy), 2*(qx*qz-qw*qy), 1-2*(qx*qx+qy*qy)
            e,f = 2*(qx*qy+qw*qz), 2*(qy*qz-qw*qx)
            err = 0.
            for rx,rz in proto["roots"]:
                rx,rz = scale*rx,scale*rz
                err = max(err,abs(y + e*rx+f*rz - terrain.y(x+a*rx+b*rz,z+c*rx+d*rz)))
                if err>.019:
                    break
            if err>.019:
                continue
            n = len(planted)+1
            scene.node("草坪叶簇 · %05d"%n, mesh=proto["mesh"], at=(x,y,z),
                       scale=(scale,scale,scale), kind="groundcover", grassRelief=True, tier=form)
            scene.doc["nodes"][-1]["rotation"] = [qx,qy,qz,qw]
            counts[form] += 1
            districts[DISTRICTS[sum(z>=b for b in (-540,-165,410))]] += 1
            tufts += proto["tufts"]
            blades += proto["blades"]
            triangles += proto["triangles"]
            used.add((form,k))
            max_ground_error = max(max_ground_error,err)
            planted.append((x,z))
    if hero is not None and counts["detail"]:
        hx,hz = map(float,hero)
        close = _view(terrain,hx,hz)
        ex,ez = hx-8.5, hz-7.0
        wide = {"eye":[ex,terrain.y(ex,ez)+2.9,ez],
                "target":[hx+3.0,terrain.y(hx,hz)+.3,hz+2.0],"fov":53}
        catalog.append(dict(key="grass_relief",name="育贤广场北园 · 草叶近景",group="校园场地",
                            x=hx,z=hz,y=terrain.y(hx,hz),h=.6,r=7,viewpoint=close,
                            views={"facade":dict(close,label="俯身看草叶"),
                                   "garden":dict(wide,label="园路旁草坪")},
                            note="沿草尖望向北园林带。脚边的草从深色叶鞘伸出，路缘较长，空地间留有疏密变化。"))
    return {"patches":len(planted),"tufts":tufts,"blades":blades,"triangles":triangles,
            "sharedMeshesUsed":len(used),"patchesByType":dict(counts),"patchesByDistrict":dict(districts),
            "suitableAreaM2":round(site.area),"maxTiltedRootErrorM":round(max_ground_error,5),
            "maxBladeHeightM":round(max(p["height"] for p in pool.values())*1.04,3),
            "conservativeMaskInsetM":{k:round(v,3) for k,v in max_reach.items()},
            "closeView":None if hero is None else _view(terrain,*hero),
            "placement":"校园公共绿地、路缘和育贤广场两翼。草叶种类、密度和朝向为春季景观概化。"}
