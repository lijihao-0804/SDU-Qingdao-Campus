"""Reconstruct the northern Qingdao campus parcels against two image epochs.

Coordinates are metres east/south of the campus origin. The Wayback release is
an archive version, not an acquisition date. Temporary building heights, court
subdivision and the 10 m ground-material transitions are approximate.
"""
from pathlib import Path
import math

import numpy as np
from shapely.affinity import scale
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from qd_geometry import Shape
from qd_terrain import sourcepolygon

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {
    "sports_site": "https://hq.qd.sdu.edu.cn/info/1017/2721.htm",
    "sports_open": "https://www.qdxq.sdu.edu.cn/info/1819/64729.htm",
    "pickleball_at_b1": "https://tyb.qd.sdu.edu.cn/info/1020/1833.htm",
    "hall": "https://www.qdxq.sdu.edu.cn/info/1722/47541.htm",
    "research_yard": "https://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260923_27392337.htm",
    "orthophoto": "https://livingatlas.arcgis.com/wayback/#active=3692&mapCenter=120.68288%2C36.37141%2C19",
    "satellite": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_51STA_20261007_0_L2A",
}
# Metal roofs traced on both sides of Haoran Avenue. These are ancillary
# works compounds in the aerials. Occupants and the number of floors are unknown.
CABINS = (
    (-78.3,-622.6,-47.8,-615.0), (-78.3,-610.9,-47.5,-603.4),
    (-78.3,-599.2,-47.1,-591.8), (-78.4,-586.6,-45.9,-578.9),
    (-43.5,-585.2,-36.1,-553.7), (-39.4,-621.4,-33.1,-593.3),
    (-122.0,-491.5,-96.4,-483.5), (-127.0,-473.0,-97.3,-465.9),
    (-125.0,-510.5,-97.5,-502.8),
)


def _ring(x, z, rx, rz):
    return scale(Point(x,z).buffer(1,quad_segs=64), xfact=rx,yfact=rz,origin=(x,z))


def _line(coords, width):
    return LineString(coords).buffer(width/2,cap_style="flat",join_style="round")


def _open_ground(region):
    """Accept connected bright, low-NDVI 10 m pixels only within the works lot."""
    with np.load(ROOT/"data/map/sentinel-20261007.npz") as sat:
        x, z = np.meshgrid(sat["x"],sat["z"])
        red = sat["red"].astype(float)
        nir = sat["nir"].astype(float)
        left, top, right, bottom = region.bounds
        mask = ((x >= left-5) & (x <= right+5) & (z >= top-5) &
                (z <= bottom+5) & (sat["rgb"][:,:,0] >= 84) &
                ((nir-red)/(nir+red+1) < .39))
        cells = [box(a-5,b-5,a+5,b+5) for a,b in zip(x[mask],z[mask])]
    # Round away the 10 m image pixel corners. Preserve the original source fence.
    coarse = unary_union(cells)
    return coarse.buffer(5,quad_segs=3).buffer(-6.0,quad_segs=3).intersection(region)


def layout(data):
    rows = {r["id"]:r for key in ("pitches","construction","buildings","greens") for r in data[key]}
    court = sourcepolygon(rows["s2/north-courts"])
    roads = unary_union([_line(r["line"],r["width"]+.75) for r in data["roads"]
                         if len(r["line"])>1 and not r.get("tunnel")])
    built = unary_union([sourcepolygon(row) for row in data["buildings"]])
    lakes = unary_union([sourcepolygon(row) for row in data["water"]])
    protect = unary_union([roads, built.buffer(.45), lakes.buffer(.9)])
    cleared = sourcepolygon(rows["way/1575469862"]).buffer(-.85)
    cx, cz = rows["s2/hall-c1"]["center"]
    # The constructed v4/v5 roof is larger than the initial 10 m source polygon.
    hall = cleared.difference(_ring(cx,cz,82.6,84.1)).difference(protect)
    lane = unary_union([
        _line([(-11,-740),(-14,-699),(-14,-607),(-9,-559),(22,-556),(94,-554),(163,-553),(164,-610)],5.6),
        _line([(-11,-738),(3,-741),(51,-741),(100,-739),(151,-735)],4.8),
        _line([(-12,-588),(4,-571),(23,-563),(43,-561)],5.1),
        _line([(164,-607),(150,-578),(132,-568),(108,-558)],5.8),
    ]).intersection(hall)
    compounds = unary_union([
        Polygon([(-80,-625),(-45,-625),(-30,-621),(-26,-590),(-22,-587),(-22,-553),(-79,-552)]),
        Polygon([(-130,-523),(-94,-523),(-92,-448),(-124,-448),(-132,-466)]),
    ]).difference(protect)
    research_zone = unary_union([
        box(-88,-532,45,-366),
        Polygon([(42,-534),(101,-535),(101,-384),(67,-368),(39,-375)]),
        Polygon([(99,-532),(322,-538),(341,-519),(349,-466),(299,-457),
                 (258,-439),(219,-399),(175,-372),(103,-377)]),
        Polygon([(169,-401),(242,-431),(263,-416),(245,-341),(206,-294),(180,-312)]),
    ])
    research = _open_ground(research_zone).difference(protect).difference(compounds)
    # Confine unpaved garden walks to the row-planted eastern block. The western
    # parallel strip and yard roads run separately, outside the mapped woodland.
    forest = sourcepolygon(rows["way/982199351"])
    rows_walk = unary_union([
        _line([(254,-748),(253,-550)],2.5), _line([(327,-741),(328,-550)],2.25),
        _line([(185,-705),(360,-704)],2.4), _line([(185,-650),(368,-648)],2.4),
        _line([(185,-597),(380,-596)],2.2),
    ]).intersection(forest.buffer(-1)).difference(protect)
    # The B1-side walkway joins the court to the mapped residence access.
    walkway = _line([(-72,-988),(-66,-988),(-62,-990)],2.5).difference(protect).difference(court)
    return dict(court=court, hall=hall, lane=lane, compounds=compounds,
                research=research, garden_walks=rows_walk, entrance=walkway)


def reserve(data):
    """Shapely area protecting only modelled solid or hard ground from planting."""
    return unary_union(list(layout(data).values())).buffer(.32,quad_segs=2)


def _surface(scene, terrain, name, area, colour, lift, key):
    shape = Shape(name)
    terrain.skin(shape,area,colour,lift)
    scene.node(name,shape=shape,kind="parcelGround",parcel=key,approximate=True)


def _cabins(scene,terrain,perimeter):
    count=0
    colours=("#829aab","#849daf","#7893a8","#c0c5bd","#758ba0",
             "#89979e","#75869f","#68829f","#abb6b4")
    for i,(left,top,right,bottom) in enumerate(CABINS):
        base=box(left,top,right,bottom)
        if not perimeter.covers(base): continue
        x,z=base.centroid.coords[0]
        w,d=right-left,bottom-top
        # Buildings grade into their site. The low plinth has an individually
        # draped lower edge, with a common upper edge under the wall panels.
        corners=[(left,top),(left,bottom),(right,bottom),(right,top)]
        datum=max(terrain.y(a,b) for a,b in corners)+.23
        name="北区工程用房 · %02d"%(i+1)
        shape=Shape(name)
        for j,(a,b) in enumerate(corners):
            c,e=corners[(j+1)%4]
            shape.mesh("台基",[(a,terrain.y(a,b)+.03,b),(c,terrain.y(c,e)+.03,e),
                              (c,datum+.05,e),(a,datum+.05,b)],[(0,1,2,3)],"#989c94")
        h=3.15
        shape.box("浅色装配式墙板",x,datum+h/2,z,w,h,d,"#cfcec0")
        along_x=w>d
        long,short=(w,d) if along_x else (d,w)
        def pt(t,o,y):
            return (x+t,y,z+o) if along_x else (x+o,y,z+t)
        for side in (-1,1):
            o=side*(short/2+.15)
            roof=[pt(-long/2-.14,o,datum+h+.12),pt(long/2+.14,o,datum+h+.12),
                  pt(long/2+.14,0,datum+h+.59),pt(-long/2-.14,0,datum+h+.59)]
            shape.mesh("浅坡彩钢屋面",roof,[(0,1,2,3)],colours[i])
            n=max(1,int(long//3.8))
            for k in range(n):
                t=long*((k+.5)/n-.5)
                a,y,b=pt(t,side*(short/2+.026),datum+1.72)
                shape.box("成组侧窗",a,y,b,1.4 if along_x else .08,1.08,
                          .08 if along_x else 1.4,"#667b81")
        scene.node(name,shape=shape,kind="worksCabin",key="v6-works-cabin-%02d"%(i+1),approximate=True)
        count+=1
    return count


def _nets(scene,terrain,stations):
    shape=Shape("阅海居西侧 · 匹克球网")
    for x,z in stations:
        for dx in (-3.36,3.36):
            shape.cyl("网柱",x+dx,terrain.y(x+dx,z)+.83,z,.055,1.0,"#4b6464",8)
        for j in range(5):
            y=1.18-j*.145
            shape.mesh("疏网横线",[(px,terrain.y(px,z)+y+dy,z)
                                  for px,dy in [(x-3.32,0),(x+3.32,0),(x+3.32,.016),(x-3.32,.016)]],
                       [(0,1,2,3)],"#596868")
        for k in range(27):
            px=x-3.25+k*.25
            shape.box("疏网竖丝",px,terrain.y(px,z)+.91,z,.017,.57,.017,"#596868")
        shape.mesh("白色网带",[(px,terrain.y(px,z)+1.25+dy,z)
                               for px,dy in [(x-3.35,0),(x+3.35,0),(x+3.35,.048),(x-3.35,.048)]],
                   [(0,1,2,3)],"#e4e6db")
    scene.node(shape.name,shape=shape,kind="sport",parcel="v6-north-courts")


def _sport(scene,terrain,site):
    _surface(scene,terrain,"阅海居西侧 · 球场边带",site,"#87999a",.342,"v6-north-courts")
    inner=site.buffer(-1.05,join_style="mitre")
    south=inner.intersection(box(-125,-968,-65,-910))
    north=inner.difference(south)
    _surface(scene,terrain,"北区室外运动场 · 靛蓝面层",north,"#58699d",.362,"v6-north-courts")
    _surface(scene,terrain,"北区室外运动场 · 蓝色活动区",south,"#558bc0",.362,"v6-north-courts")
    stations=[(x,z) for x in (-110,-96,-82) for z in (-1010,-986)]
    paint=[]; fields=[]
    for x,z in stations:
        playing=box(x-3.05,z-6.705,x+3.05,z+6.705)
        fields.append(playing)
        paint.append(playing.boundary.buffer(.035,cap_style="flat",join_style="mitre"))
        for sign in (-1,1):
            paint.extend([_line([(x-3.05,z+sign*2.134),(x+3.05,z+sign*2.134)],.070),
                          _line([(x,z+sign*2.134),(x,z+sign*6.705)],.070)])
    _surface(scene,terrain,"北区匹克球场 · 双打界内面",unary_union(fields),"#446395",.378,"v6-north-courts")
    _surface(scene,terrain,"北区匹克球场 · 端线与非截击区",unary_union(paint),"#eeeadd",.404,"v6-north-courts")
    _nets(scene,terrain,stations)
    # The remaining manifold supports a different blue finish. Its current
    # discipline and striping cannot be resolved at 10 m, so leave it open.
    furnishing=Shape("北区体育场 · 周边坐凳与灯具")
    for z in (-1010,-984,-947,-930):
        x=-119
        h=terrain.y(x,z)+.35
        furnishing.box("场边坐凳",x,h+.49,z,.52,.12,2.2,"#997b5f")
        for u in (-.74,.74):
            furnishing.box("凳脚",x,h+.22,z+u,.4,.44,.13,"#7e8985")
    for x in (-119.4,-72.8):
        for z in (-1019,-973,-924):
            h=terrain.y(x,z)+.35
            furnishing.cyl("侧灯柱",x,h+3.8,z,.105,7.6,"#aab4ae",10)
            furnishing.box("投光灯",x,h+7.6,z,.64,.18,.40,"#d5d9ce")
    scene.node(furnishing.name,shape=furnishing,kind="sport",parcel="v6-north-courts")


def _ground_finish(scene):
    """Repeat an original aggregate texture in metres, with broad changes in tone."""
    from PIL import Image
    from scipy.ndimage import gaussian_filter
    from qd_spring_surfaces import add_image

    rng=np.random.default_rng(682065)
    grain=rng.normal(size=(192,192))
    def band(sigma):
        smooth=gaussian_filter(grain,sigma,mode="wrap")
        return smooth/max(.001,smooth.std())
    # A near-white multiplier preserves the calibrated diffuse ground colours.
    coarse=band(9.0)*3.2+band(2.1)*3.3+grain*5.6
    tile=np.clip(243+coarse,216,255).astype(np.uint8)
    texture=add_image(scene,"整地与施工通道 · 矿料颗粒",Image.fromarray(tile).convert("RGB"),"JPEG",True)
    names=("#a28f72","#a28c6d","#b2a38c","#bcb197","#a69876")
    keys={scene.colors[n] for n in names if n in scene.colors}
    for key in keys:
        scene.doc["materials"][key]["pbrMetallicRoughness"].update(baseColorTexture=texture,roughnessFactor=.98)
    for mesh in scene.doc["meshes"]:
        for prim in mesh["primitives"]:
            if prim["material"] not in keys:
                continue
            attrs=prim["attributes"]
            pos=scene.doc["accessors"][attrs["POSITION"]]
            view=scene.doc["bufferViews"][pos["bufferView"]]
            verts=np.frombuffer(scene.raw,dtype="<f4",offset=view["byteOffset"],
                                count=pos["count"]*3).reshape(-1,3).copy()
            x,z=verts[:,0],verts[:,2]
            uv=np.column_stack(((x+.31*z)/3.4,(z-.31*x)/3.4))
            value=.965+.033*np.sin(x*.046+z*.029)*np.cos(z*.071-x*.023)
            attrs["TEXCOORD_0"]=scene.accessor(uv,"<f4","VEC2",5126,34962)
            attrs["COLOR_0"]=scene.accessor(np.column_stack((value,value,value)),"<f4","VEC3",5126,34962)


def build(scene,terrain,data,catalog):
    areas=layout(data)
    _sport(scene,terrain,areas["court"])
    _surface(scene,terrain,"阅海居运动场 · 东侧入口",areas["entrance"],"#b5ad96",.18,"v6-north-courts")
    _surface(scene,terrain,"学生会堂建设用地 · 外圈整地面",areas["hall"].difference(areas["lane"]),
             "#a28f72",.119,"v6-hall-ground")
    _surface(scene,terrain,"学生会堂建设用地 · 浅色通道",areas["lane"],"#bcb197",.121,"v6-hall-ground")
    _surface(scene,terrain,"浩然大道两侧 · 工程用房院地",areas["compounds"],"#b2a38c",.14,"v6-works-compound")
    _surface(scene,terrain,"研究院 M、D 区 · 整地施工范围",areas["research"],"#a28c6d",.113,"v6-research-yard")
    _surface(scene,terrain,"会堂东侧 · 种植地行间通道",areas["garden_walks"],"#a69876",.116,"v6-garden-tracks")
    built=_cabins(scene,terrain,areas["compounds"])
    _ground_finish(scene)
    for key,title,x,z,h,r,eye,note in [
        ("v6-north-courts","北区体育场 · 阅海居西侧匹克球场",-96,-989,2,56,(-168,38,-912),
         "校方赛事规程将匹克球场定位在阅海居B1正门。十月卫星影像能辨蓝色运动场；匹克球划线数量、分布及灯位为示意。"),
        ("v6-hall-ground","学生会堂 · 林庭与外侧施工场地",76,-647,20,108,(-121,94,-476),
         "高分影像可辨三瓣屋体、中央树庭、外围通道和西南侧临时用房。工地表面、临建檐高和设施位置按影像估绘。"),
        ("v6-research-yard","工程技术研究院 · 施工与室外配套",108,-454,15,120,(-83,83,-313),
         "M、D区附近可辨整地和工程用房。2026年9月D区室外配套招标，十月卫星影像用于区分已清理地块与林地。"),
    ]:
        ex,dy,ez=eye; y=terrain.y(x,z)
        catalog.append(dict(key=key,name=title,x=x,y=y,z=z,h=h,r=r,group="校园场地",
                            note=note,viewpoint=dict(eye=[ex,y+dy,ez],target=[x,y+h*.4,z],fov=44)))
    return {"v6NorthernCourtAreaM2":round(areas["court"].area),
            "v6PickleballIllustrativeCourts":6,"v6WorksCabins":built,
            "v6HallExteriorGroundM2":round(areas["hall"].area),
            "v6ResearchExposedGroundM2":round(areas["research"].area),
            "v6NurseryTrackM2":round(areas["garden_walks"].area)}

