"""Video 3: calibrated settlements, regional approaches and Ao Shan relief.

The input is a small attributed local extract. Campus and park buildings stay with
their original models. We refine the original Sentinel terrain primitive in place,
then measure house footings and clip roadway surfacing against that exact mesh.
"""
from pathlib import Path
import base64
from collections import Counter, defaultdict
import json
import math
import zlib

import mapbox_earcut as earcut
import numpy as np
import shapely as sh
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.polygon import orient

from qd_geometry import Shape
from qd_terrain import face

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'v5_horizon.json'


def _array(scene, index):
    acc = scene.doc['accessors'][index]
    view = scene.doc['bufferViews'][acc['bufferView']]
    dtype = {5123:'<u2', 5125:'<u4', 5126:'<f4'}[acc['componentType']]
    size = {'VEC3':3, 'VEC2':2, 'SCALAR':1}[acc['type']]
    return np.frombuffer(scene.raw, dtype, count=acc['count'] * size,
                         offset=view.get('byteOffset',0)+acc.get('byteOffset',0)).reshape(-1,size).copy()


def _triangles(scene, primitive):
    points = _array(scene, primitive['attributes']['POSITION'])
    indices = _array(scene, primitive['indices']).reshape(-1,3)
    return points[indices]


def _refine_relief(scene, primitive, heights, datum):
    # Unique projected coordinates weld adjacent 160 m tiles before splitting
    # any shared edge. The coast, the inner seam and the original UV map persist.
    source = _triangles(scene, primitive).reshape(-1,3).astype(float)
    _, keep, inv = np.unique(source[:,[0,2]].round(4), axis=0, return_index=True, return_inverse=True)
    points = source[keep]
    indices = inv.reshape(-1,3)
    base_count = len(indices)
    dem = np.frombuffer(zlib.decompress(base64.b64decode(heights['samples'])), '<i2').reshape(heights['shape'])
    origin = np.asarray(heights['origin'])
    def from_dem(points):
        pos = np.clip((points[:,[0,2]]-origin)/heights['spacing'], 0, np.array(dem.shape[::-1])-1.0001)
        i,j = pos.astype(int).T
        a,b = (pos - pos.astype(int)).T
        return ((1-a)*(1-b)*dem[j,i]+a*(1-b)*dem[j,i+1]+
                (1-a)*b*dem[j+1,i]+a*b*dem[j+1,i+1])*.1-datum-.12
    def weights(points):
        x,y,z = points.T
        setback = np.maximum(abs(x)-920,abs(z)-1530)
        return (np.clip((setback-170)/360,0,1)*np.clip((y+datum-18)/22,0,1)*
                np.clip((9200-np.maximum(abs(x),abs(z)))/700,0,1))
    weighted_deltas = []
    for min_edge in (131,78):
        tri = points[indices]
        delta = np.roll(tri[:,:,[0,2]],-1,axis=1)-tri[:,:,[0,2]]
        edge_len = np.linalg.norm(delta,axis=2)
        eligible = (weights(tri.mean(1))>.01) & (edge_len.max(1)>min_edge)
        edges = np.sort(np.stack([indices, np.roll(indices,-1,axis=1)],axis=2),axis=2)
        selected = edges[eligible][edge_len[eligible]>min_edge]
        if not len(selected):
            continue
        selected = np.unique(selected,axis=0)
        midpoint = points[selected].mean(1)
        diff = (from_dem(midpoint)-midpoint[:,1])*weights(midpoint)
        midpoint[:,1] += diff
        weighted_deltas.extend(abs(diff))
        lookup = {tuple(edge):len(points)+i for i,edge in enumerate(selected)}
        points = np.vstack((points,midpoint))
        next_idx = []
        for tri,ed in zip(indices,edges):
            a,b,c = map(int,tri)
            m,n,o = (lookup.get(tuple(pair)) for pair in ed)
            if m is not None and n is not None and o is not None:
                next_idx.extend([(a,m,o),(m,b,n),(o,n,c),(m,n,o)])
            elif m is None and n is None and o is None:
                next_idx.append((a,b,c))
            else:
                # Handle the three rotations explicitly to avoid T junctions.
                corners = [a,b,c]; mids = [m,n,o]
                if mids.count(None)==2:
                    j=next(j for j,id_ in enumerate(mids) if id_ is not None)
                    a,b,c=[corners[(j+k)%3] for k in range(3)]
                    m=mids[j];next_idx.extend([(a,m,c),(m,b,c)])
                else:
                    j=mids.index(None)
                    a,b,c=[corners[(j+k)%3] for k in range(3)]
                    n,o=mids[(j+1)%3],mids[(j+2)%3]
                    next_idx.extend([(a,b,n),(a,n,o),(n,c,o)])
        indices = np.asarray(next_idx,dtype=np.int32)
    normals = np.zeros_like(points)
    ele = points[indices]
    vectors = np.cross(ele[:,1]-ele[:,0],ele[:,2]-ele[:,0])
    for i in range(3):
        np.add.at(normals,indices[:,i],vectors)
    length=np.maximum(np.linalg.norm(normals,axis=1),1e-12)
    normals /= length[:,None]
    attrs=primitive['attributes']
    attrs['POSITION']=scene.accessor(points,'<f4','VEC3',5126,34962)
    attrs['NORMAL']=scene.accessor(normals,'<f4','VEC3',5126,34962)
    attrs['TEXCOORD_0']=scene.accessor((points[:,[0,2]]+10000)/20000,'<f4','VEC2',5126,34962)
    primitive['indices']=scene.accessor(indices.ravel(),'<u4','SCALAR',5125,34963)
    return dict(baseTriangles=base_count,triangles=len(indices),newMeasuredVertices=len(weighted_deltas),
                largestCorrectionM=round(float(max(weighted_deltas,default=0)),2)),ele


class Ground:
    def __init__(self, terrain_triangles):
        t=np.asarray(terrain_triangles,dtype=float)
        norm=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
        mask=abs(norm[:,1])>1.e-6
        self.tris=t[mask]
        self.norm=norm[mask]
        self.polys=sh.polygons(self.tris[:,:,[0,2]])
        self.tree=sh.STRtree(self.polys)

    def heights(self,coords):
        coords=np.asarray(coords)
        out=np.full(len(coords),np.nan)
        a,b=self.tree.query(sh.points(coords),predicate='intersects')
        if len(a):
            p=self.tris[b,0];n=self.norm[b]
            out[a]=p[:,1]-(n[:,0]*(coords[a,0]-p[:,0])+n[:,2]*(coords[a,1]-p[:,2]))/n[:,1]
        return out

    def drape(self,shape,region,material,lift):
        if region.is_empty:
            return 0.
        area=0.
        for ti in self.tree.query(region,predicate='intersects'):
            inter=region.intersection(self.polys[ti])
            if inter.area<.03:
                continue
            n=self.norm[ti];p=self.tris[ti,0]
            def y(x,z):
                return p[1]-(n[0]*(x-p[0])+n[2]*(z-p[2]))/n[1]+lift
            face(shape,inter,material,y)
            area+=inter.area
        return area


def _roads(scene, ground, info, boundary):
    from shapely.ops import substring
    limits=boundary.buffer(3050).intersection(box(-4300,-4100,3050,4200))
    surfaces=[]; marks=[]
    for _,name,width,pts,oneway,kind in info['roads']:
        road=LineString(pts).intersection(limits)
        parts=[road] if road.geom_type=='LineString' else [v for v in getattr(road,'geoms',[]) if v.geom_type=='LineString']
        for line in parts:
            if line.length<3:
                continue
            surfaces.append(line.buffer(width/2,cap_style=2,join_style=1,quad_segs=3))
            if oneway!='yes' or width<9.4 or kind!='trunk':
                continue
            for side in (-1,1):
                strip=line.offset_curve(side*width/6,quad_segs=3)
                if strip.geom_type!='LineString':
                    continue
                for distance in np.arange(0.,strip.length-2,20.):
                    seg=substring(strip,distance,min(distance+6.4,strip.length))
                    marks.append(seg.buffer(.085,cap_style=2))
    asphalt=sh.union_all(surfaces)
    shape=Shape('滨海公路与外围道路 · 地形贴合路面')
    area=ground.drape(shape,asphalt,'#737679',.145)
    paint=ground.drape(shape,sh.union_all(marks),'#c7c4b9',.177)
    scene.node(shape.name,shape=shape,kind='hinterland',surface='regionalRoad',roadAreaM2=round(area,1),markAreaM2=round(paint,1))
    return asphalt


def _roof_clip(points, normal, center, side):
    out=[]
    for i,a in enumerate(points):
        b=points[(i+1)%len(points)]
        da=np.dot(a-center,normal)*side;db=np.dot(b-center,normal)*side
        if da>=-1e-7:
            out.append(a)
        if (da>1e-7 and db<-1e-7) or (da<-1e-7 and db>1e-7):
            out.append(a+(b-a)*(da/(da-db)))
    return out


CLAY=('#984f3e','#ab614a','#8c5144','#b56850','#9f5b48')
SLATE=('#858582','#858c8f','#939a97')
WALL=('#c8b9a3','#c2b7a7','#c8c1b2','#bcb4a9')
APARTMENT=('#c3bcb6','#c8c5bd','#bcc2c1','#cbc3b8')
CROWN=('#929898','#a5a39b','#959b9c')


def _house(shape, ring, ground, height, form, id_, nearby, detailed):
    poly=Polygon(ring)
    center=np.asarray(poly.centroid.coords[0]); pts=np.asarray(ring,dtype=float)
    if not poly.exterior.is_ccw:
        pts=pts[::-1];ground=ground[::-1]
    floor=float(np.median(ground))
    peak=max(float(max(ground))+2.5,floor+height)
    ridge=form in ('tile','slate')
    shade=(id_*2654435761) & 0xffffffff
    walls=(WALL if ridge else APARTMENT)[shade%4]
    roof=(CLAY if form=='tile' else SLATE if form=='slate' else CROWN)[(shade//11)% (5 if form=='tile' else 3)]
    if ridge:
        rect=np.array(poly.minimum_rotated_rectangle.exterior.coords)[:4]
        vectors=np.roll(rect,-1,axis=0)-rect
        v=vectors[np.argmax(np.linalg.norm(vectors,axis=1))]
        normal=np.array([-v[1],v[0]])/np.linalg.norm(v)
        center=rect.mean(0);half=max(.2,abs((rect-center)@normal).max())
        rise=min(3.2,max(1.15,half*.35),height*.38)
    def top(q):
        return peak-min(1.,abs(np.dot(q-center,normal))/half)*rise if ridge else peak
    for j,a in enumerate(pts):
        k=(j+1)%len(pts);b=pts[k];pa=(a[0],top(a),a[1]);pb=(b[0],top(b),b[1])
        crest=[]
        if ridge:
            da=np.dot(a-center,normal);db=np.dot(b-center,normal)
            if da*db<-1e-7:
                q=a+(b-a)*da/(da-db);crest=[(q[0],peak,q[1])]
        facepts=[(a[0],ground[j]-.22,a[1]),pa,*crest,pb,(b[0],ground[k]-.22,b[1])]
        shape.mesh('屋身',facepts,[tuple(range(len(facepts)))],walls)
        # In the eastern field shot, nearby village houses have painted masonry
        # gables, dark paired windows, a narrow eave and one/two storeys.
        length=float(np.linalg.norm(b-a))
        if detailed and height<21 and length>4.2:
            unit=(b-a)/length
            out=np.array([unit[1],-unit[0]])*.055
            def panel(lo,hi,bottom,top_,material):
                start=a+unit*lo+out;end=a+unit*hi+out
                points=[(start[0],bottom,start[1]),(start[0],top_,start[1]),
                        (end[0],top_,end[1]),(end[0],bottom,end[1])]
                shape.mesh('临街窗与檐口',points,[(0,1,2,3)],material)
            eave=peak-rise if ridge else peak
            if ridge and abs(np.dot(unit,normal))<.34 and length>6:
                panel(0,length,eave-.19,eave-.03,'#806852')
            storeys=max(1,min(4,round((eave-floor)/3.05)))
            floor_step=(eave-floor)/storeys
            bays=max(1,min(7,int(length/3.75)))
            for level in range(storeys):
                bottom=floor+level*floor_step+min(.94,floor_step*.31)
                top_=bottom+min(1.28,floor_step*.45)
                for bay in range(bays):
                    center_bay=length*(bay+.5)/bays
                    wide=min(1.53,length/bays*.49)
                    panel(center_bay-wide/2,center_bay+wide/2,bottom,top_,'#697982')
            if ridge and abs(np.dot(unit,normal))>.79 and length>6 and rise>1.25:
                panel(length*.46,length*.54,eave+.30,eave+min(.89,rise*.70),'#706e67')
        if form=='tower' and nearby and np.linalg.norm(b-a)>11:
            # Recessed-looking bands only at the scale legible in the oblique shot.
            side=b-a;unit=side/np.linalg.norm(side)
            start=a+side*.10;end=b-side*.10;offset=np.array([unit[1],-unit[0]])*.045
            for level in np.arange(floor+5.7,peak-1.4,5.8):
                q=start+offset;r=end+offset
                span=[(q[0],level,q[1]),(q[0],level+.72,q[1]),
                      (r[0],level+.72,r[1]),(r[0],level,r[1])]
                shape.mesh('分层窗带',span,[(0,1,2,3)],'#8e999b')
    triangles=earcut.triangulate_float64(pts.copy(),np.array([len(pts)],dtype='uint32')).reshape(-1,3)
    for tri in triangles:
        ring3=pts[tri]
        faces=[_roof_clip(ring3,normal,center,s) for s in (-1,1)] if ridge else [ring3]
        for coords in faces:
            if len(coords)<3:
                continue
            ps=[(q[0],top(q),q[1]) for q in coords]
            shape.mesh('坡顶' if ridge else '平屋面',ps,[tuple(reversed(range(len(ps))))],roof)


def _roadside_trees(scene, coast, seam, info, data, boundary, asphalt):
    # Rows in the opening/closing highway shots and behind the eastern track.
    # Setbacks follow mapped carriageways. Positions are illustrative along
    # the video-supported belt; existing trees, roofs and pavement take priority.
    from PIL import Image
    from scipy.spatial import cKDTree
    texture=np.asarray(Image.open(ROOT/'assets/海岸环境.jpg').convert('RGB'),dtype=float)
    roof_tree=sh.STRtree([Polygon(row[3]) for row in info['footprints']])
    prior=[(n['translation'][0],n['translation'][2]) for n in scene.doc['nodes']
           if n.get('extras',{}).get('kind')=='flora' and 'translation' in n]
    prior_tree=cKDTree(prior) if prior else None
    inner=boundary.buffer(6.)
    pavement=asphalt.buffer(.4)
    sh.prepare(inner);sh.prepare(pavement)
    rng=np.random.default_rng(305321)
    supports=[(r[1],r[2],LineString(r[3])) for r in info['roads'] if r[1] in ('滨海公路','滨海公路辅路')]
    supports.extend(('东田径场南北向村道',r['width'],LineString(r['line'])) for r in data['roads'] if r['id']=='way/453282530')
    candidates=[]
    for name,width,line in supports:
        step=10.7 if name=='滨海公路' else 9.3
        for t in np.arange(step*.5,line.length-step*.4,step):
            along=t+rng.uniform(-1.5,1.5);p=line.interpolate(along)
            if abs(p.x)>1700 or abs(p.y)>2100:
                continue
            a=np.asarray(line.interpolate(max(0,along-1)).coords[0])
            b=np.asarray(line.interpolate(min(line.length,along+1)).coords[0])
            v=b-a;length=np.linalg.norm(v)
            if length<.1:
                continue
            normal=np.array([-v[1],v[0]])/length
            for side in (-1,1):
                pos=np.asarray(p.coords[0])+normal*side*(width/2+rng.uniform(2.4,4.3))
                q=sh.Point(pos)
                if inner.intersects(q) or pavement.intersects(q) or roof_tree.query(q.buffer(3),predicate='intersects').size:
                    continue
                if prior_tree is not None and prior_tree.query(pos)[0]<5.8:
                    continue
                j,i=((pos[::-1]+10000)/20000*np.array(texture.shape[:2])).astype(int)
                rr,gg,bb=texture[j,i]
                if (rr-gg>17 or bb>gg+12) and name!='东田径场南北向村道':
                    continue
                candidates.append(pos)
    if not candidates:
        return 0
    heights=coast.heights(candidates)
    if seam:
        use=np.isnan(heights);heights[use]=seam.heights(np.asarray(candidates)[use])
    shape=Shape('滨海公路及东田径场外 · 道路乔木')
    accepted=set()
    colors=('#61734e','#6f8257','#727f52','#607751','#738b62')
    total=0
    for pos,y in zip(candidates,heights):
        if not np.isfinite(y):
            continue
        x,z=pos
        sector=(math.floor(x/5),math.floor(z/5))
        if any((sector[0]+i,sector[1]+j) in accepted for i,j in ((0,0),(1,0),(-1,0),(0,1),(0,-1))):
            continue
        accepted.add(sector)
        h=rng.uniform(4.7,7.6);r=rng.uniform(1.75,2.65);rot=rng.uniform(0,6.28)
        shape.cyl('树干',x,y+h*.24-.09,z,.14,h*.48,'#776951',5)
        ends=[(x,y+h*.34,z)]
        for ry,factor in ((.49,.88),(.67,1),(.85,.72)):
            for k in range(7):
                a=rot+k*2*math.pi/7;rr=r*factor*rng.uniform(.89,1.11)
                ends.append((x+math.cos(a)*rr,y+ry*h+rng.uniform(-.15,.15),z+math.sin(a)*rr))
        ends.append((x+.2,y+h,z-.16));faces=[]
        for k in range(7):
            j=(k+1)%7;faces.extend([(0,1+k,1+j),(1+k,8+k,8+j,1+j),
                                    (8+k,15+k,15+j,8+j),(15+k,22,15+j)])
        shape.mesh('树冠',ends,faces,colors[int(rng.integers(len(colors)))])
        total+=1
    scene.node(shape.name,shape=shape,kind='hinterland',surface='roadsidePlanting',treeCount=total)
    return total


def build(scene,terrain,data,catalog):
    info=json.loads(DATA.read_text('utf8'))
    context=[n for n in scene.doc['nodes'] if n.get('extras',{}).get('kind')=='terrainContext']
    if len(context)!=1:
        raise ValueError('Exactly one coastal context mesh is required')
    node=context[0]
    prim=scene.doc['meshes'][node['mesh']]['primitives'][0]
    relief,triangles=_refine_relief(scene,prim,info['relief'],terrain.datum)
    node['extras']['v5Relief']=relief
    coast=Ground(triangles)
    boundary=Polygon(data['boundary']).buffer(0)
    road=_roads(scene,coast,info,boundary)
    # Keep the 24–70 m terrestrial strip between the campus buffer and rural mesh.
    inner=[]
    for n in scene.doc['nodes']:
        if n['name']=='校园及滨海地形':
            for p in scene.doc['meshes'][n['mesh']]['primitives']:
                inner.append(_triangles(scene,p))
    seam=Ground(np.concatenate(inner)) if inner else None
    trees=_roadside_trees(scene,coast,seam,info,data,boundary,road)
    features=info['footprints']
    coords=np.concatenate([np.asarray(f[3]) for f in features])
    levels=coast.heights(coords)
    if seam is not None and np.isnan(levels).any():
        mask=np.isnan(levels); levels[mask]=seam.heights(coords[mask])
    ofs=0;groups={};counts=defaultdict(Counter); skipped=Counter()
    for id_,height,form,ring in features:
        n=len(ring);base=levels[ofs:ofs+n];ofs+=n
        if np.isnan(base).any():
            skipped['outsideLandMesh']+=1;continue
        if float(np.ptp(base))>max(7,height*.65):
            skipped['steepFoundation']+=1;continue
        poly=Polygon(ring)
        if not poly.is_valid or poly.area<15 or poly.intersection(road).area>max(4.,poly.area*.12):
            skipped['roadOrInvalid']+=1;continue
        x,z=poly.centroid.coords[0]
        sector=(math.floor((x+250)/1400),math.floor((z+250)/1400))
        if sector not in groups:
            groups[sector]=Shape('鳌山卫校外围街区 · %d,%d'%sector)
        _house(groups[sector],ring,base,float(height),form,id_,abs(x)<2600 and abs(z)<3500,poly.distance(boundary)<600)
        counts[sector][form]+=1
    for sector,shape in sorted(groups.items()):
        stats=counts[sector]
        scene.node(shape.name,shape=shape,kind='hinterland',surface='settlement',
                   roofCounts=dict(stats),buildingCount=sum(stats.values()),gridSector=list(sector),
                   source='3D-GloBFP 2416 / data/v5_horizon.json')
    total=sum(sum(v.values()) for v in counts.values())
    summary=dict(footprints=total,sourceFootprints=len(features),skipped=dict(skipped),sectors=len(groups),roadsideTrees=trees,relief=relief)
    node['extras']['v5Settlements']=summary
    for p in info['viewpoints']:
        x,y,z=p['target']
        catalog.append(dict(key=p['key'],name=p['name'],x=x,y=y,z=z,h=18,r=220,group='校园周边',
                            viewpoint={k:p[k] for k in ('eye','target','fov')},note='用户航拍可见的外围街区与天际线。'))
    print('V5 horizon',json.dumps(summary,ensure_ascii=False),flush=True)
    return summary
