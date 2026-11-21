"""Rebuild the metre-scale campus from the attributed, bundled OSM extract.
Usage: python tools/qmap.py  (requires NumPy, SciPy, and Shapely 2)
"""
from pathlib import Path
import json
import math

from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "data" / "map"
LON0, LAT0 = 120.68204, 36.36559
PHI = math.radians(LAT0)
A, E2 = 6378137., 0.0066943799901413165
DEN = math.sqrt(1. - E2 * math.sin(PHI)**2)
MX = math.radians(1.) * A * math.cos(PHI) / DEN
MZ = math.radians(1.) * A * (1. - E2) / DEN**3
CAMPUS_WAY = 548364981
MAP_URL = "https://hq.qd.sdu.edu.cn/info/1053/1824.htm"
FLOORS_URL = "https://www.view.sdu.edu.cn/info/1003/46267.htm"
LIBRARY_URL = "https://www.sdsx.sdu.edu.cn/info/1160/10010.htm"
ARENA_URL = "https://www.chnja.net/portal/news/detail.html?id=954"

def local(lon, lat):
    return ((lon - LON0) * MX, (LAT0 - lat) * MZ)

def rounded(points, ring=False):
    pts = [[round(x, 2), round(z, 2)] for x,z in points]
    return pts[:-1] if ring and pts[0] == pts[-1] else pts

def parts(g, kind):
    if not g.is_empty:
        if g.geom_type == kind:
            yield g
        elif hasattr(g, "geoms"):
            for item in g.geoms:
                yield from parts(item, kind)

def record(e):
    t = e.get("tags", {})
    return dict(id=e["type"] + "/" + str(e["id"]), name=t.get("name", ""), source="OpenStreetMap", approx=False)

def polygon_fields(g):
    return dict(poly=rounded(g.exterior.coords, True),
                holes=[rounded(r.coords, True) for r in g.interiors],
                center=rounded([g.centroid.coords[0]])[0], area_m2=round(g.area, 1))

def building(e, shape):
    i = e["id"]
    t = e["tags"]
    f = {**record(e), **polygon_fields(shape)}
    f["kind"] = "academic"
    ar = shape.area
    if "凤凰居" in f["name"] or "专家公寓" in f["name"]:
        f["kind"] = "residence"
    elif i == 970257674: f["kind"] = "library"
    elif i == 970257675: f["kind"] = "museum"
    elif i == 982199335: f["kind"] = "arena"
    elif i == 982199336: f["kind"] = "stand"
    elif i == 868015917: f["kind"] = "dining"
    elif i in (1022925330,1022925331,1020621361,1020621362,1020621363): f["kind"] = "gatehouse"
    elif ar < 600: f["kind"] = "annex"
    f["osm_building"] = t["building"]
    if i==970257674:
        f.update(height=66.3, levels=12, height_approx=False, height_source=LIBRARY_URL)
    elif i==982199335:
        f.update(height=35., height_approx=True, height_source=ARENA_URL,
                 height_note="Published approximate roof high point of the competition hall, not the full polygon.")
    elif i==970257675:
        f.update(levels=6, levels_source=FLOORS_URL)
    elif i==13110947:
        f.update(levels=4, levels_source=FLOORS_URL)
    elif i==868015917:
        f.update(levels=3, levels_source=FLOORS_URL)
    elif "凤凰居" in f["name"] and "11" not in f["name"]:
        f.update(levels=6,levels_source=FLOORS_URL,levels_note="Local wings step to four storeys.")
    return f

def create():
    raw = json.loads((MAP/"osm-source.json").read_text(encoding="utf8"))
    els = raw["elements"]
    nodes = {e["id"]:e for e in els if e["type"]=="node"}
    xy = {i:local(n["lon"], n["lat"]) for i,n in nodes.items()}
    ways = {e["id"]:e for e in els if e["type"]=="way"}
    def coords(w): return [xy[n] for n in w["nodes"]]
    boundary = Polygon(coords(ways[CAMPUS_WAY]))
    near = boundary.buffer(135)
    water_extent = box(-750, -1430, 720, 1370)
    coast_extent = box(-850, -1500, 1800, 1460)
    doc = {k:[] for k in ("buildings","roads","pitches","water","greens","plazas","parking","gates","coastlines","beaches","construction")}
    doc["boundary"] = rounded(boundary.exterior.coords, True)
    doc["metadata"] = dict(title="山东大学（青岛校区）", address="山东省青岛市即墨区滨海路72号", 
        origin={"lon":LON0,"lat":LAT0,"crs":"WGS84"}, units="metres", x="east", z="south",
        projection="Local WGS84 tangent-plane scale at origin", metres_per_degree={"longitude":MX,"latitude":MZ},
        boundary_id="way/548364981",boundary_area_m2=round(boundary.area, 1),boundary_kind="OSM mapped campus perimeter; generalized community outline",
        bounds_xz=[round(v,2) for v in boundary.bounds],
        attribution="© OpenStreetMap contributors",license="ODbL 1.0",
        copyright="https://www.openstreetmap.org/copyright", license_url="https://opendatacommons.org/licenses/odbl/1-0/",
        source=raw["request"],raw_snapshot=raw["downloaded_utc"],official_map=MAP_URL,
        positional_accuracy="No surveyed ground control or independently verified absolute accuracy. Centimetre storage is numerical rounding only.",
        diagram="The university published a schematic of opened areas; named gate and building positions are derived from OSM. The northern sector has sparse mapped coverage.",
        height_policy="Only documented building heights or floor counts are supplied. Heights inferred by 3D authoring are illustrative.",
        roads_policy="OSM centre lines with width estimates from class or lanes unless a numerical width was mapped.",
        water_policy="Pond within the boundary plus nearby mapped water polygons tagged context; marine shore is a separate coastline array.",
        ring_policy="poly and boundary are open rings (implicit closing edge); holes are arrays of open courtyard/void rings.")
    member_ids = set()
    for e in els:
        if e["type"] != "relation" or "building" not in e.get("tags",{}): continue
        rings={"outer":[],"inner":[]}
        for m in e.get("members",[]):
            if m["type"]=="way" and m["role"] in rings and m["ref"] in ways:
                rings[m["role"]].append(LineString(coords(ways[m["ref"]])))
                member_ids.add(m["ref"])
        shells = list(polygonize(rings["outer"]))
        holes = list(polygonize(rings["inner"]))
        for shell in shells:
            shape = Polygon(shell.exterior, [p.exterior for p in holes if shell.covers(p.representative_point())])
            if boundary.covers(shape.representative_point()): doc["buildings"].append({**building(e,shape),"scope":"campus"})
    widths={"footway":2.8,"path":2.5,"steps":2.5,"cycleway":3.,"service":5.3,
            "residential":7.5,"living_street":6.,"tertiary":9.,"tertiary_link":6.,
            "secondary":12.,"secondary_link":6.5,"primary":14.,"trunk":15.}
    track_ids={970257666,996232451}
    court_bases={970257650,970257663,970257664,970257665}
    for i,w in ways.items():
        t=w.get("tags",{}); n=w["nodes"]; cs=coords(w)
        if i==CAMPUS_WAY or i in member_ids: continue
        hwy=t.get("highway")
        if hwy in widths and len(cs)>1:
            line=LineString(cs)
            for j,p in enumerate(parts(line.intersection(near),"LineString")):
                if p.length<1: continue
                f=record(w);f["id"] += ":"+str(j) if j else ""
                width=widths[hwy]
                width_kind="class estimate"
                if t.get("lanes","").isdigit() and hwy not in ("footway","steps"):
                    width=int(t["lanes"])*3.25 + 0.8
                    width_kind="lane estimate"
                if t.get("width","").replace(".","",1).isdigit():
                    width=float(t["width"]); width_kind="tag"
                if t.get("name","").endswith("大道") and width_kind=="class estimate": width=max(width,9.0)
                try: grade=int(t.get("layer","0"))
                except ValueError: grade=0
                doc["roads"].append({**f,"line":rounded(p.coords),"width":width,"width_source":width_kind,"kind":hwy,"grade":grade,
                    "bridge":t.get("bridge","no")!="no","tunnel":t.get("tunnel","no")!="no","surface":t.get("surface",""),
                    "scope":"campus" if boundary.covers(p.interpolate(.5,normalized=True)) else "context"})
        if t.get("natural")=="coastline":
            for j,p in enumerate(parts(LineString(cs).intersection(coast_extent),"LineString")):
                doc["coastlines"].append({**record(w),"line":rounded(p.coords),"part":j})
        if n[0]!=n[-1] or len(n)<4: continue
        poly=Polygon(cs)
        if not poly.is_valid: poly=poly.buffer(0)
        if poly.is_empty: continue
        span="campus" if boundary.buffer(2).covers(poly.representative_point()) else "context"
        if "building" in t and (span=="campus" or poly.distance(boundary)<5):
            if poly.geom_type=="Polygon":
                doc["buildings"].append({**building(w,poly),"scope":span})
            continue
        group=None; clip=boundary
        if t.get("natural")=="water": group="water"; clip=water_extent; kind=t.get("water","pond")
        elif t.get("natural")=="beach": group="beaches"; clip=coast_extent; kind="sand"
        elif t.get("leisure") in ("pitch","track"):
            group="pitches"; kind="track" if i in track_ids else "court_base" if i in court_bases else t.get("sport",t.get("leisure"))
        elif t.get("landuse") in ("forest","grass","meadow") or t.get("natural")=="wood" or t.get("leisure")=="park":
            group="greens";kind=t.get("landuse",t.get("natural",t.get("leisure")));clip=near if kind=="park" else boundary
        elif t.get("place")=="square": group="plazas";kind="square"
        elif t.get("amenity") in ("parking","parking_space"): group="parking";kind=t["amenity"]
        elif t.get("landuse")=="construction": group="construction";kind="construction"
        if not group: continue
        for j,part in enumerate(parts(poly.intersection(clip),"Polygon")):
            if part.area<20: continue
            f={**record(w),**polygon_fields(part),"kind":kind,"scope":span}
            if j: f["id"]+=":"+str(j)
            if group=="pitches":
                f["sport"]=kind; f["sport_source"]="OSM sport tag" if t.get("sport") else "campus map interpretation"
                f["base"]=kind in ("track","court_base")
            doc[group].append(f)
    for n in nodes.values():
        t=n.get("tags",{})
        if t.get("barrier")=="gate" and t.get("name"):
            doc["gates"].append({**record(n),"point":rounded([xy[n["id"]]])[0],"lon":n["lon"],"lat":n["lat"]})
    doc["pitches"].sort(key=lambda v:-v["area_m2"])
    enrich(doc,ways,coords)
    return doc

SAT = "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_51STA_20261007_0_L2A"
NORTH_MAP = "http://www.bgxx.qd.sdu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=5831&wbtreeid=1004"
HALL = "https://www.qdxq.sdu.edu.cn/info/1722/47541.htm"
PHASE2 = "https://jjc.qd.sdu.edu.cn/info/1022/1446.htm"

def enrich(doc, ways, coords):
    import numpy as np
    from shapely.geometry import Point
    from shapely.geometry.polygon import orient
    from shapely.affinity import scale
    all_features = {f["id"]:f for group in doc.values() if isinstance(group,list)
                    for f in group if isinstance(f,dict) and "id" in f}
    all_features["way/982180787"].update(name="樱海湖", name_source=NORTH_MAP)
    all_features["way/982199335"].update(official_name="宋君复体育馆", name_source="https://www.qdxq.sdu.edu.cn/info/1819/64682.htm")
    names={970257668:"淦昌苑F区",970257670:"淦昌苑A区",970257671:"第周苑E区",868015920:"第周苑B区",
        868015921:"第周苑F区",868015918:"第周苑C区",868015916:"第周苑D区",868015919:"第周苑A区",
        1018848586:"淦昌苑B区",970257667:"淦昌苑C区",868015915:"淦昌苑D区",970257669:"淦昌苑E区"}
    for i,name in names.items():
        f=all_features["way/"+str(i)]
        f["group_name"]=name
        if i==970257669: f.update(name="环境科学与工程学院", name_source="https://www.huanke.sdu.edu.cn/info/1065/5655.htm")
        if not f["name"]: f.update(name=name,name_source=MAP_URL)
    def add(group,ident,name,kind,g,info,**attrs):
        f={"id":"s2/"+ident,"name":name,"kind":kind,"scope":"campus","approx":True,
           "source":SAT,"interpretation_source":info,"geometry_method":"Generalized interpretation of 10 m Sentinel-2 pixels",
           **polygon_fields(orient(g)),**attrs}
        doc[group].append(f)
        return f
    def flat(x1,z1,x2,z2): return box(x1,z1,x2,z2)
    def cblock(x,z,w,d,arm):
        return Polygon([(x,z),(x+w,z),(x+w,z+arm),(x+arm,z+arm),
                        (x+arm,z+d-arm),(x+w,z+d-arm),(x+w,z+d),(x,z+d)])
    blocks=[
        ("b1","阅海居 B1","residence",cblock(-49,-1042,84,90,21)),
        ("b2","阅海居 B2","residence",flat(50,-1038,71,-968)),
        ("b5","阅海居 B5","residence",flat(-50,-956,-30,-881)),
        ("b6","晨园餐厅","dining",flat(-15,-941,29,-887)),
        ("b9","阅海居 B9","residence",cblock(-49,-870,87,90,19)),
        ("b10","阅海居 B10","residence",flat(50,-864,71,-782))]
    for ident,name,kind,g in blocks:
        f=add("buildings",ident,name,kind,g,NORTH_MAP)
        if ident=="b6":f.update(levels=2,levels_source="https://www.bgxx.qd.sdu.edu.cn/content.jsp?urltype=news.NewsContentUrl&wbnewsid=5833&wbtreeid=1004")
    for i,z in enumerate((935,984,1036,1088,1143),start=4):
        add("buildings","south-t"+str(i),"专家公寓 T"+str(i),"residence",
            flat(465,z-10,568,z+11),PHASE2)
    hall=scale(Point(76,-648).buffer(1,resolution=18),73,76)
    void=scale(Point(75,-648).buffer(1,resolution=12),51,52)
    add("buildings","hall-c1","学生会堂 C1","auditorium",hall.difference(void),HALL,
        levels=5,levels_source=HALL,state="project observed in October 2026; opening date unverified",
        note="Pale annular roof and central open area simplified from imagery; design has three shell-shaped volumes.")
    m=flat(-72,-512,32,-387).difference(flat(-51,-491,10,-411))
    add("buildings","research-m","工程技术研究院 M区","academic",m,NORTH_MAP,
        state="roof visible; occupancy unverified")
    d1=Polygon([(113,-497),(164,-497),(164,-477),(140,-477),(140,-407),(163,-407),
                (163,-386),(111,-386)])
    d5=Polygon([(169,-520),(313,-520),(313,-466),(289,-466),(289,-478),(191,-478),
                (191,-460),(170,-460)])
    for ident,label,g in [("d1","D1",d1),("d5","D5",d5)]:
        add("buildings","research-"+ident,"工程技术研究院 "+label,"academic",g,NORTH_MAP,
            levels=4,levels_source="https://ggzy.qingdao.gov.cn/c/TradeDetals-ZtbShow/176918-5021-0-0-0/bc18c233-765d-49f8-b52e-e9f44be4c833-B03CE5B6FC1D2D3C2D5FCEBC39AA2406.html",
            state="Construction project; October 2026 image shows roof-level massing.")
    add("pitches","north-courts","北区室外球场","court_base",flat(-121,-1027,-71,-916),NORTH_MAP,
        sport="court_base",base=True)
    if "way/1575469862" in all_features:
        all_features["way/1575469862"].update(name="学生会堂项目用地",context="The building is mapped separately.")
    # Fit the two campus diagrams separately; independent check features are excluded from fitting.
    control_south=[
        (548364982,548364983,270,164),(548364982,868015887,267,311),(548364988,548364990,933,575),
        (548364989,548364991,390,731),(548364991,548364994,815,731),(548364994,868002331,813,1099)]
    test_south=[(548364989,548364990,390,575),(548364991,548364993,568,731),(548364993,868002331,567,1005)]
    # Northern illustration coordinates refer to a 750x850 resampling of the 794x900 original.
    control_north=[
        (548364982,548364986,161,149),(548364986,868015888,483,149),(548364982,548364985,174,348),
        (548364982,548364984,184,492),(548364984,868015888,567,492),(548364983,868015888,678,732)]
    test_north=[(548364985,868015888,534,348),(548364982,548364983,207,732),(548364986,548364987,370,149)]
    def registration(rows,tests,url,size,original):
        def pair(row):
            i,j,u,v=row; p=LineString(coords(ways[i])).intersection(LineString(coords(ways[j])))
            if p.geom_type!="Point":raise ValueError((i,j,p))
            return {"roads":[ways[i]["tags"]["name"],ways[j]["tags"]["name"]],"osm":[i,j],"uv":[u,v],
                "xz":rounded([p.coords[0]])[0]}
        fit=[pair(row) for row in rows];check=[pair(row) for row in tests]
        mat=np.array([f["uv"]+[1] for f in fit])
        coeff=np.linalg.lstsq(mat,np.array([f["xz"] for f in fit]),rcond=None)[0]
        for p in fit+check:
            p["residual_m"]=round(float(np.linalg.norm(np.array(p["uv"]+[1])@coeff-np.array(p["xz"]))),1)
        return dict(source=url,image_dimensions=size,source_image_dimensions=original,affine_uv1_to_xz=coeff.round(6).tolist(),
             reference="Image pixel centres from upper left; numeric road coordinates are community OSM values",
             controls=fit,checks=check,control_rmse_m=round(float(np.sqrt(np.mean([p["residual_m"]**2 for p in fit]))),1),
             check_rmse_m=round(float(np.sqrt(np.mean([p["residual_m"]**2 for p in check]))),1),
             note="Diagram-to-map residuals only; this does not assess positional error against surveyed ground truth.")
    doc["metadata"]["diagram_registration"]={
        "south":registration(control_south,test_south,MAP_URL,[1024,1232],[1024,1232]),
        "north":registration(control_north,test_north,NORTH_MAP,[750,850],[794,900])}
    # Show broad vegetated northern blocks from visible reflectance while keeping the mapped building and road network clear.
    from scipy.ndimage import binary_opening, binary_closing, label
    sat=np.load(MAP/"sentinel-20261007.npz")
    r=sat["red"].astype(float);n=sat["nir"].astype(float)
    # Provider indicates that the BOA additive offset was already applied to the COG values.
    vegetation=(n-r)/(n+r+1)>.46
    x,z=np.meshgrid(sat["x"],sat["z"])
    vegetation=binary_opening(binary_closing(vegetation & (z<-180),iterations=1),iterations=1)
    labels,ncomp=label(vegetation)
    boundary=Polygon(doc["boundary"])
    occupied=unary_union([Polygon(k["poly"]).buffer(7) for k in doc["buildings"]+doc["water"]+doc["pitches"]]
                        +[LineString(k["line"]).buffer(k["width"]/2+3) for k in doc["roads"]]
                        +[Polygon(k["poly"]) for k in doc["greens"]+doc["construction"]])
    for k in range(1,ncomp+1):
        select=labels==k
        if select.sum()<16:continue
        pads=[flat(xi-5,zi-5,xi+5,zi+5) for xi,zi in zip(x[select],z[select])]
        shape=unary_union(pads).intersection(boundary).difference(occupied).simplify(11,preserve_topology=True)
        for j,g in enumerate(parts(shape,"Polygon")):
            if g.area>2200:
                add("greens",f"vegetation-{k}-{j}","","mixed_vegetation",g,SAT)
    doc["metadata"].update(sentinel_source=SAT,sentinel_credit="Contains modified Copernicus Sentinel data (2026).",
       sentinel_terms="https://dataspace.copernicus.eu/terms-and-conditions",sentinel_date="2026-10-07",sentinel_resolution_m=10,
       supplemental_accuracy="Satellite roof outlines are generalized from 10 m pixels. Roof edges, building subdivisions, and dates of opening have additional unquantified uncertainty.",
       diagram="Campus diagrams identify named blocks and access roads. Only additions with visible October 2026 imagery evidence are modelled.",
       supplemental_note="The eastern library forecourt shows paving and landscaping on the fall image; a permanent pool on the axis was not confirmed. Legal campus lines and survey ground control are unavailable.")
    doc["pitches"].sort(key=lambda v:-v["area_m2"])

if __name__=="__main__":
    result=create()
    target=MAP/"campus.json"
    temp=target.with_suffix(".tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    temp.replace(target)
    print({k:len(v) for k,v in result.items() if isinstance(v,list)})
