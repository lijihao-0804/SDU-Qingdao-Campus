"""Yuxian Square side gardens traced in the campus metre grid.

Wayback World Imagery release 3692, registration cross-checked against the
mapped transverse paths. The date of the original exposure is not known.
The V2 00:18.5 frame independently shows the planted edges and ceremony axis.
"""
import math
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from shapely.prepared import prep

from qd_terrain import sourcepolygon


REFERENCE = "https://livingatlas.arcgis.com/wayback/#active=3692&mapCenter=120.68190%2C36.36619%2C19"
# Local centres of dark-green crown groups in the registered aerial, selected at
# a minimum seven-metre spacing. Canopy colour and shade cannot identify species.
CROWNS = (
    (-151, -154), (-150, -15), (-150, 5), (-145, -114), (-144, 9), (-144, 17), (-142, -145), (-139, -21),
    (-138, -10), (-138, 28), (-137, -126), (-137, 9), (-136, -140), (-132, -1), (-130, -131), (-130, -107),
    (-128, -155), (-125, -122), (-125, -114), (-124, -21), (-123, -132), (-120, 22), (-119, -5), (-118, -156),
    (-117, -144), (-116, -110), (-114, -18), (-113, 20), (-112, -10), (-112, 6), (-111, -133), (-111, -115),
    (-106, 22), (-105, -13), (-105, 14), (-103, -156), (-103, -114), (-103, -24), (-103, 7), (-102, -141),
    (-102, -132), (-92, 14), (-91, -19), (-91, 1), (-90, -141), (-90, -128), (-90, 26), (-89, -148),
    (-89, -113), (-82, 9), (-80, -154), (-80, -125), (-77, -109), (-77, 27), (-76, -3), (-76, 20),
    (-72, -135), (-70, -111), (-69, 8), (-69, 17), (-68, -155), (-68, 27), (-66, -127), (-65, -20),
    (-62, -111), (-61, -153), (-61, -139), (-60, -123), (-60, -6), (-58, -105), (-57, 26), (-56, -148),
    (-52, -4), (-52, 9), (-51, -133), (-50, -124), (-49, -151), (-48, -114), (-48, -16), (-44, 8),
    (-43, 27), (-41, -13), (-40, -144), (-38, -119), (-37, -155), (-34, 5), (-33, 27), (-31, -148),
    (-31, -14), (-29, -135), (-29, -109), (-29, 14), (-26, -21), (-25, -141), (-23, -7), (-22, 1),
    (-21, -125), (-17, 27), (-15, -2), (-14, -150), (-13, -129), (-12, -106), (-8, 14), (-5, -114),
    (-4, -18), (-3, -11), (-3, 6), (-3, 25), (-2, -153), (-2, -131), (1, -107), (2, 18),
    (3, -19), (4, -4), (5, -145), (6, -156), (8, 8), (10, 19), (13, -17), (13, 28),
    (14, -3), (15, -143), (15, -120), (15, 13), (18, 22), (20, -127), (21, -17), (22, -116),
    (25, -144), (27, 15), (30, -2), (31, 22), (32, -20), (33, -156), (33, -147), (33, -140),
    (33, -111), (41, 28), (43, -107), (43, -17), (43, 4), (44, -154), (44, -142), (44, -134),
    (44, -122), (52, 28), (54, -107), (55, -155), (55, -7), (55, 17), (56, -130), (56, 4),
    (59, -146), (59, -122), (62, -16), (63, -116), (63, 27), (66, -8), (67, -127), (69, -141),
    (71, -1), (74, -156), (75, -145), (75, 10), (76, -138), (76, -11), (76, 18), (79, -25),
    (80, -4), (80, 27), (83, -156), (86, -111), (86, 6), (88, -132), (90, -16), (99, -147),
    (99, -119), (99, -18),
)


def curve(points, width):
    """Cubic traced on the orthophoto, expressed in local campus metres."""
    a,b,c,d=np.asarray(points, dtype=float)
    t=np.linspace(0,1,35)[:,None]
    line=(1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
    return LineString(line).buffer(width/2,cap_style="flat",quad_segs=4)


class Gardens:
    def __init__(self,data,road,walk):
        site=sourcepolygon(next(r for r in data["plazas"] if r["id"]=="way/981132252"))
        # The existing civic landmark contains the broad stone podium, flag court
        # and tree belts on the axis. Stay clear of its -102.8 ... -28.8 m slab.
        self.north=site.intersection(box(-158.4,-159.9,105.3,-103.3))
        self.south=site.intersection(box(-158.4,-28.2,104.7,30.7))
        self.wings=self.north.union(self.south)
        # Supplementary walks visible in the ortho but absent from the community
        # map. Coordinates below use a 3.5 px/m tracing view of this exact extent.
        def point(px,pz):return (-167+px/3.5,-170+pz/3.5)
        def trace(coords,width):return curve([point(*p) for p in coords],width)
        def diagonal(a,b,w):return LineString([point(*a),point(*b)]).buffer(w/2,cap_style="flat")
        extras=[
            trace([(17,176),(188,81),(333,111),(410,239)],2.3),
            trace([(103,30),(162,193),(361,280),(525,99)],3.4),
            trace([(170,127),(222,160),(286,175),(344,178)],.95),
            trace([(182,128),(239,150),(291,161),(337,166)],.90),
            trace([(16,579),(151,658),(309,657),(406,506)],2.4),
            trace([(116,710),(152,550),(341,501),(512,606)],3.5),
            trace([(174,625),(219,588),(298,567),(359,567)],1.15),
            trace([(190,624),(222,598),(290,579),(345,578)],1.10),
            diagonal((480,30),(628,236),3.6),diagonal((536,30),(657,236),2.2),
            diagonal((812,237),(925,30),3.2), diagonal((837,239),(943,98),2.5),
            diagonal((492,709),(631,517),3.6),diagonal((540,710),(659,516),2.2),
            diagonal((811,515),(920,714),3.1), diagonal((834,515),(954,679),2.6),
            Point(*point(451,134)).buffer(5.0,quad_segs=18),
        ]
        self.extras=unary_union(extras).intersection(self.wings)
        # Keep mapped paths continuous across wing edges. The outer road and
        # footways already have their own raised surfaces.
        self.lawns=self.wings.difference(unary_union([road.buffer(.45),walk.buffer(.45),self.extras]))
        self.paving=self.wings.difference(self.lawns)

    def build(self,scene,terrain,catalog):
        from qd_v6_planting import low_views
        clear=self.lawns.difference(low_views(terrain,catalog))
        nodes=scene.doc["nodes"]
        existing=[n["translation"][::2] for n in nodes if n.get("extras",{}).get("kind")=="flora"]
        nearby=cKDTree(existing) if existing else None
        meshes={m["name"]:i for i,m in enumerate(scene.doc["meshes"])}
        pool=[meshes["乔木"+str(i)] for i in range(1,6)]
        rng=np.random.default_rng(69056)
        # Actual shared broadleaf crown radii in the exported v5 botanical
        # meshes reach up to 5.57 m at full scale. Trees here have smaller
        # measured groups. Apply per-size clearance from garden walks.
        areas={k:prep(clear.buffer(-(k*0.1*5.65+.18),quad_segs=10)) for k in (5,6,7,8)}
        placed=[]
        counts={"north":0,"south":0}
        for i,(x,z) in enumerate(CROWNS):
            small=int(rng.choice((5,6,7,8),p=(.15,.34,.36,.15)))
            if not areas[small].covers(Point(x,z)):
                continue
            if nearby is not None and nearby.query((x,z))[0]<6.8:
                continue
            if any(math.hypot(x-a,z-b)<7.0 for a,b in placed):
                continue
            wing="north" if z<-80 else "south"
            counts[wing]+=1
            placed.append((x,z))
            sc=small*.1
            scene.node("育贤广场"+("北园" if wing=="north" else "南园")+f" · {counts[wing]:03}",
                       mesh=pool[i%5],at=(x,terrain.y(x,z)-.02,z),yaw=float(rng.uniform(0,math.tau)),
                       scale=(sc,sc*float(rng.uniform(.97,1.05)),sc),kind="flora",shrub=False,
                       v6Garden="yuxian-"+wing,species="园地阔叶树群（概化）")
        return {"source":REFERENCE,"video":"实景参照/视频时码/V2-018.50.jpg",
                "northLawnM2":round(self.lawns.intersection(self.north).area),
                "southLawnM2":round(self.lawns.intersection(self.south).area),
                "gardenPavingM2":round(self.paving.area),"trees":counts,
                "treeCandidatesFromOrtho":len(CROWNS),
                "interpretation":"广场南北两翼依据正射影像与既有园路恢复。树冠中心、树高、苗木种类与小径宽度按图概化。"}


def audit():
    """Read the actual exported square polygons and camera rays, without substituting source areas."""
    import json
    from pathlib import Path
    import shapely
    from v2_entrance_audit import Scene
    from v6_vegetation_audit import camera_rays
    root=Path(__file__).resolve().parents[1]
    model=Scene(root/"山东大学青岛校区.glb")
    data=json.loads((root/"data/map/campus.json").read_text("utf8"))
    catalog=json.loads((root/"data/locations.json").read_text("utf8"))
    road=[]
    walk=[]
    for r in data["roads"]:
        if r.get("tunnel") or len(r["line"])<2:
            continue
        narrow=r["width"]<7 and r["kind"] in ("footway","pedestrian","cycleway","path","steps","track")
        (walk if narrow else road).append(LineString(r["line"]).buffer(r["width"]/2,quad_segs=4))
    road=unary_union(road)
    gardens=Gardens(data,road,unary_union(walk).difference(road))
    extent=gardens.wings.bounds
    def projected(name):
        idx=next(i for i,n in enumerate(model.nodes) if n["name"]==name)
        rings=[]
        for tris,_ in model.triangles(idx):
            xz=tris[:,:,[0,2]]
            keep=np.all(xz.max(1)>=extent[:2],axis=1)&np.all(xz.min(1)<=extent[2:],axis=1)
            raw=shapely.polygons(xz[keep]);rings.extend(raw[shapely.area(raw)>.00001])
        return unary_union(rings)
    paving=projected("石材广场与步行带").union(projected("步行道"))
    turf=projected("校园及滨海地形")
    core=projected("育贤广场")
    design=gardens.lawns.difference(core)
    exposed=design.intersection(turf).difference(paving)
    ids=[i for i,n in enumerate(model.nodes) if n.get("extras",{}).get("v6Garden")]
    groups={"north":0,"south":0}
    min_gap=math.inf
    radius={}
    for i in ids:
        n=model.nodes[i];wing=n["extras"]["v6Garden"].split("-")[-1];groups[wing]+=1
        local=n["mesh"]
        if local not in radius:
            radius[local]=max(np.linalg.norm(model.accessor(p["attributes"]["POSITION"])[:,[0,2]],axis=1).max()
                              for p in model.g["meshes"][local]["primitives"])
        point=Point(*n["translation"][::2])
        assert exposed.covers(point),n["name"]
        min_gap=min(min_gap,point.distance(gardens.lawns.boundary)-radius[local]*n["scale"][0])
    rays=camera_rays(model,ids,catalog)
    probe=box(14,-149,65,-135)
    result={"sourceGLBSHA256":model.digest,"trees":groups,"designedLawnM2":round(design.area),"hiddenUnderCeremonySlabM2":round(gardens.lawns.intersection(core).area,2),
            "visibleLawnM2":round(exposed.area),"mappedWalkAndPavingOverlapM2":round(paving.intersection(gardens.lawns).area,4),
            "targetPlotVisibleLawnM2":round(exposed.intersection(probe).area),"crownClearanceM":round(float(min_gap),3),
            "catalogRays":rays}
    assert exposed.area>design.area-.25 and min_gap>-.02 and all(groups.values()),result
    assert not rays["hits"] and result["targetPlotVisibleLawnM2"]>400,result
    result["passed"]=True
    out=root/"data/v6_yuxian_audit.json"
    scratch=out.with_suffix(".tmp")
    scratch.write_text(json.dumps(result,ensure_ascii=False,indent=2),"utf8")
    scratch.replace(out)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    audit()

