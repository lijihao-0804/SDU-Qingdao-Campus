"""Vertical intersections with the ground and paving triangles present in the exported scene."""
import numpy as np
import shapely
from scipy.spatial.transform import Rotation


class Geometry:
    def __init__(self,doc,buffer):
        self.doc=doc
        self.buffer=buffer
        self.nodes=doc['nodes']
        self.matrices={}
        def visit(i,parent):
            n=self.nodes[i]
            if 'matrix' in n:
                local=np.array(n['matrix'],dtype=float).reshape(4,4).T
            else:
                local=np.eye(4)
                local[:3,:3]=Rotation.from_quat(n.get('rotation',[0,0,0,1])).as_matrix() @ np.diag(n.get('scale',[1,1,1]))
                local[:3,3]=n.get('translation',[0,0,0])
            self.matrices[i]=parent@local
            for child in n.get('children',[]):visit(child,self.matrices[i])
        for root in doc['scenes'][doc.get('scene',0)]['nodes']:visit(root,np.eye(4))

    def values(self,index):
        acc=self.doc['accessors'][index]
        view=self.doc['bufferViews'][acc['bufferView']]
        dtype=np.dtype({5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[acc['componentType']])
        n={'VEC3':3,'VEC2':2,'SCALAR':1}[acc['type']]
        return np.ndarray((acc['count'],n),dtype,self.buffer,offset=view.get('byteOffset',0)+acc.get('byteOffset',0),
                          strides=(view.get('byteStride',dtype.itemsize*n),dtype.itemsize))

    def transform(self,i,pts):
        m=self.matrices[i]
        return pts@m[:3,:3].T+m[:3,3]

    def batches(self,i,morph=False):
        mesh=self.doc['meshes'][self.nodes[i]['mesh']]
        for p in mesh['primitives']:
            v=self.values(p['attributes']['POSITION'])
            if morph and p.get('targets'):
                v=v.astype(float)
                for w,target in zip(self.nodes[i].get('weights',mesh.get('weights',[])),p['targets']):
                    if w and 'POSITION' in target:v+=w*self.values(target['POSITION'])
            ix=self.values(p['indices']).ravel().reshape(-1,3)
            yield p,self.transform(i,v)[ix]

    def local_vertices(self,i):
        return np.vstack([self.values(p['attributes']['POSITION']) for p in self.doc['meshes'][self.nodes[i]['mesh']]['primitives']])


class Surface:
    def __init__(self,geo,water=False):
        vertices=[];owners=[];modes=[]
        for i in geo.matrices:
            n=geo.nodes[i];e=n.get('extras',{});kind=e.get('kind');surface=e.get('surface')
            if water:
                if kind not in ('sea','water','surfWater'):continue
                mode=1
            elif kind=='terrainContext':mode=0
            elif ((kind=='ground' and n['name'] in ('校园及滨海地形','两苑庭院与入口下方土基')) or
                  (kind=='waterfrontShore' and surface in ('land','sand','subtidal'))):mode=1
            elif kind in ('ground','parcelGround') or (kind=='waterfront' and surface in ('road','walk','plantingBed')):mode=2
            elif kind=='plazaDetail' and e.get('plazaKey')=='innovation-forecourt' and not e.get('owner'):mode=2
            elif e.get('key') in ('zhensheng','huagang'):mode=2
            else:continue
            for prim,tri in geo.batches(i,morph=water):
                if e.get('key') in ('zhensheng','huagang'):
                    m=geo.doc['materials'][prim['material']]
                    src=m.get('extras',{}).get('sourceSurface',m['name']).lower()
                    if src not in ('#b9b4a8','#83925d','#b9b7a7'):continue
                    relative=tri[:,:,1]-geo.matrices[i][1,3]
                    tri=tri[(relative.min(1)>=.04)&(relative.max(1)<=.26)]
                cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
                t=tri[abs(cross[:,1])>1e-7]
                if len(t):
                    vertices.append(t);owners.append(np.full(len(t),i,'i4'));modes.append(np.full(len(t),mode,'i1'))
        self.tri=np.vstack(vertices)
        self.owners=np.concatenate(owners)
        self.modes=np.concatenate(modes)
        self.normals=np.cross(self.tri[:,1]-self.tri[:,0],self.tri[:,2]-self.tri[:,0])
        self.index=shapely.STRtree(shapely.polygons(self.tri[:,:,[0,2]]))

    def coastal_toes(self,geo,xz):
        if not hasattr(self,'subtidal'):
            node=next(i for i in geo.matrices if geo.nodes[i].get('extras',{}).get('surface')=='subtidal')
            self.bed_ids=np.flatnonzero(self.owners==node)
            self.subtidal=shapely.STRtree(shapely.polygons(self.tri[self.bed_ids][:,:,[0,2]]))
        q=shapely.points(xz);near=self.subtidal.nearest(q);poly=self.subtidal.geometries[near]
        toe=shapely.get_coordinates(shapely.get_point(shapely.shortest_line(q,poly),-1))
        # Nudge a few centimetres into the existing submerged sand triangle.
        center=shapely.get_coordinates(shapely.centroid(poly));towards=center-toe
        toe+=towards*np.minimum(.4,.06/np.maximum(1.e-9,np.linalg.norm(towards,axis=1)))[:,None]
        h=self.heights(toe)
        h[np.linalg.norm(toe-xz,axis=1)>1.25]=np.nan
        return toe,h

    def heights(self,xz,bare=False,exclude=None):
        xz=np.asarray(xz,float).reshape(-1,2)
        yy=np.full(len(xz),-np.inf)
        for first in range(0,len(xz),24000):
            xy=xz[first:first+24000]
            for exact in (True,False):
                missing=np.arange(len(xy)) if exact else np.flatnonzero(~np.isfinite(yy[first:first+len(xy)]))
                if not len(missing):break
                pts=shapely.points(xy[missing])
                # Adjacent exported tiles can round the same boundary coordinate
                # to opposite sides of a float32 ULP. Permit at most one mm
                # lateral mismatch and evaluate the actual triangle plane.
                if exact:a,b=self.index.query(pts,predicate='intersects')
                else:a,b=self.index.query(pts,predicate='dwithin',distance=.001)
                a=missing[a]
                keep=(self.modes[b]<=1) if bare else np.ones(len(b),bool)
                if exclude is not None:keep&=self.owners[b]!=exclude
                a,b=a[keep],b[keep]
                native=np.zeros(len(xy),bool);native[a[self.modes[b]>0]]=True
                mask=(self.modes[b]>0)|~native[a];a,b=a[mask],b[mask]
                p=self.tri[b,0];n=self.normals[b]
                y=p[:,1]-(n[:,0]*(xy[a,0]-p[:,0])+n[:,2]*(xy[a,1]-p[:,2]))/n[:,1]
                np.maximum.at(yy,first+a,y)
        yy[~np.isfinite(yy)]=np.nan
        return yy

# Tolerances refer to air under a structural toe or the lowest sampled root.
LIMITS = {'building': .055, 'coastalBuilding': .055, 'serviceBuilding': .055,
          'settlement': .075, 'retainingWall': .055, 'arcadePier': .055, 'sportsBase': .06, 'bridgePier': .05, 'bridgeAbutment': .05,
          'stairs': .055, 'paving': .06, 'regionalRoad': .075, 'furniture': .05,
          'tree': .045, 'shrub': .055, 'groundcover': .065, 'coastalGrass': .055,
          'roadsideTrunk': .065, 'parkingWheels': .055}
SAMPLE_STEP = {'paving': 3., 'regionalRoad': 5., 'settlement': 3.}
PAVEMENT = ('道路','路缘','铺地','步行带','步道','铺面','路面','步行道','人行道','入口铺地','铺石')
STONE = {'paving':'#827d72','regionalRoad':'#666767','stairs':'#a69c8d',
         'bridgePier':'#9a9b8f','bridgeAbutment':'#a2a297','furniture':'#928b7e',
         'roadsideTrunk':'#776951'}

def material(geo,prim):
    m=geo.doc['materials'][prim['material']]
    return m.get('extras',{}).get('sourceSurface',m['name']).lower()

def classification(n):
    e=n.get('extras',{});k=e.get('kind');s=e.get('surface');name=n['name']
    if e.get('key') in {f'way-{n}' for n in range(970257682,970257686)}:return 'arcadePier'
    if e.get('arenaSouth')=='retaining':return 'retainingWall'
    if e.get('key') in ('blue_track','east_track'):return 'sportsBase'
    if k in ('building','landmark') and e.get('key') not in ('track','yuxian','east-track','west-track'):
        return 'building'
    if k=='plazaDetail' and e.get('owner'):return 'building'
    if k=='worksCabin':return 'serviceBuilding'
    if s=='parkBuilding':return 'coastalBuilding'
    if s=='settlement':return 'settlement'
    if s=='bridge':return 'bridgePier'
    if s=='roadsidePlanting':return 'roadsideTrunk'
    if s=='steps':return 'stairs'
    if k=='parcelGround' and any(w in name for w in ('东侧入口','通道','院地','园内小径','球场边带','整地')):return 'paving'
    if k=='ground' and any(w in name for w in PAVEMENT) and '土基' not in name:return 'paving'
    if k=='waterfront' and s in ('walk','road'):return 'paving'
    if s=='regionalRoad':return 'regionalRoad'
    if k=='flora':return 'shrub' if e.get('shrub') else 'tree'
    if k=='groundcover':return 'groundcover'
    if k=='waterfrontFurniture' and '春草' in name:return 'coastalGrass'
    if k in ('walkFurniture','waterfrontFurniture'):return 'furniture'
    if k=='parkingVehicle':return 'parkingWheels'

def _unique_edges(edges,boundary=False):
    if not len(edges):return np.empty((0,2,3))
    a=np.asarray(edges,float)
    # Projected endpoints match even along risers connecting two tread heights.
    pos=np.rint(a[:,:,[0,2]]*10000).astype('i8')
    flip=(pos[:,1,0]<pos[:,0,0])|((pos[:,1,0]==pos[:,0,0])&(pos[:,1,1]<pos[:,0,1]))
    pos[flip]=pos[flip,::-1];a[flip]=a[flip,::-1]
    _,idx,n=np.unique(pos.reshape(-1,4),axis=0,return_index=True,return_counts=True)
    if boundary:idx=idx[n==1]
    return a[idx]

def _bottom_sides(tri,minimum=None):
    # One triangle of each vertical quad has a true lower edge and an upper
    # vertex directly over one of those endpoints. Handles sloping foundations.
    n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    t=tri[(abs(n[:,1])<.0005*np.maximum(.001,np.linalg.norm(n[:,[0,2]],axis=1)))]
    edges=[]
    for a,b in ((0,1),(1,2),(2,0)):
        c=3-a-b
        aligned=np.linalg.norm(t[:,a][:,[0,2]]-t[:,b][:,[0,2]],axis=1)<.0005
        for low,high in ((a,b),(b,a)):
            sel=aligned&(t[:,high,1]>np.maximum(t[:,low,1],t[:,c,1])+.012)
            if minimum is not None:sel&=np.maximum(t[:,low,1],t[:,c,1])<=minimum+.026
            if sel.any():edges.append(t[sel][:,[low,c]])
    return np.concatenate(edges) if edges else np.empty((0,2,3))

def edge_groups(geo,i,category):
    parts=list(geo.batches(i))
    if category=='arcadePier':
        t=np.vstack([t for p,t in parts if material(geo,p)=='#b77261'])
        sections=[]
        # Slice just above each actual pier base. A 2 cm lip across an arch
        # opening is intentionally excluded, keeping the public passage open.
        for offset in (-2.24,-1.15):
            base=geo.matrices[i][1,3]+offset;cut=base+.14
            low=t[:,:,1].min(1);high=t[:,:,1].max(1)
            for triangle in t[(abs(low-base)<.035)&(high>cut)]:
                pts=[]
                for a,b in ((0,1),(1,2),(2,0)):
                    p,q=triangle[a],triangle[b]
                    if (p[1]<=cut)!=(q[1]<=cut):
                        v=p+(q-p)*(cut-p[1])/(q[1]-p[1]);v[1]=base;pts.append(v)
                if len(pts)==2:sections.append(pts)
        yield category,_unique_edges(sections)
        return
    if category in ('paving','stairs','regionalRoad','sportsBase'):
        alltri=[]
        for p,t in parts:
            src=material(geo,p)
            if category=='stairs' and src not in ('#b8afa0','#c4bbab'):continue
            if category=='regionalRoad' and src!='#737679':continue
            if category=='sportsBase' and src not in ('#a4aba2','#b47661'):continue
            norm=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
            sel=abs(norm[:,1])>.5*np.linalg.norm(norm,axis=1)
            if sel.any():alltri.append(t[sel])
        if alltri:
            t=np.vstack(alltri);edges=np.concatenate([t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]])
            boundary=_unique_edges(edges,True)
            if len(boundary):
                # Drape triangulation may have T-junctions. A numerical edge
                # unmatched by index can still lie inside a continuous slab.
                xz=boundary[:,:,[0,2]];delta=xz[:,1]-xz[:,0]
                length=np.linalg.norm(delta,axis=1)
                offset=np.column_stack((-delta[:,1],delta[:,0]))*np.minimum(.08,.008/np.maximum(length,1e-9))[:,None]
                pts=np.concatenate([xz.mean(1)+offset,xz.mean(1)-offset])
                hit=shapely.STRtree(shapely.polygons(t[:,:,[0,2]])).query(shapely.points(pts),predicate='intersects')[0]
                inside=np.zeros(len(pts),bool);inside[hit]=True
                boundary=boundary[inside[:len(boundary)]^inside[len(boundary):]]
            yield category,boundary
        return
    if category=='bridgePier':
        # The builder emits continuous underside quads in longitudinal order.
        # Only the transverse ends of the first and last deck quad are abutments.
        for p,t in parts:
            if material(geo,p)=='#b7b9ad':
                yield 'bridgeAbutment',np.array([t[0,[0,1]],t[-1,[1,2]]])
    mats=None
    if category=='settlement':
        from qd_video_horizon import WALL,APARTMENT
        mats=set(WALL+APARTMENT)
    if category=='bridgePier':mats={'#a6a797'}
    if category=='serviceBuilding':mats={'#989c94'}
    if category=='retainingWall':mats={'#bab7a8','#a9aaa0'}
    if category=='roadsideTrunk':mats={'#776951'}
    chosen=[t for p,t in parts if mats is None or material(geo,p) in mats]
    if not chosen:return
    miny=None if category in ('settlement','roadsideTrunk','retainingWall','serviceBuilding') else min(t[:,:,1].min() for t in chosen)
    edges=np.vstack([_bottom_sides(t,miny) for t in chosen])
    if len(edges) and miny is None:
        # A triangulated gable fan can run from an actual foundation corner to
        # a roof crest. Both structural endpoints must have a vertical column
        # above them, and each must be the lowest vertex in that column.
        points=np.vstack([t.reshape(-1,3) for t in chosen])
        columns={}
        for x,y,z in np.unique(points,axis=0):
            key=(round(x,4),round(z,4))
            lo,hi=columns.get(key,(y,y));columns[key]=(min(lo,y),max(hi,y))
        valid=[]
        for edge in edges:
            endpoints=[columns[round(x,4),round(z,4)] for x,_,z in edge]
            valid.append(all(y<=lo+.025 and hi>lo+.025 for (_,y,_),(lo,hi) in zip(edge,endpoints)))
        edges=edges[np.array(valid)]
    # A light dome can terminate in a sloping curved shell with no vertical
    # sides. Its lowest horizontal footprint is the toe in that case.
    if not len(edges) and miny is not None:
        out=[]
        for t in chosen:
            for a,b in ((0,1),(1,2),(2,0)):
                mask=(np.maximum(t[:,a,1],t[:,b,1])<=miny+.025)&(t[:,3-a-b,1]>miny+.04)
                if mask.any():out.append(t[mask][:,[a,b]])
        if out:edges=np.vstack(out)
    yield category,_unique_edges(edges)

def stations(edges,step):
    if not len(edges):return edges
    lengths=np.linalg.norm((edges[:,1]-edges[:,0])[:,[0,2]],axis=1)
    edges=edges[lengths>.001];lengths=lengths[lengths>.001]
    count=np.maximum(1,np.ceil(lengths/step).astype(int))
    reps=np.repeat(np.arange(len(edges)),count)
    start=np.arange(len(reps))-np.repeat(np.cumsum(count)-count,count)
    ab=edges[reps];delta=ab[:,1]-ab[:,0]
    return np.stack([ab[:,0]+delta*(start/count[reps])[:,None],
                     ab[:,0]+delta*((start+1)/count[reps])[:,None]],1)

def probe(surface,span,exclude):
    pts=np.stack([span[:,0],span.mean(1),span[:,1]],axis=1)
    h=surface.heights(pts[:,:,[0,2]].reshape(-1,2),exclude=exclude).reshape(-1,3)
    return pts[:,:,1]-h,h

def _key(edge):
    stored=np.asarray(edge,dtype='<f4').astype(float)
    a=tuple(np.rint(stored[0]*1000).astype(int));b=tuple(np.rint(stored[1]*1000).astype(int))
    return tuple(sorted((a,b)))

def installed_supports(geo):
    result={}
    for i in geo.matrices:
        e=geo.nodes[i].get('extras',{})
        if e.get('kind')!='groundSupport':continue
        quads={}
        for _,t in geo.batches(i):
            if len(t)%2:raise ValueError('Odd triangle count in ground support')
            # Read actual indexed geometry: triangles (A,B,b) and (A,b,a).
            t=t.reshape(-1,2,3,3)
            if not np.allclose(t[:,0,0],t[:,1,0]) or not np.allclose(t[:,0,2],t[:,1,1]):
                raise ValueError('Unexpected ground support topology')
            for pair in t:
                top=pair[0,:2];bottom=pair[1,[2,1]]
                if np.max(np.linalg.norm(top[:,[0,2]]-bottom[:,[0,2]],axis=1))>(1.26 if e['category']=='stairs' else .001):raise ValueError('Disconnected ground support')
                quads[_key(top)]=(top,bottom)
        result[(e['groundContactOwner'],e['category'])]=quads
    return result


def root_points(geo,i,cache):
    n=geo.nodes[i];key=n['mesh']
    if key not in cache:
        v=geo.local_vertices(i)
        low=v[v[:,1]<=v[:,1].min()+.022]
        # Sample actual basal vertices nearest the centre plus both plan axes.
        # Avoid bounding box corners which may have no geometry.
        mid=low[:,[0,2]].mean(0)
        ids=[np.argmin(np.linalg.norm(low[:,[0,2]]-mid,axis=1))]
        for axis in (0,2):ids.extend((np.argmin(low[:,axis]),np.argmax(low[:,axis])))
        cache[key]=low[ids].copy()
    return geo.transform(i,cache[key])

def new_stats():
    return {k:dict(nodes=0,stations=0,uncovered=0,overLimit=0,worstGapM=0.,examples=[],noSampleNodes=[],waterOnlyStations=0) for k in LIMITS}

def record(row,i,name,gaps,pts,tol):
    row['nodes']+=1;row['stations']+=len(gaps)
    valid=np.isfinite(gaps);row['uncovered']+=int((~valid).sum())
    row['overLimit']+=int((gaps>tol).sum())
    if not len(gaps):row['noSampleNodes'].append(dict(node=i,name=name))
    if not valid.any():return
    j=np.nanargmax(gaps);v=float(gaps[j])
    row['worstGapM']=max(row['worstGapM'],round(v,4))
    if v>tol:
        row['examples'].append(dict(node=i,name=name,gapM=round(v,4),xyzM=pts[j].round(3).tolist()))
        row['examples'].sort(key=lambda x:-x['gapM']);del row['examples'][5:]

def evaluate(geo):
    surface=Surface(geo);water=Surface(geo,water=True);stats=new_stats();classes={};cache={};roots=[];skirts=[];moves=[]
    installed=installed_supports(geo)
    for i in geo.matrices:
        n=geo.nodes[i];category=classification(n)
        if not category:continue
        classes[category]=classes.get(category,0)+1
        if category in ('tree','shrub','groundcover','coastalGrass','parkingWheels'):
            roots.append((i,category,root_points(geo,i,cache)))
            continue
        for group,edges in edge_groups(geo,i,category):
            span=stations(edges,SAMPLE_STEP.get(group,1.5))
            gap,h=probe(surface,span,i)
            toe_xz=None
            if group=='stairs' and not np.isfinite(h).all():
                pts=np.stack((span[:,0],span.mean(1),span[:,1]),1)
                toe_xz=pts[:,:,[0,2]].copy();missing=~np.isfinite(h)
                toe_xz[missing],h[missing]=surface.coastal_toes(geo,toe_xz[missing])
                gap=pts[:,:,1]-h
                stats[group]['tidalApronStations']=int(missing.any(1).sum())
            finite=np.isfinite(gap).all(1)
            if not finite.all():
                missing=span[~finite];mids=missing.mean(1)
                wh=water.heights(mids[:,[0,2]])
                submerged=(wh-mids[:,1])>.025
                if submerged.any():
                    row=stats[group];row['waterOnlyStations']+=int(submerged.sum())
                    interval=np.array([np.min((wh-mids[:,1])[submerged]),np.max((wh-mids[:,1])[submerged])])
                    if 'waterOnlySubmergenceM' in row:
                        interval=[min(interval[0],row['waterOnlySubmergenceM'][0]),max(interval[1],row['waterOnlySubmergenceM'][1])]
                    row['waterOnlySubmergenceM']=np.round(interval,3).tolist()
            gapmax=np.full(len(span),np.nan)
            gapmax[finite]=gap[finite].max(1)
            tol=LIMITS[group];quads=installed.get((i,group),{})
            for j in np.flatnonzero((gapmax>tol) & bool(quads)):
                entry=quads.get(_key(span[j]))
                if entry is None:continue
                top,bot=entry
                if np.linalg.norm(top[0]-span[j,0])>.015:top=top[::-1];bot=bot[::-1]
                if np.max(np.abs(top-span[j]))>.015:continue
                bottom=np.array([bot[0,1],bot[:,1].mean(),bot[1,1]])
                grade=h[j]
                if np.max(abs(top[:,[0,2]]-bot[:,[0,2]]))>.001:
                    grade=surface.heights(np.stack((bot[0],bot.mean(0),bot[1]))[:,[0,2]],exclude=i)
                    if not np.isfinite(grade).all():continue
                gapmax[j]=max(0.,np.max(bottom-grade))
            record(stats[group],i,n['name'],gapmax,span.mean(1),tol)
            bad=np.flatnonzero(gapmax>tol)
            if len(bad):
                top=span[bad];bottom=top.copy()
                # Both toes penetrate grade, including any concave midpoint.
                if toe_xz is not None:
                    bottom[:,0,0]=toe_xz[bad,0,0];bottom[:,0,2]=toe_xz[bad,0,1]
                    bottom[:,1,0]=toe_xz[bad,2,0];bottom[:,1,2]=toe_xz[bad,2,1]
                adjust=np.maximum(0.,h[bad][:,[0,2]].mean(1)-h[bad,1])
                bottom[:,:,1]=np.minimum(top[:,:,1]-.018,h[bad][:,[0,2]]-adjust[:,None]-.085)
                skirts.append((i,group,np.stack((top[:,0],top[:,1],bottom[:,1],bottom[:,0]),axis=1)))
    if roots:
        positions=np.stack([q[2] for q in roots])
        heights=surface.heights(positions[:,:,[0,2]].reshape(-1,2)).reshape(-1,5)
        gaps=positions[:,:,1]-heights
        for (i,group,p),g in zip(roots,gaps):
            # A tuft, axle or trunk is unsupported only when ALL sampled roots
            # clear the grade. A single high corner on a sloping verge is normal.
            clearance=float(np.min(g))
            record(stats[group],i,geo.nodes[i]['name'],np.array([clearance]),p[:1],LIMITS[group])
            if group!='parkingWheels' and clearance>LIMITS[group]:
                moves.append((i,clearance+.014))
    return dict(triangles=len(surface.tri),candidateNodes=classes,categories=stats),skirts,moves

def ground_scene(scene):
    """Close measured exposed edges and seat unsupported plants on exported grade."""
    from qd_geometry import Shape,lin
    geo=Geometry(scene.doc,scene.raw)
    report,skirts,moves=evaluate(geo)
    for i,drop in moves:
        n=scene.doc['nodes'][i]
        # Plant instances are top-level nodes. Preserve full rotation and scale.
        if i not in scene.doc['scenes'][scene.doc.get('scene',0)]['nodes'] or 'matrix' in n:
            raise ValueError('Unsupported nested plant transform: '+n['name'])
        n['translation'][1]-=drop
    for i,group,quads in skirts:
        name=scene.doc['nodes'][i]['name']+' · 接地基脚'
        shape=Shape(name);colour=STONE.get(group,'#a39b8e')
        material_name='接地基脚 · '+colour
        shape.mesh('外沿基脚',quads.reshape(-1,3),np.arange(quads.size//3).reshape(-1,4),material_name)
        scene.node(name,shape=shape,kind='groundSupport',groundContactOwner=i,category=group)
        # New material only; original architecture and planted surfaces stay intact.
        idx=scene.colors[material_name];m=scene.doc['materials'][idx]
        m['pbrMetallicRoughness']['baseColorFactor']=[lin(int(colour[j:j+2],16)/255) for j in (1,3,5)]+[1.]
        m['pbrMetallicRoughness'].update(roughnessFactor=.98,metallicFactor=0.)
        m.setdefault('extensions',{})['KHR_materials_specular']={'specularFactor':0.}
    if skirts:
        used=scene.doc.setdefault('extensionsUsed',[])
        if 'KHR_materials_specular' not in used:used.append('KHR_materials_specular')
    return dict(verifiedGroundTriangles=report['triangles'],additionalSupportNodes=len(skirts),
                supportQuads=sum(len(q) for _,_,q in skirts),seatedPlants=len(moves))

