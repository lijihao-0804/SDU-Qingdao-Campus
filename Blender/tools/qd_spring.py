"""Spring specimens, anchored to photographed campus sectors in data/spring_sources.json.

Positions are in the campus X-east/Z-south metre grid. North sector parcels and all
individual plants are interpretive samples. The per-site camera reads the same
graded terrain as the scene. All repeated plants reuse non-textured native meshes.
"""
from collections import Counter
from dataclasses import dataclass
import math
import random

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from qd_geometry import Shape


@dataclass(frozen=True)
class Site:
    key: str
    title: str
    polygon: tuple
    spacing: tuple
    count: int
    species: tuple
    preferred: tuple     # camera subject X/Z, then eye offset X/Y/Z and focal angle
    note: str
    seed: int


SITES = (
    Site('spring_arena_orchard', '宋君复体育馆西侧果树林',
         ((-325,735),(-294,686),(-228,695),(-223,777),(-259,800),(-327,779)),
         (8.1,8.9), 63, ('cherry','cherry','pear','pear','cherry','chestnut','crabapple','chestnut'),
         (-278,740,-13,2.65,6.3,49),
         '体育馆西侧栽有樱桃、秋月梨、板栗和垂丝海棠。可在花枝之间望见白色体育建筑。树位为实景绿地内的代表性取样。', 31025),
    Site('spring_huagang_grove', '华岗苑西侧果树林',
         ((-171,53),(-143,53),(-139,74),(-143,113),(-169,117),(-174,83)),
         (8.6,9.0), 10, ('apricot','chestnut','apricot','chestnut','apricot'),
         (-158,80,-10,2.05,6.4,49),
         '2026年春，华岗苑西侧树林与校友林合计接收28株杏树与板栗；照片可见修枝后的树冠和木撑。这里呈现西侧林的一小段，分区株数及株位待实测。', 60407),
    Site('spring_north_cherries', '北区樱花林（片区示意）',
         ((102,-1196),(131,-1210),(187,-1202),(209,-1171),(194,-1124),(148,-1117),(111,-1142)),
         (7.3,7.7), 65, ('sakura','sakura','sakuraWhite','sakura','sakuraWhite'),
         (154,-1167,-8.8,3.2,15,48),
         '校内观察者在北区五千多株樱花中认出四株郁金樱。普通樱花留出疏密变化，浅绿郁金樱仅作单株展示。公开资料只定位到北区，林缘与树位均为示意。', 30426),
    Site('spring_yuehai_walk', '阅海居1号楼花带',
         ((33.1,-1022.1),(43.8,-1022.1),(44.0,-973.0),(33.4,-973.0)),
         (6.2,6.2), 7, ('streetWhite',),
         (38.55,-989.7,8.25,3.65,-17.0,48),
         '校区融媒体实景中，阅海居1号楼旁有沿路开放的粉白花树。取一段有树冠空间的绿带呈现，具体树种、株数及拍摄方位未见图注。', 50408),
    Site('spring_student_farm', '大学生实验农场·青青果园（片区示意）',
         ((-208,-1046),(-196,-1054),(-174,-1049),(-169,-1024),(-184,-1016),(-207,-1025)),
         (8.0,8.0), 6, ('peach',),
         (-190,-1036,-7.2,2.45,9.6,49),
         '青青果园是法学院在北区实验农场的四块劳动园地之一。以桃树和成行的低矮蓝莓表现这块小园，公开照片未提供其测量坐标。', 40506),
)


def _domain(data):
    return Polygon(data['boundary']).buffer(0)


def planted_extent(data):
    """Reserve only these four finite patches when drawing the older tree layer."""
    return unary_union([Polygon(s.polygon) for s in SITES]).intersection(_domain(data))


@dataclass(frozen=True)
class TreeForm:
    name: str
    stem: float
    spread: float
    rise: float
    droop: float
    flowers: tuple
    leaves: tuple
    bloom: float


WHITE = ('#f5eee1','#ebe3d8','#fff7ea')
PINK = ('#e4a7b0','#eec1c7','#f2d1ce')
LEAF = ('#91a361','#a7ae69','#718651')
BRONZE = ('#a89868','#aa8665','#8a965c')
FORMS = {
    'cherry': TreeForm('樱桃',1.20,1.30,1.40,.07,('#e4d4d2','#f0e3df','#f2e9dd'),LEAF,.83),
    'pear': TreeForm('秋月梨',1.40,1.16,1.72,-.05,WHITE,LEAF,.92),
    'crabapple': TreeForm('垂丝海棠',1.10,1.37,1.48,.38,('#cb7d91','#dd99ab','#eab5bd'),BRONZE,.89),
    'apricot': TreeForm('杏',1.46,1.55,1.48,.08,('#f0d8d4','#e7c5c6','#f4e4da'),BRONZE,.62),
    'chestnut': TreeForm('板栗',1.30,1.32,1.70,-.09,(),('#91a363','#abb175','#849550'),0),
    'sakura': TreeForm('观赏樱花',1.58,1.82,1.70,.18,PINK,BRONZE,.93),
    'sakuraWhite': TreeForm('淡色观赏樱花',1.55,1.71,1.73,.10,('#e6c7cc','#f1dcda','#f6e8e1'),LEAF,.90),
    'ukon': TreeForm('郁金樱',1.54,1.63,1.65,.14,('#c5ca9b','#d7d5ad','#d6c7af'),BRONZE,.88),
    'streetWhite': TreeForm('粉白春花树（种未定）',1.62,1.33,1.68,.08,('#ebe0df','#f1e6e1','#e4ccd0'),LEAF,.93),
    'peach': TreeForm('桃',1.04,1.43,1.42,.03,('#dc99ab','#e8b0bc','#ecc4c7'),BRONZE,.86),
    'blueberry': TreeForm('蓝莓',.12,.50,.67,.18,('#e4dfc9','#ded9c6','#ede8db'),('#849366','#819768','#9baa73'),.45),
}


def _combined(shape, material, pts, normals, idx):
    vert, norm, indices = shape.parts[material]
    start = len(vert)
    vert.extend(pts)
    norm.extend(normals)
    indices.extend(start+i for i in idx)


def _normal(a):
    length=math.sqrt(sum(v*v for v in a))
    return tuple(v/max(length,1.e-8) for v in a)


def _twig(shape,p,q,a,b,material):
    direction=_normal(tuple(q[i]-p[i] for i in range(3)))
    side=_normal((direction[1],-direction[0],0)) if abs(direction[2])<.97 else (1,0,0)
    dx,dy,dz=direction
    sx,sy,sz=side
    second=(dy*sz-dz*sy,dz*sx-dx*sz,dx*sy-dy*sx)
    substantial = a>.05 and material in ('#77756e','#c7c7bc','#725c56','#715e50')
    steps=10 if substantial else 6 if a>.06 else 4
    ns=[tuple(side[i]*math.cos(j*math.tau/steps)+second[i]*math.sin(j*math.tau/steps)
              for i in range(3)) for j in range(steps)]
    # A slight asymmetric branch collar swells near the insertion and then
    # tapers. It is confined to scaffold wood, avoiding busy ridges on twigs.
    rings=[(p,a,False)]
    if substantial:
        rings.append((tuple(p[i]+.18*(q[i]-p[i]) for i in range(3)),a*.82+b*.18,True))
    rings.append((q,b,False))
    pts=[tuple(pos[i]+radius*(1.+(.085+.055*math.cos(j*math.tau/steps)) if collar else 1.)*n[i]
               for i in range(3)) for pos,radius,collar in rings for j,n in enumerate(ns)]
    indices=[]
    for level in range(len(rings)-1):
        for j in range(steps):
            k=(j+1)%steps
            indices.extend(level*steps+i for i in (j,k,steps+k,j,steps+k,steps+j))
    _combined(shape,material,pts,ns*len(rings),indices)


def _move(p,angle,distance,dy):
    return (p[0]+math.cos(angle)*distance,p[1]+dy,p[2]+math.sin(angle)*distance)


def _flower(shape,c,size,angle,tilt,material,phase,deep=False):
    # A single fluted corolla: ten scalloped points, back turned in, with warm receptacle.
    vx=(math.cos(angle),0,math.sin(angle))
    vy=(-math.sin(angle)*math.cos(tilt),math.sin(tilt),math.cos(angle)*math.cos(tilt))
    n=(-math.sin(angle)*math.sin(tilt),-math.cos(tilt),math.cos(angle)*math.sin(tilt))
    n=tuple(-k for k in n)
    pts=[c]; normals=[n]; idx=[]
    for i in range(10):
        t=i*math.pi/5+phase
        r=size*(1 if i%2==0 else .63)
        height=size*(.25 if i%2==0 else .13) * (1.7 if deep else 1.)
        pts.append(tuple(c[k]+r*math.cos(t)*vx[k]+r*math.sin(t)*vy[k]+height*n[k] for k in range(3)))
        normals.append(_normal(tuple(n[k]+.22*(math.cos(t)*vx[k]+math.sin(t)*vy[k]) for k in range(3))))
        idx.extend((0,(i+1)%10+1,i+1))
    _combined(shape,material,pts,normals,idx)


def _cluster(shape,c,r,material,rng):
    # A rounded spray with separate lobes; visible through the gaps between spurs.
    phase=rng.random()*math.tau; squash=rng.uniform(.62,.89)
    pts=[(c[0],c[1]+r*.70,c[2]),(c[0],c[1]-r*.57,c[2])]
    normals=[(0,1,0),(0,-1,0)]; idx=[]
    for i in range(9):
        angle=phase+i*math.tau/9
        rr=r*(rng.uniform(.87,1.14) if i%3 else rng.uniform(.57,.78))
        hh=rng.uniform(-.12,.25)
        pts.append((c[0]+math.cos(angle)*rr,c[1]+r*hh,c[2]+math.sin(angle)*rr*squash))
        normals.append(_normal((math.cos(angle),hh,math.sin(angle)/squash)))
        j=2+i;k=2+(i+1)%9;idx.extend((0,k,j,1,j,k))
    _combined(shape,material,pts,normals,idx)


def _leaf(shape,c,angle,length,width,rise,material):
    dx,dz=math.cos(angle),math.sin(angle)
    tip=_move(c,angle,length,rise)
    mid=_move(c,angle,length*.57,rise*.58)
    pts=(c,(mid[0]-dz*width,mid[1]-.018,mid[2]+dx*width),
         (mid[0],mid[1]+width*.40,mid[2]),
         (mid[0]+dz*width,mid[1]-.018,mid[2]-dx*width),tip)
    normals=((0,1,0),(-dz*.35,.94,dx*.35),(0,1,0),(dz*.35,.94,-dx*.35),(0,1,0))
    _combined(shape,material,pts,normals,(0,1,2,2,1,4,0,2,3,3,2,4))


def _spray(shape,form,c,angle,rng,small=False):
    factor=.48 if small else 1.
    flowered=bool(form.flowers) and rng.random()<form.bloom
    if flowered:
        if small:  # drooping, urn-shaped blueberry flowers under the leaves
            for k in range(4):
                a=angle+(k-1.5)*.53;pos=_move(c,a,rng.uniform(.036,.075),-.03)
                base=(pos[0],pos[1]-.03,pos[2])
                _cluster(shape,base,.028,rng.choice(form.flowers),rng)
        else:
            mat=rng.choice(form.flowers)
            radius=rng.uniform(.096,.162)
            _cluster(shape,c,radius,mat,rng)
            for i in range(4):
                a=angle+i*1.8
                pos=_move(c,a,radius*rng.uniform(.62,1.14),radius*rng.uniform(-.07,.67))
                _flower(shape,pos,.036+rng.random()*.025,a,rng.uniform(.25,1.),rng.choice(form.flowers),rng.random(),True)
    count=rng.randrange(3,6) if not flowered else rng.randrange(1,3)
    for i in range(count):
        a=angle+i*2.14+rng.uniform(-.28,.28)
        length=rng.uniform(.12,.26)*factor*(1.55 if not form.flowers else 1)
        _leaf(shape,c,a,length,length*rng.uniform(.20,.29),rng.uniform(-.05,.105)*factor,rng.choice(form.leaves))
    if not flowered and not form.flowers:
        _cluster(shape,c,.13*factor,rng.choice(form.leaves),rng)


def _berry_tree(species,variant):
    form=FORMS[species]; small=species=='blueberry'
    rng=random.Random(4789+list(FORMS).index(species)*701+variant*39)
    shape=Shape(form.name+' · 春季枝冠 '+str(variant+1))
    bark='#685749' if small else ('#705b51' if species in ('sakura','sakuraWhite','ukon','peach') else '#73634f')
    twigs='#887260'
    base=(0.,-.10,0.)
    bend=(rng.uniform(-.10,.10),form.stem*.55,rng.uniform(-.11,.11))
    fork=(bend[0]+rng.uniform(-.12,.12),form.stem,bend[2]+rng.uniform(-.11,.11))
    thick=.032 if small else (.14 if species in ('sakura','sakuraWhite','ukon','apricot') else .107)
    _twig(shape,base,bend,thick,thick*.88,bark);_twig(shape,bend,fork,thick*.88,thick*.65,bark)
    arms=6 if small or species in ('sakura','sakuraWhite','ukon') else 5
    origin=rng.random()*math.tau
    for i in range(arms):
        ang=origin+i*math.tau/arms+rng.uniform(-.22,.22)
        stock=rng.uniform(.76,1.) if not small else rng.uniform(.2,.97)
        start=tuple(bend[t]+(fork[t]-bend[t])*stock for t in range(3))
        push=form.spread*rng.uniform(.38,.60)
        knot=_move(start,ang-.08,push,form.rise*rng.uniform(.44,.65))
        end=_move(knot,ang+.12,push*.55,form.rise*rng.uniform(.16,.38))
        _twig(shape,start,knot,thick*.66,thick*.41,bark)
        _twig(shape,knot,end,thick*.42,thick*.26,bark)
        # Lateral bearing wood starts below the terminal forks. Several distinct
        # tiers keep the blossoms on branches through the canopy as well as at its rim.
        tiers=2 if species in ('sakura','sakuraWhite','ukon','crabapple','streetWhite') else 1
        for level in range(tiers):
            frac=.47+.29*level+rng.uniform(-.065,.065)
            joint=tuple(start[t]+(knot[t]-start[t])*frac for t in range(3))
            angle=ang+(1 if (i+level)%2 else -1)*rng.uniform(.66,1.2)
            wrist=_move(joint,angle,form.spread*rng.uniform(.39,.59),form.rise*rng.uniform(.17,.32))
            _twig(shape,joint,wrist,thick*.23,thick*.13,twigs)
            for offset in (-.52,.13,.65):
                a=angle+offset
                q=_move(wrist,a,form.spread*rng.uniform(.27,.46),form.rise*rng.uniform(-.045,.19)-form.droop*.32)
                _twig(shape,wrist,q,thick*.125,thick*.038,twigs)
                for f in (.36,.68,1):
                    spur=tuple(wrist[t]+(q[t]-wrist[t])*f for t in range(3))
                    _spray(shape,form,spur,a+rng.uniform(-.55,.55),rng,small)
        for j in range(3):
            a=ang+(j-1)*.76+rng.uniform(-.23,.23)
            root=knot if j!=1 else end
            shoulder=_move(root,a,form.spread*rng.uniform(.24,.44),form.rise*rng.uniform(.22,.47))
            _twig(shape,root,shoulder,thick*.28,thick*.14,twigs)
            for k in range(3):
                aa=a+(k-1)*.76+rng.uniform(-.23,.2)
                tip=_move(shoulder,aa,form.spread*rng.uniform(.19,.37),
                          form.rise*rng.uniform(.02,.29)-form.droop*(.5 if small else 1))
                _twig(shape,shoulder,tip,thick*.14,thick*.05,twigs)
                for frac in (.26,.68,1.):
                    spur=tuple(shoulder[t]+(tip[t]-shoulder[t])*frac for t in range(3))
                    direction=aa+rng.choice((-1,1))*rng.uniform(.34,.99)
                    sprig=_move(spur,direction,rng.uniform(.07,.21)*(.42 if small else 1),
                                rng.uniform(.03,.15)*(.43 if small else 1))
                    _twig(shape,spur,sprig,thick*.064,thick*.025,twigs)
                    _spray(shape,form,sprig,direction,rng,small)
    if species in ('apricot','chestnut') and variant==0:
        for i in range(3):
            angle=.7+i*math.tau/3
            foot=_move(base,angle,.61,0)
            rest=_move(fork,angle,.06,-.14)
            _twig(shape,foot,rest,.034,.027,'#9c896a')
    return shape


# Survey/planning envelopes used by the already approved layouts and camera targets.
# Each new editable mesh is fitted to its corresponding canopy radius and top.
ENVELOPES={
    'cherry':((2.448377461516584,3.3452111248428844),(2.478410794024404,3.7233637154795765)),
    'pear':((2.160392048739677,4.147571257304656),(2.2545932782253897,4.093523215136766)),
    'crabapple':((2.2853360551492394,3.1587787410468846),(2.6370232562948197,3.16228283397035)),
    'apricot':((2.5038511576854967,3.9858226747098264),(2.5798421740225526,3.577650711428126)),
    'chestnut':((2.5750015493486424,4.079465386878367),(2.3383494892346945,4.006356187719336)),
    'sakura':((3.080836769073645,4.42678227160439),(3.170762561783805,4.36741361680818)),
    'sakuraWhite':((2.946901831152821,4.234625803245608),(2.9778679687524314,4.161286317987618)),
    'ukon':((2.76696866538079,4.000339566382978),(2.9405770149212387,3.904718900625911)),
    'streetWhite':((2.4969279574646306,4.21224008037317),(2.2916028762989944,3.9837876711538436)),
    'peach':((2.3678911032447343,3.3179572133626243),(2.546376616476061,3.2201432412760496)),
}
BLOSSOM='#f6eee7'


def _blossom_texture(scene):
    """Four alpha-cut trusses. Each flower bears five independently drawn notched petals."""
    from PIL import Image,ImageDraw
    tile=512
    atlas=Image.new('RGBA',(tile*2,tile*2),(248,238,234,0))
    for v in range(4):
        rng=random.Random(9440+v)
        im=Image.new('RGBA',(tile,tile),(248,239,235,0));d=ImageDraw.Draw(im)
        scope=[(.28,.35,.174),(.59,.22,.155),(.78,.47,.16),(.42,.56,.169),(.61,.69,.119)]
        if v==1:scope=scope[:4]
        if v==2:scope.extend([(.19,.65,.11),(.81,.20,.102)])
        for x,y,size in scope:
            qx=(x+rng.uniform(-.033,.033))*tile;qy=(y+rng.uniform(-.030,.030))*tile
            d.line(((.50*tile,.99*tile),(.49*tile,.76*tile),(qx,qy)),fill=(177,156,119,250),width=6)
        for x,y,size in scope:
            cx=x*tile;cy=y*tile;r=size*tile
            rotation=rng.uniform(0,math.tau);squash=rng.uniform(.68,1.)
            for j in range(5):
                a=rotation+j*math.tau/5
                # Petals broaden away from the base; two rounded lobes flank a shallow notch.
                curve=((0.,0.),(.26,-.22),(.58,-.41),(.83,-.43),(.97,-.33),(1.,-.16),
                       (.90,0.),(1.,.14),(.97,.31),(.82,.43),(.57,.43),(.26,.23))
                pts=[(cx+r*(u*math.cos(a)-b*math.sin(a)),cy+r*squash*(u*math.sin(a)+b*math.cos(a))) for u,b in curve]
                shade=rng.randint(233,254)
                d.polygon(pts,fill=(min(255,shade+4),shade,min(255,shade+1),255))
                def inside(u,b):
                    return (cx+r*(u*math.cos(a)-b*math.sin(a)),cy+r*squash*(u*math.sin(a)+b*math.cos(a)))
                d.polygon([inside(u,b) for u,b in ((0,0),(.37,-.19),(.66,-.10),(.45,-.02),(.24,.09))],
                          fill=(min(255,shade+1),shade-12,shade-7,255))
                for bend in (-.16,0.,.16):
                    d.line([inside(.15,.01),inside(.41,bend*.35),inside(.73,bend)],
                           fill=(226,200,195,250),width=2)
            d.ellipse((cx-r*.16,cy-r*.14,cx+r*.16,cy+r*.14),fill=(229,191,120,255))
            for j in range(8):
                a=rotation+j*math.tau/8
                px,py=cx+r*.215*math.cos(a),cy+r*.215*math.sin(a)*squash
                d.line([(cx,cy),(px,py)],fill=(213,175,119,255),width=2)
                d.ellipse((px-2.3,py-2.3,px+2.3,py+2.3),fill=(241,209,140,255))
        atlas.paste(im,(v%2*tile,v//2*tile))
    # Transparently stored in glTF so the same five-petal cutouts reach Blender and the browser.
    from qd_spring_surfaces import add_image
    tex=add_image(scene,'春日花序 · 五瓣花与细花梗',atlas,'PNG',False)
    mat=scene.doc['materials'][scene.colors[BLOSSOM]]
    mat.update(alphaMode='MASK',alphaCutoff=.32,doubleSided=True)
    mat['pbrMetallicRoughness'].update(baseColorFactor=[1,1,1,1],baseColorTexture=tex,roughnessFactor=.87)


def _truss(shape,p,angle,rise,size,tint,rng):
    """Two slightly folded planes keep each small cluster directional in space."""
    from qd_geometry import lin
    width=size*rng.uniform(.68,.94)
    side=(math.cos(angle),0.,math.sin(angle))
    forward=(-math.sin(angle),0.,math.cos(angle))
    height=size*rng.uniform(.85,1.16)
    ex,ey=math.cos(rise),math.sin(rise)
    axis=(ex*forward[0],ey,ex*forward[2]);surface=(-ey*forward[0],ex,-ey*forward[2])
    pts=[]
    for v in (0.,1.):
        for u in (-.5,0.,.5):
            bulge=.085*width*(1-abs(u)*2)
            pts.append(tuple(p[k]+side[k]*width*u+axis[k]*height*v+surface[k]*bulge for k in range(3)))
    vv,nn,ii=shape.parts[BLOSSOM];off=len(vv)
    vv.extend(pts);nn.extend([surface]*6)
    ii.extend(off+i for i in (0,3,4,0,4,1,1,4,5,1,5,2))
    which=rng.randrange(4);x0=which%2*.5;y0=which//2*.5
    uv=shape.uvs[BLOSSOM]
    for v in (.992,.008):
        for u in (.008,.5,.992):uv.append((x0+u*.5,y0+v*.5))
    rgb=tuple(lin(int(tint[i:i+2],16)/255) for i in (1,3,5))
    shape.vertex_tints[BLOSSOM].extend([rgb]*6)


def _curve(a,b,f):
    return tuple(a[k]+(b[k]-a[k])*f for k in range(3))


def _terminal(sh,form,p,angle,length,rise,rng,blooming):
    """A 5–10 mm-diameter fruiting twig carries trusses at several nodes down its length."""
    kink=rng.uniform(-.36,.36)
    mid=_move(p,angle+kink,length*.52,rise*.57+rng.uniform(-.025,.025))
    tip=_move(mid,angle-kink*.63,length*.5,rise*.43)
    _twig(sh,p,mid,rng.uniform(.0036,.0052),.0032,'#82685a')
    _twig(sh,mid,tip,.0033,.0017,'#967d69')
    count=rng.randrange(5,9)
    flush=rng.random()
    for j in range(count):
        f=(j+rng.uniform(.27,.77))/count
        node=_curve(p,mid,2*f) if f<.5 else _curve(mid,tip,2*f-1)
        direction=angle+(-1 if j%2==0 else 1)*rng.uniform(.48,1.6)
        sprig=_move(node,direction,rng.uniform(.025,.075),rng.uniform(-.018,.043))
        if blooming and rng.random()<form.bloom*.91:
            _twig(sh,node,sprig,.0024,.00125,'#987e69')
            _truss(sh,sprig,direction+rng.uniform(-.78,.78),rng.uniform(.26,1.50),
                   rng.uniform(.128,.215),rng.choice(form.flowers),rng)
            if flush>.49 and rng.random()<.47:
                _truss(sh,sprig,direction+1.1,rng.uniform(.18,1.50),rng.uniform(.10,.15),rng.choice(form.flowers),rng)
        if not blooming or (flush>.59 and j%2==0) or rng.random()<.19:
            for k in range(rng.randrange(1,4)):
                a=direction+(k-1)*.72
                length=rng.uniform(.085,.173)*(1.20 if not form.flowers else 1.)
                _leaf(sh,sprig,a,length,length*rng.uniform(.19,.29),rng.uniform(-.048,.075),rng.choice(form.leaves))


def _fit(shape,radius,height):
    pts=[v for vs,_,_ in shape.parts.values() for v in vs]
    horizontal=radius/max(math.hypot(v[0],v[2]) for v in pts)
    vertical=height/max(v[1] for v in pts)
    for vs,normals,_ in shape.parts.values():
        vs[:]=[(v[0]*horizontal,v[1]*vertical,v[2]*horizontal) for v in vs]
        normals[:]=[_normal((n[0]/horizontal,n[1]/vertical,n[2]/horizontal)) for n in normals]


def _tree(species,variant):
    if species=='blueberry':
        return _berry_tree(species,variant)
    from collections import defaultdict
    form=FORMS[species];r,h=ENVELOPES[species][variant]
    rng=random.Random(12013+list(FORMS).index(species)*193+variant*1421)
    sh=Shape(form.name+' · 错层枝梢 '+str(variant+1))
    sh.uvs=defaultdict(list);sh.vertex_tints=defaultdict(list)
    bark='#715e50' if species in ('pear','chestnut','apricot') else '#725c56'
    wood='#846c5d'
    phi=rng.uniform(0,math.tau)
    base=(0.,-.07,0.);leader=[base]
    tilt=rng.uniform(.13,.26)*r
    for i,frac in enumerate((.19,.30,.41,.52,.63,.73,.82,.89,.95)):
        ang=phi+.39*math.sin(frac*7)+rng.uniform(-.26,.26)
        drift=tilt*(frac**1.35)
        leader.append((math.cos(ang)*drift,h*frac,math.sin(ang)*drift))
    thick=(.056 if species in ('sakura','sakuraWhite','ukon','streetWhite') else .064)*rng.uniform(.89,1.17)
    for j,(a,b) in enumerate(zip(leader,leader[1:])):
        t=j/(len(leader)-1);u=(j+1)/(len(leader)-1)
        _twig(sh,a,b,.003+thick*(1-t)**1.18,.003+thick*(1-u)**1.18,bark)
    # Stagger scaffold attachments over the leader, with shorter growth towards the top.
    # One weaker side and curved, off-axis terminal leaders break radial vase symmetry.
    count=11 if species in ('sakura','sakuraWhite','ukon') else 9
    for j in range(count):
        fraction=(j+rng.uniform(.15,.78))/count
        attach=(.19+rng.uniform(-.035,.055) if variant==0 else .30+rng.uniform(-.045,.04))+fraction*.55
        where=next((i for i in range(1,len(leader)) if leader[i][1]>=attach*h),len(leader)-1)
        frac=(attach*h-leader[where-1][1])/(leader[where][1]-leader[where-1][1])
        root=_curve(leader[where-1],leader[where],frac)
        ang=phi+j*2.39996+rng.uniform(-.41,.41)
        stretch=r*(1-fraction*.63)*rng.uniform(.56,.81)
        climb=(h-root[1])*rng.uniform(.29,.72)
        dangling=form.droop*rng.uniform(.25,1.12)
        arm=[root]
        for k in range(1,5):
            t=k*.25;stray=rng.uniform(-.19,.19)
            a=ang+stray+.24*math.sin(t*3.7+j)
            arm.append(_move(root,a,stretch*t,climb*(t**.82)-dangling*t*t))
            _twig(sh,arm[k-1],arm[k],max(.006,(1-(k-1)*.25)*.031)*(1-.41*fraction),
                  max(.005,(1-k*.25)*.031)*(1-.41*fraction),wood)
        for k in range(1,7):
            mix=(k+rng.uniform(-.33,.21))/7.;v=mix*4;seg=min(3,int(v))
            point=_curve(arm[seg],arm[seg+1],v-seg)
            a=ang+(1 if k%2==0 else -1)*rng.uniform(.58,1.31)
            d=stretch*rng.uniform(.22,.53)*(1-.23*mix)
            lift=h*rng.uniform(.068,.17)*(1-.47*fraction)
            b1=_move(point,a+rng.uniform(-.23,.23),d*.54,lift*.57)
            b2=_move(b1,a+rng.uniform(-.22,.22),d*.49,lift*.47-dangling*.22)
            _twig(sh,point,b1,.014*(1-.30*fraction),.009,wood)
            _twig(sh,b1,b2,.009,.005,'#8c7364')
            leafy=rng.random()>(form.bloom*.79+.13) if form.flowers else True
            for n,(bas,turn) in enumerate(((_curve(point,b1,.72),-.90),(_curve(b1,b2,.32),.78),(b2,-.48),(b2,.50))):
                twig_ang=a+turn+rng.uniform(-.32,.32)
                _terminal(sh,form,bas,twig_ang,rng.uniform(.20,.43),rng.uniform(-.055,.28)-dangling*.15,rng,not leafy)
        for n in range(4):
            t=math.pi*n/2
            _terminal(sh,form,arm[-1],ang+t*.38,rng.uniform(.23,.44),rng.uniform(.07,.29),rng,bool(form.flowers))
    if species in ('apricot','chestnut') and variant==0:
        for i in range(3):
            a=.7+i*math.tau/3
            _twig(sh,_move(base,a,.59,0.),_move(leader[2],a,.035,-.11),.030,.024,'#9b8868')
    _fit(sh,r,h)
    return sh


def _north_supports(scene,terrain,region,positions,eye):
    """A few immigrant trees in the photographed grove retain three wooden stakes."""
    from shapely.geometry import Point
    rng=random.Random(426013);sh=Shape('北区樱花林 · 局部支撑与浅树盘')
    by_eye=sorted(positions,key=lambda v:math.hypot(v[0]-eye[0],v[1]-eye[1]))
    # Keep one readable example beside the photographed foreground specimen.
    featured=positions[0]
    selected=[featured]+[p for j,p in enumerate(by_eye) if j in (4,9,16,24,35,46,57) and p!=featured]
    if len(selected)<8:
        selected.extend(p for p in by_eye[2:4] if p not in selected)
    selected=selected[:8]
    count=0
    for x,z,height,_ in selected:
        r=rng.uniform(.68,.82)
        if not region.covers(Point(x,z).buffer(r+.13)):continue
        count+=1;y=terrain.y(x,z);phase=rng.random()*math.tau
        # A very low, open-edged soil basin, separately draped at each rim vertex.
        circles=[[],[],[]];rad=[r,.86*r,.72*r]
        pieces=19
        for i in range(pieces):
            a=phase+i*math.tau/pieces
            jig=rng.uniform(.95,1.055)
            for ring,s in enumerate(rad):
                xx=x+math.cos(a)*s*jig;zz=z+math.sin(a)*s*jig
                circles[ring].append((xx,terrain.y(xx,zz)+(.012,.066,.028)[ring],zz))
        for k in range(2):
            pts=circles[k]+circles[k+1]
            sh.mesh('低矮土缘',pts,[(j,pieces+j,pieces+(j+1)%pieces,(j+1)%pieces) for j in range(pieces)],'#99876b')
        sh.mesh('盘内裸土',[(x,y+.02,z)]+circles[-1],[(0,1+(k+1)%pieces,1+k) for k in range(pieces)],'#a79676')
        top=min(1.35,height*.37)
        for i in range(3):
            a=phase+i*math.tau/3
            xx=x+math.cos(a)*r*.91;zz=z+math.sin(a)*r*.91
            head=(x+math.cos(a)*.055,y+top,z+math.sin(a)*.055)
            _twig(sh,(xx,terrain.y(xx,zz),zz),head,.025,.020,'#907b59')
        for n in range(9):
            a=math.tau*n/9;b=math.tau*(n+1)/9
            _twig(sh,(x+math.cos(a)*.086,y+top-.045,z+math.sin(a)*.086),
                  (x+math.cos(b)*.086,y+top-.045,z+math.sin(b)*.086),.010,.010,'#63594a')
    if count:scene.node(sh.name,shape=sh,kind='landscape',vegetation=True,season='spring',site='spring_north_cherries')
    return count


def _ground(species):
    rng=random.Random(4302 if species=='violet' else 9067)
    shape=Shape('草隙堇菜色小花' if species=='violet' else '初春低草')
    for i in range(29):
        angle=rng.random()*math.tau;rad=math.sqrt(rng.random())*.77
        x,z=math.cos(angle)*rad,math.sin(angle)*rad*.74
        h=rng.uniform(.055,.135)
        for j in range(4):
            a=angle+j*1.66
            _leaf(shape,(x,.012,z),a,rng.uniform(.055,.13),rng.uniform(.016,.033),h*.62,
                  rng.choice(('#6f814e','#829456','#95a065')))
        if species=='violet' and rng.random()<.63:
            top=(x+.018,h,z+.009)
            _twig(shape,(x,.008,z),top,.004,.002,'#7f965b')
            _flower(shape,top,rng.uniform(.023,.039),angle,.7,
                    rng.choice(('#987aa4','#a589ad','#806c9b')),rng.random())
    return shape


def _sitesampling(site,rng):
    if site.key=='spring_yuehai_walk':
        return [(38.55,-989.7)]+[(38.55+rng.uniform(-.25,.23),z) for z in (-1017.9,-1011.2,-1004.0,-996.8,-982.5,-976.2)]
    patch=Polygon(site.polygon)
    left,top,right,bottom=patch.bounds
    dx,dz=site.spacing
    target_x,target_z=site.preferred[:2]
    candidates=[(target_x,target_z)]
    row=0; z=top+dz*.48
    while z<bottom:
        x=left+dx*(.40+.38*(row%2))
        while x<right:
            candidates.append((x+rng.uniform(-.14,.14)*dx,z+rng.uniform(-.13,.13)*dz))
            x+=dx
        row+=1;z+=dz
    rest=candidates[1:];rng.shuffle(rest)
    # Preserve variety across the full plot when only a sample of the trees is drawn.
    return candidates[:1]+rest


def _anchors(site,area):
    x,z,dx,dy,dz,fov=site.preferred
    if not area.contains(Point(x,z)):
        p=area.representative_point();x,z=p.x,p.y
    eye=(x+dx,z+dz)
    return (x,z),eye,dy,fov


def build(scene,terrain,data,allowed,obstacles,roads,catalog):
    """Append real instanced scene nodes and terrain-relative viewing points."""
    # The caller supplies buildings, their door axes, footways, parking, courts and water.
    # The extra road and shoreline mask also protects standalone builds.
    extent=planted_extent(data)
    blockers=[obstacles]
    for key in ('pitches','parking','water','beaches','construction','buildings','plazas'):
        for row in data.get(key,()):
            if len(row.get('poly',()))>=3:
                shell=Polygon(row['poly'],row.get('holes',())).buffer(0)
                if extent.intersects(shell):
                    blockers.append(shell.buffer(.4))
    for road in roads:
        if road.get('tunnel') or len(road.get('line',()))<2:
            continue
        footprint=LineString(road['line']).buffer(road['width']*.5+.62,quad_segs=3)
        if extent.intersects(footprint):
            blockers.append(footprint)
    clear=extent.intersection(allowed).difference(unary_union(blockers))
    meshes={}
    result={'trees':0,'shrubs':0,'groundcover':0,'sites':{},'viewpoints':[]}
    for site in SITES:
        region=clear.intersection(Polygon(site.polygon)).buffer(0)
        if region.is_empty or region.area<14:
            raise ValueError('Spring site has no open planting ground: '+site.key)
        inside=prep(region)
        preferred,eye,eye_height,fov=_anchors(site,region)
        ray=LineString([eye,preferred])
        rng=random.Random(site.seed)
        positions=[]
        tall=[];species_count=Counter()
        def put(kind,x,z,sc,variant):
            is_ground=kind in ('violet','herb')
            shrub=is_ground or kind=='blueberry'
            cachekey=(kind,variant)
            if cachekey not in meshes:
                sh=_ground(kind) if is_ground else _tree(kind,variant)
                pts=[p for vertices,_,_ in sh.parts.values() for p in vertices]
                radius=max(math.hypot(float(p[0]),float(p[2])) for p in pts)
                h=max(float(p[1]) for p in pts)
                meshes[cachekey]=(scene.shape(sh),radius,h)
            mesh,r0,h0=meshes[cachekey]
            radius=r0*sc
            at=Point(x,z)
            if not inside.contains(at) or at.distance(region.boundary)<radius+.15:
                return False
            # A planted bed may extend under tree shade while its centre avoids the trunk.
            if any(math.hypot(x-u,z-v) < ((.68+r2*.15) if is_ground and not small
                                         else (radius+r2+.32))
                   for u,v,r2,small in positions):
                return False
            if not shrub and (at.distance(Point(*eye))<radius+1.8 or
                              (at.distance(Point(*preferred))>3.2 and at.distance(ray)<radius+.42)):
                return False
            y=terrain.y(x,z)
            sy=sc*rng.uniform(.95,1.065)
            name=({'violet':'堇菜色低花丛','herb':'春草'}[kind] if is_ground else FORMS[kind].name)
            scene.node(site.title+' · '+name+str(species_count[kind]+1),
                       mesh=mesh,at=(x,y+.022 if is_ground else y,z),
                       yaw=rng.random()*math.tau,scale=(sc,sy,sc),kind='flora',shrub=shrub,
                       species=name,season='spring',site=site.key,canopyRadius=round(radius,3))
            positions.append((x,z,radius,shrub))
            if not shrub:
                tall.append((x,z,h0*sy,kind))
            species_count[kind]+=1
            result['shrubs' if shrub else 'trees']+=1
            if is_ground:result['groundcover']+=1
            return True

        candidates=_sitesampling(site,rng)
        # Fixed subject for each camera goes first if the actual host mask allows the tree.
        candidates[0]=preferred
        for x,z in candidates:
            n=len(tall)
            if n>=site.count:break
            species=site.species[n%len(site.species)]
            if site.key=='spring_north_cherries' and n==3:species='ukon'
            sc=rng.uniform(.80,1.09)
            if site.key=='spring_north_cherries':sc*=1.20
            if site.key=='spring_student_farm':sc*=.88
            if site.key=='spring_yuehai_walk':sc=rng.uniform(.79,.91)
            put(species,x,z,sc,n%2)
        if not tall:
            raise ValueError('Could not place a spring specimen at '+site.key)

        if site.key=='spring_student_farm':
            # Two small staggered berry rows, with open walking space between the rows.
            centre=region.centroid
            for offset in (7.3,4.5,-5.4):
                for i in range(13):
                    x=centre.x+(i-6)*1.42+rng.uniform(-.12,.12)
                    z=centre.y+offset+rng.uniform(-.15,.15)
                    put('blueberry',x,z,rng.uniform(.70,.92),i%2)
        # Short, discontinuous ground herbs; only a few drifts carry muted purple flowers.
        lx,lz,rx,rz=region.bounds
        patches=8 if site.key=='spring_arena_orchard' else (10 if site.key=='spring_north_cherries' else 4)
        if site.key=='spring_yuehai_walk':patches=2
        for i in range(patches*3):
            if i>=patches and sum(species_count[v] for v in ('herb','violet'))>=patches*3:
                break
            if i<2:
                fx,fz,_,_=min(tall,key=lambda t:math.hypot(t[0]-preferred[0],t[1]-preferred[1]))
                cx,cz=fx+rng.uniform(-3,3),fz+rng.uniform(-3,3)
            else:
                cx,cz=rng.uniform(lx,rx),rng.uniform(lz,rz)
            for j in range(rng.randrange(3,7)):
                x,z=cx+rng.uniform(-2.6,2.6),cz+rng.uniform(-2.5,2.5)
                put('violet' if (i+j)%3==0 else 'herb',x,z,rng.uniform(.84,1.28),0)

        focus=min(tall,key=lambda t:math.hypot(t[0]-preferred[0],t[1]-preferred[1]))
        ex,ez=eye
        target=[round(focus[0],3),round(terrain.y(focus[0],focus[1])+focus[2]*.68,3),round(focus[1],3)]
        camera={'eye':[round(ex,3),round(terrain.y(ex,ez)+eye_height,3),round(ez,3)],
                'target':target,'fov':fov}
        catalog.append(dict(key=site.key,name=site.title,x=target[0],y=round(terrain.y(target[0],target[2]),3),
                            z=target[2],h=round(focus[2],2),r=17,group='春日花木',note=site.note,viewpoint=camera))
        if site.key=='spring_north_cherries':
            result['northSupports']=_north_supports(scene,terrain,region,tall,eye)
        result['sites'][site.key]=dict(species_count)
        result['viewpoints'].append(dict(key=site.key,**camera))
    if BLOSSOM in scene.colors:_blossom_texture(scene)
    result['sharedMeshes']=len(meshes)
    return result
