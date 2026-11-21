"""Campus review viewpoints and the exposed land section in the focused view."""
from shapely import get_parts, segmentize
from qd_geometry import Shape

CLOSE_VIEWS=[
 ('contact-dining','曦园 · 坡侧基脚',[450.5,9.15,645.5],[464.,8.75,657.],52),
 ('contact-phoenix','凤凰居五号楼 · 转角基脚',[286.5,13.35,771.8],[274.,12.58,785.2],50),
 ('botanic-cherry','淦昌苑 · 枝头花序',[195.354,.774,113.628],[197.594,1.314,115.036],32),
 ('botanic-grass','育贤广场 · 草丛叶鞘',[31.750,-2.160,-146.306],[32.763,-2.302,-145.759],37),
 ('botanic-hedge','图书馆花园 · 方篱嫩梢',[131.326,-.860,29.133],[130.659,-1.206,27.172],39),
]

def add_views(catalog):
    for key,name,eye,target,fov in CLOSE_VIEWS:
        x,y,z=target
        catalog.append(dict(key=key,name=name,x=x,y=y,z=z,r=4,h=1,group='校园近景',
                            viewpoint=dict(eye=eye,target=target,fov=fov,minOrbitDistance=.38),
                            note='可环绕查看，滚轮或双指可调整距离。'))

def add_cut_edge(scene,terrain,domain,core,waterfront):
    # Show soil only where the section cuts land. The natural swash and the
    # coast-facing sides of piers stay open to the sea.
    frame=core.intersection(domain)
    cut=frame.boundary.difference(waterfront.shore.buffer(4))
    from qd_terrain import face
    shape=Shape('建模区断面 · 土层')
    material='建模区 · 土层断面'
    face(shape,frame,material,-32.)
    for line in get_parts(segmentize(cut,3)):
        if line.geom_type not in ('LineString','LinearRing'):continue
        pts=list(line.coords)
        for (x,z),(x1,z1) in zip(pts,pts[1:]):
            y=terrain.y(x,z)-.025
            y1=terrain.y(x1,z1)-.025
            shape.mesh('断面土层',[(x,y,z),(x1,y1,z1),(x1,-32,z1),(x,-32,z)],[(0,1,2,3)],material)
    scene.node(shape.name,shape=shape,kind='terrainCut',sceneRegion='cutEdge')
    slot=scene.colors[material]
    m=scene.doc['materials'][slot];m['doubleSided']=True
    m['pbrMetallicRoughness'].update(baseColorFactor=[.34,.25,.17,1.],roughnessFactor=1.,metallicFactor=0.)
    m.setdefault('extensions',{})['KHR_materials_specular']={'specularFactor':0.}
