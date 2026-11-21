"""Read the actual arcade/host triangles, check eight joints and transverse walking clearance."""
import argparse
import json
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

from qd_phoenix_arcades import GROUND, HOSTS, KEY, ROOT, buildings, cover_plan, links
from qd_terrain import sourcepolygon
from v2_entrance_audit import Ground, Scene, SOIL, exact_segment

def groups(model,i):
    result={}
    for tris,ranges in model.triangles(i):
        for name,first,last in ranges:
            result.setdefault(name,[]).append(tris[first:last])
    return {name:np.concatenate(parts) for name,parts in result.items()}

def projected(tris):
    faces=[Polygon(pts[:,[0,2]]) for pts in tris]
    return unary_union([p for p in faces if p.area>1e-7])

def at_height(tris,y):
    # Intersect non-horizontal faces with the plane at the actual slab elevation.
    lines=[]
    for t in tris[(tris[:,:,1].min(1)<y)&(tris[:,:,1].max(1)>y)]:
        xz=[]
        for a,b in zip(t,np.roll(t,-1,axis=0)):
            if (a[1]<y)!=(b[1]<y):
                p=a+(b-a)*((y-a[1])/(b[1]-a[1]))
                xz.append(p[[0,2]])
        if len(xz)==2:lines.append(LineString(xz))
    return unary_union(lines)

def check(model,before=None):
    rows=buildings()
    keys={key:key.replace('/','-') for core,hosts in HOSTS.items() for key in (core,*hosts)}
    by_key={n.get('extras',{}).get('key'):i for i,n in enumerate(model.nodes)}
    old_by_key={} if before is None else {n.get('extras',{}).get('key'):i for i,n in enumerate(before.nodes)}
    parts={k:groups(model,by_key[v]) for k,v in keys.items()}
    tri={k:np.concatenate([t for t,_ in model.triangles(by_key[v])]) for k,v in keys.items()}
    ground=Ground(model,(np.array([255,734]),np.array([365,920])))
    data=json.loads((ROOT/'data/map/campus.json').read_text('utf-8-sig'))
    from qd_phoenix_garden import reserve
    beds=reserve(data)
    paths=unary_union([LineString(r['line']).buffer(r['width']/2)
                       for r in data['roads'] if len(r['line'])>1 and not r.get('tunnel')])
    report=[]
    for key,hosts in HOSTS.items():
        core=sourcepolygon(rows[key])
        original=core
        if before:
            g=groups(before,old_by_key[keys[key]])
            original=MultiPoint(g['砌体外墙开洞'][:,:,[0,2]].reshape(-1,2)).convex_hull
            assert original.hausdorff_distance(core)<.01,key
        new_roof=projected(parts[key]['接翼连廊 · 廊顶内底'])
        low_roofs=[t for t in parts[key]['接翼连廊 · 廊顶内底']]
        level=float(np.mean(np.asarray(low_roofs)[:,:,1]))+.04
        p=cover_plan(key)
        paving=p.buffer(.20,join_style='mitre')
        assert paving.disjoint(beds) and paving.disjoint(paths),key
        for i in model.near([p.bounds[0],-200,p.bounds[1]],[p.bounds[2],200,p.bounds[3]]):
            n=model.nodes[i]
            if n.get('extras',{}).get('kind') in ('flora','groundcover'):
                loc=model.transform(i,np.zeros((1,3)))[0]
                assert not p.contains(Point(loc[[0,2]])),(key,n['name'],'植物落点在通廊内')
        adjacent=np.concatenate([tri[key],*(tri[h] for h in hosts)])
        rays=0
        def traverse(a,b,c,d,count):
            nonlocal rays
            for j in range(count):
                for offset in (-.12,0,.12):
                    frac=(j+.5+offset)/count
                    left=a+(c-a)*frac
                    right=b+(d-b)*frac
                    across=(right-left)/np.linalg.norm(right-left)
                    left-=.40*across
                    right+=.40*across
                    hits=ground.hit(*((left+right)/2))
                    assert GROUND in hits and hits[GROUND]>=max(hits.values())-.01,(key,hits)
                    # Sample the local ground slope at both sides, including
                    # ankle height: a clear eye-level ray alone misses a sill.
                    base_left=ground.hit(*left)[SOIL]+.135
                    base_right=ground.hit(*right)[SOIL]+.135
                    for height in (.08,.35,1.2,1.75,2.10):
                        start=np.array([left[0],base_left+height,left[1]])
                        end=np.array([right[0],base_right+height,right[1]])
                        assert exact_segment(start,end,adjacent) is None,(key,j,frac,height,start,end)
                        rays+=1
        ends=[]
        corners=sorted(core.exterior.coords[:-1],key=lambda xy:xy[1])
        a,b=sorted(corners[:2]);c,d=sorted(corners[2:])
        traverse(*np.array([a,b,c,d]),max(2,round(np.linalg.norm(np.subtract(c,a))/5.3)))
        for host,land,_ in links(key):
            a,b,d,c=np.array(land.exterior.coords[:4])
            count=max(1,round(np.linalg.norm(c-a)/5.4))
            traverse(a,b,c,d,count)
            wall=parts[host]['砌体外墙开洞']
            wall_line=at_height(wall,level)
            contact=wall_line.intersection(land).length
            # The window reveals/frames may interrupt the masonry at this height.
            assert contact>1.5,(key,host,'实际墙身接触长度',contact)
            host_plan=sourcepolygon(rows[host])
            assert new_roof.intersection(core).area>2.5 and new_roof.covers(land.buffer(-.005))
            overlap=land.intersection(host_plan).area
            assert 5.8<overlap<6.9,(key,host,overlap)
            ends.append({'host':rows[host]['name'],'originalWallGapM':round(original.distance(host_plan),3),
                         'coveredReturnInsideWingM2':round(overlap,3),
                         'actualMasonryAtSoffitContactM':round(contact,3),'newProjectedGapM':round(new_roof.distance(host_plan),4)})
        report.append({'key':keys[key],'ends':ends,'clearWalkingRays':rays,
                       'pavingToGardenBedsM':round(paving.distance(beds),2),'pavingToMappedPathsM':round(paving.distance(paths),2)})
    return {'glbSHA256':model.digest,'view':KEY,'baselineGLBSHA256':before.digest if before else None,
            'clearHeightTestedM':[.08,.35,1.2,1.75,2.10],'galleries':report,'clearWalkingRays':sum(row['clearWalkingRays'] for row in report)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--glb',type=Path,default=ROOT/'山东大学青岛校区.glb')
    parser.add_argument('--before',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'data/凤凰居接翼拱廊核验.json')
    args=parser.parse_args()
    result=check(Scene(args.glb),Scene(args.before) if args.before else None)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
