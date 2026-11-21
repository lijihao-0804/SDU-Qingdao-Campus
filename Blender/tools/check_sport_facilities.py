from pathlib import Path
import math
import argparse
import json
import struct
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from qd_geometry import CampusFile
from qd_sport_facilities import ROOT, NET_DARK, NET_LIGHT, WHITE, build, VERSION


def read_model(path):
    scene=CampusFile()
    with path.open("rb") as f:
        n=struct.unpack("<4sIII4s",f.read(20))[3]
        scene.doc=json.loads(f.read(n))
        n,tag=struct.unpack("<I4s",f.read(8));assert tag==b"BIN\0"
        scene.raw=bytearray(f.read(n))
    return scene


def values(scene,idx):
    acc=scene.doc["accessors"][idx];v=scene.doc["bufferViews"][acc["bufferView"]]
    dtype={5123:"<u2",5125:"<u4",5126:"<f4"}[acc["componentType"]]
    size={"VEC3":3,"VEC2":2,"SCALAR":1}[acc["type"]]
    offset=v.get("byteOffset",0)+acc.get("byteOffset",0)
    return np.frombuffer(scene.raw,dtype,count=acc["count"]*size,offset=offset).reshape(-1,size)


def inspect(scene,path):
    g=scene.doc
    assert g["asset"]["extras"]["sportFacilities"]==VERSION
    mats=g["materials"]
    nodes=g["nodes"]
    def parts(n):return g["meshes"][n["mesh"]]["primitives"]
    def colour(n,c):return [p for p in parts(n) if mats[p["material"]]["name"]==c]
    def positions(p):return values(scene,p["attributes"]["POSITION"])
    def tris(p):return positions(p)[values(scene,p["indices"]).ravel()].reshape(-1,3,3)
    def net_ends(n):
        ps=colour(n,NET_LIGHT)
        assert len(ps)==1 and "TEXCOORD_0" in ps[0]["attributes"]
        a=positions(ps[0]);assert a[:,2].min()<-45 and a[:,2].max()>45
        return sum(np.any(a[:,2]*side>45) for side in (-1,1))
    listed=[n for n in nodes if n.get("extras",{}).get("sportDiscipline")]
    hall=[n for n in nodes if n.get("extras",{}).get("sportHall")=="coveredCourt"]
    tracks=[n for n in nodes if n.get("extras",{}).get("sportTrackDetail")]
    assert len(listed)==34 and len(hall)==4 and len({n["mesh"] for n in hall})==1 and len(tracks)==2
    assert len({n["extras"]["sportMapId"] for n in listed})==len(listed)
    from v2_entrance_audit import Scene,Ground
    terrain=Ground(Scene(path),np.array([[-30,410],[478,868]]))
    balls=0;nets={};goals=0;min_paint=float("inf");min_substrate=float("inf")
    for n in listed+hall:
        k=n.get("extras",{}).get("sportDiscipline","basketball")
        if n in listed:
            floor,=[p for p in parts(n) if mats[p["material"]]["name"] in
                    {"#ac755d","#599cad","#81a868","#296ca5","#84a899","#ba927a"}]
            pos=positions(floor);w,d=np.max(pos[:,[0,2]],axis=0)
            x,y,z=n["translation"];q=n["rotation"];yaw=2*math.atan2(q[1],q[3])
            for sx,sz in ((-1,-1),(1,-1),(-1,1),(1,1),(0,0),(-1,0),(1,0),(0,-1),(0,1)):
                u,v=.985*sx*w,.985*sz*d
                px=x+math.cos(yaw)*u+math.sin(yaw)*v;pz=z-math.sin(yaw)*u+math.cos(yaw)*v
                hits=terrain.hit(px,pz)
                higher=max(h for name,h in hits.items() if name in {"校园及滨海地形","球场组团铺面"})
                min_substrate=min(min_substrate,float(y+pos[:,1].max()-higher))
        if k=="basketball":
            r,=colour(n,"#ce6337");v=positions(r)
            assert len(v)>500 and (v[:,1].max()-v[:,1].min())<.06
            assert sum(np.any(v[:,2]*sgn>11) for sgn in (-1,1))==2
            balls+=2
            # The two white arcs reach into the half-courts over six metres from
            # the ring. The centre paint, keys and perimeter share one height.
            paint,=colour(n,WHITE)
            tri=tris(paint)
            planar=tri[(np.ptp(tri[:,:,1],axis=1)<1e-5)&(tri[:,:,1].max(axis=1)<.36)]
            field=unary_union([Polygon(t[:,[0,2]]) for t in planar if Polygon(t[:,[0,2]]).area>1e-8])
            coords=v[:,2];ringz=np.median(coords[coords>0])
            for sign in (-1,1):
                assert field.distance(Point(0,sign*(ringz-6.75)))<.065
            if n in hall:
                y=.295
            else:
                surface_materials={"#ac755d","#599cad","#6ca49c"}
                y=max(positions(pr)[:,1].max() for pr in parts(n) if mats[pr["material"]]["name"] in surface_materials)
            min_paint=min(min_paint,float(np.median(planar[:,:,1])-y))
        elif k in ("tennis","volleyball","badminton"):
            net,=colour(n,NET_DARK);xyz=positions(net)
            assert "TEXCOORD_0" in net["attributes"] and abs(xyz[:,2]).max()<.001
            assert np.ptp(xyz[:,0])>5.8 and np.ptp(xyz[:,1])>.71 
            if k=="volleyball":
                lines,=colour(n,WHITE);v=tris(lines);v=v[np.ptp(v[:,:,1],axis=1)<1e-5]
                white=unary_union([Polygon(t[:,[0,2]]) for t in v if Polygon(t[:,[0,2]]).area>.000001])
                assert all(white.distance(Point(0,z))<.025 for z in (-3,3))
            nets[k]=nets.get(k,0)+1
        elif k=="soccer":
            goals+=net_ends(n)
    for n in tracks:goals+=net_ends(n)
    east,=[n for n in tracks if n["extras"]["sportTrackDetail"]=="east"]
    pad,=colour(east,"#559eb9");sand,=colour(east,"#d4bc91")
    assert np.allclose(positions(pad)[:,[0,2]].mean(axis=0),[-1,58.5],atol=.01)
    assert np.allclose(positions(sand)[:,[0,2]].mean(axis=0),[52.8,-27],atol=.01)
    assert len([n for n in nodes if n.get("extras",{}).get("key")=="way-982199336"])==1
    assert min_substrate>.035 and min_paint>.014 and balls==40 and goals==8 and nets=={"tennis":12,"badminton":2,"volleyball":2}
    return dict(outdoorMappedCourts=len(listed),indoorBasketballCourts=len(hall),hoops=balls,
                competitionNets=nets,footballGoalNets=int(goals),eastHighJumpPads=1,eastLongJumpPits=1,
                minimumBasketballPaintSeparationMetres=round(min_paint,3),
                minimumSlabClearanceOverTerrainMetres=round(min_substrate,3),terrainSamples=9*len(listed))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Check final glTF geometry, or create an isolated incremental fixture.")
    parser.add_argument("model",type=Path,nargs="?",default=ROOT/"山东大学青岛校区.glb")
    parser.add_argument("--fixture",type=Path,help="Destination folder for an isolated incremental build")
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    model=args.model
    scene=read_model(model)
    if args.fixture:
        data=json.loads((ROOT/"data/map/campus.json").read_text("utf8"));catalog=json.loads((ROOT/"data/locations.json").read_text("utf8"))
        stats=build(scene,data,catalog)
        args.fixture.mkdir(parents=True,exist_ok=True)
        fixture=args.fixture/"山东大学青岛校区.glb";scene.save(fixture)
        (args.fixture/"locations.json").write_text(json.dumps(catalog,ensure_ascii=False),"utf8")
        (args.fixture/"sources.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2),"utf8")
        del scene
        model=fixture;scene=read_model(model)
    report=inspect(scene,model)
    if args.report:args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf8")
    print(json.dumps(report,ensure_ascii=False))
