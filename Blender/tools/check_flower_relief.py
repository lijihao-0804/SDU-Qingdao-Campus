"""Check physical plants in the delivered GLB, including shared mesh transforms."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely import contains_xy, prepare
from shapely.geometry import LineString
from shapely.ops import unary_union

from qd_arena_groundflowers import BED, EYES, GRASS, LEAVES, PETALS, SOIL, STEMS
from qd_grass_relief import MATERIAL as GRASS_MATERIAL
from qd_petal_sprays import PETAL_MATERIAL
from qd_terrain import sourcepolygon
from v2_entrance_audit import Scene

ROOT = Path(__file__).resolve().parents[1]
TREE_SITES = ("ganchang-cherry-walk", "ganchang-cherry-south", "ganchang-ce-cherries", "library-flower-court")
PHOENIX = "spring_phoenix_garden"


def audit(path):
    scene = Scene(path)
    def material_name(prim):
        return scene.g["materials"][prim["material"]]["name"]

    def physical(prim):
        attrib = prim["attributes"]
        mat = scene.g["materials"][prim["material"]]
        assert mat.get("alphaMode", "OPAQUE")=="OPAQUE" and "COLOR_0" in attrib, mat["name"]
        vertices = scene.accessor(attrib["POSITION"])
        ids = scene.accessor(prim["indices"]).reshape(-1,3)
        assert len(ids)>0 and ids.max()<len(vertices) and np.isfinite(vertices).all()
        return vertices,ids

    def first_component_depth(vertices, ids):
        # A single connected petal cup must have thickness around its own
        # best-fit plane. Testing the spread of an entire crown would also
        # accept a set of flat flower cards oriented in different directions.
        first = ids.ravel()
        second = np.roll(ids,-1,axis=1).ravel()
        graph = coo_matrix((np.ones(len(first), dtype=bool), (first,second)),
                           shape=(len(vertices),len(vertices))).tocsr()
        _, labels = connected_components(graph, directed=False)
        xyz = vertices[labels==labels[first[0]]]
        assert len(xyz)>=5
        axes = np.linalg.svd(xyz-xyz.mean(axis=0),compute_uv=False)
        return float(axes[-1]/axes[0])

    site_meshes = defaultdict(Counter)
    grass = []
    slope_parts = defaultdict(set)
    for i,n in enumerate(scene.nodes):
        e = n.get("extras",{})
        is_phoenix_bloom = e.get("site")==PHOENIX and not e.get("species","").startswith("常绿")
        if e.get("kind")=="flora" and (e.get("site") in TREE_SITES or is_phoenix_bloom):
            site_meshes[e["site"]][n["mesh"]] += 1
        if e.get("grassRelief"):
            assert e["kind"]=="groundcover"
            grass.append((i,n))
        if e.get("arenaPlantPart"):
            slope_parts[e["arenaPlantPart"]].add(n["mesh"])
    assert set((*TREE_SITES,PHOENIX))==set(site_meshes), list(site_meshes)
    petal_geometry = {}
    for counts in site_meshes.values():
        for m in counts:
            if m in petal_geometry:
                continue
            prim, = [p for p in scene.g["meshes"][m]["primitives"] if material_name(p)==PETAL_MATERIAL]
            v,f = physical(prim)
            depth = first_component_depth(v,f)
            assert depth>.02,(m,"flat crown flower",depth)
            petal_geometry[m] = {"cupDepthRatio": round(depth,4), "opaquePetalTriangles":len(f)}
    trees = {site:{"trees":sum(counts.values()), "sharedMeshIDs":sorted(counts),
                   "opaquePetalTriangles":sum(petal_geometry[m]["opaquePetalTriangles"]*c for m,c in counts.items())}
             for site, counts in site_meshes.items()}
    tips = {p:[] for p in ("cushions","exposedSoil","shoots","grasses")}
    for part in tips:
        exported = [prim for mesh in sorted(slope_parts[part]) for prim in scene.g["meshes"][mesh]["primitives"]]
        for prim in exported:
            v,f = physical(prim)
            name = material_name(prim)
            row = {"material":name,"vertices":len(v),"triangles":len(f)}
            if name==PETALS:
                row["lobeDepthRatio"] = round(first_component_depth(v,f),4)
                assert row["lobeDepthRatio"]>.002, row
            tips[part].append(row)
    assert {p["material"] for p in tips["shoots"]}=={PETALS,EYES,LEAVES,STEMS}
    assert {p["material"] for g in ("grasses","cushions","exposedSoil") for p in tips[g]}=={BED,GRASS,SOIL}
    raw = json.loads((ROOT/"data/map/campus.json").read_text("utf-8-sig"))
    blocked = unary_union([sourcepolygon(row) for tag in ("water","buildings","pitches","parking") for row in raw[tag]]+
                          [LineString(r["line"]).buffer(r["width"]/2,quad_segs=4) for r in raw["roads"]
                           if len(r["line"])>1 and not r.get("tunnel")])
    prepare(blocked)
    proto, tiers, districts = {}, Counter(), Counter()
    bad, triangles = [], 0
    for i,n in grass:
        m=n["mesh"]
        if m not in proto:
            prim, = scene.g["meshes"][m]["primitives"]
            assert material_name(prim)==GRASS_MATERIAL
            v,ids = physical(prim)
            # Every blade has a root pair, a narrower bent strip and a tip.
            assert len(v)%5==0 and len(ids)==3*(len(v)//5)
            p=v.reshape(-1,5,3);roots=p[:,:2].mean(1);knees=p[:,2:4].mean(1);end=p[:,4]
            bent=np.linalg.norm(np.cross(knees-roots,end-roots),axis=1)
            assert np.quantile(bent,.1)>1e-5
            proto[m]=(v,len(ids))
        v,n_tris=proto[m]
        # Check every real vertex after its exported quaternion, height and scale.
        xyz=scene.transform(i,v)
        if contains_xy(blocked,xyz[:,0],xyz[:,2]).any():
            bad.append(n["name"])
        triangles+=n_tris
        tiers[n["extras"]["tier"]]+=1
        districts[("北区","科研及生态区","图书馆与学院区","运动与生活区")[sum(n["translation"][2]>=z for z in (-540,-165,410))]]+=1
    assert not bad,("grass on mapped hard ground",bad[:15],len(bad))
    assert set(tiers)=={"field","verge","detail"} and len(districts)==4 and len(grass)>len(proto)
    stats=json.loads((ROOT/"data/立体草坪.json").read_text("utf-8-sig"))
    assert stats["patchesByType"]==tiers and stats["patchesByDistrict"]==districts and stats["triangles"]==triangles
    return {"passed":True,"glbSHA256":scene.digest,"treeSites":trees,"treeMeshMeasurements":petal_geometry,
            "arena":tips,"grass":{"patches":len(grass),"sharedMeshes":len(proto),"triangles":triangles,
            "blades":triangles//3,"patchesByTier":dict(tiers),"patchesByDistrict":dict(districts),
            "instancesWithLeafVerticesOnMappedHardGroundOrWater":len(bad)}}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,default=ROOT/"山东大学青岛校区.glb")
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    result=audit(args.model)
    if args.report:
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),"utf8")
    print(json.dumps(result,ensure_ascii=False),flush=True)
