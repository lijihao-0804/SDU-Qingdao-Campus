"""Assembly and close-up navigation for the photo-referenced academic blocks."""
import math
from shapely.affinity import translate
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
from qd_signage import emit


def modules():
    import qd_huiwen, qd_dizhou
    return (qd_huiwen, qd_dizhou)


def academic_index():
    by_id = {int(str(s['osm']).split('/')[-1]): (mod,s)
             for mod in modules() for s in mod.SPECS}
    if len(by_id) != 14:
        raise ValueError('Expected fourteen distinct academic blocks')
    return {'way/'+str(i): entry for i,entry in by_id.items()}


def camera_view(row, v, terrain, footprint, other_buildings, h):
    x,z=row['center']
    dx,dy,dz=v['target']
    nx,nz=v['normal']
    length=math.hypot(nx,nz)
    nx,nz=nx/length,nz/length
    x0,z0=x+dx,z+dz
    # Anchor stairs at the entrance, where people need to meet the ground plane.
    base=terrain.y(x0+5*nx,z0+5*nz)+.05
    target=[x0,base+dy,z0]
    poses={}
    # Fit a human-height entrance view in front of the public door. Reduce the
    # viewing distance when an opposing courtyard wing breaks the line of sight.
    def clear(x1,z1):
        ray=LineString([(x0+nx*1.4,z0+nz*1.4),(x1,z1)])
        return not other_buildings.intersects(ray) and footprint.intersection(ray).length<.3
    for dist in (17,15,13,11,9,7,5):
        x1,z1=x0+nx*dist,z0+nz*dist
        if clear(x1,z1):break
    poses['entrance']=dict(eye=[x1,terrain.y(x1,z1)+1.7,z1],target=target,fov=48)
    size=max(footprint.bounds[2]-footprint.bounds[0],footprint.bounds[3]-footprint.bounds[1])
    # A moderately elevated three-quarter view shows the entrance and the wings.
    side=.30
    poses['facade']=dict(eye=[x+(nx+nz*side)*size*1.03,base+h+.28*size,
                              z+(nz-nx*side)*size*1.03],target=[x,base+.46*h,z],fov=42)
    poses['roof']=dict(eye=[x+(nx*.53-nz*.62)*size,base+size*1.24,
                            z+(nz*.53+nx*.62)*size],target=[x,base+h*.52,z],fov=48)
    # Keep a small Z offset so orbit controls also preserve a stable north-up nadir.
    poses['roof_plan']=dict(eye=[x,base+h+size*1.53,z+.04],target=[x,base+h-.50,z],fov=42)
    poses['roof_edge']=dict(eye=[x+(nx+.36*nz)*size*.70,base+h+size*.19,
                                  z+(nz-.36*nx)*size*.70],target=[x,base+h-1.15,z],fov=53)
    return base,poses,[nx,nz]


def add(scene, mod, spec, row, footprint, blockers, terrain, catalog, records, corridors):
    x,z=row['center']; key=spec['key']
    local=translate(footprint,-x,-z)
    from qd_geometry import record_components
    token=record_components.set(True)
    try:
        shape,h=mod.build(dict(row),local)
    finally:
        record_components.reset(token)
    if not shape.parts:raise ValueError(key)
    v=mod.VIEWS[key]
    base,views,normal=camera_view(row,v,terrain,footprint,blockers,h)
    name=spec['name']
    descriptions={'会文北楼':'长翼沿广场展开，观察凹进的中央窗带、侧翼与红瓦屋脊。',
                  '会文南楼':'长翼和分段坡屋顶围合会文广场南侧；南向入口参照工程记录。',
                  '淦昌苑C座':'海洋研究院的横牌位于入口左侧粗石墙上。','淦昌苑E座':'双圆柱支撑石材门框。左侧是环境科学与工程学院横牌，右侧是楼座竖牌。'}
    label=spec.get('note') or spec.get('caption') or descriptions.get(name) or '临院门廊与通高窗带采用石材线脚，红瓦坡顶围合平屋面。'
    scene.node(name,shape=shape,at=(x,base,z),kind='building',key=key,refined=True)
    emit(scene,shape,(x,base,z),records)
    aliases=set()
    for a in [row.get('group_name'),row.get('name'),*spec.get('aliases',()),*spec.get('residents',())]:
        if a and a!=name:
            aliases.add(a.replace('环境工程与科学学院','环境科学与工程学院'))
    if '微生物国家重点实验室' in aliases:
        aliases.remove('微生物国家重点实验室')
        aliases.add('微生物改造技术全国重点实验室')
    catalog.append(dict(key=key,name=name,x=x,y=base,z=z,h=h,
                        r=max(local.bounds[2]-local.bounds[0],local.bounds[3]-local.bounds[1])/2,
                        aliases=sorted(aliases),note=label,group='学院楼',views=views,normal=normal))
    door=views['entrance']['target'];eye=views['entrance']['eye']
    corridors.append(LineString([(door[0],door[2]),(eye[0],eye[2])]).buffer(5.2))

