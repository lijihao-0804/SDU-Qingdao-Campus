"""Draped, low-growing spring flower cushions at the arena. Coordinates are metres, Y up."""
import math
from collections import defaultdict

import numpy as np
import mapbox_earcut
import shapely
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter
from scipy.spatial.transform import Rotation

from qd_geometry import Shape
from qd_spring_surfaces import add_image
from qd_terrain import Terrain


BED = "体育馆南弯 · 低矮玫红地被"
SOIL = "南弯裸土 · 枯草壤土"
PETALS = "南弯草花 · 五裂花冠"
EYES = "南弯草花 · 深红花眼"
STEMS = "南弯草花 · 分枝与花梗"
LEAVES = "南弯草花 · 对生针叶"
GRASS = "南弯花隙 · 春草与枯草"


def linear(rgb):
    x = np.asarray(rgb) / 255.
    return np.where(x < .04045, x / 12.92, ((x + .055) / 1.055) ** 2.4)


def normalise(v):
    length = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(length, 1.e-12)


def bind_colours(scene):
    for name in (PETALS, EYES, STEMS, LEAVES, GRASS, SOIL):
        material = scene.doc["materials"][scene.mat(name)]["pbrMetallicRoughness"]
        material.update(baseColorFactor=[1, 1, 1, 1], roughnessFactor=.91)


def sample(grid, x, z):
    """Interpolate using the same diagonal as the campus TIN."""
    u, v = (x - grid.x0) / grid.step, (z - grid.z0) / grid.step
    i = np.clip(np.floor(u).astype(int), 0, grid.heights.shape[1]-2)
    j = np.clip(np.floor(v).astype(int), 0, grid.heights.shape[0]-2)
    a, b = u-i, v-j
    h = grid.heights
    return np.where(a+b <= 1., h[j,i] + a*(h[j,i+1]-h[j,i]) + b*(h[j+1,i]-h[j,i]),
                    h[j+1,i+1] + (1-a)*(h[j+1,i]-h[j+1,i+1]) + (1-b)*(h[j,i+1]-h[j+1,i+1]))


def clipped_tin(xx,zz,region):
    # The campus land-cover triangulator discards sub-0.04 m² fragments. That
    # would discard most boundary faces on this 30 cm mesh and leave sawteeth.
    xz = np.stack((xx,zz),axis=-1).reshape(-1,2)
    ids = np.arange(xx.size).reshape(xx.shape)[:-1,:-1].ravel()
    w = xx.shape[1]
    corners = np.concatenate((ids[:,None]+[0,w,1], ids[:,None]+[w+1,1,w]))
    triangles = shapely.polygons(xz[corners])
    shapely.prepare(region)
    full = shapely.covers(region,triangles)
    edge = ~full & shapely.intersects(region,triangles)
    result = [xz[corners[full]]]
    def add(p):
        if p.geom_type=="Polygon" and p.area>1e-9:
            rings=[np.asarray(r.coords)[:-1] for r in (p.exterior,*p.interiors)]
            coords=np.concatenate(rings)
            face=mapbox_earcut.triangulate_float64(coords,np.cumsum([len(r) for r in rings],dtype=np.uint32))
            if len(face): result.append(coords[face.reshape(-1,3)[:,::-1]])
        elif hasattr(p,"geoms"):
            for part in p.geoms:add(part)
    for frag in shapely.intersection(triangles[edge],region):
        add(frag)
    return np.concatenate(result)


def cushions(site, terrain):
    grid = Terrain.__new__(Terrain)
    grid.step = site.grid.step / 5.
    x0,z0,x1,z1 = site.flowers.bounds
    grid.x0 = site.grid.x0 + grid.step*(math.floor((x0-site.grid.x0)/grid.step)-2)
    grid.z0 = site.grid.z0 + grid.step*(math.floor((z0-site.grid.z0)/grid.step)-2)
    xx,zz = np.meshgrid(np.arange(grid.x0,x1+3*grid.step,grid.step),
                        np.arange(grid.z0,z1+3*grid.step,grid.step))
    rng = np.random.default_rng(735111)
    def field(along, across):
        noise = gaussian_filter(rng.standard_normal(xx.shape), (along,across), mode="reflect")
        return (noise-noise.mean()) / max(noise.std(),.001)

    coarse = field(3.1,5.6)
    fine = field(1.05,1.46)
    edge = shapely.distance(shapely.points(xx,zz),site.flowers.boundary)
    # Clamp the blanket against openings. Tall hummocks meet in short, dark furrows.
    depth = np.clip(.102+.035*coarse+.034*fine+.012*field(.55,.93), .018,.189)
    grid.heights = sample(site.grid,xx,zz) + .033 + np.clip(edge/.42,0,1)*depth
    layer = Shape("体育馆南弯 · 随坡玫红花海")
    xz, inverse = np.unique(np.round(clipped_tin(xx,zz,site.flowers).reshape(-1,2),7),axis=0,return_inverse=True)
    vertices = np.column_stack((xz[:,0],sample(grid,*xz.T),xz[:,1]))
    faces = inverse.ravel().reshape(-1,3)
    # Weld shared vertices so the cushions round smoothly and the narrow shadows remain legible.
    triangles = vertices[faces]
    normal = np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    sums = np.zeros_like(vertices)
    for corner in range(3):
        np.add.at(sums,faces[:,corner],normal)
    layer.parts[BED] = [vertices,normalise(sums),faces.ravel().tolist()]
    x,y,z = vertices.T
    relief = y - sample(site.grid,x,z)
    blossom = np.clip((relief-.035)/.165,0,1)
    tint = np.column_stack((.49+.50*blossom, .59+.40*blossom, .51+.48*blossom))
    layer.vertex_tints = {BED:tint.tolist()}
    layer.uvs = {BED:np.column_stack((x*.48+z*.11+.12*np.sin(z*.65),
                                     z*.48-x*.11+.10*np.cos(x*.79))).tolist()}
    return layer, grid


def soil(scene, site, terrain):
    shape = Shape("体育馆花坡 · 缝隙与边缘裸土")
    # Bare earth is only visible at the ragged margins and in real breaks in the cover.
    access=site.drive.union(site.lower_walk).union(site.upper_path)
    exposed = site.flower_ground.buffer(.19).difference(access.buffer(.02))
    terrain.skin(shape,exposed,SOIL,.019)
    x,_,z = np.asarray(shape.parts[SOIL][0]).T
    ripple = np.sin(.9*x+.38*z)*.5 + np.sin(x*2.7-z*1.04)*.5
    colours = np.array([239,232,217])+ripple[:,None]*np.array([12,14,16])
    shape.vertex_tints = {SOIL:linear(colours).tolist()}
    shape.uvs = {SOIL:np.column_stack((x*.76+z*.13,z*.76-x*.13)).tolist()}
    scene.node(shape.name,shape=shape,kind="landscape",arenaPlantPart="exposedSoil")
    size=384
    rng=np.random.default_rng(611191)
    grit=rng.normal(0,13,(size,size))
    coarse=gaussian_filter(grit,9,mode="wrap")
    level=grit+21*coarse+3.3*gaussian_filter(grit,1.35,mode="wrap")
    ground=Image.fromarray(np.uint8(np.clip(np.array([149,120,82])+level[:,:,None],0,255)))
    draw=ImageDraw.Draw(ground)
    for k in range(1400):
        a=rng.uniform(0,math.tau); span=rng.uniform(1.4,12)
        u,v=rng.integers(0,size,2)
        draw.line((u,v,u+math.cos(a)*span,v+math.sin(a)*span),
                  fill=(175,153,104) if k%3 else (115,97,63))
    scene.doc["materials"][scene.mat(SOIL)]["pbrMetallicRoughness"]["baseColorTexture"]=add_image(
        scene,"南弯 · 露土与细枯茎",ground,"JPEG",True)


class Sprig:
    """A small reusable local mesh with shared vertices for curved petals and folded leaves."""
    def __init__(self):
        self.parts = defaultdict(lambda:[[],[],[]])

    def patch(self, material, vertices, triangles, colours):
        positions, indices, tints = self.parts[material]
        start = len(positions)
        positions.extend(vertices)
        indices.extend(tuple(start+j for j in face) for face in triangles)
        tints.extend(colours)

    def twig(self, a, b, radius, colour):
        a,b = np.asarray(a),np.asarray(b)
        direction = normalise(b-a)
        cross = normalise(np.cross(direction,[0,1,0]))
        up = np.cross(cross,direction)
        rim = radius*np.array([cross, -.5*cross+.866*up, -.5*cross-.866*up])
        self.patch(STEMS,np.concatenate((a+rim,b+rim*.70)),
                   [(j,(j+1)%3,j+3) for j in range(3)] +
                   [((j+1)%3,(j+1)%3+3,j+3) for j in range(3)], [colour]*6)

    def blade(self, material, base, angle, length, width, lift, colour):
        base = np.asarray(base)
        along=np.array([math.cos(angle),0,math.sin(angle)])*length
        side=np.array([-math.sin(angle),0,math.cos(angle)])*width
        mid=base+.46*along+[0,lift*.82,0]
        tip=base+along+[0,lift,0]
        self.patch(material,[base,mid-side,mid+[0,width*.7,0],mid+side,tip],
                   [(0,2,1),(0,3,2),(1,2,4),(2,3,4)],
                   np.clip([colour*.59,colour*.88,colour*1.10,colour*.91,colour],0,255))

    def flower(self, centre, radius, phase, colour, rng):
        # Five slightly notched lobes splay out from a depressed throat. The centre
        # and margins have their own heights, so an oblique camera sees a cupped profile.
        tilt=rng.uniform(-.33,.33,2)
        ring=[]
        for j in range(5):
            a=phase+j*math.tau/5
            forward=np.array([math.cos(a),0,math.sin(a)])*radius*rng.uniform(.92,1.09)
            across=np.array([-forward[2],0,forward[0]])
            def pt(u,v,h):
                delta=forward*u+across*v
                return centre+delta+[0,radius*h+tilt[0]*delta[0]+tilt[1]*delta[2],0]
            verts=[pt(.08,0,0),pt(.51,-.235,.19),pt(.89,-.28,.27),
                   pt(.99,-.13,.31),pt(.89,0,.24),pt(.98,.15,.28),pt(.86,.30,.22),pt(.51,.235,.14)]
            self.patch(PETALS,verts,[(0,2,1),(0,4,2),(2,4,3),(0,7,4),(4,7,6),(4,6,5)],
                       np.clip([colour*.55,colour*.86,colour*.99,colour*1.05,colour,
                                colour*1.04,colour*.99,colour*.89],0,255))
            ring.append(pt(.19,0,.065))
        # A dark throat sinks below the corolla. Its small warm centre rises
        # above the ring, so it is readable when looking obliquely up the bed.
        throat=centre+[0,-radius*.085,0]
        tips=[throat+np.array([math.cos(phase+j*math.tau/3)*radius*.086,
                               radius*(.20+.035*(j%2)),math.sin(phase+j*math.tau/3)*radius*.086])
              for j in range(3)]
        self.patch(EYES,[throat,*ring,*tips],
                   [(0,1+(j+1)%5,j+1) for j in range(5)]+[(0,7,6),(0,8,7),(0,6,8),(6,7,8)],
                   [[140,63,85],*([[110,32,69]]*5),[221,159,108],[234,175,119],[203,135,99]])


def prototype(seed, grass=False):
    rng=np.random.default_rng(seed)
    item=Sprig()
    if grass:
        for j in range(int(rng.integers(7,12))):
            root=[rng.uniform(-.014,.014),.001,rng.uniform(-.014,.014)]
            colour=np.array(rng.choice([[105,123,63],[141,147,78],[171,147,87],[166,153,105]]))
            item.blade(GRASS,root,j*2.4+rng.uniform(-.4,.4),rng.uniform(.027,.10),rng.uniform(.0023,.005),
                       rng.uniform(.045,.118),colour)
    else:
        root=np.array([-.06,-.017,0.])
        knee=np.array([-.005,.008,rng.uniform(-.013,.013)])
        wood=np.array([109,97,60]);leaf=np.array([88,120,61])
        item.twig(root,knee,.0019,wood)
        palette=[[217,38,141],[230,55,154],[205,39,135],[228,95,176],
                 [216,66,159],[235,114,188],[224,42,152],[235,69,160]]
        colour=np.array(palette[seed%len(palette)])
        for j in range(2 + int(seed%3==0)):
            a=(j-1)*1.27+rng.uniform(-.48,.48)
            endpoint=knee+[math.cos(a)*rng.uniform(.047,.103),rng.uniform(.012,.032),
                           math.sin(a)*rng.uniform(.046,.097)]
            item.twig(knee,endpoint,.0012,wood)
            for t in (.22,.57):
                for sign in (-1,1):
                    item.blade(LEAVES,knee+t*(endpoint-knee),a+sign*rng.uniform(.65,1.48),
                               rng.uniform(.020,.044),rng.uniform(.0025,.0045),
                               rng.uniform(.005,.024),leaf*rng.uniform(.83,1.19))
            item.flower(endpoint,rng.uniform(.013,.020),rng.uniform(0,math.tau),colour,rng)
    return {k:(np.asarray(v),np.asarray(t),linear(np.asarray(c))) for k,(v,t,c) in item.parts.items()}


def cluster(seed,grass=False):
    """A handful of rooted, outward-creeping shoots share one local origin."""
    rng=np.random.default_rng(seed)
    grouped=defaultdict(lambda:[[],[],[],0])
    count=1 if grass else 5+seed%4
    for k in range(count):
        a=math.tau*(k+rng.uniform(-.26,.26))/count
        radius=0 if grass else rng.uniform(.016,.093)
        centre=np.array([math.cos(a)*radius,0.,math.sin(a)*radius])
        co,si=math.cos(a),math.sin(a)
        rotation=np.array([[co,0,-si],[0,1,0],[si,0,co]])
        for mat,(v,faces,col) in prototype(seed*11+k,grass).items():
            acc=grouped[mat]
            acc[0].append(v@rotation.T+centre)
            acc[1].append(faces+acc[3]); acc[3]+=len(v)
            acc[2].append(col)
    shape=Shape(("南弯边草" if grass else "南弯匍匐花垫")+f" · {seed}")
    shape.vertex_tints={}
    for mat,(vv,ff,cc,_) in grouped.items():
        positions=np.concatenate(vv); faces=np.concatenate(ff)
        tr=positions[faces]
        normals=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0])
        sums=np.zeros_like(positions)
        for j in range(3):np.add.at(sums,faces[:,j],normals)
        shape.parts[mat]=[positions,normalise(sums),faces.ravel().tolist()]
        shape.vertex_tints[mat]=np.concatenate(cc).tolist()
    return shape,count


def scatter(scene, site, grid):
    rng=np.random.default_rng(349072)
    eye=np.array(site.xy(66,18.9))
    x0,z0,x1,z1=site.flowers.bounds
    n=int((x1-x0)*(z1-z0)*7.2)
    x=rng.uniform(x0,x1,n); z=rng.uniform(z0,z1,n)
    # A margin of 14 cm lets the outermost tips trail across the soil edge.
    inside=shapely.contains_xy(site.flowers.buffer(-.14),x,z)
    x,z=x[inside],z[inside]
    focus=np.exp(-((x-eye[0])**2+(z-eye[1])**2)/(2*6.4**2))
    depth=sample(grid,x,z)-sample(site.grid,x,z)
    bloom=np.clip((depth-.05)/.13,.08,1)
    keep=rng.random(len(x)) < (.45+6.7*focus)*(.37+.63*bloom)/7.2
    roots=np.column_stack((x[keep],z[keep]))
    access=site.drive.union(site.lower_walk).union(site.upper_path)
    domain=site.flower_ground.buffer(.15).difference(site.flowers.buffer(-.23)).difference(access.buffer(.16))
    n=int((x1-x0)*(z1-z0)*1.85)
    x=rng.uniform(x0,x1,n); z=rng.uniform(z0,z1,n)
    keep=shapely.contains_xy(domain,x,z)
    grass_roots=np.column_stack((x[keep],z[keep]))
    shoots=0
    for grass, points in ((False,roots),(True,grass_roots)):
        variants=5 if grass else 10
        patterns=[cluster(116+j,grass) for j in range(variants)]
        meshes=[scene.shape(shape) for shape,_ in patterns]
        x,z=points.T
        eps=.095 if grass else .14
        def sample_surface(x,z):
            return (np.where(shapely.contains_xy(site.flowers,x,z),sample(grid,x,z),sample(site.grid,x,z)+.019)
                    if grass else sample(grid,x,z))
        height=sample_surface(x,z)
        # Match each shared patch to the local tangent. A 28-cm chord avoids
        # an abrupt bend across a TIN diagonal while keeping the root at grade.
        slope_x=(sample_surface(x+eps,z)-sample_surface(x-eps,z))/(2*eps)
        slope_z=(sample_surface(x,z+eps)-sample_surface(x,z-eps))/(2*eps)
        angle=rng.uniform(0,math.tau,len(points)); c=np.cos(angle); s=np.sin(angle)
        up=normalise(np.column_stack((-slope_x,np.ones_like(x),-slope_z)))
        along=normalise(np.column_stack((c,c*slope_x+s*slope_z,s)))
        across=np.cross(along,up)
        quats=Rotation.from_matrix(np.stack((along,up,across),axis=-1)).as_quat()
        label="南弯花隙边草" if grass else "南弯匍匐花簇"
        for i,(px,pz) in enumerate(points):
            j=int(rng.integers(variants)); scale=float(rng.uniform(.82,1.26))
            scene.node(label+f" · {i+1:04d}",mesh=meshes[j],at=(float(px),float(height[i])-.002,float(pz)),
                       scale=(scale,scale,scale),kind="groundcover",arenaPlantPart="grasses" if grass else "shoots")
            scene.doc["nodes"][-1]["rotation"]=quats[i].tolist()
            if not grass:shoots+=patterns[j][1]
    return dict(floweringCushions=len(roots),floweringShoots=shoots,grassTufts=len(grass_roots))
