"""Compact, editable glTF assembly. Campus coordinates use metres and glTF Y up."""
from collections import defaultdict
from pathlib import Path
import json, math, struct, numpy as np

from contextvars import ContextVar
from qd_raw_arch_finishes import part_hint
record_components = ContextVar('record_components', default=False)

class Shape:
    def __init__(self, name):
        self.name=name
        self.components = defaultdict(list) if record_components.get() else None
        self.finish_hints=defaultdict(set)
        self.parts=defaultdict(lambda:[[],[],[]])
    def mesh(self,name,vertices,faces,material):
        self.finish_hints[material].add(part_hint(name))
        v,n,idx=self.parts[material]
        first=len(idx)//3
        pts=[tuple(p) for p in vertices]
        for face in faces:
            if len(face)<3: continue
            a,b,c=[pts[k] for k in face[:3]]
            u=[b[i]-a[i] for i in range(3)]; t=[c[i]-a[i] for i in range(3)]
            normal=(u[1]*t[2]-u[2]*t[1],u[2]*t[0]-u[0]*t[2],u[0]*t[1]-u[1]*t[0])
            length=math.sqrt(sum(q*q for q in normal))
            if length<1e-9:continue
            norm=tuple(q/length for q in normal); off=len(v)
            v.extend(pts[k] for k in face);n.extend([norm]*len(face))
            for i in range(1,len(face)-1):idx.extend((off,off+i,off+i+1))
        if self.components is not None and len(idx)//3 > first:
            groups=self.components[material]
            if groups and groups[-1][0]==name and groups[-1][2]==first:
                groups[-1][2]=len(idx)//3
            else:
                groups.append([name,first,len(idx)//3])
    def box(self,name,x,y,z,w,h,d,material,yaw=0):
        co,si=math.cos(yaw),math.sin(yaw)
        ps=[(x+a*w/2*co+c*d/2*si,y+b*h/2,z-a*w/2*si+c*d/2*co) for a,b,c in
            [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
        self.mesh(name,ps,[(0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(3,7,6,2),(0,1,5,4)],material)
    def cyl(self,name,x,y,z,r,h,material,sides=20):
        rim=[(math.cos(i*2*math.pi/sides)*r,math.sin(i*2*math.pi/sides)*r) for i in range(sides)]
        v=[(x+a,y+level,z+b) for level in (-h/2,h/2) for a,b in rim]
        faces=[(i,sides+i,sides+(i+1)%sides,(i+1)%sides) for i in range(sides)]
        faces+=[tuple(reversed(range(sides,2*sides))),tuple(range(sides))]
        self.mesh(name,v,faces,material)

def lin(c):return c/12.92 if c<.04045 else ((c+.055)/1.055)**2.4
GLAZING_ROUGHNESS={'glass':.22,'#405766':.22,'#3c6072':.21,'#465966':.23,
                   '#516671':.22,'#687b83':.24}
class CampusFile:
    def __init__(self):
        self.doc={'asset':{'version':'2.0','generator':'山东大学青岛校区 · 可维护场景'},'scene':0,'scenes':[{'nodes':[]}],
            'nodes':[],'meshes':[],'materials':[],'bufferViews':[],'accessors':[]}
        self.raw=bytearray();self.colors={};self.part_finishes={}
    def mat(self,key):
        if key in self.colors:return self.colors[key]
        specials={'water':('#659799',.32,0),'asphalt':('#74797b',.94,0),
                  'grass':('#a8be80',.98,0),'stone':('#c2b6a4',.85,0),'leaf':('#80965b',.88,0)}
        if str(key).lower() in GLAZING_ROUGHNESS:
            specials[key]=('#779ba7' if key=='glass' else key,GLAZING_ROUGHNESS[key.lower()],0.)
        val,rough,metal=specials.get(key,(key,.81,0))
        if not isinstance(val,str) or not val.startswith('#'):val='#bfbcae'
        if len(val)==4:val='#'+''.join(t*2 for t in val[1:])
        rgb=[lin(int(val[i:i+2],16)/255) for i in (1,3,5)]
        mat={'name':str(key),'pbrMetallicRoughness':{'baseColorFactor':rgb+[1],'metallicFactor':metal,'roughnessFactor':rough},'doubleSided':True}
        self.colors[key]=len(self.doc['materials']);self.doc['materials'].append(mat);return self.colors[key]
    def accessor(self,a,dtype,typ,comp,target):
        a=np.ascontiguousarray(a,dtype=dtype)
        while len(self.raw)%4:self.raw.append(0)
        view={'buffer':0,'byteOffset':len(self.raw),'byteLength':a.nbytes,'target':target}
        self.raw.extend(a.tobytes());vi=len(self.doc['bufferViews']);self.doc['bufferViews'].append(view)
        acc={'bufferView':vi,'componentType':comp,'count':len(a),'type':typ}
        if typ=='VEC3':acc.update(min=a.min(0).tolist(),max=a.max(0).tolist())
        ai=len(self.doc['accessors']);self.doc['accessors'].append(acc);return ai
    def shape(self,shape):
        ps=[]
        for color,(v,n,idx) in shape.parts.items():
            if not idx:continue
            code,dtype=(5123,'<u2') if len(v)<=65535 else (5125,'<u4')
            ps.append({'attributes':{'POSITION':self.accessor(v,'<f4','VEC3',5126,34962),'NORMAL':self.accessor(n,'<f4','VEC3',5126,34962)},
                       'indices':self.accessor(idx,dtype,'SCALAR',code,34963),'material':self.mat(color)})
            uvs=getattr(shape,'uvs',{}).get(color)
            if uvs:
                if len(uvs)!=len(v):raise ValueError((shape.name,'UV count'))
                ps[-1]['attributes']['TEXCOORD_0']=self.accessor(uvs,'<f4','VEC2',5126,34962)
            tints=getattr(shape,'vertex_tints',{}).get(color)
            if tints:
                if len(tints)!=len(v):raise ValueError((shape.name,'leaf tint count'))
                ps[-1]['attributes']['COLOR_0']=self.accessor(tints,'<f4','VEC3',5126,34962)
            if shape.components and shape.components.get(color):
                ps[-1]['extras']={'componentRanges':shape.components[color]}
            self.part_finishes[id(ps[-1])]=shape.finish_hints.get(color,set())
        if not ps:return None
        i=len(self.doc['meshes']);self.doc['meshes'].append({'name':shape.name,'primitives':ps});return i
    def node(self,name,shape=None,mesh=None,at=(0,0,0),yaw=0,scale=(1,1,1),**extra):
        if mesh is None:mesh=self.shape(shape)
        if mesh is None:return
        node={'name':name,'mesh':mesh,'translation':list(at),'rotation':[0,math.sin(yaw/2),0,math.cos(yaw/2)],'scale':list(scale),'extras':extra}
        self.doc['scenes'][0]['nodes'].append(len(self.doc['nodes']));self.doc['nodes'].append(node)
    def save(self,path):
        while len(self.raw)%4:self.raw.append(0)
        self.doc['buffers']=[{'byteLength':len(self.raw)}]
        js=json.dumps(self.doc,ensure_ascii=False,separators=(',',':')).encode()
        js+=b' '*((-len(js))%4)
        with Path(path).open('wb') as f:
            f.write(struct.pack('<4sII',b'glTF',2,28+len(js)+len(self.raw)));f.write(struct.pack('<I4s',len(js),b'JSON'));f.write(js)
            f.write(struct.pack('<I4s',len(self.raw),b'BIN\0'));f.write(self.raw)

