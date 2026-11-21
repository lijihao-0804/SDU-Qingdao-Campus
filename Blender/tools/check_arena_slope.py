"""Check the actual graded terrain, upper path, lower lane and planting in the final GLB."""
import argparse
import json
from pathlib import Path
import numpy as np
import shapely

from qd_arena_slope import ArenaSlope
from qd_arena_groundflowers import BED, PETALS, EYES, STEMS, LEAVES, GRASS, SOIL
from v2_entrance_audit import Scene,Ground


def measure_planting(scene, site, ground):
    from collections import Counter
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    totals=Counter(); elements=Counter(); cache={}
    roles=Counter(); sample_height=[]; colour_span=[]; foliage_extent=[]
    access=site.drive.union(site.lower_walk).union(site.upper_path)
    shapely.prepare(access)
    for i,node in enumerate(scene.nodes):
        role=node.get("extras",{}).get("arenaPlantPart")
        if not role:continue
        roles[role]+=1
        mesh=node["mesh"]
        if mesh not in cache:
            parts=[]
            for primitive in scene.g["meshes"][mesh]["primitives"]:
                attrs=primitive["attributes"]
                name=scene.g["materials"][primitive["material"]]["name"]
                v=scene.accessor(attrs["POSITION"])
                ids=scene.accessor(primitive["indices"]).ravel().reshape(-1,3)
                colours=scene.accessor(attrs["COLOR_0"])
                assert np.all(np.isfinite(v)) and np.all(np.isfinite(colours))
                count=0
                if name in (PETALS,EYES,LEAVES,GRASS,STEMS):
                    edge=ids[:,[1,2,0]]
                    adj=coo_matrix((np.ones(ids.size),(ids.ravel(),edge.ravel())),shape=(len(v),len(v)))
                    count,labels=connected_components(adj,directed=False)
                    if name==PETALS:
                        # Measure cupping from the actual vertices of each connected lobe.
                        depths=[]
                        for c in range(count):
                            pts=v[labels==c]
                            _,_,axes=np.linalg.svd(pts-pts.mean(0),full_matrices=False)
                            depths.append(float(np.ptp((pts-pts.mean(0))@axes[-1])))
                        assert np.median(depths)>.0004,depths
                        colour_span.append(np.ptp(colours,axis=0).max())
                parts.append((name,v,len(ids),count))
            cache[mesh]=parts
        for name,v,n,count in cache[mesh]:
            totals[name]+=n;elements[name]+=count
            world=scene.transform(i,v)
            # Includes the outermost petal/grass tips and the underlying bed itself.
            assert not shapely.intersects_xy(access,world[:,0],world[:,2]).any(),(node["name"],name)
            if name==BED:
                for x,y,z in world[::max(1,len(world)//360)]:
                    hit=ground.hit(x,z)
                    if "校园及滨海地形" in hit:
                        sample_height.append(y-hit["校园及滨海地形"])
            if name==EYES:
                foliage_extent.append(world[:,[0,2]].mean(0))
    assert set(roles)=={"shoots","grasses","exposedSoil","cushions"},roles
    assert set(totals)=={BED,SOIL,PETALS,EYES,STEMS,LEAVES,GRASS},totals
    assert min(colour_span)>.1 and elements[PETALS]==5*elements[EYES],elements
    assert elements[EYES]>5000 and elements[GRASS]>1000 and elements[LEAVES]>elements[EYES]
    assert len(sample_height)>200
    low,med,high=np.percentile(sample_height,[5,50,95])
    assert .01<low<med<high<.31 and high-low>.07,(low,med,high)
    assert np.min(np.ptp(np.asarray(foliage_extent),axis=0))>55
    return dict(floweringCushionInstances=roles["shoots"],grassTuftInstances=roles["grasses"],
                meshPrototypes=len(cache),fiveLobedFlowers=elements[EYES],petalLobes=elements[PETALS],
                needleLeaves=elements[LEAVES],grassBlades=elements[GRASS],stemSegments=elements[STEMS],
                storedTriangles=sum(n for parts in cache.values() for _,_,n,_ in parts),
                instancedTriangles=sum(totals.values()),cushionReliefP05P50P95Metres=[round(t,3) for t in (low,med,high)],
                reliefSamples=len(sample_height),plantVerticesOnAccessRoutes=0)


def audit(path):
    scene=Scene(path)
    owner,=[n for n in scene.nodes if n.get("extras",{}).get("key")=="song_arena"]
    x,y,z=owner["translation"]
    site=ArenaSlope(x,z,y-.005)
    lo,hi=np.asarray(site.region.bounds).reshape(2,2)
    ground=Ground(scene,np.array([lo-2,hi+2]))
    profile=[]
    for st in (41,59,77,93,109):
        up=site.xy(st,19.8);down=site.xy(st,0);flower=site.xy(st,10.8)
        upper,lower,bed=(ground.hit(*p) for p in (up,down,flower))
        soil="校园及滨海地形";road="连续沥青路面";walk="步行道"
        assert soil in upper and soil in lower and road in lower and walk in upper,(st,upper,lower)
        # Use the actual walk and road, not camera heights or station settings.
        dz=upper[walk]-lower[road]
        assert 3.6<dz<4.7,(st,dz)
        assert road not in upper and walk not in lower,(st,upper,lower)
        for off in (-2.65,2.65):
            strip=ground.hit(*site.xy(st,off));assert road in strip,(st,off,strip)
        assert any(n.endswith("随坡玫红花海") for n in bed),(st,bed)
        profile.append(dict(station=st,upperPathM=round(upper[walk],3),lowerRoadM=round(lower[road],3),
                            reliefM=round(dz,3)))
    expected={"flowers","walk","retaining","furniture"}
    assert {n.get("extras",{}).get("arenaSouth") for n in scene.nodes if n.get("extras",{}).get("arenaSouth")}==expected
    # The base of the pre-existing arena stays within five millimetres of its grade.
    origin=ground.hit(x,z)
    # Ground's spatial index intentionally covers only the southern bend. The
    # building origin is outside that local index, so query a second small box.
    if "校园及滨海地形" not in origin:
        c=np.array([x,z]);origin=Ground(scene,np.array([c-.5,c+.5])).hit(x,z)
    assert abs(origin["校园及滨海地形"]+.005-y)<.02
    return dict(verified=True,modelSHA256=scene.digest,profiles=profile,clearRoadWidthSampledM=5.3,
                arenaBaseDifferenceM=round(y-origin["校园及滨海地形"],4),
                geometricPlanting=measure_planting(scene,site,ground))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("model",nargs="?",type=Path,default=Path(__file__).resolve().parents[1]/"山东大学青岛校区.glb")
    p.add_argument("--report",type=Path)
    a=p.parse_args();out=audit(a.model)
    if a.report:a.report.write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf8")
    print(json.dumps(out,ensure_ascii=False))
