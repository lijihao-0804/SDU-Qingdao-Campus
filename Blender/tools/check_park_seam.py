"""Independent cross sections of the exported Qingdao campus GLB, in metres.
Example: python -X utf8 -B check_park_seam.py --project F:/.../夕照校园-v6 --model F:/.../after.glb --json after.json
Sampling and the acceptance footprint use source survey/OSM, never proposed fill polygons.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import struct
import numpy as np
import shapely as sh
from shapely.geometry import LineString, Point, Polygon
from scipy.spatial.transform import Rotation


def survey(project):
    data = json.loads((project / 'data/map/campus.json').read_bytes())
    source = json.loads((project / 'data/map/osm-source.json').read_bytes())['elements']
    scale = data['metadata']['metres_per_degree']
    nodes = {n['id']: ((n['lon']-120.68204)*scale['longitude'],
                       (36.36559-n['lat'])*scale['latitude'])
             for n in source if n['type'] == 'node'}
    park_way = next(n for n in source if n['type'] == 'way' and n['id'] == 548365000)
    park = Polygon([nodes[i] for i in park_way['nodes']]).buffer(0)
    campus = Polygon(data['boundary']).buffer(22, quad_segs=5)
    return campus, park


def cross_sections(campus, park, x_step, z_step):
    south = park.bounds[3]
    north = max(campus.bounds[1], park.bounds[1])
    stations = sorted(set(np.arange(math.ceil(north/z_step)*z_step, south, z_step).tolist()
                          + [-1260.,-1200.,-1100.,-1000.,-700.,-410.,-310.,-210.,-100.,-65.,-45.,-35.,-30.,-26.]))
    rows = {'campus_to_park': [], 'north_park_road': []}
    for name, levels in [('campus_to_park',stations),('north_park_road',
        np.arange(math.ceil(park.bounds[1]/z_step)*z_step, north, z_step))]:
        for z in levels:
            cut = LineString([(-2000,z),(2500,z)])
            park_line = park.intersection(cut)
            if park_line.is_empty or park_line.length < 1: continue
            right = park_line.bounds[0]
            if name == 'campus_to_park':
                section = campus.intersection(cut)
                if section.is_empty or section.length < 1: continue
                left = section.bounds[2]
            else:
                # The original park contains a narrow discontinuity in the last ~12 m
                # west of its mapped inland edge. Do not demand new land out to the
                # western carriageway, which is already outside the park.
                left = right-12
            if right < left: continue
            xs = np.r_[left-.31, np.arange(left+.17, right, x_step), right+.29]
            rows[name].append((float(z), float(left), float(right), xs))
    return rows


class Model:
    def __init__(self,path,extra_land):
        self.buf = path.read_bytes()
        size = struct.unpack_from('<I',self.buf,12)[0]
        self.doc = json.loads(self.buf[20:20+size])
        self.off = 28+size
        self.nodes = self.doc['nodes']
        self.xyz = []
        self.meta = []
        self.owner = []
        self.walls = []
        self.extra_land = extra_land
        self.world = {}
        self.regions = {}
        for n in self.doc['scenes'][self.doc.get('scene',0)]['nodes']:
            self.visit(n,np.eye(4),'core')
        if not self.xyz: raise ValueError('No model surface triangles in study area.')
        self.xyz = np.concatenate(self.xyz)
        self.owner = np.concatenate(self.owner)
        self.tree = sh.STRtree(sh.polygons(np.ascontiguousarray(self.xyz[:,:,[0,2]])))
        self.is_core = np.asarray([r[1]!='surroundings' for r in self.meta])
        self.is_water = np.asarray([r[2]=='water' for r in self.meta])
        self.is_road = np.asarray([r[2]=='road' for r in self.meta])
        self.wall_tree = sh.STRtree(sh.linestrings(np.asarray(self.walls))) if self.walls else None

    def array(self,idx):
        a = self.doc['accessors'][idx]
        b = self.doc['bufferViews'][a['bufferView']]
        typ = np.dtype({5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']])
        dim = {'VEC3':3,'SCALAR':1}[a['type']]
        return np.ndarray((a['count'],dim),typ,self.buf,
                          self.off+b.get('byteOffset',0)+a.get('byteOffset',0),
                          strides=(b.get('byteStride',typ.itemsize*dim),typ.itemsize))

    def visit(self,i,parent,region):
        n = self.nodes[i]
        ex = n.get('extras',{})
        region = ex.get('sceneRegion',region)
        if 'matrix' in n:
            m = np.array(n['matrix']).reshape(4,4).T
        else:
            m = np.eye(4)
            m[:3,:3] = Rotation.from_quat(n.get('rotation',[0,0,0,1])).as_matrix() @ np.diag(n.get('scale',[1,1,1]))
            m[:3,3] = n.get('translation',[0,0,0])
        m = parent @ m
        self.world[i] = m
        self.regions[i] = region
        for child in n.get('children',[]): self.visit(child,m,region)
        if 'mesh' not in n: return
        name = n.get('name',''); kind = ex.get('kind'); surface = ex.get('surface')
        if kind in ('sea','surfWater'): group = 'water'
        elif kind == 'terrainCut' and region == 'cutEdge': group = 'wall'
        elif name in self.extra_land: group = 'land'
        elif kind == 'ground' and any(k in name for k in ('车道','沥青','铺面','步行道','道路','步道')): group = 'road'
        elif kind in ('ground','parcelGround','terrainContext'): group = 'land'
        elif kind == 'waterfrontShore' and surface in ('land','sand'): group = 'land'
        elif kind=='waterfront' and surface in ('road','walk','plantingBed'): group='road' if surface!='plantingBed' else 'land'
        elif kind=='hinterland' and surface=='regionalRoad': group='road'
        else: return
        owner = len(self.meta)
        self.meta.append((name,region,group))
        for p in self.doc['meshes'][n['mesh']]['primitives']:
            pos = self.array(p['attributes']['POSITION'])
            pos = pos @ m[:3,:3].T + m[:3,3]
            tr = pos[self.array(p['indices']).reshape(-1,3)]
            # Includes all source survey rows and real-water witnesses.
            keep = (tr[:,:,0].max(1)>210)&(tr[:,:,0].min(1)<1100)&(tr[:,:,2].max(1)>-2010)&(tr[:,:,2].min(1)<-20)
            tr=tr[keep]
            if not len(tr): continue
            if group=='wall':
                low=tr[:,:,1].min(1);high=tr[:,:,1].max(1)
                g=tr[(high-low>3)&((tr[:,:,1] > low[:,None]+1).sum(1)==2)]
                if len(g):
                    ends=g[g[:,:,1]>g[:,:,1].min(1)[:,None]+1].reshape(-1,2,3)[:,:,[0,2]]
                    self.walls.extend(ends[np.linalg.norm(ends[:,0]-ends[:,1],axis=1)>.01].tolist())
                continue
            a = tr[:,1]-tr[:,0]; b=tr[:,2]-tr[:,0]
            tr=tr[np.abs(a[:,0]*b[:,2]-a[:,2]*b[:,0])>1e-8]
            if len(tr):
                self.xyz.append(tr)
                self.owner.append(np.full(len(tr),owner,np.int32))

    def hits(self,xy):
        i,j=self.tree.query(sh.points(xy),predicate='intersects')
        xyz=self.xyz[j]
        a,b,c=xyz[:,0],xyz[:,1],xyz[:,2]
        bx,bz=b[:,0]-a[:,0],b[:,2]-a[:,2];cx,cz=c[:,0]-a[:,0],c[:,2]-a[:,2]
        u,v=xy[i,0]-a[:,0],xy[i,1]-a[:,2]; det=bx*cz-bz*cx
        y=a[:,1]+(u*cz-v*cx)/det*(b[:,1]-a[:,1])+(v*bx-u*bz)/det*(c[:,1]-a[:,1])
        node=self.owner[j]
        def top(mask):
            ii=i[mask];nn=node[mask];h=y[mask]
            order=np.lexsort((h,ii));ii=ii[order]
            alts=np.full(len(xy),np.nan); owners=np.full(len(xy),-1,np.int32)
            alts[ii]=h[order];owners[ii]=nn[order]
            return alts,owners
        land=~self.is_water[node]
        return top(land&self.is_core[node]), top(land), top(self.is_water[node])

    def interior_walls(self,z,left,right):
        if self.wall_tree is None: return []
        line=LineString([(left-.5,z),(right+.5,z)])
        intersects=self.wall_tree.query(line,predicate='intersects')
        pts=sh.intersection(self.wall_tree.geometries[intersects],line)
        return sorted(set(np.round(sh.get_coordinates(pts)[:,0],2).tolist()))


def audit(model,groups,reference_water=None):
    report={}
    for group,rows in groups.items():
        stats=Counter(); examples=[]; witnesses=[]; worst=[0,None]; wall_examples=[]; mode_dz=0.
        for z,left,right,x in rows:
            xy=np.column_stack((x,np.full(len(x),z)))
            (hc,nc),(hf,nf),(water,nw)=model.hits(xy)
            expected_water=(reference_water.hits(xy)[2][0] if reference_water else water)
            dry=~np.isfinite(expected_water)
            missing=dry&~np.isfinite(hc); full_missing=dry&~np.isfinite(hf)
            covered=dry&np.isfinite(hc)&np.isfinite(hf)
            if covered.any(): mode_dz=max(mode_dz,float(np.max(np.abs(hc[covered]-hf[covered]))))
            stats.update(rows=1,drySamples=int(dry.sum()),waterSamplesExcluded=int((~dry).sum()),
                         missingCore=int(missing.sum()),missingFull=int(full_missing.sum()),
                         coreRoadSamples=int((np.isin(nc,np.flatnonzero(model.is_road))&dry).sum()),
                         fullRoadSamples=int((np.isin(nf,np.flatnonzero(model.is_road))&dry).sum()),
                         landOverSourceWater=int((~dry&np.isfinite(hc)).sum()))
            wall_x=model.interior_walls(z,left,right)
            if wall_x:
                stats['sectionsWithInteriorCuts']+=1
                if len(wall_examples)<5: wall_examples.append({'z':z,'x':wall_x})
            def runs(mask):
                edges = np.r_[0,np.where(mask[1:]!=mask[:-1])[0]+1,len(mask)]
                return [[round(float(x[i]),2),round(float(x[k-1]),2)] for i,k in zip(edges,edges[1:]) if mask[i]]
            gap=runs(missing)
            if gap and len(examples)<5: examples.append({'z':z,'x':gap})
            d=np.abs(np.diff(hc)); same=dry[1:]&dry[:-1]&np.isfinite(d)&(np.diff(x)>.99)
            if same.any():
                idx=np.argmax(np.where(same,d,-1))
                if d[idx]>worst[0]: worst=[round(float(d[idx]),4),[round(float(x[idx]),2),z]]
            if z in (-1960,-1800,-1500,-1260,-1200,-1100,-700,-410,-310,-100,-65,-45,-30,-26):
                witnesses.append(dict(z=z,x=[round(left,2),round(right,2)],missingCoreX=gap,
                                      missingFullX=runs(full_missing),cutWallX=wall_x))
        report[group]=dict(**stats,sectionsWithCuts=int(stats.get('sectionsWithInteriorCuts',0)),
                           maxCoreFullSurfaceDifferenceM=round(mode_dz,4),
                           largestOneMetreCoreHeightChange=worst,missingExamples=examples,
                           cutExamples=wall_examples,witnesses=witnesses)
    # Witnesses sampled in the original GLB nearshore water, offshore of sand.
    sites=np.array([[765.,-310.],[708.,-410.],[552.,-800.],[501.,-1100.],[498.,-1200.],[630.,-1500.]])
    (hc,_),(hf,_),(wc,_)=model.hits(sites)
    ref=reference_water.hits(sites)[2][0] if reference_water else wc
    report['shoreWitnesses']=[dict(x=x,z=z,referenceWater=bool(np.isfinite(w0)),water=bool(np.isfinite(w)),
                                    coreLand=bool(np.isfinite(c)),fullLand=bool(np.isfinite(f)))
                              for (x,z),c,f,w,w0 in zip(sites,hc,hf,wc,ref)]
    return report


def check_shore_band(model, reference, park):
    reference=reference or model
    counts=Counter()
    examples=[]
    for z in np.arange(math.ceil(park.bounds[1]/5)*5,park.bounds[3],5):
        section=park.intersection(LineString([(-2000,z),(2500,z)]))
        if section.is_empty: continue
        x=np.arange(math.floor(section.bounds[0])-3,math.ceil(section.bounds[2])+82,2)+.37
        xy=np.column_stack((x,np.full(len(x),z+.19)))
        (c,_),(f,_),(w,_)=model.hits(xy)
        if model is reference: old_f,old_w=f,w
        else: _,(old_f,_),(old_w,_)=reference.hits(xy)
        wet=np.isfinite(old_w)&~np.isfinite(old_f)
        lost=wet&~np.isfinite(w)
        raised_c=wet&np.isfinite(c)&(c>old_w+.04)
        raised_f=wet&np.isfinite(f)&(f>old_w+.04)
        counts.update(originalWetSamples=int(wet.sum()),missingWater=int(lost.sum()),
                      newCoreLandAboveWater=int(raised_c.sum()),newFullLandAboveWater=int(raised_f.sum()))
        problem=lost|raised_c|raised_f
        if problem.any() and len(examples)<5:
            idx=np.flatnonzero(problem)[0]
            examples.append([round(float(x[idx]),2),round(float(z+.19),2)])
    return dict(**counts,examples=examples,pitchXZ=[2,5])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--reference-model',type=Path,help='Original GLB, for invariant water-mask comparison')
    parser.add_argument('--json',type=Path)
    parser.add_argument('--x-step',type=float,default=1)
    parser.add_argument('--z-step',type=float,default=5)
    parser.add_argument('--extra-land',action='append',default=[])
    args=parser.parse_args()
    if not 0<args.x_step<=2 or not 0<args.z_step<=20: raise ValueError('Unsupported sample pitch')
    campus,park=survey(args.project)
    groups=cross_sections(campus,park,args.x_step,args.z_step)
    model=Model(args.model,set(args.extra_land))
    ref=Model(args.reference_model,set()) if args.reference_model and args.reference_model.resolve()!=args.model.resolve() else None
    result=dict(model=str(args.model.resolve()),parkOSMWay=548365000,parkBoundsXZ=list(park.bounds),
                campusParkZLimits=[max(campus.bounds[1],park.bounds[1]),min(campus.bounds[3],park.bounds[3])],
                pitchXZ=[args.x_step,args.z_step],measurements=audit(model,groups,ref))
    result['measurements']['shoreWaterBand']=check_shore_band(model,ref,park)
    if args.json: args.json.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for key,value in result['measurements'].items():
        if isinstance(value,dict): print(key,{k:v for k,v in value.items() if k not in ('missingExamples','cutExamples','witnesses')})
        else: print(key,value)


if __name__=='__main__': main()

