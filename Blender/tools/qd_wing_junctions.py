"""Separation between the end pavilions and the east and west teaching wings.

Local metres. Both quadrangles use the same mirrored construction; the existing
centreline portals, individual roofs and courtyard elevations remain distinct.
"""
from qd_teaching_courts import FLOOR, PAVING

GAP = 6.4
END_BAY = 8.7
CLEAR = 4.65
BRIDGE_DEPTH = 4.15


def end_pavilions(b,group,extent,inner,outer,height):
    from qd_landmarks import CORNICE,LIGHT
    depth=outer-inner
    centre=(inner+outer)/2
    for side in (-1,1):
        cx=side*(extent-END_BAY/2)
        # Clear L-shaped portico: enter through the end elevation, then turn
        # toward the adjacent slot. The stone piers carry the upper floors.
        b.cube(group+' 端楼架空层石铺地',PAVING,cx,FLOOR-.075,centre,END_BAY,.15,depth)
        b.cube(group+' 端楼上层体量',LIGHT,cx-side*.55,(height+CLEAR)/2,centre,
               END_BAY-1.10,height-CLEAR,depth)
        pier=(depth-8.5)/2
        for direction in (-1,1):
            zz=centre+direction*(depth-pier)/2
            b.cube(group+' 端门灰石墩', '#a49f91', side*(extent-.65), CLEAR/2,zz,1.30,CLEAR,pier)
            b.cube(group+' 端墙凹窗侧壁', LIGHT,side*(extent-.55),(height+CLEAR)/2,zz,1.10,height-CLEAR,pier)
        b.cube(group+' 端门石过梁',CORNICE,side*(extent-.55),CLEAR+.27,centre,1.1,.54,depth)
        b.cube(group+' 端墙凹窗顶板',CORNICE,side*(extent-.55),height-.39,centre,1.10,.78,depth)


def court_arcades(b,group,halfspan,plane):
    from math import cos, sin, pi
    from qd_video_landmarks import perforated, jambs, arch_loop, rectangle
    for side in (-1,1):
        xmin, xmax = 9.8, halfspan-.86
        span = xmax-xmin
        centre = side*(xmin+xmax)/2
        n = max(3,round(span/4.85))
        bays = [centre+(i-(n-1)/2)*span/n for i in range(n)]
        half = .365*span/n
        face = lambda x,y:(x,y,plane+.98)
        recess = lambda x,y:(x,y,plane+.25)
        holes = [arch_loop(x,half,.19,2.05,1.55,16) for x in bays]
        perimeter = rectangle(centre,2.23,span,4.45)
        perforated(b,group+' 首层灰石拱廊', '#a49f91', perimeter,holes,face)
        jambs(b,group+' 石拱廊檐口与侧面',perimeter,face,recess,'#ada89b')
        for x,hole in zip(bays,holes):
            jambs(b,group+' 石拱券深窗洞',hole,face,recess,'#837f75')
            for j in range(13):
                a, end = (j+.032)*pi/13,(j+.968)*pi/13
                ring=[(x+(half+t)*cos(ang),2.05+(1.55+t)*sin(ang),plane+1.008)
                      for ang,t in ((a,0),(a,.22),(end,.22),(end,0))]
                b.poly(group+' 拱顶分缝石块',('#b6b0a2','#bdb6a7','#afa998')[j%3],ring)
        b.cube(group+' 石廊细压檐','#c3bdad',centre,4.47,plane+.69,span+.12,.18,.82)


def joints(b, group, inner_z, inner_x, outer_x, outer_z, wall_height):
    from qd_landmarks import CORNICE, LIGHT, METAL, glass
    floor = FLOOR
    bridge_z = inner_x + .48 * (outer_x - inner_x)
    for sign in (-1, 1):
        # The full-height slot is open to the sky on both sides of the bridge.
        cx = sign * (inner_z - GAP / 2)
        b.poly(group+' 翼端入院石径', PAVING,
               [(cx-GAP/2,floor,inner_x),(cx-GAP/2,floor,outer_x+.15),
                (cx+GAP/2,floor,outer_x+.15),(cx+GAP/2,floor,inner_x)])
        def paving_band(centre_x,centre_z,span,depth,material):
            b.cube(group+' 入口石径镶带',material,centre_x,floor+.009,centre_z,span,.018,depth)
        for edge in (-1,1):
            paving_band(cx+edge*(GAP/2-.29),(inner_x+outer_x)/2,.16,outer_x-inner_x,'#a09f96')
        joints_count=max(1,round((outer_x-inner_x)/2.0))
        for i in range(1,joints_count):
            paving_band(cx,inner_x+i*(outer_x-inner_x)/joints_count,GAP-.77,.046,'#aba99e')
        bottom, top = CLEAR, wall_height - 2.2
        b.cube(group+' 架空连廊楼板', '#a89c88', cx, bottom+.18, bridge_z, GAP, .36, BRIDGE_DEPTH)
        b.cube(group+' 连廊压顶', CORNICE, cx, top, bridge_z, GAP, .26, BRIDGE_DEPTH+.14)
        for side in (-1,1):
            plane = bridge_z + side*BRIDGE_DEPTH/2
            # The two sides have opposing normals. A local window grid works
            # on either elevation, with the frame returned towards the observer.
            x0,x1 = cx-GAP/2,cx+GAP/2
            lo,hi = bottom+.36,top-.13
            for j in range(3):
                for k in range(3):
                    xa=x0+j*GAP/3+.045; xb=x0+(j+1)*GAP/3-.045
                    ya=lo+k*(hi-lo)/3+.06; yb=lo+(k+1)*(hi-lo)/3-.06
                    pane=[(xa,ya,plane),(xb,ya,plane),(xb,yb,plane),(xa,yb,plane)]
                    b.poly(group+' 后退连廊玻璃', '#53707a', pane if side>0 else pane[::-1])
            for j in range(4):
                b.cube(group+' 连廊细竖框',METAL,x0+j*GAP/3,(lo+hi)/2,plane,.092,hi-lo,.12)
            for k in range(4):
                b.cube(group+' 连廊横框',METAL,cx,lo+k*(hi-lo)/3,plane,GAP,.127,.13)
        # Gable end of the perpendicular wing. A strongly framed window is
        # visible above the stone base in the user's fourth reference.
        ex = sign*(outer_z+inner_z)/2
        width = 8.5
        glass(b,group+' 端部内凹大窗',ex,(wall_height+CLEAR)/2,outer_x-1.04,width,wall_height-CLEAR-.65,4,3)
        for dx in (-1,1):
            b.cube(group+' 端窗上下贯通壁柱',LIGHT,ex+dx*(width/2+.52),(wall_height+CLEAR)/2,outer_x+.15,.69,wall_height-CLEAR-.50,.35)
        for i,over in enumerate((1.70,1.17,.60)):
            b.cube(group+' 端楼阶形收边',CORNICE,ex,wall_height-.46+i*.22,outer_x+.32,width+over,.24,.61)
