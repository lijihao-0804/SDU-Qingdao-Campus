"""Editable indoor courts, playing nets and athletics equipment for Qingdao campus."""
import math
from pathlib import Path

import mapbox_earcut as ear
import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from qd_civic import beam
from qd_geometry import Shape, lin
from qd_spring_surfaces import add_image

ROOT=Path(__file__).resolve().parents[1]
WHITE="#f2efde"
NET_DARK="球网 · 深青编绳网孔"
NET_LIGHT="球网 · 米白编绳网孔"
INDOOR_LIGHT="风雨操场 · 内侧漫射采光带"
COURT_KINDS={"basketball","volleyball","tennis","badminton","soccer"}
LEGACY_KIT={"#f3eedb","#587c78","#c26842","#566c68","#718281"}
VERSION="青岛运动设施-1"
SOURCES={
    "风雨操场校方竣工实拍与场数":"https://jjc.qd.sdu.edu.cn/info/1022/1262.htm",
    "风雨操场全封闭钢桁架":"https://jjc.qd.sdu.edu.cn/info/1022/1055.htm",
    "网球场、东田径场、室外篮球场与小足球场实地检查":"https://www.tyb.sdu.edu.cn/info/1115/5670.htm",
    "室外网球场预约":"https://tyb.qd.sdu.edu.cn/info/1020/1487.htm",
    "东侧运动区":"实景参照/视频时码/V3-090.50.jpg",
    "东田径场沙坑、蓝色落地区、场门及东侧球场":"实景参照/视频时码/V3-098.50.jpg",
    "蓝色田径场、风雨操场与体育馆的相邻位置":"实景参照/视频时码/V3-126.50.jpg",
}


def surface(s,name,shape,y,colour):
    for g in getattr(shape,"geoms",[shape]):
        if g.is_empty or g.geom_type!="Polygon" or g.area < 1e-6:
            continue
        rings=[np.asarray(r.coords)[:-1] for r in (g.exterior,*g.interiors)]
        pts=np.concatenate(rings)
        idx=ear.triangulate_float64(pts,np.cumsum([len(a) for a in rings],dtype=np.uint32)).reshape(-1,3)
        s.mesh(name,[(x,y,z) for x,z in pts],idx[:,::-1],colour)


def mark(points,width=.075):
    return LineString(points).buffer(width/2,cap_style="flat",join_style="round")


def rect(w,d,width=.075):
    return mark([(-w,-d),(w,-d),(w,d),(-w,d),(-w,-d)],width)


def arc(x,z,r,start,end,count=70):
    return [(x+r*math.cos(a),z+r*math.sin(a)) for a in np.linspace(start,end,count)]


def net_panel(s,name,points,uv,colour,cell):
    idx=[(0,1,2)] if len(points)==3 else [(0,1,2,3)]
    s.mesh(name,points,idx,colour)
    if not hasattr(s,"uvs"):
        s.uvs={}
    s.uvs.setdefault(colour,[]).extend((a/cell,b/cell) for a,b in uv)


def install_materials(scene):
    a=np.arange(64)+.5
    wire=np.minimum(a,64-a)
    coverage=np.maximum(0,np.minimum(1,3.2-np.minimum(wire[:,None],wire[None,:])))
    rgba=np.full((64,64,4),255,dtype=np.uint8);rgba[:,:,3]=np.rint(coverage*255)
    tex=add_image(scene,"运动绳网 · 方孔与柔边",Image.fromarray(rgba),"PNG",True)
    for material,colour in ((NET_DARK,(59,75,71)),(NET_LIGHT,(224,225,208))):
        m=scene.doc["materials"][scene.mat(material)]
        m.update(alphaMode="BLEND",doubleSided=True,extras={"sportNet":True})
        m["pbrMetallicRoughness"].update(baseColorFactor=[lin(n/255) for n in colour]+[1.0],baseColorTexture=tex,roughnessFactor=.84)
    m=scene.doc["materials"][scene.mat(INDOOR_LIGHT)]
    m["pbrMetallicRoughness"].update(baseColorFactor=[.78,.8,.8,1],roughnessFactor=.88)
    m["emissiveFactor"]=[.95,.91,.82]
    m["extensions"]={"KHR_materials_emissive_strength":{"emissiveStrength":2.8}}
    if "KHR_materials_emissive_strength" not in scene.doc.setdefault("extensionsUsed",[]):
        scene.doc["extensionsUsed"].append("KHR_materials_emissive_strength")


def basketball(s,w,d,y,inside=False):
    """Dimensions are half spans; all court paint shares one triangulated surface."""
    lines=[rect(w,d),mark([(-w,0),(w,0)]),mark(arc(0,0,1.8,0,math.tau))]
    for sign in (-1,1):
        end=sign*d
        hoop=end-sign*1.575
        free=end-sign*5.8
        lines.append(mark([(-2.45,end),(-2.45,free),(2.45,free),(2.45,end)]))
        lines.append(mark([(x,free-sign*z) for x,z in arc(0,0,1.8,0,math.pi)]))
        corner=min(w-.87,6.59)
        r=6.75
        a=math.acos(corner/r)
        pts=[(-corner,end)]+[(x,hoop-sign*z) for x,z in arc(0,0,r,math.pi-a,a)]+[(corner,end)]
        lines.append(mark(pts))
        lines.append(mark([(x,hoop-sign*z) for x,z in arc(0,0,1.25,0,math.pi)]))
        for lateral in (-1,1):
            for delta in (1.78,2.7,3.7,4.66):
                x=lateral*2.45;z=end-sign*delta
                lines.append(mark([(x,z),(x+lateral*.15,z)],.055))
        # A single steel support carries the board, hoop and braided net.
        post=end+sign*.90;board=end-sign*1.20
        s.box("篮架锚座",0,y+.085,post,.54,.17,.64,"#48635f")
        s.box("篮架立柱",0,y+1.57,post,.16,3.05,.18,"#34746f")
        for x in (-.42,.42):
            beam(s,"篮板悬臂",(0,y+2.45,post),(x,y+3.49,board+sign*.10),.055,"#64837e")
            beam(s,"篮板背架",(0,y+3.08,post),(x,y+3.70,board+sign*.10),.045,"#819a93")
        s.box("浅灰篮板",0,y+3.54,board,1.8,1.05,.065,"#c6d3ce")
        for x in (-.88,.88):
            s.box("篮板侧包边",x,y+3.54,board,.035,1.05,.085,"#596d66")
        front=board-sign*.041
        for zheight in (3.03,3.48):
            s.box("篮板目标框",0,y+zheight,front,.61,.035,.012,"#e4ece3")
        for x in (-.288,.288):
            s.box("篮板目标框",x,y+3.25,front,.035,.46,.012,"#e4ece3")
        s.box("篮圈固定片",0,y+3.05,(board+hoop+sign*.225)/2,.18,.055,.19,"#b86136")
        top=[]
        for k in range(25):
            a=math.tau*k/24
            top.append((.226*math.cos(a),y+3.05,hoop+.226*math.sin(a)))
        for a,b in zip(top,top[1:]):
            beam(s,"橙色篮圈",a,b,.022,"#ce6337",6)
        for k in range(10):
            a=math.tau*k/10
            p=(.22*math.cos(a),y+3.034,hoop+.22*math.sin(a))
            for hand in (-1,1):
                b=a+hand*math.pi/10
                v=(.147*math.cos(b),y+2.83,hoop+.147*math.sin(b))
                endp=(.13*math.cos(a+hand*math.tau/10),y+2.65,hoop+.13*math.sin(a+hand*math.tau/10))
                beam(s,"篮网绳",p,v,.009,"#dadbc9",4)
                beam(s,"篮网绳",v,endp,.009,"#dadbc9",4)
        if inside:
            surface(s,"红色限制区",box(-2.45,min(free,end),2.45,max(free,end)),y+.006,"#aa625f")
    if inside:
        surface(s,"红色中圈",Point(0,0).buffer(1.8,quad_segs=32),y+.006,"#aa625f")
    surface(s,"篮球边线、三分、罚球线与无撞人区",unary_union(lines),y+.024,WHITE)


def sport_net(s,kind,w,d,y):
    sizes={"tennis":(5.485,11.885,1.07,.914,.05,.047),
           "volleyball":(4.5,9,2.43,2.43,1.43,.100),
           "badminton":(3.05,6.70,1.55,1.524,.79,.028)}
    target_w,target_d,top,mid,bottom,cell=sizes[kind]
    w=min(w,target_w);d=min(d,target_d)
    lines=[rect(w,d,.061)]
    if kind=="tennis":
        for hand in (-1,1):
            lines.append(mark([(hand*4.115,-d),(hand*4.115,d)],.059))
            lines.append(mark([(-4.115,hand*6.4),(4.115,hand*6.4)],.059))
            lines.append(mark([(0,hand*(d-.12)),(0,hand*d)],.06))
        lines.append(mark([(0,-6.4),(0,6.4)],.059))
    elif kind=="volleyball":
        for z in (-3,0,3):
            lines.append(mark([(-w,z),(w,z)],.061))
    else:
        for x in (-2.59,2.59):
            lines.append(mark([(x,-d),(x,d)],.051))
        for hand in (-1,1):
            for z in (1.98,d-.76):
                lines.append(mark([(-w,hand*z),(w,hand*z)],.051))
            lines.append(mark([(0,hand*1.98),(0,hand*d)],.051))
    surface(s,"比赛场地划线",unary_union(lines),y+.025,WHITE)
    span=w+(.66 if kind=="tennis" else .42 if kind=="volleyball" else 0)
    for x in (-span,span):
        s.cyl("有底座的网柱",x,y+top/2,0,.057,top,"#436a63",10)
        s.cyl("网柱帽",x,y+top+.018,0,.065,.045,"#e1e2d5",10)
        s.box("场网拉紧器",x,y+top-.23,-.07,.14,.15,.10,"#9da99e")
    for i in range(12):
        x1,x2=span*(-1+2*i/12),span*(-1+2*(i+1)/12)
        h1=mid+(top-mid)*(x1/span)**2;h2=mid+(top-mid)*(x2/span)**2
        b1,b2=bottom,bottom
        if kind=="badminton":
            b1+=h1-mid;b2+=h2-mid
        net_panel(s,"比赛网面",[(x1,y+b1,0),(x2,y+b2,0),(x2,y+h2,0),(x1,y+h1,0)],
                  [(x1,b1),(x2,b2),(x2,h2),(x1,h1)],NET_DARK,cell)
        s.mesh("网顶白带",[(x1,y+h1-.038,-.011),(x2,y+h2-.038,-.011),(x2,y+h2+.018,-.011),(x1,y+h1+.018,-.011)],[(0,1,2,3)],WHITE)
    if kind=="tennis":
        s.box("网中央压带",0,y+mid/2,.013,.045,mid,.027,WHITE)
    if kind=="volleyball":
        for x in (-w,w):
            for j in range(8):
                s.cyl("标志杆",x,y+top+(j+.5)*.10,0,.017,.10,("#bd6655",WHITE)[j%2],6)


def goal(s,d,y,existing_frame=False):
    for side in (-1,1):
        front=d*side;back=(d+1.85)*side;h=2.44;r=3.66
        if not existing_frame:
            for x in (-r,r):
                beam(s,"球门立柱",(x,y,front),(x,y+h,front),.064,WHITE,8)
                beam(s,"后斜撑",(x,y+h,front),(x,y+.035,back),.044,WHITE)
            beam(s,"球门横梁",(-r,y+h,front),(r,y+h,front),.064,WHITE,8)
        beam(s,"地面收网横杆",(-r,y+.032,back),(r,y+.032,back),.033,"#a8b3a7",6)
        for x in (-r,r):
            net_panel(s,"门侧网",[(x,y,front),(x,y+.035,back),(x,y+h,front)],
                      [(0,0),(1.85,0),(0,h)],NET_LIGHT,.118)
        net_panel(s,"后侧斜网",[(-r,y+h,front),(r,y+h,front),(r,y+.035,back),(-r,y+.035,back)],
                  [(0,0),(2*r,0),(2*r,math.hypot(h,1.85)),(0,math.hypot(h,1.85))],NET_LIGHT,.118)


def soccer(s,w,d,y):
    pen=min(16.5,d*.38)
    lines=[rect(w,d,.11),mark([(-w,0),(w,0)],.11),mark(arc(0,0,9.15,0,math.tau),.11)]
    for sign in (-1,1):
        for width,step in ((20.16,pen),(9.16,5.5)):
            lines.append(mark([(-width,sign*d),(-width,sign*(d-step)),(width,sign*(d-step)),(width,sign*d)],.11))
        a=math.asin((pen-11)/9.15)
        lines.append(mark([(x,sign*(d-11-z)) for x,z in arc(0,0,9.15,a,math.pi-a)],.11))
        lines.append(Point(0,sign*(d-11)).buffer(.145))
        for t in (-1,1):
            lines.append(mark([(t*(w-x),sign*(d-z)) for x,z in arc(0,0,1,0,math.pi/2)],.11))
    lines.append(Point(0,0).buffer(.145))
    surface(s,"足球训练场标线",unary_union(lines),y+.025,WHITE)
    goal(s,d,y)


def primitive_list(scene,shape):
    idx=scene.shape(shape)
    assert idx==len(scene.doc["meshes"])-1
    return scene.doc["meshes"].pop()["primitives"]


def substrate_triangles(scene):
    """Read the existing terrain and sloped apron triangles under the outdoor courts."""
    groups=[]
    doc=scene.doc
    def array(i):
        a=doc["accessors"][i];v=doc["bufferViews"][a["bufferView"]]
        size={"VEC3":3,"SCALAR":1}[a["type"]]
        dtype={5123:"<u2",5125:"<u4",5126:"<f4"}[a["componentType"]]
        return np.frombuffer(scene.raw,dtype,count=a["count"]*size,offset=v.get("byteOffset",0)+a.get("byteOffset",0)).reshape(-1,size)
    for n in doc["nodes"]:
        if n.get("name") not in ("校园及滨海地形","球场组团铺面"):continue
        for p in doc["meshes"][n["mesh"]]["primitives"]:
            vertices=array(p["attributes"]["POSITION"])
            faces=array(p["indices"]).reshape(-1,3)
            tri=vertices[faces]+np.asarray(n.get("translation",[0,0,0]))
            interval=(tri[:,:,0].max(1)>-28)&(tri[:,:,0].min(1)<479)&(tri[:,:,2].max(1)>410)&(tri[:,:,2].min(1)<870)
            groups.append(tri[interval])
    return np.concatenate(groups)


def ground_court(shape,node,w,d,ground):
    """Bench the flat playing slab above its entire sloping base, close all exposed ends."""
    cx,cy,cz=node["translation"]
    q=node.get("rotation",[0,0,0,1]);angle=2*math.atan2(q[1],q[3]);c,s=math.cos(angle),math.sin(angle)
    w,d=w/2,d/2
    rim=[]
    corners=[(-w,-d),(w,-d),(w,d),(-w,d)]
    for a,b in zip(corners,corners[1:]+corners[:1]):
        count=max(1,math.ceil(math.dist(a,b)/1.4))
        rim.extend(np.linspace(a,b,count,endpoint=False))
    rim=np.asarray(rim)
    # For planar terrain, the greatest height over a convex court occurs on its
    # boundary or at an existing terrain vertex contained within the court.
    pts=np.column_stack((cx+c*rim[:,0]+s*rim[:,1],cz-s*rim[:,0]+c*rim[:,1]))
    bounds=pts.min(0)-.002,pts.max(0)+.002
    all_xz=ground[:,:,[0,2]]
    take=np.all((all_xz.max(1)>=bounds[0]) & (all_xz.min(1)<=bounds[1]),axis=1)
    tri=ground[take]
    if not len(tri):raise ValueError(("No supporting sport apron",node["name"]))
    g=tri[:,:,[0,2]]
    A,B,C=g[:,0],g[:,1],g[:,2];u=B-A;v=C-A
    den=u[:,0]*v[:,1]-u[:,1]*v[:,0]
    ok=np.abs(den)>.00001
    g=g[ok];tri=tri[ok];A=A[ok];u=u[ok];v=v[ok];den=den[ok]
    p=pts[:,None,:]-A[None,:,:]
    wa=(p[:,:,0]*v[:,1]-p[:,:,1]*v[:,0])/den
    wb=(u[:,0]*p[:,:,1]-u[:,1]*p[:,:,0])/den
    inside=(wa>=-.00001)&(wb>=-.00001)&(wa+wb<=1.00001)
    height=tri[:,0,1]+wa*(tri[:,1,1]-tri[:,0,1])+wb*(tri[:,2,1]-tri[:,0,1])
    sampled=np.max(np.where(inside,height,-np.inf),axis=1)
    if not np.all(np.isfinite(sampled)):raise ValueError(("Open terrain under sports apron",node["name"]))
    verts=tri.reshape(-1,3)
    vx,vz=verts[:,0]-cx,verts[:,2]-cz
    within=(abs(c*vx-s*vz)<=w+.001)&(abs(s*vx+c*vz)<=d+.001)
    high=max(np.max(sampled),np.max(verts[within,1],initial=-np.inf))
    top=max(cy,float(high)+.035)
    node["translation"][1]=top
    for i,(x,z) in enumerate(rim):
        j=(i+1)%len(rim);xn,zn=rim[j]
        low0=min(-.026,sampled[i]-top-.026);low1=min(-.026,sampled[j]-top-.026)
        shape.mesh("球场挡边与地面相接",[(x,-.02,z),(xn,-.02,zn),(xn,low1,zn),(x,low0,z)],[(0,1,2,3)],"#a6aaa2")
    return round(top-cy,3)

def outdoor(scene,data):
    pitches=[r for r in data["pitches"] if r["kind"] in COURT_KINDS]
    nodes={(round(n["translation"][0],2),round(n["translation"][2],2)):n
           for n in scene.doc["nodes"] if n.get("extras",{}).get("kind")=="sport" and n.get("translation")}
    counts={kind:0 for kind in sorted(COURT_KINDS)}
    ground=substrate_triangles(scene)
    for row in pitches:
        key=tuple(row["center"]);node=nodes.get(key)
        # Main stadium's mapped grass is already incorporated in its landmark.
        if node is None:
            if row["id"]!="way/970257649":
                raise ValueError(("Court mesh absent",row["id"]))
            continue
        mesh=scene.doc["meshes"][node["mesh"]];old=mesh["primitives"]
        kept=[pr for pr in old if scene.doc["materials"][pr["material"]]["name"] not in LEGACY_KIT]
        if len(kept)==len(old):
            raise ValueError(("Unknown legacy sports equipment",row["id"]))
        ring=np.array(Polygon(row["poly"]).minimum_rotated_rectangle.exterior.coords[:4])
        w,d=sorted([np.linalg.norm(ring[0]-ring[1]),np.linalg.norm(ring[1]-ring[2])])
        s=Shape(row["kind"])
        kind=row["kind"]
        if kind=="basketball":
            basketball(s,min(7.5,w*.46),min(14,d*.465),.058)
        elif kind=="soccer":
            soccer(s,min(34,w*.46),min(52.5,d*.465),.058)
        else:
            sport_net(s,kind,w/2-.08,d/2-.08,.058)
        slab_rise=ground_court(s,node,w,d,ground)
        mesh["primitives"]=kept+primitive_list(scene,s)
        node["extras"].update(sportDiscipline=kind,sportMapId=row["id"],slabRiseM=slab_rise)
        counts[kind]+=1
    return counts


def add_at(scene,shape,owner,extra):
    at=owner["translation"]
    scene.node(shape.name,shape=shape,at=at,kind="sport",**extra)
    scene.doc["nodes"][-1]["rotation"]=owner.get("rotation",[0,0,0,1])


def indoor(scene,hall):
    # Four cross-hall courts fit inside the published 3600 square metre building.
    floor=Shape("风雨操场 · 硅PU地坪与内侧钢桁架")
    floor.box("红色馆地",0,.24,0,85.7,.10,43.6,"#9c5b59")
    # The official completion photos show white arched trusses, red court
    # perimeters, dark green playing fields and a red centre circle on each.
    def crown(z):
        return 5.96+8.02*math.sqrt(max(0,1-(z/22.9)**2))
    spans=np.linspace(-22.5,22.5,17)
    for i,x in enumerate((-40,-30,-20,-10,0,10,20,30,40)):
        for j,(z0,z1) in enumerate(zip(spans,spans[1:])):
            hi0,hi1=crown(z0),crown(z1)
            for dh in (.14,.78):
                beam(floor,"白色承重拱弦",(x,hi0-dh,z0),(x,hi1-dh,z1),.067,"#c0c7be",8)
            beam(floor,"桁架腹杆",(x,hi0-(.14 if j%2==0 else .78),z0),(x,hi1-(.78 if j%2==0 else .14),z1),.038,"#b3c0b6",6)
            if i < 8 and 1<=j<=14:
                # Located under the closed original roof. Diffuse panels provide
                # local indoor light in Cycles without changing the campus rig.
                floor.mesh("拱顶内侧漫射带",[(x+.31,hi0-.06,z0),(x+2.05,hi0-.06,z0),(x+2.05,hi1-.06,z1),(x+.31,hi1-.06,z1)],[(0,1,2,3)],INDOOR_LIGHT)
        for z in (-10,10):
            ht=crown(z)-.78
            beam(floor,"灯具吊杆",(x,ht,z),(x,ht-.56,z),.029,"#747f78",6)
            floor.cyl("悬吊灯罩",x,ht-.64,z,.28,.18,"#7d8982",12)
            floor.cyl("投光面",x,ht-.735,z,.255,.013,INDOOR_LIGHT,12)
    add_at(scene,floor,hall,dict(sportHall="floor"))
    base=Shape("风雨操场 · 一个标准篮球场及两副篮架")
    surface(base,"绿色比赛场",box(-7.52,-14.02,7.52,14.02),.295,"#4d7465")
    basketball(base,7.5,14,.295,True)
    mi=scene.shape(base)
    x,y,z=hall["translation"]
    for i,off in enumerate((-30,-10,10,30),1):
        scene.node(f"风雨操场 · 第{i}片篮球场",mesh=mi,at=(x+off,y,z),kind="sport",sportHall="coveredCourt",courtNumber=i)


def track(scene,node,is_east):
    s=Shape(("东田径场" if is_east else "蓝色田径场")+" · 足球门网与场地细节")
    goal(s,52.5,.28,existing_frame=True)
    if is_east:
        # Perspective registration on the four football corners in V3 98.50:
        # landing mat centre about (-1,58) and sand pit about (+53,-27).
        s.box("落地区防滑承台",-1,.365,58.5,6.3,.31,4.12,"#626f73")
        for i in (-1,0,1):
            s.box("分块软垫",-1+i*2.04,.785,58.5,2.02,.58,3.96,"#48a8b4")
        s.box("蓝色防护罩",-1,1.10,58.5,6.20,.085,4.06,"#559eb9")
        for x in (-3.04,1.04):
            s.box("跳高架底脚",x,.28,56.13,.63,.14,.62,"#8e948e")
            s.cyl("跳高标尺",x,1.47,56.13,.042,2.41,"#c4cbd0",8)
        beam(s,"横杆",(-3.02,1.78,56.13),(1.02,1.78,56.13),.021,"#bbb967",8)
        # The actual sand bed is outside the eastern straight and clear of
        # Gewu Road. The buffer and sand share the same raised edging.
        s.box("沙坑低座",52.8,.165,-27,3.45,.15,8.8,"#a69276")
        s.box("跳远浅砂",52.8,.248,-27,3.12,.016,8.45,"#d4bc91")
        s.box("助跑道",52.8,.174,-2.7,1.32,.14,39.1,"#9f5757")
        for x in (52.19,53.41):s.box("助跑道边线",x,.258,-2.7,.045,.012,39.1,WHITE)
        s.box("起跳板",52.8,.258,-20.6,1.22,.024,.20,WHITE)
    add_at(scene,s,node,dict(sportTrackDetail="east" if is_east else "blue"))


def views(catalog,lookup):
    keys={p["key"] for p in catalog}
    hx,hy,hz=lookup["way-982199336"]["translation"]
    ex,ey,ez=lookup["east_track"]["translation"]
    items=[
        ("sport-covered-hall","风雨操场 · 馆内四片篮球场",[hx+39,hy+4.9,hz-13],[hx-15,hy+2.2,hz+1],61,"校方竣工图确认硅PU场地与四片标准篮球场。红绿场面和白色钢桁架据校方照片，场间距、灯位与器材细节按比例概化。"),
        ("sport-east-courts","东侧运动区 · 篮排网羽球场",[284,92,714],[412,7,545],49,"东侧室外球场组团按开放地图逐场定位，比赛线、篮架与球网按各球类的常用尺寸表达。"),
        ("sport-basketball-close","东侧篮球场 · 篮架与三分线",[354,12.6,595],[374.1,7.8,581],49,"近看双臂篮架、篮圈绳网、三分弧和罚球区。"),
        ("sport-tennis-volleys","东侧排球与网球场 · 球网",[322,13.5,433],[351,5.0,453],50,"从西北向东南看排球场、天线杆及其东侧的网球区。"),
        ("sport-east-athletics","东田径场 · 跳高落地区",[ex+23,ey+12.5,ez+88],[ex,ey+1.2,ez+56],47,"东田径场南端蓝色落地区据航片定位，东直道外侧补浅沙坑及助跑道。设备外形和尺寸为概化值。"),
    ]
    for key,title,eye,target,fov,note in items:
        if key in keys:continue
        catalog.append(dict(key=key,name=title,group="校园场地",x=target[0],y=target[1],z=target[2],
                            h=3,r=40,note=note,viewpoint=dict(eye=eye,target=target,fov=fov)))


def build(scene,data,catalog):
    lookup={n.get("extras",{}).get("key"):n for n in scene.doc["nodes"]}
    if scene.doc["asset"].get("extras",{}).get("sportFacilities")==VERSION:
        views(catalog,lookup)
        return
    scene.colors.update({m["name"]:i for i,m in enumerate(scene.doc["materials"]) if "name" in m})
    install_materials(scene)
    counts=outdoor(scene,data)
    expected={"soccer":2,"basketball":16,"tennis":12,"volleyball":2,"badminton":2}
    if counts!=expected:raise ValueError(("Mapped playing areas",counts))
    indoor(scene,lookup["way-982199336"])
    track(scene,lookup["east_track"],True)
    track(scene,lookup["blue_track"],False)
    scene.doc["asset"].setdefault("extras",{})["sportFacilities"]=VERSION
    views(catalog,lookup)
    return {"outdoor":counts,"coveredBasketballCourts":4,"basketballHoops":40,"tennisNets":12,
            "volleyballNets":2,"badmintonNets":2,"footballGoalNets":8,
            "eastHighJumpPads":1,"eastLongJumpPits":1,"viewpoints":[p["key"] for p in catalog if p["key"].startswith("sport-")],
            "sources":SOURCES,"interpretation":"场地位置取自校方说明及既有底图；四个室内场地的布局、运动器材型号与尺寸和东田径场助跑道长度是依据相片与规则尺度的概化。"}
