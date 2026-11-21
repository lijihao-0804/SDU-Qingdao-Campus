"""博物馆东侧校友文化林。照片和正射图只用于辨认地物，模型以米制几何呈现。"""
import math
from collections import Counter
from pathlib import Path
import numpy as np
from shapely import covers, points
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from qd_geometry import Shape
from qd_terrain import sourcepolygon

OSM_ID = "way/981132253"
KEY = "v6-alumni-garden"
SOURCE = {
    "official": "https://www.view.sdu.edu.cn/info/1003/76009.htm",
    "orthophoto": "https://livingatlas.arcgis.com/wayback/#active=3692&mapCenter=120.68467%2C36.36088%2C19",
    "campusAerials": ["实景参照/地标/航拍02_南向北鸟瞰.png","实景参照/地标/航拍05_校区总览.png"],
    "satellite": "data/map/sentinel-20261007.npz",
}
# Normalized against the north-up 915 by 1144 pixel reference crop, extent
# [125,385] to [345,660] in campus metres. Keep these readings independent of
# campus-model camera projection and of future display resolution.
def world(pixel):
    x,y=pixel
    return (125+x*220/915,385+y*275/1144)


def curve(coords, closed=False):
    p=[world(v) for v in coords]
    for _ in range(2):
        refined=[] if closed else [p[0]]
        for a,b in zip(p,p[1:]+([p[0]] if closed else [])):
            refined.extend(((a[0]*.75+b[0]*.25,a[1]*.75+b[1]*.25),
                            (a[0]*.25+b[0]*.75,a[1]*.25+b[1]*.75)))
        p=refined if closed else refined+[p[-1]]
    return Polygon(p) if closed else LineString(p)


# Denser woody strips are separated by grass and several pale footways.
BEDS=(
    [(185,174),(326,159),(350,200),(302,211),(271,284),(217,300),(183,263)],
    [(277,395),(278,328),(318,253),(365,221),(418,219),(491,244),(532,271),(523,292),(481,272),(430,268),(383,297),(352,361),(325,402)],
    [(222,467),(314,474),(348,459),(369,403),(412,365),(479,346),(541,374),(622,348),(679,331),(682,391),(628,417),(578,432),(521,418),(474,391),(436,409),(414,460),(365,501),(291,529),(244,542)],
    [(259,578),(296,542),(358,526),(406,469),(463,440),(499,426),(536,457),(569,446),(611,438),(619,463),(567,492),(484,501),(441,535),(395,541),(350,559),(326,610)],
    [(214,617),(282,615),(311,657),(293,707),(232,701)],
    [(503,629),(514,577),(550,554),(601,542),(655,509),(678,490),(671,539),(636,557),(603,589),(549,612),(535,650)],
    [(630,738),(711,703),(762,748),(746,788),(683,806),(661,870),(616,854),(613,806)],
    [(278,797),(313,805),(342,847),(371,866),(410,870),(452,843),(487,838),(502,868),(469,905),(409,928),(359,917),(323,895)],
    [(207,900),(282,894),(316,960),(401,968),(480,953),(588,934),(660,919),(642,968),(578,995),(451,1001),(388,1021),(267,1030),(206,1007)],
    [(621,161),(691,164),(749,180),(737,218),(687,229),(632,216),(585,239),(547,228),(569,191)],
)
# Supplement the surveyed community-map loop with visible secondary paths.
# The straight pale west-side fan and small west arrival apron are hard paving.
PATHS=(
    (2.0,[(181,327),(235,342),(278,355)]),
    (1.8,[(183,399),(237,404),(278,411)]),
    (1.8,[(182,471),(221,472)]),
    (1.8,[(184,767),(222,765),(256,763)]),
    (1.8,[(181,841),(228,840),(265,842)]),
    (2.1,[(182,911),(226,905),(278,891)]),
    (1.45,[(196,473),(270,468),(326,468),(347,457),(366,415),(387,383),(428,360),(473,351),(507,359),(554,374),(591,366),(654,348),(691,343),(745,342)]),
    (1.65,[(292,612),(330,654),(375,686),(424,706),(474,699),(496,686),(524,699),(562,720),(599,740),(621,733),(673,705),(737,693)]),
    (1.65,[(258,765),(299,767),(340,788),(381,811),(415,819),(463,806),(493,793),(513,768),(522,733),(498,694)]),
    (1.5,[(512,896),(497,858),(488,809),(464,770)]),
    (1.65,[(684,348),(680,418),(688,479),(692,543),(689,611),(694,680),(705,701)]),
)
ROLES={"lawn":("校友文化林 · 开敞草坪","#9fa572",.078),
       "beds":("校友文化林 · 曲线林带与植床","#819265",.083),
       "paths":("校友文化林 · 园内小径与西侧铺装","#c2b394",.137)}


def layout(data):
    site=sourcepolygon(next(r for r in data["plazas"] if r["id"]==OSM_ID))
    roads=[]
    for r in data["roads"]:
        if r.get("tunnel") or len(r["line"])<2:continue
        ln=LineString(r["line"])
        if ln.distance(site)<r["width"]*.5+.6:
            roads.append(ln.buffer(r["width"]*.5,quad_segs=4))
    surveyed=unary_union(roads).intersection(site)
    plantable=site.difference(surveyed)
    paths=[curve(coords).buffer(width*.5,quad_segs=4) for width,coords in PATHS]
    for coords in [
        [(181,575),(214,578),(226,588),(217,602),(180,603)],
        [(181,578),(195,580),(193,754),(181,767)],
        [(182,324),(192,327),(193,540),(182,537)],
        [(181,763),(191,762),(190,903),(179,914)],
        [(178,908),(188,908),(190,960),(178,967)],
    ]:paths.append(Polygon([world(v) for v in coords]))
    paths=unary_union(paths).intersection(plantable)
    beds=unary_union([curve(coords,True) for coords in BEDS]).intersection(plantable).difference(paths)
    lawn=plantable.difference(paths).difference(beds)
    return dict(site=site,surveyed=surveyed,lawn=lawn,beds=beds,paths=paths)


def _surface(scene,terrain,role,p):
    name,colour,lift=ROLES[role];shape=Shape(name)
    terrain.skin(shape,p,colour,lift)
    if role in ("lawn","beds"):
        vertices=np.asarray(shape.parts[colour][0])
        x,z=vertices[:,0],vertices[:,2]
        shape.uvs={colour:list(zip(x*.42+z*.15,z*.42-x*.15))}
        light=.92+.055*np.sin(x*.072+.5*np.sin(z*.07))*np.cos(z*.049-x*.025)
        shape.vertex_tints={colour:list(zip(light,light+.015,light-.005))}
    scene.node(name,shape=shape,kind="parcelGround",parcel=KEY,gardenRole=role)
    if role in ("lawn","beds") and "grass" in scene.colors:
        turf=scene.doc["materials"][scene.colors["grass"]]["pbrMetallicRoughness"]
        if "baseColorTexture" in turf:
            mat=scene.doc["materials"][scene.colors[colour]]["pbrMetallicRoughness"]
            tint=[1.0,.88,.79,1.0] if role=="lawn" else [.62,.74,.57,1.0]
            mat.update(baseColorFactor=tint,baseColorTexture=turf["baseColorTexture"],roughnessFactor=.97)


def _plant(scene,terrain,data,areas,catalog):
    from qd_v6_planting import low_views
    blocked=low_views(terrain,catalog)
    usable=areas["beds"].union(areas["lawn"]).difference(blocked)
    grown=prep(usable.buffer(-3.2,quad_segs=4))
    low=prep(usable.buffer(-1.25,quad_segs=4))
    beds=prep(areas["beds"]);names={m["name"]:i for i,m in enumerate(scene.doc["meshes"])}
    rng=np.random.default_rng(247523)
    trees=[];shrubs=[]
    for z in np.arange(422,629,6.6):
        for x in np.arange(169,305,6.8):
            xx,zz=float(x+rng.uniform(-1.4,1.4)),float(z+rng.uniform(-1.4,1.4))
            q=Point(xx,zz);in_bed=beds.contains(q)
            edge=areas["site"].boundary.distance(q)<10
            if not grown.contains(q) or rng.random()>(.70 if in_bed else .39 if edge else .065):continue
            sc=float(rng.uniform(.53,.85) if in_bed else rng.uniform(.62,.99))
            trees.append((xx,zz));k=int(rng.integers(1,6))
            scene.node("校友文化林 · 阔叶树 "+str(len(trees)),mesh=names["乔木"+str(k)],
                       at=(xx,terrain.y(xx,zz)+.075,zz),yaw=float(rng.uniform(0,math.tau)),
                       scale=(sc,sc,sc),kind="flora",shrub=False,site=KEY)
    for z in np.arange(424,628,4.9):
        for x in np.arange(171,305,5.1):
            xx,zz=float(x+rng.uniform(-1.2,1.2)),float(z+rng.uniform(-1.2,1.2))
            q=Point(xx,zz)
            if not low.contains(q) or not beds.contains(q) or rng.random()>.52:continue
            if any((xx-a)**2+(zz-b)**2<6 for a,b in trees):continue
            shrubs.append((xx,zz));k=int(rng.integers(1,4));sc=float(rng.uniform(.58,1.02))
            scene.node("校友文化林 · 低灌木 "+str(len(shrubs)),mesh=names["灌丛"+str(k)],
                       at=(xx,terrain.y(xx,zz)+.076,zz),yaw=float(rng.uniform(0,math.tau)),
                       scale=(sc,sc,sc),kind="flora",shrub=True,site=KEY)
    return len(trees),len(shrubs)


def build(scene,terrain,data,catalog):
    parts=layout(data)
    for role in ROLES:_surface(scene,terrain,role,parts[role])
    trees,shrubs=_plant(scene,terrain,data,parts,catalog)
    x,z=235.5,525;y=terrain.y(x,z)
    catalog.append(dict(key=KEY,name="校友广场 · 博物馆东侧校友文化林",group="校园场地",x=x,y=y,z=z,h=8,r=105,
                        viewpoint=dict(eye=[336,y+92,665],target=[229,y+2,521],fov=50),
                        note="博物馆东侧的校友文化林由环路、园内支路、草坪及成片种植组成。林带与小径依正射和航拍概化，株位、树种与铺地材料为近似。"))
    return dict(areaM2=round(parts["site"].area,1),surfaceAreasM2={k:round(parts[k].area,1) for k in ("surveyed",*ROLES)},
                trees=trees,shrubs=shrubs,sources=SOURCE,
                uncertainty="正射地图用于辨认路径与林地轮廓，树种、株位和材色按实景近似。")


def check_export(model,data):
    """Use the actual exported surfaces, and check the park against legacy plaza paving."""
    areas=layout(data);result={};plants=Counter();common_paving=[];green=areas["beds"].union(areas["lawn"])
    for i in model.world:
        n=model.nodes[i];e=n.get("extras",{})
        if "mesh" not in n:continue
        if n["name"]=="石材广场与步行带":
            for batch,_ in model.triangles(i):
                xz=batch[:,:,[0,2]];b=areas["site"].bounds
                near=(xz[:,:,0].max(axis=1)>b[0])&(xz[:,:,0].min(axis=1)<b[2])&(xz[:,:,1].max(axis=1)>b[1])&(xz[:,:,1].min(axis=1)<b[3])
                common_paving.extend(Polygon(t).intersection(green).area for t in xz[near])
        if e.get("site")==KEY and e.get("kind")=="flora":
            x,_,z=model.transform(i,np.zeros((1,3)))[0]
            assert green.covers(Point(x,z)),("校友林植株越界",x,z)
            plants["shrubs" if e["shrub"] else "trees"]+=1
        if e.get("parcel")!=KEY:continue
        role=e["gardenRole"]
        tri=np.concatenate([batch for batch,_ in model.triangles(i)]);centers=tri.mean(axis=1)
        assert np.all(covers(areas[role].buffer(.045),points(centers[:,0],centers[:,2]))),role
        a,b=tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]
        measured=float(np.abs(a[:,0]*b[:,2]-a[:,2]*b[:,0]).sum()*.5)
        assert abs(measured-areas[role].area)<max(.5,.002*areas[role].area),(role,measured,areas[role].area)
        result[role]=round(measured,2)
    assert set(result)==set(ROLES) and plants["trees"] and plants["shrubs"]
    assert sum(common_paving)<.2,("旧广场铺面覆盖校友林",sum(common_paving))
    return dict(exportedAreasM2=result,exportedPlants=dict(plants),legacyPavingOnGreenM2=round(sum(common_paving),3))

