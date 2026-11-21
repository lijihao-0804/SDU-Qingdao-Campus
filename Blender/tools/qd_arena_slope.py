"""Local fine terrain and planting at the sunken southern bend of Song Junfu Arena."""
import math
import numpy as np
from PIL import Image,ImageDraw
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter
import shapely
from shapely.geometry import LineString,Polygon,box
from shapely.affinity import rotate
from shapely.ops import unary_union

from qd_civic import beam
from qd_geometry import Shape
from qd_terrain import Terrain
from qd_spring_surfaces import add_image
import qd_arena_groundflowers as groundflowers

FLOWERS=groundflowers.BED
REFERENCES=["实景参照/校园补拍/体育馆南弯花坡01.jpg","实景参照/校园补拍/体育馆南弯花坡02.jpg",
            "实景参照/校园补拍/体育馆南弯与馆侧车道.jpg"]
DROP=4.15


def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0.,1.)
    return t*t*(3-2*t)


def smooth_path(points):
    pts=np.asarray(points,dtype=float)
    d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
    t=np.linspace(0,d[-1],math.ceil(d[-1]/.62)+1)
    return np.column_stack([PchipInterpolator(d,pts[:,j])(t) for j in (0,1)])


def plant_image():
    """The fine layer between modelled shoots, with dark leaves between flower heads."""
    n=768;rng=np.random.default_rng(196174)
    def field(sigma):
        f=gaussian_filter(rng.normal(size=(n,n)),sigma,mode="wrap")
        return (f-f.mean())/max(f.std(),.0001)
    wide=field(30);speck=field(2.2);fine=field(.8)
    ratio=np.clip(.71+.22*wide+.15*speck+.10*fine,.03,1)
    leaf=np.array([80.,92.,52.]);pink=np.array([214.,44.,145.])
    base=leaf+(pink-leaf)*ratio[:,:,None]+(3*wide+4*fine)[:,:,None]
    im=Image.fromarray(np.uint8(np.clip(base,0,255)));draw=ImageDraw.Draw(im)
    colours=np.array([[223,61,154],[237,86,170],[194,42,127],[241,108,185],[204,54,145],[228,63,162]])
    for _ in range(11500):
        x,z=rng.integers(0,n,2)
        if rng.random()>.2+.8*ratio[z,x]:continue
        color=colours[rng.integers(len(colours))]+rng.normal(0,5)
        radius=rng.uniform(1.6,3.4);size=radius*.53;phase=rng.random()*math.tau
        for dx in (0,n if x<6 else -n if x>n-7 else 0)[:2 if x<6 or x>n-7 else 1]:
            for dz in (0,n if z<6 else -n if z>n-7 else 0)[:2 if z<6 or z>n-7 else 1]:
                for k in range(5):
                    a=phase+k*math.tau/5
                    px=x+dx+.58*radius*math.cos(a);pz=z+dz+.58*radius*math.sin(a)
                    draw.ellipse((px-size,pz-size,px+size,pz+size),fill=tuple(np.clip(color,0,255).astype(int)))
                draw.point((x+dx,z+dz),fill=(146,80,73))
    return im


class ArenaSlope:
    def __init__(self,x,z,base):
        self.x,self.z,self.base=x,z,base
        # The southern canopy ends at local Z 215. The lane goes round its
        # southwest corner, then joins the actual mapped service road to the east.
        local=[(-68,133),(-65,146),(-60,164),(-57,179),(-53,190),(-47,199),
               (-39,205),(-25,209),(-9,209),(8,205),(25,195),(44,185),(59,178),
               (-34.09-x,861.05-z)]
        pts=smooth_path([(x+u,z+v) for u,v in local])
        self.line=LineString(pts)
        self.s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
        self.length=self.s[-1];self.pts=pts
        tx=np.gradient(pts[:,0],self.s);tz=np.gradient(pts[:,1],self.s)
        length=np.hypot(tx,tz);self.nx=-tz/length;self.nz=tx/length
        self.drive=self.line.buffer(3.06,cap_style="flat",join_style="round")
        self.upper_path=self.ribbon(12,self.length-27,18.8,21.05)
        from qd_civic import ROOF
        rows=ROOF[9:-2]
        built=Polygon([(x+l+(r-l)*.10-181.5,z+rz-269) for rz,l,r in rows]+
                      [(x+l+(r-l)*.90-181.5,z+rz-269) for rz,l,r in reversed(rows)])
        access=self.ribbon(29,self.length-46,-15.8,-3.27).difference(built)
        self.lower_walk=self.ribbon(13,self.length-21,-5.32,-3.27).union(access)
        self.reserve=self.ribbon(0,self.length,-6.5,22.6).union(self.lower_walk).buffer(.5)
        self.region=self.reserve.union(self.ribbon(0,self.length,-26,30)).buffer(4)
        flower=self.ribbon(20,self.length-43,
                           lambda s:3.95+.38*np.sin(.091*s)+.23*np.sin(.29*s)+.13*np.cos(1.23*s),
                           lambda s:17.83+.46*np.sin(.115*s+.8)+.22*np.cos(.55*s)+.11*np.sin(1.41*s))
        # Leave irregular bare clumps and keep the full upper walk passable.
        pockets=[]
        for station,off,r1,r2,angle in [(24,16,5,2.3,35),(39,14.8,3.7,1.6,60),(52,7.2,2.1,.8,30),
                         (64,16.6,3,.9,65),(71,10,2.6,.68,30),(84,15.2,3.8,1.4,10),
                         (98,8.4,3,1.1,-10),(112,15.8,2.1,1.2,18),(123,7.3,3.6,1.9,-30)]:
            px,pz=self.xy(station,off)
            t=np.linspace(0,math.tau,42,endpoint=False)
            rad=.72+.11*np.sin(3*t+station)+.14*np.cos(5*t+off)+.055*np.sin(8*t)
            patch=rotate(Polygon(np.column_stack((px+r1*rad*np.cos(t),pz+r2*rad*np.sin(t)))),angle)
            pockets.append(patch)
        self.flower_ground=flower
        self.flowers=flower.difference(unary_union(pockets))
        self.grid=None

    def xy(self,s,offset):
        x=np.interp(s,self.s,self.pts[:,0])+np.interp(s,self.s,self.nx)*offset
        z=np.interp(s,self.s,self.pts[:,1])+np.interp(s,self.s,self.nz)*offset
        return x,z

    def ribbon(self,start,end,left,right):
        s=np.linspace(start,end,max(3,int((end-start)/.70)+1))
        a=np.column_stack(self.xy(s,left(s) if callable(left) else left))
        b=np.column_stack(self.xy(s,right(s) if callable(right) else right))
        return Polygon(np.concatenate((a,b[::-1]))).buffer(0)

    def grade(self,terrain):
        # Snap to both the 42 m source grid and its diagonals at the patch edges.
        # The 1.5 m subgrid supports the actual road cut, rather than covering the
        # original flat plateau with an overlapping surface.
        old_y,old_skin=terrain.y,terrain.skin
        small=Terrain.__new__(Terrain);small.step=terrain.step/28
        x0,z0,x1,z1=self.region.bounds;st=terrain.step
        x0=terrain.x0+math.floor((x0-terrain.x0)/st)*st
        z0=terrain.z0+math.floor((z0-terrain.z0)/st)*st
        x1=terrain.x0+math.ceil((x1-terrain.x0)/st)*st
        z1=terrain.z0+math.ceil((z1-terrain.z0)/st)*st
        small.x0=x0;small.z0=z0
        xs=np.arange(x0,x1+small.step/2,small.step);zs=np.arange(z0,z1+small.step/2,small.step)
        xx,zz=np.meshgrid(xs,zs);old=np.array([[old_y(x,z) for x in xs] for z in zs])
        pts=shapely.points(xx,zz)
        stations=shapely.line_locate_point(self.line,pts)
        center_x,center_z=self.xy(stations,0)
        dx=xx-center_x;dz=zz-center_z
        offset=dx*np.interp(stations,self.s,self.nx)+dz*np.interp(stations,self.s,self.nz)
        fade=smooth(3,35,stations)*(1-smooth(self.length-45,self.length-3,stations))
        across=smooth(-26,-15,offset)*(1-smooth(4.05,18.7,offset))
        # Both the asphalt and the adjacent walk remain near-level laterally.
        # Taper back to the imported DEM before the two road junctions.
        crest_x,crest_z=self.xy(self.s,19.8)
        crest=np.array([old_y(x,z) for x,z in zip(crest_x,crest_z)])
        cut=np.interp(stations,self.s,crest)-DROP
        weight=fade*across
        small.heights=old+(cut-old)*weight
        # Bank immediately behind the short retaining face, visible at the
        # uphill end of the service lane. It merges back into the flower slope.
        end_bank=smooth(11,19,stations)*(1-smooth(32,42,stations))
        small.heights+=1.57*end_bank*smooth(4.3,6.15,offset)*(1-smooth(7.25,13.6,offset))
        rect=box(x0,z0,x1,z1)
        def elevation(x,z):
            return small.y(x,z) if x0<=x<x1 and z0<=z<z1 else old_y(x,z)
        def skin(shape,geom,material,lift=0):
            if geom.is_empty:return
            if not geom.intersects(rect):
                old_skin(shape,geom,material,lift)
                return
            small.skin(shape,geom.intersection(rect),material,lift)
            other=geom.difference(rect)
            if not other.is_empty:old_skin(shape,other,material,lift)
        terrain.y=elevation;terrain.skin=skin;self.grid=small
        self.max_cut=float(np.max(old-small.heights))
        # An existing arena origin must keep its pre-cut base.
        assert abs(terrain.y(self.x,self.z)-self.base)<.01

    def _basement(self,shape,terrain):
        # Follow the already modelled tapered curtain wall at its real X/Z,
        # extending down only where the road cut exposes the plinth.
        from qd_civic import ROOF
        local=[(self.x+l+(r-l)*.1-181.5,self.z+rz-269) for rz,l,r in ROOF[16:-2]]
        rx,l,r=ROOF[-3]
        local.extend([(self.x+l+(r-l)*.9-181.5,self.z+rx-269)])
        path=LineString(local)
        s=np.linspace(0,path.length,math.ceil(path.length/2)+1)
        pts=[path.interpolate(v) for v in s]
        for a,b in zip(pts,pts[1:]):
            low_a=min(self.base-.015,terrain.y(a.x,a.y)-.14)
            low_b=min(self.base-.015,terrain.y(b.x,b.y)-.14)
            if min(low_a,low_b)>self.base-.22:continue
            shape.mesh("随开挖地形接到场馆基脚",[(a.x,low_a,a.y),(b.x,low_b,b.y),(b.x,self.base+.012,b.y),(a.x,self.base+.012,a.y)],[(0,1,2,3)],"#bab7a8")
        for station in np.arange(3,path.length-1,4.3):
            p=path.interpolate(station);p2=path.interpolate(station+.2)
            dx,dz=p2.x-p.x,p2.y-p.y;norm=math.hypot(dx,dz)
            nx,nz=-dz/norm,dx/norm;angle=-math.atan2(dz,dx)
            ground=terrain.y(p.x+nx*.4,p.y+nz*.4)
            if self.base-ground<2.2:continue
            shape.box("下层石柱",p.x+nx*.22,(ground+self.base)/2,p.y+nz*.22,.38,self.base-ground,.42,"#a9aaa0",angle)
            q=path.interpolate(min(path.length,station+1.96))
            shape.box("低层横窗",q.x+nx*.035,self.base-.92,q.y+nz*.035,1.12,.63,.072,"#536166",angle)

    def _wall(self,s,terrain):
        # A short retaining face closes the uphill end of the curve, beyond
        # the planted middle. Its height tapers into the sloping ground.
        stations=np.linspace(11,42,42)
        def pair(at,off):
            x,z=self.xy(at,off);bot=terrain.y(x,z)+.04
            peak=1.83*float(smooth(11,19,at)*(1-smooth(32,42,at)))
            return (x,bot,z),(x,bot+max(.10,peak),z)
        for a,b in zip(stations,stations[1:]):
            aa,at=pair(a,4.13);ba,bt=pair(b,4.13)
            _,ai=pair(a,4.48);_,bi=pair(b,4.48)
            s.mesh("灰色挡墙正面",[aa,ba,bt,at],[(0,1,2,3)],"#83847c")
            s.mesh("挡墙压顶",[at,bt,bi,ai],[(0,1,2,3)],"#adae9f")
        for st in (20,25,31):
            x,z=self.xy(st,4.16);g=terrain.y(x,z)
            s.box("挡墙竖缝",x,g+.78,z,.035,1.35,.08,"#72746e")

    def build(self,scene,terrain,catalog):
        planter,cushion_grid=groundflowers.cushions(self,terrain)
        scene.node(planter.name,shape=planter,kind="ground",arenaSouth="flowers",arenaPlantPart="cushions")
        groundflowers.soil(scene,self,terrain)
        planting_detail=groundflowers.scatter(scene,self,cushion_grid)
        groundflowers.bind_colours(scene)
        fine_petals=plant_image()
        tex=add_image(scene,"南弯地被 · 玫红花冠与春草",fine_petals,"JPEG",True)
        mat=scene.doc["materials"][scene.mat(FLOWERS)]
        mat["pbrMetallicRoughness"].update(baseColorFactor=[1,1,1,1],baseColorTexture=tex,roughnessFactor=.94)
        rgb=np.asarray(fine_petals,dtype=float)
        micro=gaussian_filter((rgb[:,:,0]-rgb[:,:,1])/185.,.72,mode="wrap")
        du=(np.roll(micro,-1,1)-np.roll(micro,1,1))*.82
        dv=(np.roll(micro,-1,0)-np.roll(micro,1,0))*.82
        normals=groundflowers.normalise(np.stack((-du,dv,np.ones_like(du)),axis=-1))
        normal_img=Image.fromarray(np.uint8(np.clip(normals*.5+.5,0,1)*255))
        mat["normalTexture"]=add_image(scene,"南弯地被 · 细花瓣与叶间凹隙",normal_img,"PNG",True)
        sidewalk=Shape("体育馆南端 · 下层沿馆步道与缘石")
        terrain.skin(sidewalk,self.lower_walk,"#b6b4a7",.158)
        terrain.skin(sidewalk,self.ribbon(10,self.length-12,3.08,3.39),"#ded8c6",.235)
        terrain.skin(sidewalk,self.ribbon(12,self.length-17,-3.37,-3.08),"#dbd6c6",.236)
        scene.node(sidewalk.name,shape=sidewalk,kind="ground",arenaSouth="walk")
        walls=Shape("体育馆南弯 · 挡墙与下层立面")
        self._basement(walls,terrain);self._wall(walls,terrain)
        scene.node(walls.name,shape=walls,kind="landscape",arenaSouth="retaining")
        plants=Shape("体育馆花坡 · 坡顶疏树与圆灯")
        rng=np.random.default_rng(41571)
        for st in np.linspace(19.5,33.5,6):
            x,z=self.xy(st,6.17);radius=float(rng.uniform(.48,.65));y=terrain.y(x,z)+radius*.71
            rings=[[(x+radius*math.sin(ph)*math.cos(k*math.tau/10),y+radius*.91*math.cos(ph),z+radius*math.sin(ph)*math.sin(k*math.tau/10))
                    for k in range(10)] for ph in np.linspace(.015,math.pi-.015,7)]
            plants.mesh("挡墙上修剪灌木",[v for ring in rings for v in ring],[(i*10+k,i*10+(k+1)%10,(i+1)*10+(k+1)%10,(i+1)*10+k) for i in range(6) for k in range(10)],"#668253")
        # Grounded cycle parking on the building side of the lower walk.
        for st in (47,48.3,49.6,51.2,54,55.6,57,58.5,66,67.4,68.8,70.5,72,74):
            x,z=self.xy(st,-7.1);y=terrain.y(x,z)+.16
            a=float(np.interp(st,self.s,np.unwrap(np.arctan2(self.nz,self.nx))))+.28+rng.uniform(-.08,.08)
            dx,dz=math.cos(a),math.sin(a)
            def pt(u,h,v=0):
                return (x+u*dx-v*dz,y+h,z+u*dz+v*dx)
            for axle in (-.51,.51):
                pts=[pt(axle+.29*math.cos(t),.29+.29*math.sin(t)) for t in np.linspace(0,math.tau,13)]
                for p,q in zip(pts,pts[1:]):beam(plants,"停放车辆轮胎",p,q,.028,"#434a48",5)
            frame=("#526b6f","#916e64","#8f9792","#52635d")[int(rng.integers(4))]
            for p,q in ((pt(-.51,.29),pt(-.12,.66)),(pt(-.12,.66),pt(.05,.32)),
                        (pt(.05,.32),pt(.41,.73)),(pt(.41,.73),pt(.51,.29)),(pt(-.12,.66),pt(-.16,.82))):
                beam(plants,"车架",p,q,.034,frame,6)
            beam(plants,"车把",pt(.41,.82,-.23),pt(.41,.82,.23),.027,"#545c58",5)
            sx,sy,sz=pt(-.16,.83)
            plants.box("坐垫",sx,sy,sz,.22,.065,.17,"#484c45",-a)
        for j,st in enumerate((26,41,55,72,87,102)):
            x,z=self.xy(st,16.5+float(rng.uniform(-.55,.55)));y=terrain.y(x,z)+.035
            h=float(rng.uniform(4.8,6.6));lean=rng.uniform(-.30,.3,2)
            beam(plants,"花坡疏树树干",(x,y,z),(x+lean[0],y+h*.78,z+lean[1]),.092,"#716e58",7)
            for k in range(9):
                a=(k*2.40+j*.72);level=.44+.028*k
                org=(x+lean[0]*level,y+h*level,z+lean[1]*level)
                reach=rng.uniform(.72,1.35)*(1-.23*(k/9))
                mid=(org[0]+math.cos(a)*reach*.57,org[1]+h*.15,org[2]+math.sin(a)*reach*.57)
                tip=(org[0]+math.cos(a)*reach,org[1]+h*rng.uniform(.27,.43),org[2]+math.sin(a)*reach)
                beam(plants,"春季枝干",org,mid,.034,"#756f5b",6)
                beam(plants,"梢枝",mid,tip,.016,"#7c755c",5)
                b=a+.59
                twig=(mid[0]+math.cos(b)*.44,mid[1]+.54,mid[2]+math.sin(b)*.44)
                beam(plants,"嫩枝",mid,twig,.012,"#7c755c",5)
        for st in (31,79,110):
            x,z=self.xy(st,18.30);y=terrain.y(x,z)+.04
            plants.cyl("银灰灯柱",x,y+2.30,z,.073,4.6,"#aab1a9",10)
            for i in range(3):
                a=math.tau*i/3+.2;xb=x+.46*math.cos(a);zb=z+.46*math.sin(a)
                beam(plants,"圆灯分枝",(x,y+3.95,z),(xb,y+4.33,zb),.04,"#b2b8ad",6)
                radius=.19
                rings=[[(xb+radius*math.sin(phi)*math.cos(t*math.tau/10),y+4.49+radius*math.cos(phi),zb+radius*math.sin(phi)*math.sin(t*math.tau/10)) for t in range(10)] for phi in np.linspace(.001,math.pi-.001,8)]
                plants.mesh("乳白圆灯",[v for row in rings for v in row],[(r*10+k,r*10+(k+1)%10,(r+1)*10+(k+1)%10,(r+1)*10+k) for r in range(7) for k in range(10)],"#ede4ce")
        scene.node(plants.name,shape=plants,kind="landscape",arenaSouth="furniture")
        # From the higher west-side path, the pink bank fills the foreground;
        # the lower access road turns round the arena on the right.
        def lift(st,off,h):
            px,pz=self.xy(st,off);return [round(float(px),3),round(terrain.y(px,pz)+h,3),round(float(pz),3)]
        eye=lift(66,18.9,1.78);target=lift(42,-6.9,1.84)
        entry=dict(key="arena-flower-slope",aliases=["体育馆花海","体育馆花坡","宋君复体育馆南弯","下沉车道"],name="体育馆南弯 · 花坡与下沉车道",group="春日花木",
                   x=target[0],y=target[1],z=target[2],h=3,r=38,
                   viewpoint=dict(eye=eye,target=target,fov=55),
                   note="从坡顶步道沿玫红花海望向馆侧下层出入口。弯道、灰色挡墙、稀疏树与路灯据校园补拍；高差、范围和花种均为影像概化。")
        if not any(p["key"]==entry["key"] for p in catalog):catalog.append(entry)
        sections=[]
        for st in (40,58,76,92,108):
            hi=lift(st,19.8,0);lo=lift(st,0,0)
            sections.append({"stationM":st,"upper":hi,"lower":lo,"reliefM":round(hi[1]-lo[1],3)})
        assert 3.4<max(row["reliefM"] for row in sections)<5.5
        return dict(key=entry["key"],photoReferences=REFERENCES,terrainStepMetres=self.grid.step,
                    maximumTerrainCutM=round(self.max_cut,3),flowerAreaM2=round(self.flowers.area,2),
                    lowerRoadWidthM=6.12,upperWalkWidthM=2.25,terrainSections=sections,plantingDetail=planting_detail,
                    viewpoint=entry["viewpoint"],method="局部细分原地形后连续下切，原始馆体基准保留。屋檐南端、储才路接点与原航片定位；构造和高差按用户照片估计。")


def install(terrain,specs):
    _,_,x,z,_=next(q for q in specs if q[1]["key"]=="song_arena")
    site=ArenaSlope(x,z,terrain.y(x,z))
    site.grade(terrain)
    terrain.arena_slope=site
    return site
