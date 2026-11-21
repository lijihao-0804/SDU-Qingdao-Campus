"""Campus soft ground and planting, in local X-east / Z-south metres.

The ground uses October Sentinel-2 as a relative vegetation-density observation,
not as a photographed spring albedo. Tree positions, species forms and residual
open-ground colours are interpretations of the school records and aerials.
"""
from pathlib import Path
from collections import Counter
import math

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, distance_transform_edt
from scipy.spatial import cKDTree
from shapely import contains_xy, prepare
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

from qd_terrain import sourcepolygon

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "academicAvenuesAndSportNursery": "https://hq.qd.sdu.edu.cn/info/1017/2436.htm",
    "northRainGarden": "https://jjc.qd.sdu.edu.cn/info/1022/1059.htm",
    "museumAlumniGarden": "https://www.view.sdu.edu.cn/info/1003/76009.htm",
    "imagery": "data/map/sentinel-20261007.npz",
    "aerial": "实景参照/地标/航拍02_南向北鸟瞰.png",
    "hallTreeCourt": "https://livingatlas.arcgis.com/wayback/#active=3692&mapCenter=120.68288%2C36.37141%2C19",
    "academicAerial": "实景参照/会文与淦昌/2019_周青先_会文与淦昌斜俯视.png",
}


def read_accessor(scene, index):
    acc = scene.doc["accessors"][index]
    view = scene.doc["bufferViews"][acc["bufferView"]]
    dtype = {5126: "<f4", 5125: "<u4", 5123: "<u2"}[acc["componentType"]]
    dims = {"SCALAR": 1, "VEC3": 3, "VEC2": 2}[acc["type"]]
    offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    return np.frombuffer(scene.raw, dtype, acc["count"] * dims, offset).reshape(-1, dims).copy()


def nursery_rows(data):
    """North research quarter's mapped woody plot; retain tall verge trees outside it."""
    outline = next(r for r in data["greens"] if r["id"] == "way/982199351")
    return sourcepolygon(outline).buffer(-7,quad_segs=3)


class Site:
    """Regular 4-m field for smooth land-cover transitions on the original terrain."""
    resolution = 4.0

    def __init__(self, data, available):
        self.area = Polygon(data["boundary"]).buffer(0).intersection(available)
        self.boundary = Polygon(data["boundary"]).buffer(0)
        x0, z0, x1, z1 = self.boundary.bounds
        self.x0, self.z0 = math.floor(x0 / 4) * 4 - 32, math.floor(z0 / 4) * 4 - 32
        xx, zz = np.meshgrid(np.arange(self.x0, x1 + 36, 4), np.arange(self.z0, z1 + 36, 4))
        self.xx, self.zz = xx, zz
        prepare(self.area)
        self.mask = contains_xy(self.area, xx, zz)
        self.fade = gaussian_filter(self.mask.astype(float), 1.40)
        # Cover the narrow turf verge reaching a kerb; the visible road and
        # entrance pavement are independent opaque surfaces in the source scene.
        self.fade = np.clip(self.fade * 1.8, 0, 1)
        greens = unary_union([sourcepolygon(r) for r in data["greens"] if r["kind"] == "forest"])
        woodland = gaussian_filter(contains_xy(greens, xx, zz).astype(float), 1.6)
        self.lake = unary_union([sourcepolygon(r) for r in data["water"] if r["kind"] == "pond"])
        wetland = np.exp(-distance_transform_edt(~contains_xy(self.lake, xx, zz)) * 4 / 22)
        hall = next(r for r in data["buildings"] if r["id"] == "s2/hall-c1")
        court = Polygon(max(hall["holes"],key=lambda ring: Polygon(ring).area))
        hall_floor = gaussian_filter(contains_xy(court.buffer(-3),xx,zz).astype(float),1.4)
        self.rows = gaussian_filter(contains_xy(nursery_rows(data),xx,zz).astype(float),1.15)
        self.woods, self.wet = np.maximum(woodland*(1-self.rows),.8*hall_floor), wetland
        with np.load(ROOT / SOURCES["imagery"]) as sat:
            red, nir = sat["red"].astype(float), sat["nir"].astype(float)
            ndvi = (nir - red) / np.maximum(red + nir, 1)
            sx, sz = sat["x"], sat["z"]
            gx, gz = np.meshgrid(sx, sz)
            # Omit roof and tarmac samples from smoothing at their boundaries.
            padded = self.area.buffer(1)
            prepare(padded)
            good = contains_xy(padded, gx, gz) & (ndvi > .09) & (nir > 470)
            den = gaussian_filter(good.astype(float), 1.15)
            val = (gaussian_filter(np.where(good, ndvi, 0), 1.15) + .37 * .07) / (den + .07)
            self.veg = map_coordinates(val, [(zz - sz[0]) / (sz[1] - sz[0]),
                                              (xx - sx[0]) / (sx[1] - sx[0])], order=1, mode="nearest")

    def sample(self, field, x, z):
        return map_coordinates(field, [(z - self.z0) / 4, (x - self.x0) / 4], order=1, mode="nearest")

    def tint(self, x, z):
        dry = np.clip((self.sample(self.veg, x, z) - .18) / .49, 0, 1)
        woods = self.sample(self.woods, x, z)
        wet = self.sample(self.wet, x, z)
        fade = self.sample(self.fade, x, z)
        dry = dry * dry * (3 - 2 * dry)
        # Low-cover turf retains straw, while vigorous patches have cooler,
        # darker understory. Seasonal colours are estimated, not classified taxa.
        srgb = (np.array([152., 151., 104.]) + dry[:, None] * [-42., -12., -18.]
                + woods[:, None] * [-17., -15., -10.] + wet[:, None] * [-9., -5., 1.])
        rows = self.sample(self.rows,x,z)[:,None]
        srgb = srgb*(1-rows*.93) + rows*.93*np.array([155.,143.,103.])
        variation = (3.5 * np.sin(.052*x + .014*z + 1.5*np.sin(.027*z)) +
                     2.7 * np.sin(.077*z - .018*x) + 2.1 * np.cos(.103*x + .038*z))
        srgb += variation[:, None] * [1.15, 1., .78]
        # Keep the original repeating 2.24-m grass blade texture and material.
        # Divide out the texture's mean in linear light for glTF COLOR_0.
        ratio = ((srgb/255 + .055) / (np.array([130.,158.,96.])/255 + .055)) ** 2.4
        # A brighter copy of the source grass tile keeps COLOR_0 in [0,1].
        legacy = (.50 + .23*np.sin(x*.049+np.sin(z*.071)) +
                  .16*np.sin(z*.091+x*.038) + .10*np.cos(x*.022-z*.033))
        old = np.column_stack((.84+.145*legacy, .89+.106*legacy, .79+.17*legacy))
        return np.clip(((1-fade[:,None])*old + fade[:,None]*ratio) / GAIN, 0, 1)


# The material texture is brightened in sRGB, then tints scale it back down.
# Preserves the original colour outside the study mask, and leaves room for straw.
GAIN = np.array([1.60, 1.15, 1.36])


def soften_ground(scene, site):
    import io
    from PIL import Image
    from qd_spring_surfaces import add_image
    node = next(n for n in scene.doc["nodes"] if n["name"] == "校园及滨海地形")
    mesh = scene.doc["meshes"][node["mesh"]]
    prim = mesh["primitives"][0]
    attrs = prim["attributes"]
    xyz = read_accessor(scene, attrs["POSITION"])
    original = read_accessor(scene, prim["indices"]).ravel()
    triangles = xyz[original].reshape(-1, 3, 3)
    parts = []
    for _ in range(5):
        mid = triangles.mean(axis=1)
        lengths = np.max(np.sum((triangles-np.roll(triangles,1,axis=1))**2, axis=2),axis=1)
        # Include a halo around the planted area to resolve the colour gradient.
        strength = site.sample(site.fade, mid[:,0], mid[:,2])
        for corner in triangles.transpose(1,0,2):
            strength = np.maximum(strength, site.sample(site.fade,corner[:,0],corner[:,2]))
        selection = (lengths > 100) & (strength > .006)
        if not selection.any():
            break
        parts.append(triangles[~selection])
        a,b,c = triangles[selection].transpose(1,0,2)
        ab,bc,ca = (a+b)/2,(b+c)/2,(c+a)/2
        triangles = np.concatenate([np.stack(v,axis=1) for v in
                                    [(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)]])
    parts.append(triangles)
    triangles = np.concatenate(parts)
    # Weld positions rather than storing three complete glTF vertices per face.
    # All new vertices are edge midpoints inside their original terrain planes.
    v, i = np.unique(triangles.reshape(-1,3), axis=0, return_inverse=True)
    index = i.reshape(-1,3)
    normals = np.zeros_like(v)
    face = np.cross(v[index[:,1]]-v[index[:,0]],v[index[:,2]]-v[index[:,0]])
    for j in range(3):
        np.add.at(normals,index[:,j],face)
    lengths = np.linalg.norm(normals,axis=1)
    normals[lengths < 1e-10] = [0,1,0]
    normals /= np.where(lengths < 1e-10,1.,lengths)[:,None]
    x,z = v[:,0],v[:,2]
    xz = np.stack((x*.42+z*.15, z*.42-x*.15),axis=1)
    turf = scene.doc["materials"][prim["material"]]["pbrMetallicRoughness"]["baseColorTexture"]
    tex = scene.doc["textures"][turf["index"]]
    im = scene.doc["images"][tex["source"]]
    buf = scene.doc["bufferViews"][im["bufferView"]]
    start = buf.get("byteOffset",0)
    old = np.asarray(Image.open(io.BytesIO(scene.raw[start:start+buf["byteLength"]])).convert("RGB"),dtype=float)
    bright = np.uint8(np.clip(((old/255+.055)*GAIN**(1/2.4)-.055)*255,0,255))
    token = add_image(scene,"夕照草坪 · 草皮纤维",Image.fromarray(bright),"JPEG",True)
    material = scene.mat("校园草地 · 地表湿度与林下色泽")
    scene.doc["materials"][material]["pbrMetallicRoughness"].update(
        baseColorFactor=[1.,1.,1.,1.],baseColorTexture=token,roughnessFactor=.97,metallicFactor=0)
    prim["material"] = material
    for name, values, typ in (("POSITION",v,"VEC3"),("NORMAL",normals,"VEC3"),
                              ("COLOR_0",site.tint(x,z),"VEC3"),("TEXCOORD_0",xz,"VEC2")):
        attrs[name] = scene.accessor(values,"<f4",typ,5126,34962)
    dtype, code = ("<u2",5123) if len(v) <= 65535 else ("<u4",5125)
    prim["indices"] = scene.accessor(i,dtype,"SCALAR",code,34963)
    tiles = {}
    for title, region in [("北区",site.zz< -540),("科研及生态区",(site.zz>=-540)&(site.zz<-165)),
                          ("图书馆与学院区",(site.zz>=-165)&(site.zz<410)),("运动与生活区",site.zz>=410)]:
        sel = site.mask & region
        if sel.any():
            tiles[title] = dict(availableSquareMetresAt4m=int(sel.sum()*16),
                                vegetationIndex=[round(float(q),3) for q in np.quantile(site.veg[sel],[.1,.5,.9])])
    return dict(originalTriangles=len(original)//3, refinedTriangles=len(index),
                vertices=len(v), softGroundByDistrict=tiles)


def low_views(terrain, catalog):
    # Keep horizontal room for the whole crown; include low portions of a
    # descending view ray and fan the corridor out towards the facade.
    corridors = []
    for loc in catalog:
        views = list(loc.get("views",{}).values()) + [loc.get("viewpoint")]
        for view in views:
            if not isinstance(view,dict) or "eye" not in view or "target" not in view:
                continue
            eye, target = np.array(view["eye"]), np.array(view["target"])
            length = float(np.linalg.norm((target-eye)[[0,2]]))
            if length < .2 or length > 1300:
                continue
            line = np.linspace(eye, target, max(3, math.ceil(length/7)+1))
            for a,b in zip(line,line[1:]):
                if min(q[1]-terrain.y(q[0],q[2]) for q in (a,b)) < 13:
                    corridors.append(LineString([a[[0,2]],b[[0,2]]]).buffer(5.0 + min(4,length*.025),quad_segs=2))
    return unary_union(corridors)


def nursery_shrubs(scene, terrain, site, area, blocked, old):
    """Low deciduous nursery stock, with predominantly open soil between rows."""
    from qd_geometry import Shape
    from qd_planting import branch
    rng = np.random.default_rng(69103)
    allowed = prep(area.intersection(site.area).difference(blocked).buffer(-1.3,quad_segs=6))
    materials = ("#686f43", "#7f8650", "#8c9054")
    meshes=[]
    for k in range(3):
        sh=Shape("会堂东侧 · 小冠木本 "+str(k+1))
        branch(sh,(0,-.02,0),(0,.85,0),.049,.024,"#70614b")
        for i in range(5):
            angle=i*math.tau/5+k*.21
            x,z=.35*math.cos(angle),.35*math.sin(angle)
            branch(sh,(0,.34,0),(x,.91,z),.022,.011,"#70614b")
            pts=[(x,.62,z),(x,1.44+.045*(i%3),z)]
            for j in range(6):
                a=math.tau*j/6+i*.27
                pts.append((x+math.cos(a)*.44,.99+.065*(j%2),z+math.sin(a)*.4))
            faces=[(1,2+(j+1)%6,2+j) for j in range(6)]+[(0,2+j,2+(j+1)%6) for j in range(6)]
            sh.mesh("疏叶小冠",pts,faces,materials[(i+k)%3])
        meshes.append(scene.shape(sh))
    n=0
    for j,z0 in enumerate(np.arange(-749,-548,6.4)):
        for i,x0 in enumerate(np.arange(187,380,6.2)):
            x=float(x0+.012*(z0+650)+rng.uniform(-.25,.25))
            z=float(z0+.012*(x0-260)+rng.uniform(-.24,.24))
            if not allowed.contains(Point(x,z)) or (old is not None and old.query((x,z))[0]<3.6):
                continue
            if rng.random()<.10:
                continue
            sc=float(rng.uniform(.53,1.12));k=(i//6+j//4)%3
            n+=1
            scene.node("会堂东侧行列种植 · "+str(n),mesh=meshes[k],at=(x,terrain.y(x,z)-.02,z),
                       yaw=float(rng.uniform(0,math.tau)),scale=(sc,sc,sc),
                       kind="flora",shrub=True,species="行列木本（概化）",v6district="会堂东侧种植地")
    return n


def plant_clusters(scene, terrain, data, catalog, site):
    rng = np.random.default_rng(64420)
    obstacles = low_views(terrain, catalog)
    # Protect camera and door cones already in available, plus every approach
    # recorded in the completed public catalog. Erode by conservative crown size.
    rows_area = nursery_rows(data)
    tree_area = site.area.difference(obstacles).difference(rows_area)
    cleared = prep(tree_area.buffer(-5.4,quad_segs=12))
    plants = [n for n in scene.doc["nodes"] if n.get("extras",{}).get("kind") == "flora"]
    points = [n["translation"][::2] for n in plants]
    old = cKDTree(points) if points else None
    pool = {m["name"]: k for k,m in enumerate(scene.doc["meshes"])}
    trees = [pool["乔木"+str(i)] for i in range(1,6)]
    counts = Counter()
    new = []
    old_gap, new_gap = [], []
    nursery = box(-620,350,-205,690)
    lake_edge = site.lake.buffer(43).difference(site.lake.buffer(8))
    mapped = unary_union([sourcepolygon(r) for r in data["greens"] if r["kind"] in ("forest","mixed_vegetation")])

    def put(x,z,label,species,k,scale):
        if not cleared.contains(Point(x,z)):
            return
        d0 = old.query((x,z))[0] if old is not None else math.inf
        if d0 < 7.2:
            return
        d1 = min((math.hypot(x-a,z-b) for a,b in new),default=math.inf)
        if d1 < 8.7:
            return
        new.append((x,z)); old_gap.append(d0); new_gap.append(d1)
        counts[label] += 1
        scene.node(label+f" · {counts[label]:03}",mesh=trees[k],
                   at=(float(x),terrain.y(x,z)-.03,float(z)),yaw=float(rng.uniform(-math.pi,math.pi)),
                   scale=(float(scale),float(scale*rng.uniform(.98,1.09)),float(scale)),
                   kind="flora",shrub=False,species=species,v6district=label,
                   evidence="区域植被类型有据；株位、树形与尺度概化")

    # Visible crown groups in the tree court, traced from the north ortho mosaic.
    # The small pale opening in the south-central court and the three shell slots
    # remain open. The image release is 2026-11-18; acquisition day is unknown.
    # Coordinates reference the cropped extent [-30,180] x [-757,-545] in metres.
    rows = [(155,(249,283)), (181,(211,251,291,325)), (207,(176,216,253,299,337,365)),
            (235,(167,200,236,270,307,343,379)), (263,(160,196,232,268,303,341,376)),
            (290,(169,207,240,307,374)), (319,(178,218,247,345,378)),
            (345,(211,250,286,320,356)), (370,(239,271,310,339))]
    for j,(py,positions) in enumerate(rows):
        for i,px in enumerate(positions):
            x,z = -30.+210.*px/540., -757.+212.*py/540.
            put(x,z,"学生会堂环庭","既有阔叶树群（概化）",(j+2*i)%5,float(.86+.07*rng.random()))

    # Rows visible between the paired academic courts follow the mapped arms
    # of their service lanes. Drop any candidate close to an existing plant.
    for r in data["roads"]:
        line = LineString(r["line"])
        if not (r["kind"]=="service" and 196 < line.centroid.y < 250 and
                line.bounds[2]-line.bounds[0] > 90 and line.bounds[3]-line.bounds[1]<12):
            continue
        for side in (-1,1):
            for dist in np.arange(9,line.length-5,12.8):
                p,q = line.interpolate(dist),line.interpolate(dist+.2)
                dx,dz = q.x-p.x,q.y-p.y
                norm=math.hypot(dx,dz)
                if norm<1e-7:
                    continue
                gap = r["width"]/2+8.2
                put(p.x-side*dz*gap/norm,p.y+side*dx*gap/norm,
                    "学院轴线疏列","榉树（概化）",2,float(rng.uniform(.66,.82)))

    xmin,zmin,xmax,zmax = site.area.bounds
    xs,zs = np.meshgrid(np.arange(xmin+5,xmax,12.2),np.arange(zmin+5,zmax,13.1))
    xs=xs.ravel()+rng.normal(0,2.4,xs.size);zs=zs.ravel()+rng.normal(0,2.2,zs.size)
    vigor = site.sample(site.veg,xs,zs)
    west = contains_xy(nursery,xs,zs)
    wet = contains_xy(lake_edge,xs,zs)
    woods = contains_xy(mapped,xs,zs)
    prepare(tree_area)
    free = contains_xy(tree_area,xs,zs)
    for j in rng.permutation(len(xs)):
        if not free[j]:
            continue
        x,z = float(xs[j]),float(zs[j])
        if wet[j]:
            if rng.random()<.44:
                put(x,z,"樱海湖岸林","滨水阔叶树（概化）",3,float(rng.uniform(.68,.88)))
        elif west[j] and vigor[j]>.36:
            if rng.random()<.48:
                put(x,z,"体育场西侧幼林","混合补植（概化）",int(rng.choice([0,2,4])),float(rng.uniform(.40,.68)))
        elif woods[j] and vigor[j]>.47:
            if rng.random()<.13:
                put(x,z,"北区林缘","混合阔叶树（概化）",int(rng.integers(0,5)),float(rng.uniform(.62,.93)))
        elif vigor[j]>.53 and rng.random()<.026:
            put(x,z,"校园疏林草地","阔叶乔木（概化）",int(rng.integers(0,5)),float(rng.uniform(.57,.82)))
    avoid_tree_crowns = unary_union([Point(p).buffer(5.4,quad_segs=4) for p in new])
    rows_count = nursery_shrubs(scene,terrain,site,rows_area,obstacles.union(avoid_tree_crowns),old)
    return dict(treesByZone=dict(counts), addedTrees=len(new), nurseryShrubs=rows_count, crownClearanceM=5.4,
                minimumNewToExistingPlantM=round(float(min(old_gap)),2) if old_gap else None,
                minimumNewTreeSpacingM=round(float(min(new_gap)),2) if len(new_gap)>1 else None,
                newTreeRootsOutsideAvailable=sum(not site.area.covers(Point(p)) for p in new),
                treesInCameraCorridors=sum(obstacles.covers(Point(p)) for p in new))


def build(scene, terrain, data, catalog, available):
    """Call after spring texture binding, spring floor and the complete camera catalog."""
    site = Site(data, available)
    result = soften_ground(scene,site)
    result.update(plant_clusters(scene,terrain,data,catalog,site))
    result.update(availableSquareMetres=round(site.area.area),sources=SOURCES,
                  interpretation="2026年10月10米像元辅助草地疏密；夕照草色、树位和树形为近似。")
    return result

