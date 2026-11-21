"""Public-facing landmarks of Shandong University's Qingdao campus.

Local coordinates use metres, east/right X, up Y and south/forward Z.
Source photographs and georeferencing notes appear in data/civic_sources.json.
"""
import base64
import math
import zlib
from qd_public_roofs import arena_soffit, tiled_ring

MAP = 'https://hq.qd.sdu.edu.cn/info/1053/1824.htm'
GATE = 'https://jjc.qd.sdu.edu.cn/info/1022/1925.htm'
PHOTOS = 'https://www.qdxq.sdu.edu.cn/info/1836/52034.htm'
WEST = 'https://culture.sdu.edu.cn/sdyx/qdxq/6.htm'
TRACK = 'https://www.qdxq.sdu.edu.cn/info/1720/51566.htm'
DINING = 'https://hq.qd.sdu.edu.cn/info/1020/1910.htm'

SPECS = [
    dict(key='way-982199336',name='风雨操场',aliases=['拱顶风雨操场'],w=96.56,d=47.76,h=14.4,yaw=0.,site_x=-289.32,site_z=446.82,osm=982199336,replaces=[982199336],source='用户视频 V3 02:05–02:10',caption='淡米色分带拱壳，两端蓝色山墙，位置沿用风雨操场原建筑轮廓。'),
    dict(key='west_gate', name='西门（礼仪正门）', aliases=['西校门','正门'], w=132,d=14,h=20,yaw=-math.pi/2,lon=120.679993,lat=36.366198,replaces=[1022925330,1022925331],source=WEST),
    dict(key='north_gate', name='北校门',aliases=['北门'],w=47.5,d=9,h=16.2,yaw=math.pi,lon=120.682914,lat=36.376878,source=GATE,caption='北门西侧为16.2米高的收分石塔，塔身设棕色竖格栅，东侧为平檐传达室。'),
    dict(key='east_gate',name='东校门',aliases=['山东大学青岛校区东门'],w=40,d=113,h=16.6,yaw=0.,site_x=587.,site_z=-60.,replaces=[1020621361,1020621362,1020621363],source='https://jjc.qd.sdu.edu.cn/info/1022/1051.htm',caption='从图书馆向海望，北侧为浅石高塔，南侧低亭接弧廊，车道间为修剪绿岛。立面据实拍复原，高度为影像估计。'),
    dict(key='south_gate',name='南校门',aliases=['山东大学青岛校区南门'],w=34,d=22,h=13.4,yaw=0.,site_x=-45.64,site_z=963.09,replaces=['node/9083815756'],source='https://www.qdxq.sdu.edu.cn/info/1836/58105.htm',caption='南门西侧红顶门塔设圆形校徽与竖排“山东大学”，东侧为低矮岗亭。门面据2016与2024年实拍，塔高按比例估算。'),
    dict(key='song_arena',name='宋君复体育馆',aliases=['综合体育馆','体育馆'],w=109,d=430,h=35,yaw=0,lon=120.680864,lat=36.359405,osm=982199335,replaces=[982199335],source=PHOTOS),
    dict(key='blue_track',name='蓝色田径场',aliases=['训练运动场','体育馆北侧田径场'],w=101,d=179,h=1.4,yaw=0,lon=120.680044,lat=36.360962,osm=996232451,replaces=[996232451],source=TRACK),
    dict(key='east_track',name='东田径场',aliases=['东操场','东运动场'],w=102,d=186,h=1.4,yaw=0,lon=120.687923,lat=36.360907,osm=970257666,replaces=[970257666,970257649],source='https://tyb.qd.sdu.edu.cn/info/1041/1118.htm'),
    dict(key='xiyuan',name='曦园餐厅',aliases=['曦园','学生食堂'],w=118,d=74,h=16,yaw=0,lon=120.687865,lat=36.359384,osm=868015917,replaces=[868015917],source=DINING),
    dict(key='yuxian',name='育贤广场',aliases=['育贤广场与校训石'],w=254,d=74,h=2.4,yaw=0,lon=120.681746,lat=36.366175,osm=981132252,replaces=[981132252],source=MAP),
]

# Raster seal retained for the sports hall facade. The campus gates use vector relief.
SEAL_SHAPE = 'eNp1kT1uAjEQhZ+xhJNm3aZAuznGSkEhR+EIlClQ1qQhh8hhjChIFa5ghBTKOEKKQBhPZpwUNHHhz5p5/nsP+G8oSoUNkReOchNLGVoaiqfMNAduOcC+QGkWNtILwBAK4A1TfbrBIy/NspZi6HO9Fol2LOYtxsGWSZbMxve0s3xS6Gsv3LKqgiFyOtQwiWanMIBNtDgym0R+LKRzQGyv6JfXzPgwaRURJSaYWditKI+Zd+t1EsI6XHAM+9bESbthPYXJcFsYB98V0dLHeocvokWodlIX+qo3mnk7Fy/m3rwy+ytXaD6deWdafvlHsRJ6X6yE2rNX90/AadPlegp0R0pT8fIQQcJnKMv+2eVtbdlPcz7kjn3W/LtccgiqBDQiklz4EnIlsL/c2MeLNH8AK9yq/w=='


def relief(scene, name, x, y, z, width, height, pixels_x, pixels_y, encoded, color):
    pixels = zlib.decompress(base64.b64decode(encoded,validate=True))
    stride = (pixels_x + 7) // 8
    active = {}
    verts, faces = [], []
    def emit(run, top, bottom):
        a, b = run
        left, right = x + (a/pixels_x-.5)*width, x + (b/pixels_x-.5)*width
        hi, lo = y + (.5-top/pixels_y)*height, y + (.5-bottom/pixels_y)*height
        i=len(verts)
        verts.extend([(left,lo,z),(right,lo,z),(right,hi,z),(left,hi,z)])
        faces.append((i,i+1,i+2,i+3))
    for row in range(pixels_y + 1):
        runs = set()
        if row < pixels_y:
            start = None
            for col in range(pixels_x + 1):
                filled = col < pixels_x and pixels[row*stride+col//8] & (128 >> (col%8))
                if filled and start is None:
                    start = col
                if not filled and start is not None:
                    runs.add((start,col))
                    start = None
        for run in active.keys()-runs:
            emit(run,active[run],row)
        active = {run:active.get(run,row) for run in runs}
    scene.mesh(name,verts,faces,color)


def hip(scene, name, x, z, w, d, bottom, height, ridge, color):
    v=[(x-w/2,bottom,z-d/2),(x+w/2,bottom,z-d/2),(x+w/2,bottom,z+d/2),(x-w/2,bottom,z+d/2)]
    if ridge <= 0:
        v.append((x,bottom+height,z))
        faces=[(1,0,4),(2,1,4),(3,2,4),(0,3,4)]
    else:
        v.extend([(x-ridge/2,bottom+height,z),(x+ridge/2,bottom+height,z)])
        faces=[(1,0,4,5),(2,1,5),(3,2,5,4),(0,3,4)]
    scene.mesh(name,v,faces,color)


def arch(scene,name,x,y,z,width,height,color):
    """A semicircular head over a rectilinear glazing bay, facing local +Z."""
    radius=min(width/2,height*.60)
    spring=y+height-radius
    curve=[(x-width/2+width/2*(1+math.cos(a*math.pi/20)),spring+radius*math.sin(a*math.pi/20),z) for a in range(21)]
    perimeter=[(x-width/2,y,z),(x+width/2,y,z)]+curve
    verts=[(x,spring,z)]+perimeter
    scene.mesh(name,verts,[(0,i+1,(i+1)%len(perimeter)+1) for i in range(len(perimeter))],color)


def west_gate(s,w,d,h):
    stone, trim, cuts = '#d5cfbf','#e5decd','#aca897'
    for hand in (-1,1):
        x=hand*w*.229
        s.box('门塔花岗石台基',x,.24,0,9.8,.48,9.2,trim)
        s.box('底座与窗台',x,h*.175,0,8.9,h*.31,8.6,stone)
        s.box('基座腰线',x,h*.32,0,9.2,.48,8.9,trim)
        from qd_video_gate import shaft
        shaft(s,x,h,stone,trim)
        for face in (-1,1):
            for bay in (-1,0,1):
                arch(s,'三联拱窗',x+bay*2.30,.77,face*4.314,1.22,3.1,'#38505b')
                s.box('拱窗竖挺',x+bay*2.30,2.17,face*4.323,.065,2.85,.035,stone)
        s.box('顶端石材檐口',x,h*.85,0,8.72,.83,8.57,trim)
        s.box('顶端收分',x,h*.881,0,8.12,.55,8.00,stone)
        hip(s,'灰色四坡塔顶',x,0,8.4,8.15,h*.895,h*.105,0,'#807f7e')
        ext = w*.5-abs(x)-4.25
        wing_x=x+hand*(4.2+ext/2)
        s.box('门侧柱廊顶',wing_x,h*.295,0,ext,.75,5.1,stone)
        s.box('柱廊上檐',wing_x,h*.319,0,ext+.22,.22,5.33,trim)
        terminal=hand*(w*.5-3.9)
        s.box('柱廊尽端石亭',terminal,h*.14,0,6.4,h*.28,6.8,stone)
        s.box('尽端石亭檐口',terminal,h*.295,0,6.95,.35,7.3,trim)
        for face in (-1,1):
            arch(s,'尽端亭拱窗',terminal,.55,face*3.42,2.1,h*.16,'#60818a')
        for bay in range(5):
            colx=x+hand*(5.8+bay*(ext-4.8)/4)
            for colz in (-1.65,1.65):
                s.cyl('石廊柱',colx,h*.146,colz,.47,h*.289,stone,12)
                s.cyl('廊柱柱础',colx,.24,colz,.66,.48,trim,12)
    x=w*.229
    from qd_video_gate import approach as gate_approach
    gate_approach(s)
    from qd_gate_details import west_sign
    west_sign(s,x)


def east_gate(s,w,d,h):
    # OSM 1020621361 follows the paved fan north of the actual gatehouse.
    # Photo 3 from the library distinguishes the north tower from the low south pavilion.
    stone,trim,glass='#b4ada0','#c7c1b4','#60818a'
    from qd_terrain import face
    from shapely.geometry import Polygon
    plaza=[(-8.59,-32.86),(-8.85,-39.31),(-5.14,-41.63),(-1.34,-43.23),(4.23,-43.97),(9.13,-43.48),
           (13.89,-41.01),(17.28,-36.95),(18.51,-32.49),(18.51,-27.1),(16.38,-22.74),(13.64,-20.37),
           (8.96,-18.08),(4.02,-18.33),(4.15,-23.82),(3.79,-29.09),(2.88,-31.81),(-.22,-32.21)]
    face(s,Polygon(plaza),'#bba799',.035)
    from qd_gate_details import east_gate_tower,east_gate_pavilion,east_details
    east_gate_tower(s,h)
    east_gate_pavilion(s)
    # The south colonnade curves east at its far end. Both sides stay open.
    center=[(-3.3,25.5),(-3.,30.),(-1.6,35.),(.6,40.),(3.5,45.),(7.3,50.),(11.7,54.4),(16.1,57.4)]
    roof_top=5.36;soffit=4.91
    rings=[]
    for k,(cx,cz) in enumerate(center):
        a=center[max(0,k-1)];b=center[min(len(center)-1,k+1)]
        dx,dz=b[0]-a[0],b[1]-a[1];n=math.hypot(dx,dz);nx,nz=dz/n,-dx/n
        rings.append([(cx+sign*nx*2.20,y,cz+sign*nz*2.20) for y,sign in ((roof_top,-1),(roof_top,1),(soffit,1),(soffit,-1))])
        if k<1:continue
        for sign in (-1,1):
            px,pz=cx+sign*nx*1.72,cz+sign*nz*1.72
            s.box('弧形石廊方柱',px,soffit/2,pz,.48,soffit,.48,trim,math.atan2(dx,dz))
            s.box('弧廊柱头承托',px,soffit-.14,pz,.65,.28,.65,trim,math.atan2(dx,dz))
    for a,b in zip(rings,rings[1:]):
        v=a+b
        s.mesh('弧廊封合压顶',v,[(0,4,5,1),(3,2,6,7),(0,3,7,4),(1,5,6,2)],stone)
    s.mesh('弧廊尽端收口',rings[-1],[(0,1,2,3)],stone)
    east_details(s,center,roof_top)


def south_gate(s,w,d,h):
    # A tall inscribed pier and a single-storey staffed building flank the open road.
    from qd_gate_details import south_tower
    south_tower(s)
    cx,cz=12.2,6.3;angle=-math.radians(17)
    def pos(x,y,z):
        return cx+x*math.cos(angle)+z*math.sin(angle),y,cz-x*math.sin(angle)+z*math.cos(angle)
    def box(name,x,y,z,width,height,depth,mat):
        px,py,pz=pos(x,y,z);s.box(name,px,py,pz,width,height,depth,mat,angle)
    box('南门路侧岗亭基座',0,-.02,0,8.13,.56,3.87,'#c7c1b4')
    box('路侧值守亭',0,1.46,-.13,7.9,2.88,3.39,'#b4ada0')
    from qd_gate_details import kiosk_front
    kiosk_front(s,cx,cz,angle)
    for x in (-2.45,0.,2.45):
        box('面向道路的窗',x,1.62,-1.835,1.85,1.24,.08,'#60818a')
    verts=[pos(x,2.94,z) for x,z in ((-4.35,-2.08),(4.35,-2.08),(4.35,2.08),(-4.35,2.08))]
    verts.extend([pos(-2.73,3.8,0),pos(2.73,3.8,0)])
    s.mesh('南门值守亭低坡顶',verts,[(1,0,4,5),(2,1,5),(3,2,5,4),(0,3,4)],'#b06a54')


def north_gate(s,w,d,h):
    stone,trim='#b4ada0','#c7c1b4'
    x=w*.355
    s.cyl('西侧主塔基座',x,.25,0,3.78,.50,trim,16)
    # The west tower tapers slightly; the finished tower has a flat crown.
    layers=[(.45,3.65),(h*.27,3.45),(h*.32,3.32),(h*.78,2.91),(h*.90,2.85),(h,2.65)]
    v=[]
    for level,r in layers:
        v.extend((x+r*math.cos(i*math.tau/20),level,r*math.sin(i*math.tau/20)) for i in range(20))
    f=[(j*20+i,(j+1)*20+i,(j+1)*20+(i+1)%20,j*20+(i+1)%20) for j in range(len(layers)-1) for i in range(20)]
    f.append(tuple(reversed(range(20*(len(layers)-1),20*len(layers)))))
    s.mesh('鱼山旧校门意象石塔',v,f,stone)
    from qd_gate_details import north_tower
    north_tower(s,x,layers)
    for y,r,t in [(h*.28,3.5,.35),(h*.32,3.41,.16),(h*.80,3.06,.25),(h*.91,2.95,.28)]:
        s.cyl('环形分层檐口',x,y,0,r,t,trim,20)
    s.cyl('西塔收分顶缘',x,h-.24,0,2.72,.28,trim,32)
    s.cyl('塔顶封闭盖板',x,h-.034,0,2.58,.065,'#a9a598',32)
    sx=-w*.34
    s.box('东侧石砌传达室',sx,2.42,0,13.5,4.84,6.55,stone)
    s.box('传达室平檐',sx,4.98,0,14.0,.40,7.07,trim)
    for xx in (-4.7,-1.6,1.6,4.7):
        arch(s,'传达室石拱窗',sx+xx,.52,3.29,1.08,2.58,'#3e535a')
    for side in (-1,1):
        for i in range(3):
            s.cyl('入口石桩',side*(4.5+i*1.0),.35,2.8,.14,.70,'#b4b4aa',10)


def beam(s,name,a,b,r,material,sides=6):
    ux,uy,uz=(b[i]-a[i] for i in range(3))
    length=math.sqrt(ux*ux+uy*uy+uz*uz)
    if length<.0001:
        return
    ux,uy,uz=ux/length,uy/length,uz/length
    flat=math.hypot(ux,uz)
    vx,vy,vz=(uz/flat,0,-ux/flat) if flat>.0001 else (1.,0.,0.)
    wx,wy,wz=uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx
    verts=[]
    for p in (a,b):
        for i in range(sides):
            ct,st=math.cos(i*math.tau/sides)*r,math.sin(i*math.tau/sides)*r
            verts.append((p[0]+vx*ct+wx*st,p[1]+vy*ct+wy*st,p[2]+vz*ct+wz*st))
    faces=[(i,(i+1)%sides,sides+(i+1)%sides,sides+i) for i in range(sides)]
    s.mesh(name,verts,faces,material)


# Cross-sections in ground metres traced on the georeferenced orthophoto.
# (distance south, west roof edge, east roof edge) relative to image origin.
ROOF=[(54,152,152.5),(65,151.8,160),(85,152,165),(115,153,169.5),
      (147,156,176),(173,158,183),(199,163,191),(214,167,198),
      (222,167,201.5),(229,129.5,204),(249,129,211),(270,129,219),
      (293,129,227),(315,129,232.5),(337,129,234.3),(358,129,233),
      (382,129,228),(406,129.3,220),(429,129.5,209),(449,130,196),
      (466,132,179),(479,139,160),(484,147,151)]


def arena(s,w,d,h):
    def ground(raw_x,raw_z):
        return (raw_x-181.5)*w/109,(raw_z-269)*d/430
    def roof_point(raw_x,raw_z):
        x,z=ground(raw_x,raw_z)
        crest=math.exp(-((raw_z-322)/137)**2)
        across=max(0,1-((raw_x-163)/74)**2)
        return x,h*(.43+.38*crest+.14*crest*across),z
    def part(name,sections,start,end,color):
        v=[]
        for rz,l,r in sections:
            for u in (start,end):
                v.append(roof_point(l+(r-l)*u,rz))
        s.mesh(name,v,[(2*i,2*i+2,2*i+3,2*i+1) for i in range(len(sections)-1)],color)
    for band in range(12):
        part('白色金属帆形屋面板',ROOF,band/12,(band+1)/12,('#e5e7e3','#f0f1e9','#e9ece9')[band%3])
    # The covered north walkway sweeps along the east side of the blue track.
    for side in (1,2):
        points=[roof_point(row[side],row[0]) for row in ROOF]
        v=[p for pt in points for p in (pt,(pt[0],pt[1]-.78,pt[2]))]
        s.mesh('银白屋檐围边',v,[(i*2,i*2+1,i*2+3,i*2+2) for i in range(len(points)-1)],'#c6cbd1')
    for rz,l,r in (ROOF[i] for i in (2,3,4,5,6,7,8)):
        left=roof_point(l+.4,rz)
        right=roof_point(r-.4,rz)
        cx=(left[0]+right[0])/2
        beam(s,'北端斜撑钢柱',(cx-1.2,.05,left[2]+3),left,.36,'#adb9bd')
        beam(s,'北端斜撑钢柱',(cx+1.2,.05,right[2]-3),right,.36,'#adb9bd')
    arena_soffit(s,ROOF,roof_point)
    from qd_video_sport import arcade_skin,approach
    arcade_skin(s,ROOF,roof_point)
    approach(s)
    for rz,l,r in (ROOF[0],ROOF[-1]):
        a=roof_point(l,rz);b=roof_point(r,rz)
        s.mesh('帆形屋面封边',[a,b,(b[0],b[1]-.78,b[2]),(a[0],a[1]-.78,a[2])],[(0,1,2,3)],'#c6cbd1')
    # Tapered curtain wall, with recessed glazing under the sweeping cornice.
    side_rows=ROOF[9:-2]
    for side in (1,2):
        rings=[]
        for rz,l,r in side_rows:
            edge=l+(r-l)*(.10 if side==1 else .9)
            x,top,z=roof_point(edge,rz)
            rings.append((x,top,z))
        for bottom,top,mat in ((.0,.15,'#b9b6a9'),(.15,.46,'#708b92'),(.46,.50,'#d2d6d2'),(.50,.61,'#506d7b'),(.61,.91,'#d5d8d4'),(.91,.98,'#86999b')):
            v=[(x,y*f,z) for x,y,z in rings for f in (bottom,top)]
            s.mesh('弧面分层围护',v,[(i*2,i*2+1,i*2+3,i*2+2) for i in range(len(rings)-1)],mat)
        for (ax,ay,az),(bx,by,bz) in zip(rings,rings[1:]):
            for step in range(3):
                t=step/3
                x,y,z=(a+(b-a)*t for a,b in ((ax,bx),(ay,by),(az,bz)))
                beam(s,'外墙竖梃',(x,y*.14,z),(x,y*.62,z),.115,'#c0c8c5')
    for rz,l,r in (side_rows[0],side_rows[-1]):
        x1,t1,z=roof_point(l+(r-l)*.1,rz)
        x2,t2,_=roof_point(l+(r-l)*.9,rz)
        s.mesh('端墙',[(x1,0,z),(x2,0,z),(x2,t2*.91,z),(x1,t1*.91,z)],[(0,1,2,3)],'#6d8386')
    # Repeated clerestories mark the spine of the built roof in the aerial photographs.
    for i in range(10):
        z0=230+i*16
        u=(i+.75)/10.7
        span=(13+30*math.sin(u*math.pi)**.63)*w/109
        # Each clerestory springs from the measured roof surface at its own
        # x/z, including the sloped eastern part. No end floats in mid-air.
        half_span=span*109/w/2
        vv=[]
        for j in range(17):
            t=j/16;raw_x=164+(2*t-1)*half_span
            x,base,zz=roof_point(raw_x,z0)
            rear=roof_point(raw_x,z0+12.2)
            archh=.22+2.38*math.sin(t*math.pi)
            vv.extend([(x,base+archh,zz),(x,base+.045,zz),(rear[0],rear[1]+.055,rear[2])])
        s.mesh('银白弧面高侧窗顶',vv,[(3*j,3*j+2,3*(j+1)+2,3*(j+1)) for j in range(16)],'#e9ebe8')
        s.mesh('深色高侧窗玻璃',vv,[(3*j,3*j+1,3*(j+1)+1,3*(j+1)) for j in range(16)],'#67808a')
        for j in (0,16):
            i=3*j;s.mesh('高侧窗实心端封',vv,[(i,i+1,i+2)],'#d3d8d5')


def oval(rx,rz,straight,steps=36):
    return [(rx*math.cos(a),center+rz*math.sin(a))
            for center,first in ((straight,0),(-straight,math.pi))
            for a in (first+i*math.pi/steps for i in range(steps+1))]


def horizontal_ring(s,name,outer,inner,y,material):
    n=len(outer)
    v=[(x,y,z) for x,z in outer+inner]
    s.mesh(name,v,[(i,n+i,n+(i+1)%n,(i+1)%n) for i in range(n)],material)


def ground_disk(s,name,ring,y,material):
    v=[(0,y,0)]+[(x,y,z) for x,z in ring]
    s.mesh(name,v,[(0,(i+1)%len(ring)+1,i+1) for i in range(len(ring))],material)


def pitch(s,w,d,blue):
    outer_r=w*.49
    end_r=w*.48
    straight=d*.5-end_r
    outer=oval(outer_r,end_r,straight)
    ground_disk(s,'运动场外缘',outer,.14,'#a4aba2' if blue else '#b47661')
    ground_disk(s,'塑胶跑道',oval(outer_r-.9,end_r-.9,straight),.20,'#75b9d6' if blue else '#a34e4c')
    for i in range(9):
        inset=1.4+i*1.24
        horizontal_ring(s,'各道分界线',oval(outer_r-inset,end_r-inset,straight),oval(outer_r-inset-.115,end_r-inset-.115,straight),.235,'#f3f1db')
    sw,sd=68.,105.
    for band in range(12):
        s.box('草坪修剪纹',0,.249,(band-5.5)*sd/12,sw,.054,sd/12,(('#518346','#60974e') if blue else ('#447d43','#659c49'))[band%2])
    chalk='#f7f3de'; y=.29
    def stripe(x,z,dx,dz):
        s.box('足球场标线',x,y,z,dx,.027,dz,chalk)
    for side in (-1,1):
        stripe(side*sw/2,0,.18,sd)
        stripe(0,side*sd/2,sw,.18)
        for size,end in ((40.32,16.5),(18.32,5.5)):
            stripe(0,side*(sd/2-end),size,.17)
            for sign in (-1,1):
                stripe(sign*size/2,side*(sd/2-end/2),.17,end)
        cz=side*sd/2
        for sx in (-3.66,3.66):
            beam(s,'足球门柱',(sx,.28,cz),(sx,2.72,cz),.075,chalk)
            beam(s,'球门侧撑',(sx,2.72,cz),(sx,.30,cz+side*1.85),.06,chalk)
        beam(s,'足球门横梁',(-3.66,2.72,cz),(3.66,2.72,cz),.075,chalk)
        for lane in range(8):
            # Staggered starts on the eastern straight.
            off=2+lane*1.24
            stripe(outer_r-off,side*(straight-4.2)-lane*1.25,1.18,.14)
    stripe(0,0,sw,.18)
    horizontal_ring(s,'足球中圈',[(9.22*math.cos(a*math.tau/72),9.22*math.sin(a*math.tau/72)) for a in range(72)],[(9.03*math.cos(a*math.tau/72),9.03*math.sin(a*math.tau/72)) for a in range(72)],y+.02,chalk)
    for z in (0,-sd/2+11,sd/2-11):
        s.cyl('中点与罚球点',0,y+.018,z,.19,.035,chalk,12)


def dining(s,w,d,h):
    brick='#bf725a'; cream='#d8c29f'; red='#c77451'
    s.box('外围石质勒脚',0,h*.044,0,w,h*.088,d,'#b7ac95')
    s.box('三层餐厅主体',0,h*.45,0,w-.9,h*.74,d-.9,brick)
    for side in (-1,1):
        z=side*(d*.5-.32)
        for bay in range(16):
            x=(bay-7.5)*w/16.7
            if abs(x)<w*.105:
                continue
            arch(s,'临街拱形餐窗',x,.72,z,3.7,h*.32,'#48656b')
            for level in (.47,.69):
                s.box('二三层餐厅窗',x,h*level,z,3.18,h*.15,.16,'#60818a')
            s.box('窗间砖柱',x+2.34,h*.415,z,.51,h*.67,.35,'#cb846d')
        s.box('直通腰檐',0,h*.62,z,w,.24,.35,cream)
        s.box('檐口线',0,h*.81,z,w+.42,.38,.55,'#decaab')
    for side in (-1,1):
        x=side*(w/2-.38)
        for z in (-d*.36,-d*.25,-d*.14,-d*.03,d*.08,d*.19,d*.30,d*.41):
            for y in (.23,.48,.69):
                s.box('端面窗',x,h*y,z,.26,h*.157,2.9,'#64828a')
    roof_y=h*.815
    # Orthophoto: four pitched runs meet at true diagonally mitered hips.
    # The central rectangle is a closed lower service roof, not an open court.
    s.box('下凹设备屋面',0,roof_y,0,w-2,.30,d-2,'#96958b')
    tiled_ring(s,w+.48,d+.48,roof_y+.17,h*.17,w*.827,d*.716,w*.687,d*.415,red)
    for sign in (-1,1):
        s.box('内檐泛水压顶',0,roof_y+.38,sign*d*.2075,w*.687,.20,.28,'#b4ab99')
        s.box('内檐泛水压顶',sign*w*.3435,roof_y+.38,0,.28,.20,d*.415,'#b4ab99')
    for i in range(2):
        s.box('院内低矮设备间',-w*.21+i*.10*w,roof_y+.66,d*.07,8.0,.92,4.5,'#afada0')
    for i in range(6):
        s.box('短排屋面采光带',-w*.205+i*w*.040,roof_y+.44,-d*.105,3.5,.46,3.2,'#9baaa4')
    for i in range(3):
        s.box('局部机房与排风',w*.14+i*.055*w,roof_y+.80,-d*.04,4.3,1.20,3.5,'#bab9a9')
    for side in (-1,1):
        z=side*(d*.5+.18)
        s.box('入门赭石色门框',0,h*.38,z,w*.169,h*.73,1.4,'#b06a54')
        arch(s,'贯通入口玻璃拱窗',0,.3,z+side*.712,w*.115,h*.61,'#567d8a')
        for x in (-4,-2,0,2,4):
            s.box('入口玻璃分格竖挺',x,h*.26,z+side*.73,.12,h*.44,.045,'#3f5257')
        for y in (2.7,5.1):
            s.box('入口玻璃横挺',0,y,z+side*.742,w*.11,.12,.05,'#4b6065')
        for j in range(3):
            s.box('入口石阶',0,.095+.095*j,z+side*(2.02-j*.40),w*.16,.19+j*.19,1.25,'#c0b7a5')
        # The photo confirms the lettering but does not locate which entrance bears it.


def plaza(s,w,d,h):
    s.box('中轴浅色石材步道',0,.06,0,w,.12,d,'#cac7b6')
    # Two pedestrian lines frame the principal green east-west axis.
    for i,(start,end) in enumerate(((-.485,-.23),(-.207,.045),(.067,.281))):
        s.box('中央草坪',w*(start+end)/2,.14,0,w*(end-start),.14,d*.54,('#8faa70','#93ac72')[i%2])
    from qd_video_gate import axis
    axis(s,w,d)
    for side in (-1,1):
        s.box('树阵植栽带',0,.15,side*d*.425,w,.12,d*.132,'#91a275')
        # Street trees are placed here as shared botanical meshes by qd_planting.
    # The commemorative stone faces the west gate and stands on the planted axis.
    x=-w*.34
    footprint=[(-1.33,-5.64),(-.86,-6.72),(.48,-7.03),(1.24,-5.64),(1.32,5.93),(.24,7.1),(-1.21,6.53)]
    levels=[(.3,1.),(1.86,1.),(h,.88)]
    v=[(x+xx*scale,y,zz*scale) for y,scale in levels for xx,zz in footprint]
    n=len(footprint)
    f=[(i+j*n,i+(j+1)*n,(i+1)%n+(j+1)*n,(i+1)%n+j*n) for j in range(2) for i in range(n)]
    f.append(tuple(reversed(range(2*n,3*n))))
    s.mesh('浅色花岗岩校训石',v,f,'#d4caba')
    # The school photograph looks eastward. The traced calligraphy therefore reads
    # left to right along +Z, with its front pointing west. Fit each vertex to the
    # actual stone face, including the short bevel next to the first character.
    import json
    from pathlib import Path
    source=Path(__file__).resolve().parents[1]/'data'/'校训石手书字形.json'
    glyph=json.loads(source.read_text(encoding='utf-8'))

    class WestStoneFace:
        def mesh(self, name, vertices, faces, material):
            fitted=[]
            for u, letter_y, _ in vertices:
                world_z=u-.30
                scale=1.0 if letter_y<=1.86 else 1-.12*(letter_y-1.86)/(h-1.86)
                local_z=world_z/scale
                intersections=[]
                for (a,b),(c,d) in zip(footprint,footprint[1:]+footprint[:1]):
                    if min(b,d)<=local_z<=max(b,d) and abs(d-b)>1e-10:
                        intersections.append(a+(c-a)*(local_z-b)/(d-b))
                stone_x=x+scale*min(intersections)
                fitted.append((stone_x-.012,letter_y,world_z))
            s.mesh(name,fitted,faces,material)

    relief(WestStoneFace(),'校训石红字·照片手书',0,1.25,0,11.20,1.34,
           glyph['width'],glyph['height'],glyph['mask'],glyph['colour'])


def build(scene,key,w,d,h):
    if key=='way-982199336':
        from qd_video_sport import arch_hall
        return arch_hall(scene,w,d,h)
    if key in ('blue_track','east_track'):
        pitch(scene,w,d,key=='blue_track')
        if key=='east_track':
            from qd_video_track import terraces
            terraces(scene,w,d)
        return True
    fn={'west_gate':west_gate,'north_gate':north_gate,'east_gate':east_gate,'south_gate':south_gate,'song_arena':arena,
        'xiyuan':dining,'yuxian':plaza}.get(key)
    if fn is None:
        return False
    fn(scene,w,d,h)
    return True

