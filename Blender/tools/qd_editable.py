"""Transfer the authored college construction groups to reopened, editable Blender meshes."""
import json
import struct
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree


def group_academic_parts(doc, glb, objects, flag='refined'):
    raw=glb.read_bytes()
    start=28+struct.unpack_from('<I',raw,12)[0]
    def array(index):
        a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
        count={'VEC3':3,'SCALAR':1}[a['type']]
        dtype={5126:'<f4',5123:'<u2',5125:'<u4'}[a['componentType']]
        return np.frombuffer(raw,dtype,int(a['count']*count),start+v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,count)
    models={n['extras']['key']:doc['meshes'][n['mesh']] for n in doc['nodes'] if n.get('extras',{}).get(flag)}
    counts={}
    for o in objects:
        key=o.get('key','')
        if key not in models:continue
        geo=o.data
        fnum=len(geo.polygons);mat_slots=np.empty(fnum,np.int32);centres=np.empty(fnum*3,np.float32)
        geo.polygons.foreach_get('material_index',mat_slots);geo.polygons.foreach_get('center',centres)
        centres=centres.reshape(-1,3)
        codes=np.zeros(fnum,np.int32); names={};slot_by_source={m.get('源材质',m.name):i for i,m in enumerate(geo.materials)}
        for prim in models[key]['primitives']:
            ranges=prim.get('extras',{}).get('componentRanges',[])
            if not ranges:continue
            mat=doc['materials'][prim['material']]['name'];slot=slot_by_source[mat]
            imported=np.flatnonzero(mat_slots==slot)
            pos=array(prim['attributes']['POSITION']);idx=array(prim['indices']).reshape(-1,3)
            expected=pos[idx].mean(axis=1)[:,[0,2,1]];expected[:,1]*=-1
            lut=np.zeros(len(expected),np.int32)
            for title,a,b in ranges:
                number=names.setdefault(title,len(names)+1);lut[a:b]=number
            if len(imported)==len(expected) and np.allclose(centres[imported],expected,rtol=0,atol=.018):
                codes[imported]=lut
            else:
                distances,nearest=cKDTree(expected).query(centres[imported])
                valid=distances<.018
                codes[imported[valid]]=lut[nearest[valid]]
        face_data=geo.attributes.new('component_id','INT','FACE');face_data.data.foreach_set('value',codes)
        corners=np.empty(len(geo.loops),np.int32);geo.loops.foreach_get('vertex_index',corners)
        starts=np.empty(fnum,np.int32);geo.polygons.foreach_get('loop_start',starts)
        for title,num in names.items():
            faces=np.flatnonzero(codes==num)
            if len(faces):
                vertices=np.unique(corners[(starts[faces,None]+np.arange(3)).ravel()])
                o.vertex_groups.new(name=title).add(vertices.tolist(),1.,'REPLACE')
        o['构件面组']=json.dumps({str(v):k for k,v in names.items()},ensure_ascii=False)
        counts[key]=dict(groups=len(o.vertex_groups),faces=int(np.count_nonzero(codes)),total=fnum)
        if counts[key]['faces']<fnum*.94:
            raise ValueError(f'Incomplete component mapping on {o.name}: {counts[key]}')
    return counts

