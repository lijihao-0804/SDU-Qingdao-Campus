"""Editable exterior meshes for four landmarks on the Shandong University Qingdao campus.

Local +Y is up and +Z faces the principal elevation. Dimensions are metres.
Source notes are in ../data/landmarks_sources.json.
"""
from math import cos, sin, pi
import qd_video_landmarks as footage
from qd_public_roofs import museum_roofs, ring_volume

SPECS = [
    dict(key="library", name="青岛校区图书馆", aliases=["图书馆", "山东大学青岛校区图书馆"],
         w=96.0, d=82.0, h=66.3, yaw=-pi/2, lon=120.68400395, lat=36.36617785,
         osm=970257674, replaces=[970257674, "图书馆"],
         source="https://library.sdu.edu.cn/branch/view/17.html"),
    dict(key="museum", name="山东大学博物馆（青岛）", aliases=["博物馆", "山东大学青岛校区博物馆"],
         w=118.0, d=105.0, h=41.7, yaw=pi, lon=120.68280425, lat=36.36088545,
         osm=970257675, replaces=[970257675, "博物馆"],
         source="https://museum.sdu.edu.cn/info/1009/6878.htm"),
    dict(key="zhensheng", name="振声苑", aliases=["公共教学楼", "振声苑东楼", "振声苑南楼", "振声苑西楼", "振声苑北楼"],
         w=122.0, d=138.0, h=21.0, yaw=0.0, lon=120.68170955, lat=36.36268175,
         osm=868015924, replaces=[13110947, 868015924, 975037000, "振声苑"],
         source="https://www.view.sdu.edu.cn/info/1003/46267.htm"),
    dict(key="huagang", name="华岗苑", aliases=["华岗苑东楼", "华岗苑南楼", "华岗苑西楼", "华岗苑北楼"],
         w=125.0, d=124.0, h=22.0, yaw=0.0, lon=120.68171925, lat=36.364477,
         osm=868015925, replaces=[13110946, 868015925, 975037001, "华岗苑"],
         source="https://www.law.sdu.edu.cn/info/1100/9528.htm"),
]

# Source photos show dry-hung warm stone, patinated copper and opaque deep glazing.
STONE="#D2B89B"
LIGHT="#E6D2B5"
CORNICE="#F0DEC0"
SHADE="#AE937B"
SILL="#D6C5A9"
GLAZING="#526D78"
DEEP="#304852"
METAL="#455354"
TILE="#974E45"
REDTILE="#A45E53"
WHITE="#E6E4DA"
PALE="#CECDC6"

class Parts:
    """Batch coplanar details by building part and finish, preserving useful edit groups."""
    def __init__(self, scene, scales):
        self.scene, self.scales, self.parts = scene, scales, {}
        self.frame(0, 0, 0)

    def frame(self, x, z, yaw):
        self.x, self.z, self.c, self.s = x, z, cos(yaw), sin(yaw)

    def convert(self, xyz):
        x, y, z = xyz
        sx, sy, sz = self.scales
        return ((self.x + self.c*x + self.s*z)*sx, y*sy,
                (self.z - self.s*x + self.c*z)*sz)

    def poly(self, group, mat, pts):
        vs, fs = self.parts.setdefault((group,mat), ([],[]))
        off = len(vs)
        vs.extend(self.convert(p) for p in pts)
        fs.extend((off, off+k, off+k+1) for k in range(1, len(pts)-1))

    def rect(self, group, mat, x,y,z, w,h):
        self.poly(group,mat,[(x-w/2,y-h/2,z),(x+w/2,y-h/2,z),
                             (x+w/2,y+h/2,z),(x-w/2,y+h/2,z)])

    def cube(self, group, mat, x,y,z, w,h,d):
        x0,x1=x-w/2,x+w/2
        y0,y1=y-h/2,y+h/2
        z0,z1=z-d/2,z+d/2
        lower=[(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)]
        upper=[(a,y1,c) for a,b,c in lower]
        self.poly(group,mat,lower)
        self.poly(group,mat,upper[::-1])
        for i in range(4):
            j=(i+1)%4
            self.poly(group,mat,[lower[i],upper[i],upper[j],lower[j]])

    def roof(self, group,mat,x,z,w,d,lo,hi,topw,topd,deck=None):
        """Four hip planes and the upper deck. Distinct ridge strip can be retained."""
        lower=[(x-w/2,lo,z-d/2),(x+w/2,lo,z-d/2),
               (x+w/2,lo,z+d/2),(x-w/2,lo,z+d/2)]
        upper=[(x-topw/2,hi,z-topd/2),(x+topw/2,hi,z-topd/2),
               (x+topw/2,hi,z+topd/2),(x-topw/2,hi,z+topd/2)]
        for i in range(4):
            j=(i+1)%4
            self.poly(group,mat,[lower[i],upper[i],upper[j],lower[j]])
        if topw>0 and topd>0:
            self.poly(group if deck is None else group+" recessed upper deck",deck or mat,upper[::-1])

    def finish(self):
        for (name, mat), (vs, fs) in self.parts.items():
            self.scene.mesh(name, vs, fs, mat)


def glass(b, group, x, y, z, w, h, columns=2, rows=2, color=GLAZING):
    # Offset layers by centimetres and give frames physical thickness only where visible.
    b.rect(group+" frames",METAL,x,y,z,w,h)
    border=min(.14,w*.05,h*.05)
    cellw=(w-2*border)/columns
    cellh=(h-2*border)/rows
    for i in range(columns):
        for j in range(rows):
            b.rect(group+" glazing",color,x+(i-(columns-1)/2)*cellw,
                   y+(j-(rows-1)/2)*cellh,z+.024,cellw-.075,cellh-.075)


def arch(b, group, x,z,width, sill, spring, trim):
    """Rounded glazed opening, recessed face, radial stone arch and springing jambs."""
    r=width/2
    b.rect(group+" doors",DEEP,x,(spring+sill)/2,z,width,spring-sill)
    for i in range(18):
        a=i*pi/18
        c=(i+1)*pi/18
        p=(x+r*cos(a),spring+r*sin(a),z)
        q=(x+r*cos(c),spring+r*sin(c),z)
        b.poly(group+" fanlight",GLAZING,[(x,spring,z),p,q])
        b.poly(group+" voussoirs",CORNICE,[(p[0],p[1],z+.1),
               (x+(r+trim)*cos(a),spring+(r+trim)*sin(a),z+.1),
               (x+(r+trim)*cos(c),spring+(r+trim)*sin(c),z+.1),(q[0],q[1],z+.1)])
    for s in (-1,1):
        b.cube(group+" jambs",LIGHT,x+s*(r+trim/2),(spring+sill)/2,z,
               trim,spring-sill,.35)
    b.rect(group+" door frames",METAL,x,(spring+sill)/2,z+.04,.12,spring-sill)
    b.rect(group+" transoms",METAL,x,spring-.075,z+.05,width,.15)


def library(b):
    # Cross-plan shoulders and distinct recessed top course visible from the south.
    b.cube("Stone mass",STONE,0,23,0,78,46,72.0)
    b.cube("Stone mass",STONE,0,22.7,0,95,45.4,53)
    b.cube("Stone mass",STONE,0,47.6,0,75,4.8,76)
    for side in (-1,1):
        b.cube("Stone mass",STONE,side*35.4,23,0,7.7,46,79.0)
    ring_volume(b,"Attic ring",LIGHT,0,52,0,76.4,9.6,74.2,29.8,30.2)
    for width,height,depth,y in ((79.2,.44,80,45.8),(96,.65,54.2,45.4),
                                  (76,.46,76.8,49.5),(77.5,.64,75,56.8)):
        if y>56:
            ring_volume(b,"Upper ring cornice",CORNICE,0,y,0,width,height,depth,29.8,30.2)
        else:
            b.cube("Cornice courses",CORNICE,0,y,0,width,height,depth)

    for side,yaw in enumerate((0,pi)):
        b.frame(0,0,yaw)
        z=39.53
        footage.library_front(b,side)
        for x in (-31,31):
            for k in range(9):
                glass(b,"Corner windows",x,5.2+4.55*k,z+.30,2.9,2.7)
        for x in (-22.5,-13.5,-4.5,4.5,13.5,22.5):
            b.cube("Giant pilasters",LIGHT,x,26.95,z+.33,2.15,30.8,.75)
            b.cube("Pilaster capitals",CORNICE,x,42.20,z+.41,2.70,.82,1.15)
        for y,w in ((11.36,64.6),(12,65.3),(42.32,56.2),(46.14,66)):
            b.cube("Projecting stone bands",CORNICE,0,y,z+.27,w,.40,1)
        for x in (-17,-8.5,0,8.5,17):
            glass(b,"Clerestory",x,44.4,z+.08,4.2,2.2,3,1)
        for x in (-31,-24,-17,17,24,31):
            glass(b,"Attic sash",x,52.98,37.16,3.3,3.68,2,3)
            b.cube("Attic sills",CORNICE,x,51.04,37.2,3.7,.25,.4)
        b.rect("Attic loggia",DEEP,0,53.02,37.17,19.3,4.05)
        for x in (-7.6,-4.1,-.6,2.9,6.4):
            glass(b,"Loggia lights",x,52.94,37.22,3.05,2.92,2,2)
        for sign in (-1,1):
            for xp in (42,45.6):
                for storey in range(9):
                    glass(b,"Flanking tower lights",sign*xp,4.25+4.55*storey,26.54,1.6,2.38,1,2)
        if side==0:
            footage.library_steps(b)
    for yaw in (pi/2,-pi/2):
        b.frame(0,0,yaw)
        for x in (-21,-13.9,-6.9,0,6.9,13.9,21):
            for k in range(9):
                glass(b,"Side paired sash",x,4.13+4.59*k,47.53,3.4,2.76,2,2)
        for x in (-24.8,-17.4,-10.4,-3.5,3.5,10.4,17.4,24.8):
            b.cube("Side pilasters",LIGHT,x,24.1,47.62,.88,41.4,.4)
        for x in (-31,31):
            for k in range(8):
                glass(b,"Return sash",x,5.3+4.8*k,39.05,2.9,2.8,2,2)
        for x in (-29,-21,-13,-5,5,13,21,29):
            glass(b,"Attic side sash",x,53.03,38.23,3.6,3.1)
    footage.library_crown(b)
    b.frame(0,0,0)
    ring_volume(b,"Recessed roof court","#b7b7a7",0,57.05,0,64.2,.36,62.6,29.8,30.2)
    footage.library_lantern(b)


def curtain(b, group, x, y, z, width, height, cols, rows):
    b.rect(group+" frame",DEEP,x,y,z,width,height)
    palette=("#435A65","#526B75","#597480","#47616F")
    pitch=width/cols
    band=height/rows
    for i in range(cols):
        for j in range(rows):
            b.rect(group+" panels",palette[(2*i+j//2+i//3)%4],
                   x+(i-(cols-1)/2)*pitch,y+(j-(rows-1)/2)*band,z+.04,
                   pitch-.10,band-.11)
    for i in range(0,cols+1,2):
        b.cube(group+" mullions",METAL,x-width/2+i*pitch,y,z+.13,.18,height,.34)


def museum(b):
    # The central vessel rises from an elongated, terraced first-floor podium.
    b.cube("Gallery podium",WHITE,0,2.9,-5.40,116,5.8,59.2)
    for side in (-1,1):
        b.cube("Gallery podium",WHITE,side*40,2.9,29.34,34,5.8,11.32)
    b.cube("Plaza terrace",PALE,0,.3,0,118,.6,102)
    for s in (-1,1):
        for i in range(7):
            b.cube("Terrace steps",WHITE,0,.30+(i+1)*.34,s*(49.3-1.48*i),
                   90-2.3*i,(i+1)*.68,2.3)
        for x in (-45,45):
            for j in range(3):
                b.cube("Stepped planter","#B7B4A7",x,.6+j*.58,s*(43.2-1.5*j),
                       15.2-j*1.6,1.2+j*1.16,2.9)
                b.cube("Terrace planting","#748749",x,1.36+j*1.17,s*(43.2-1.5*j),
                       14.8-j*1.6,.40,2.1)
    b.cube("Core of the vessel",WHITE,0,19.9,0,54,28.0,46)
    b.cube("Cross gallery core",WHITE,0,20.2,-.925,44,29.2,52.35)
    # Profile of each tower is stepped back under the suspended upper copper screen.
    for yaw in (0,pi):
        b.frame(0,0,yaw)
        if yaw==0:
            footage.museum_north(b)
            footage.museum_north_supports(b)
        else:
            b.cube("Central curtain wall surround",WHITE,0,22.5,25.8,22.6,32.8,3.3)
            curtain(b,"Tall atrium glazing",0,23.1,27.49,20.7,30.5,12,8)
            b.cube("North and south glazing sill",PALE,0,7.55,27.68,22.1,.55,.7)
            for i in range(-3,4):
                glass(b,"Ground floor doors",i*2.55,4.1,34.98,2.35,4.18,2,2)
        for ix,s in enumerate((-1,1)):
            cx=21.2*s
            if yaw==0 and s==-1:
                continue
            b.cube("White tower piers",WHITE,cx,22.1,9.4,19.8,32.5,30.5)
            b.cube("Cantilevered upper galleries",WHITE,cx,33.56,18.95,20.9,15.52,21.0)
            footage.bronze(b,cx)
        # Lower protruding blocks occupy the lateral frontage of the first-floor wings.
        for s in (-1,1):
            b.cube("Low wing ends",WHITE,s*42.8,8.35,11,24.6,10.2,37.6)
            curtain(b,"Low gallery lights",s*42.8,8.52,29.84,21.85,9.05,13,3)
    for yaw in (pi/2,-pi/2):
        b.frame(0,0,yaw)
        b.cube("East-west atrium frame",WHITE,0,22.3,28.1,24.2,31.7,9.0)
        curtain(b,"Narrow side atrium glazing",0,22.6,32.64,22.25,30.0,13,8)
        for i,x in enumerate((-20.6,0,20.6)):
            b.cube("Side gallery boxes",WHITE,x,8.63,45.85,18.45,9.6,22.7)
            curtain(b,"Side window wall",x,8.72,57.24,16.95,8.28,10,3)
            b.cube("Cantilever shadow","#89948B",x,3.65,49.2,15.6,.47,14.8)
    b.frame(0,0,0)
    museum_roofs(b)
    footage.register_north_towers(b)


def triangular_gable(b, group, x, wallz, span, eave, apex, mat):
    b.poly(group,mat,[(x-span/2,eave,wallz),(x+span/2,eave,wallz),(x,apex,wallz)])


def courtyard(b, key, width, depth, height):
    """Four connected teaching or office wings, composed around an open courtyard."""
    public = key=="zhensheng"
    from qd_teaching_courts import dimensions
    outer_x,outer_z,inner_x,inner_z=dimensions(key,width,depth)
    wallh=height-4.6
    footage.court_garden(b,key,inner_x,inner_z)
    for side,yaw in enumerate((0,pi/2,pi,-pi/2)):
        b.frame(0,0,yaw)
        sidewing=side%2==1
        out=outer_x if sidewing else outer_z
        inn=inner_x if sidewing else inner_z
        depth_wing=out-inn
        from qd_wing_junctions import END_BAY, GAP, joints
        length=2*(inner_z-GAP if sidewing else outer_x)
        center=(out+inn)/2
        group=("South","East","North","West")[side]
        arched=not sidewing
        footage.court_wing(b,group,length,wallh,inn,out,arched)
        b.cube(group+" eaves",CORNICE,0,wallh,center,length+.52,.42,depth_wing+.68)
        recessed=public or sidewing
        if recessed:
            # The east-west pair of Huagang and all four Zhensheng wings have
            # a visible pale recessed deck within the tiled perimeter. The
            # middle of each quadrangle remains genuinely open to the landscape.
            top_length=length-(depth_wing*.92 if public else depth_wing*1.15)
            top_depth=depth_wing*(.35 if public else .32)
            footage.court_roof(b,key,group,side,length,center,depth_wing,wallh,height,top_length,top_depth)
        else:
            b.roof(group+" tiled roof",REDTILE,0,center,length+.8,depth_wing+.9,
                   wallh+.14,height-.62,max(2,length-depth_wing*.87),.20)
        if sidewing:
            joints(b,group,inner_z,inner_x,outer_x,outer_z,wallh)
        front=out+.02
        for sign in (-1,1):
            span=length/2-10
            n=max(5,int(round(span/4.7)))
            for i in range(n):
                wx=sign*(10+(i+.5)*span/n)
                bw=span/n*.69
                above_portico=arched and abs(wx)+bw/2>=length/2-END_BAY
                bay_low=5.05 if above_portico else wallh*.13
                bay_high=wallh*.77
                b.rect(group+" recessed bays",SHADE,wx,(bay_low+bay_high)/2,front+.036,bw+.35,bay_high-bay_low)
                for k in range(1 if above_portico else 0,4):
                    yy=(.65+(k+.5)*(wallh-1.1)/4)
                    glass(b,group+" classroom windows",wx,yy,front+.12,bw,2.6,2,2)
                if i%3==1 and i<n-1 and not sidewing:
                    zz=out-depth_wing*.14
                    triangular_gable(b,group+" dormers",wx,zz,4.15,wallh+1.04,wallh+2.63,CORNICE)
                    triangular_gable(b,group+" dormer glazing",wx,zz+.035,2.95,wallh+1.22,wallh+2.32,DEEP)
                    for s in (-1,1):
                        b.poly(group+" dormer caps",TILE,[(wx+s*2.18,wallh+.99,zz),
                           (wx,wallh+2.78,zz),(wx,wallh+2.78,zz-2.9),(wx+s*2.18,wallh+.99,zz-2.9)])
        # Smaller dark windows run continuously under the edge of each roof.
        for x in range(-int(length/2)+3,int(length/2)-2,4):
            if abs(x)>9:
                b.rect(group+" eaves windows",DEEP,x,wallh-.65,front+.14,2.1,.73)
        if arched:
            porchspan=16.8 if public else 18.2
            porch=out+1.25
            footage.passage_shell(b,group+' 主门楼',porchspan+1.5,wallh,out,porch+1.04,True,CORNICE,False)
            bottom,top=5.58,wallh-.12
            curtain(b,group+" gable wall",0,(top+bottom)/2,porch+1.09,porchspan-1.2,top-bottom,9,4)
            triangular_gable(b,group+" entrance pediment",0,porch+1.04,porchspan+1.5,wallh-.1,height,CORNICE)
            triangular_gable(b,group+" entrance gable glass",0,porch+1.1,porchspan-1.15,wallh-.13,height-.85,GLAZING)
            for i in range(-3,4):
                xx=i*1.80
                hh=(height-.85-wallh)*(1-abs(xx)/((porchspan-1.15)/2))
                if hh>.05:
                    b.rect(group+" gable glazing bars",METAL,xx,wallh+hh/2,porch+1.135,.12,hh)
            for s in (-1,1):
                pts=[(s*(porchspan/2+1.1),wallh+.12,porch+1.65),(0,height+.05,porch+1.65),
                     (0,height+.05,center),(s*(porchspan/2+1.1),wallh+.12,center)]
                b.poly(group+" cross gable tiles",REDTILE,pts if s==-1 else pts[::-1])
            footage.open_portal(b,group,porch+1.62,porch+1.04)
        else:
            footage.bridge_face(b,group,front,wallh)
        # The wings have a second elevation facing the open quadrangle.
        b.frame(0,0,yaw+pi)
        footage.court_inside(b,key,group,side,inn,out,wallh,arched)
        if arched:
            from qd_wing_junctions import court_arcades
            court_arcades(b,group,inner_x,-inn)
        inner_span=length if sidewing else 2*inner_x
        count=int(inner_span/4.8)
        for i in range(count):
            wx=(i-(count-1)/2)*inner_span/count
            if abs(wx)<7.0:
                continue
            if public and sidewing:
                b.rect(group+" 庭院成列窗间暗槽",DEEP,wx,8.80,-inn+.025,3.45,13.75)
                for dx in (-1.80,1.80):
                    b.cube(group+" 庭院通高窗间壁柱",LIGHT,wx+dx,8.70,-inn+.15,.26,14.25,.37)
            for j in range(4):
                glass(b,group+" court sash",wx,2.8+3.54*j,-inn+.035,2.76,2.40,2,1)


def build(scene,key,w,d,h):
    """Append the chosen landmark centered on the origin and return whether it is known."""
    spec=next((s for s in SPECS if key==s["key"] or key==s["name"] or key in s["aliases"]),None)
    if spec is None:
        return False
    b=Parts(scene,(w/spec["w"],h/spec["h"],d/spec["d"]))
    if spec["key"]=="library":
        library(b)
    elif spec["key"]=="museum":
        museum(b)
    else:
        courtyard(b,spec["key"],spec["w"],spec["d"],spec["h"])
    b.finish()
    return True

