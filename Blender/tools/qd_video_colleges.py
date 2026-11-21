"""Details registered to the local November video archive and independent school photographs.

Local building metres. The map and the long lens aerial resolve architectural proportions but
do not distinguish mechanical manufacturers or the exact present-day layout of roof equipment.
"""
import math
from shapely.affinity import rotate
from shapely.geometry import box

STONE = '#ded4bf'
PALE = '#eee3ce'
GLASS = '#405766'
METAL = '#91948b'
DARK = '#534f4c'


def bay(f, name, u, y, depth, w, h, d, material):
    f.shape.box(name, *f.pt(u,y,depth),w,h,d,material,f.yaw)


def arch_panel(f,name,u,base,spring,width,rise,t,colour):
    half=width/2
    outline=[(u-half,base),(u+half,base)]
    outline.extend((u+half*math.cos(i*math.pi/18),spring+rise*math.sin(i*math.pi/18)) for i in range(19))
    f.shape.mesh(name,[f.pt(a,b,t) for a,b in outline],[tuple(range(len(outline)))],colour)


def ganchang_foyer(f,s):
    """Three different south-facing heads visible together in V2 and the 2021 oblique."""
    kind=s.kind
    if kind not in ('bar_b','marine','bar_f'):
        return False
    h=s.eave; floor=5.52
    if kind=='marine':
        width=18.0
        bay(f,'淦昌C平顶石质门楼',0,(h+floor)/2+.43,.23,width,h-floor+.86,1.10,STONE)
        for side in (-1,1):
            bay(f,'海洋研究院门楼竖向厚墙',side*(width*.43),(floor+h+.82)/2,.84,1.77,h+.82-floor,.73,PALE)
            bay(f,'淦昌C高窗两侧狭窗',side*4.15,10.13,.81,.54,4.85,.13,GLASS)
        bay(f,'淦昌C中央长方高窗',0,10.28,.82,3.87,5.0,.12,GLASS)
        for u in (-.65,.65):
            bay(f,'淦昌C门楼竖梃',u,10.28,.91,.08,5.0,.07,METAL)
        for v in (8.84,10.32,11.84):
            bay(f,'淦昌C门楼横梃',0,v,.93,3.85,.10,.07,METAL)
        bay(f,'淦昌C门楼上边石线',0,h+.80,.35,width+.48,.30,1.61,PALE)
        bay(f,'淦昌C门楼下部窗台石',0,7.36,.64,10.5,.32,1.18,PALE)
    elif kind=='bar_f':
        width=18.3
        # Two square stair towers flank a recessed flat-headed bay. Both are visible at 38.50.
        bay(f,'淦昌F双塔间石质过楼',0,(h+floor)/2,.47,width-3.9,h-floor,1.19,STONE)
        for side in (-1,1):
            u=side*(width/2-1.44)
            bay(f,'淦昌F门前双塔',u,(h+.98)/2,.94,3.0,h+1.02,2.30,PALE)
            bay(f,'淦昌F方塔薄压顶',u,h+1.05,.95,3.31,.25,2.62,PALE)
            for j in (-1,0,1):
                for y,height in ((3.0,3.46),(8.76,4.48),(14.,4.78)):
                    bay(f,'淦昌F石塔窄竖缝',u+j*.65,y,2.109,.32,height,.063,GLASS)
        for i in range(6):
            for y in (8.78,13.0):
                bay(f,'淦昌F两排长窗',(i-2.5)*1.33,y,1.09,.80,3.0,.074,GLASS)
        bay(f,'淦昌F过楼下石楣',0,6.38,1.04,9.6,.54,1.13,PALE)
    else:
        width=19.4
        bay(f,'淦昌B中央石质拱窗阁',0,(h+floor)/2,.41,width,h-floor,1.16,STONE)
        bay(f,'淦昌B阁楼檐下暗窗',0,h-.93,1.02,width-2.4,1.12,.12,GLASS)
        for side in (-1,1):
            bay(f,'淦昌B门楼两侧石墩',side*(width*.455),(h+floor)/2,.77,1.46,h-floor,1.18,PALE)
        for u,w,base,spring,rise in ((0,4.75,8.00,10.22,2.30),(-5.60,1.43,8.02,10.25,.63),(5.60,1.43,8.02,10.25,.63)):
            arch_panel(f,'淦昌B拱窗石套',u,base-.18,spring,w+.44,rise+.20,1.022,PALE)
            arch_panel(f,'淦昌B三樘拱窗',u,base,spring,w,rise,1.047,GLASS)
            if u==0:
                for j in (-1,0,1):
                    bay(f,'淦昌B拱窗立梃',j*1.18,10.04,1.073,.085,3.9,.046,DARK)
                for v in (9.25,10.26):
                    bay(f,'淦昌B拱窗横梃',0,v,1.08,4.74,.095,.055,DARK)
        bay(f,'淦昌B中央石质层檐',0,h-.18,.67,width+.75,.28,1.59,PALE)
    return True


def b_arcade(f,s,length,u,width):
    if s.kind!='bar_b' or f.nz<.94 or not 28.0<length<41.0:
        return False
    arch_panel(f,'淦昌B一层连排拱券石套',u,.43,2.65,width+.42,.90,.14,PALE)
    arch_panel(f,'淦昌B一层凹入拱窗',u,.50,2.65,width,.69,.167,GLASS)
    bay(f,'淦昌B拱窗中梃',u,1.79,.20,.085,2.48,.035,DARK)
    return True


def plaza_canopy(f,s,length):
    """North/south collegiate foyers face across Huiwen Square. The central red wing is the anchor."""
    if not s.kind.startswith('hui') or abs(f.x-20.5)>2 or not 24<length<28:
        return False
    if f.nz*(1 if s.kind=='hui_n' else -1)<.94:return False
    width=min(21.2,length-3)
    bay(f,'会文广场上层玻璃门厅',0,9.90,.14,width-2.6,9.38,.36,GLASS)
    for j in range(-3,4):
        bay(f,'会文广场连续门厅窗竖框',j*(width-3.25)/7,9.90,.357,.13,9.35,.094,METAL)
    for y in (7.05,10.15,13.26):
        bay(f,'会文广场玻璃过梁',0,y,.381,width-2.36,.13,.11,DARK)
    for side in (-1,1):
        for u in (width*.30,width*.45):
            bay(f,'会文门楼通高浅色壁柱',side*u,10.17,.52,.71,10.05,1.10,PALE)
    # A shallow accessible terrace with an open centre sits in front of this glazing.
    bay(f,'会文广场门廊顶平台',0,5.07,2.22,width+1.0,.46,5.00,STONE)
    bay(f,'会文广场挑檐石压边',0,5.29,4.65,width+1.06,.38,.32,PALE)
    bay(f,'会文广场露台石栏',0,5.85,4.61,width+.90,.83,.29,STONE)
    for side in (-1,1):
        bay(f,'会文露台侧栏',side*(width+.61)/2,5.85,2.35,.29,.83,4.85,STONE)
        for u in (width*.22,width*.46):
            bay(f,'会文水平门廊支柱',side*u,2.35,4.03,.57,5.02,.65,PALE)
    for u in (-5.5,-2.75,0,2.75,5.5):
        bay(f,'会文广场门廊深色底层玻璃',u,2.43,.19,2.62,3.75,.49,GLASS)
    return True


def stepped_end(block,w,h,stone,pale,glass):
    """Raised masonry cheeks and a stepped silhouette around the dark rectangle on the wing end."""
    half=min(8.4,w*.277);top=h+2.12;bottom=4.36
    # Link each horizontal band to its own narrower top band; triangulating a concave
    # stepped silhouette with a single fan could fill in its shoulders.
    tiers=[(bottom,h-.30,half),(h-.30,h+.55,.85*half),(h+.55,h+1.38,.63*half),(h+1.38,top,.39*half)]
    for low,high,hh in tiers:
        block('学院端翼阶梯式山墙',0,(low+high)/2,.27,hh*2,high-low,1.28,stone)
    # Fog, shade and reflections obscure the subdivisions behind the picture window.
    block('学院端翼内退深色窗框',0,h*.61,1.022,half*1.24,h*.51,.24,glass)
    for side in (-1,1):
        block('学院端翼竖向石窗套',side*half*.654,h*.61,1.07,.49,h*.54,.54,pale)
    for y in (h*.348,h*.871):
        block('学院端翼窗楣及窗台石',0,y,1.12,half*1.38,.30,.65,pale)
    block('学院端翼窗间浅色横板',0,h*.565,1.166,half*1.14,h*.095,.30,pale)
    for u in (-half*.27,0,half*.27):
        block('学院端翼深窗金属梃',u,h*.61,1.173,.10,h*.50,.12,'#534f4c')


def rounded_dormer(shape,at,roof,u,tile,stone,glass):
    """A solid barrel hood; four skirt runs meet the actual supporting roof triangles."""
    half=1.40;front=-1.03;back=-2.55;thickness=.075
    x,_,z=at(u,0,front);y=roof.sheet.y(x,z)
    if y is None:return
    outer=[];inner=[];glass_points=[];faces=[]
    for i in range(17):
        a=i*math.pi/16;dx=half*math.cos(a);rise=1.04*math.sin(a)
        outer.extend([at(u+dx,y+.065+rise,front),at(u+dx,y+.265+rise,back)])
        glass_points.append(at(u+dx*.74,y+.10+.72*math.sin(a),front+.038))
        if i:
            k=i*2
            faces.append((k-2,k-1,k+1,k))
    inner=[(xx,yy-thickness,zz) for xx,yy,zz in outer]
    shape.mesh('圆拱老虎窗红瓦筒壳',outer,faces,tile)
    shape.mesh('圆拱老虎窗筒瓦檐底',inner,[f[::-1] for f in faces],stone)
    shape.mesh('圆拱老虎窗深色窗心',glass_points,[tuple(range(len(glass_points)))],glass)
    # Follow the perimeter once, front and rear arch by arch, then the straight spring edges.
    edges=[('石质前脸',2*i,2*i+2) for i in range(16)]
    edges.extend(('后墙贴坡封板',2*i+3,2*i+1) for i in range(16))
    edges.extend([('瓦面接边',1,0),('瓦面接边',32,33)])
    for name,i,j in edges:
        shape.mesh('圆拱老虎窗筒瓦封檐',[outer[i],outer[j],inner[j],inner[i]],[(0,1,2,3)],stone)
        a,b=inner[i],inner[j];verts=[];ff=[]
        for start,end,plane in roof.sheet.spans(a,b):
            top=[tuple(a[k]+(b[k]-a[k])*f for k in range(3)) for f in (start,end)]
            feet=[(xx,min(yy-.023,plane[0]*xx+plane[1]*zz+plane[2]-.085),zz) for xx,yy,zz in top]
            off=len(verts);verts.extend([feet[0],feet[1],top[1],top[0]])
            ff.append((off,off+1,off+2,off+3))
        shape.mesh('圆拱老虎窗'+name,verts,ff,stone)


def service_deck(roof,shape,deck,base,metal,ix):
    """Rows of small light roof housings and connected low runs. Placement stays on the flat deck."""
    if deck.area<110:return
    p=rotate(deck,-roof.angle,origin=(0,0));safe=p.buffer(-.46,join_style=2)
    for panel in roof.light_zones:
        if safe.intersects(panel):safe=safe.difference(panel)
    if safe.is_empty:return
    x0,z0,x1,z1=p.bounds
    along_x=x1-x0>=z1-z0
    lo,hi,c0,c1=(x0,x1,z0,z1) if along_x else (z0,z1,x0,x1)
    length=hi-lo;span=c1-c0
    if length<10 or span<3.1:return
    ca,sa=math.cos(math.radians(roof.angle)),math.sin(math.radians(roof.angle))
    def block(tag,a,c,w,d,off,hh,mat):
        x,z=(a,c) if along_x else (c,a)
        wx,wz=(w,d) if along_x else (d,w)
        footing=box(x-wx/2,z-wz/2,x+wx/2,z+wz/2)
        if not safe.covers(footing):return False
        if tag=='平台实体机箱':roof.equipment_feet.append((footing,p))
        shape.box(tag,ca*x-sa*z,base+off,sa*x+ca*z,wx,hh,wz,mat,-math.radians(roof.angle))
        return True
    if roof.id==868015915 and ix==1:
        # V3 38.50: two pale parallel raised housings on the central longitudinal terrace.
        a0=(hi+lo)*.5;centre=(c0+c1)*.5
        run=min(18.6,length*.44)
        for sign in (-1,1):
            c=centre+sign*.99
            if block('淦昌D中央两道长条设备罩',a0,c,run,1.67,.76,1.52,metal):
                block('淦昌D设备罩浅色顶板',a0,c,run+.12,1.76,1.56,.12,'#c9c5bc')
                for j in range(-2,3):
                    block('淦昌D设备罩上部分缝',a0+run*j/6,c,.10,1.74,1.64,.045,metal)
    hui=roof.id in (970257672,970257673)
    # Sparse enclosures on the Huiwen roofs; equipment closes up around the academy roof wells.
    count=max(1,min(2 if hui else 7,round(length/(34 if hui else 7.4))))
    sides=(1,) if hui or span<7 else (-1,1)
    for sign in sides:
        cross=(c0+c1)/2+sign*(span/2-min(1.81,span*.19))
        for j in range(count):
            if hui and sign==1 and (j+ix)%3==2:continue
            long=lo+(j+.64)*(length-1.6)/count
            w=1.62+(ix+j)%3*.26;d=1.28;hh=.77+(j+ix)%2*.23
            if block('平台实体机箱',long,cross,w,d,hh/2,hh,'#b1aaa0'):
                block('屋顶机箱镀锌薄盖',long,cross,w+.09,d+.10,hh+.033,.066,'#c9c5bc')
                for side in (-1,1):
                    block('机箱顶部双风口',long+side*w*.233,cross,w*.33,d*.65,hh+.077,.048,metal)
            if count>2 and j<count-1:
                run=length/count-1.82
                if run>1.1:block('屋顶设备相连的低矮管槽',long+run*.5+1.04,cross,run,.48,.33,.32,metal)


def phoenix_projection(fr, width, h, brick, cream, owner):
    """Two free north-end bays carry bowed balconies. Arcade-linked bays carry a squared porch."""
    radius = width*.442
    rounded = owner in ('way/970257676','way/970257679') and fr.z < 0
    if rounded:
        # Keep the original spring points. The front of the bow projects 2.06 m
        # from the brick face, while the rear edge runs into the glazing reveal.
        for level in (h*.30,h*.48):
            arc = [(radius*math.sin(a),.14+1.92*math.cos(a))
                   for a in [-math.pi/2+math.pi*i/32 for i in range(33)]]
            rear = -.56
            y=level-.99
            def strip(name, outside, inside, lower, upper, material):
                vertices=[]
                for (x,z),(ix,iz) in zip(outside,inside):
                    vertices.extend([fr.at(x,lower,z),fr.at(x,upper,z),
                                     fr.at(ix,upper,iz),fr.at(ix,lower,iz)])
                faces=[(3,2,1,0)]
                for i in range(len(outside)-1):
                    a=i*4
                    for k in range(4):
                        faces.append((a+k,a+4+k,a+4+(k+1)%4,a+(k+1)%4))
                e=len(vertices)-4
                faces.append((e,e+1,e+2,e+3))
                fr.s.mesh(name,vertices,faces,material)
            outline=[(-radius,rear)]+arc+[(radius,rear)]
            inside=[(-radius+.2,rear)]+[(x*(1-.20/radius),z-.20) for x,z in arc]+[(radius-.2,rear)]
            strip('凤凰居翼端弧形阳台实腹栏板',outline,inside,y,level-.08,cream)
            strip('弧形阳台金属收口',[(x*1.003,z+.025) for x,z in outline],
                  [(x*.998,z-.035) for x,z in inside],level-.08,level+.04,'#697478')
            # A closed convex slab, including the return soffit visible from below.
            n=len(outline);v=[fr.at(x,a,z) for a in (y-.16,y+.015) for x,z in outline]
            # The first two outer plan points share X. Use a centre fan for the lids.
            v += [fr.at(0,a,.45) for a in (y-.16,y+.015)]
            fs=[]
            for i in range(n):
                j=(i+1)%n
                fs.extend([(2*n,j,i),(2*n+1,i+n,j+n),(i,j,j+n,i+n)])
            fr.s.mesh('翼端弧形阳台楼板',v,fs,brick)
        return
    # The November ground film shows the recessed arched glass rising behind
    # a rectangular roof terrace. Open arcades return down both sides.
    front=3.95
    rear=-.54
    half=width*.49
    cap=h*.455
    pier=.70
    fr.block('凤凰居方挑门廊封底顶板',0,cap-.15,(front+rear)/2,2*half,.30,front-rear,brick)
    fr.block('方挑平台正面实腹女儿墙',0,cap+.37,front-.105,2*half,.75,.21,brick)
    fr.block('方挑平台浅色正面压顶',0,cap+.785,front-.105,2*half+.06,.085,.27,cream)
    for sign in (-1,1):
        u=sign*(half-.105)
        fr.block('方形平台折回栏板',u,cap+.37,(front+rear)/2,.21,.75,front-rear,brick)
        fr.block('方形平台侧面收边',u,cap+.785,(front+rear)/2,.26,.085,front-rear,cream)
    def arched_wall(origin, tangent, normal, span, jamb):
        spring = cap-2.05
        rise=1.05
        def pt(a,y,d=0):
            return fr.at(origin[0]+tangent[0]*a+normal[0]*d,y,origin[1]+tangent[1]*a+normal[1]*d)
        opening=span*.5-jamb
        for hand in (-1,1):
            low,high=sorted([hand*opening,hand*span*.5])
            v=[pt(a,b,z) for z in (-.31,0) for b in (.035,cap-.15) for a in (low,high)]
            fr.s.mesh('方挑檐下砖柱',v,[(4,5,7,6),(2,3,1,0),(0,4,6,2),(5,1,3,7),(6,7,3,2)],brick)
        arc=[(opening*math.cos(a),spring+rise*math.sin(a))
             for a in [math.pi-i*math.pi/22 for i in range(23)]]
        for (a,y),(b,z) in zip(arc,arc[1:]):
            face=[pt(a,y),pt(b,z),pt(b,cap-.14),pt(a,cap-.14)]
            back=[pt(a,y,-.31),pt(b,z,-.31),pt(b,cap-.14,-.31),pt(a,cap-.14,-.31)]
            fr.s.mesh('门廊浅拱与内券面',face+back,[(0,1,2,3),(7,6,5,4),(0,4,5,1)],brick)
    arched_wall((0,front),(1,0),(0,1),2*half,pier)
    for sign in (-1,1):
        # Leave a masonry corner on the front, meet the existing facade at the rear.
        z0=.02;z1=front-.32
        arched_wall((sign*half,(z0+z1)/2),(0,-sign),(sign,0),z1-z0,.40)
    # Divide the inset upper glass as in the axis-side winter film.
    for u in (-width*.30,-width*.15,width*.15,width*.30):
        fr.rect('翼端拱窗上部直梃',u,h*.64,-.52,.085,h*.195,'#404951')
    for y in (h*.59,h*.68):
        fr.rect('翼端拱窗玻璃横梃',0,y,-.51,width*.94,.09,'#404951')


def phoenix_slots(fr,holes,side,crownline,h,opening,kind):
    length=fr.length
    u=side*(length/2-3.38);y=(crownline+.80)/2
    for k in (-1,1):
        opening(fr,holes,u+k*1.17,y,1.54,crownline-1.10,1,kind)
        for level in range(1,5):
            fr.block('凤凰居翼肩通高暗窗横档',u+k*1.17,.88+level*(crownline-1.03)/5,-.16,1.53,.17,.09,'#3e4a50')
    return 6.75


def raised_light(shape,cx,cz,run,width,axis,angle,base,metal):
    """Low vaulted blue-grey glazing and transverse standing bars on a rectangular service plinth."""
    ca,sa=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    def at(a,c,y):
        x,z=(cx+a,cz+c) if axis=='x' else (cx+c,cz+a)
        return (ca*x-sa*z,y,sa*x+ca*z)
    n=10
    def top(v):return base+.50+.64*max(0.,1.-(2*v/width)**2)
    for i in range(n):
        v0=-width*.5+width*i/n;v1=v0+width/n
        pts=[at(-run*.5,v0,top(v0)),at(-run*.5,v1,top(v1)),
             at(run*.5,v1,top(v1)),at(run*.5,v0,top(v0))]
        # Geometry is really bowed, including the opaque blue-grey end closures below its head.
        shape.mesh('架高浅蓝色弧面长棚',pts,[(0,1,2,3) if axis=='x' else (3,2,1,0)],'#6895a7')
        for end in (-1,1):
            a=end*run*.5
            pts=[at(a,v0,base+.32),at(a,v1,base+.32),at(a,v1,top(v1)),at(a,v0,top(v0))]
            shape.mesh('蓝色长棚封闭端板',pts,[(0,1,2,3)],'#7c969b')
    for j in range(1,max(3,round(run/2.35))):
        u=(j/max(3,round(run/2.35))-.5)*run
        verts=[];ff=[]
        for i in range(n+1):
            v=width*(i/n-.5)
            verts.extend([at(u-.05,v,top(v)+.032),at(u+.05,v,top(v)+.032)])
            if i:ff.append((i*2-2,i*2,i*2+1,i*2-1))
        shape.mesh('蓝色弧面分节金属扣条',verts,ff,metal)

def hui_west_gallery(f,s,length):
    if s.kind!='hui_n' or f.nz<.94 or not 68<length<76 or f.x>-50:return
    for i in range(11):
        u=(i-5)*5.8
        x,_=f.pos(u,0)
        if abs(x-s.door[0])<6.25:continue
        bay(f,'会文北楼西翼柱廊后凹窗',u,2.26,.19,5.02,3.51,.42,GLASS)
        bay(f,'会文北楼西翼柱廊石柱',u-2.69,2.20,2.16,.63,4.50,.85,PALE)
    bay(f,'会文北楼西翼连续柱廊顶板',0,4.62,1.01,length-2.42,.50,3.52,STONE)
    bay(f,'会文北楼西翼柱廊檐带',0,4.78,2.71,length-2.14,.27,.41,PALE)


def hui_west_entry(f,s):
    if s.kind!='hui_n':return False
    width=12.42
    bay(f,'会文北楼西段偏东的通高玻璃',0,10.28,.19,width,8.40,.47,GLASS)
    for side in (-1,1):
        bay(f,'会文北楼西段蓝窗石框',side*(width/2+.48),10.31,.52,.88,8.93,.98,PALE)
    for u in (-4.12,-2.07,0,2.07,4.12):
        bay(f,'会文北楼西段竖向幕墙梃',u,10.28,.46,.105,8.40,.085,METAL)
    for y in (7.45,10.32,13.25):
        bay(f,'会文北楼西段玻璃横梃',0,y,.47,width,.11,.092,DARK)
    bay(f,'会文北楼西段入口挑檐',0,5.17,1.29,width+1.91,.56,3.92,PALE)
    return True


def phoenix_dormer(fr,u,h,tile,cream,glass):
    """Half-round window in a matching barrel of roof tile, behind the eave-side solar strip."""
    front=-2.23;back=-4.0;width=2.82;low=h+1.01
    profile=[];rim=[];inner=[]
    for i in range(19):
        a=i*math.pi/18;du=width*.5*math.cos(a);rise=1.0*math.sin(a)
        profile.extend([fr.at(u+du,low+.07+rise,front),fr.at(u+du,low+.30+rise,back)])
        rim.extend([fr.at(u+du,low+.07+rise,front+.025),fr.at(u+du*.83,low+.05+.77*rise,front+.025)])
        inner.append(fr.at(u+du*.83,low+.05+.77*rise,front+.010))
    faces=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(18)]
    fr.s.mesh('凤凰居红瓦拱形屋窗罩',profile,faces,tile)
    fr.s.mesh('凤凰居拱窗薄石前缘',rim,faces,cream)
    fr.s.mesh('凤凰居拱窗深色玻璃',inner,[tuple(range(len(inner)))],glass)
    for side in (-1,1):
        pts=[fr.at(u+side*width*.5,low+.07,front),fr.at(u+side*width*.5,low+.30,back),
             fr.at(u+side*width*.5,low-.18,back),fr.at(u+side*width*.5,low-.18,front)]
        fr.s.mesh('拱形屋窗回接瓦面',pts,[(0,1,2,3)],tile)
