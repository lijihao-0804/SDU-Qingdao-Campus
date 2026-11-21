"""Masonry gate piers, the divided approach and axis details visible in V2 00:00–00:19."""
from math import cos,sin,pi,hypot
from shapely.geometry import box,Point
from shapely.affinity import scale
from qd_terrain import face

def shaft(s,x,h,stone,trim):
    # Corners are cut into the stone rather than left square behind the masonry.
    hw,hd,cut=4.05,3.95,.79
    ring=[(-hw+cut,-hd),(hw-cut,-hd),(hw,-hd+cut),(hw,hd-cut),
          (hw-cut,hd),(-hw+cut,hd),(-hw,hd-cut),(-hw,-hd+cut)]
    bottom=h*.32;top=h*.87
    for k,a in enumerate(ring):
        b=ring[(k+1)%8];dx,dz=b[0]-a[0],b[1]-a[1];length=hypot(dx,dz)
        nx,nz=dz/length,-dx/length
        def pt(u,y,offset):
            return (x+a[0]+u*dx/length+nx*offset,y,a[1]+u*dz/length+nz*offset)
        s.mesh('切角塔身石芯',[pt(0,bottom,0),pt(0,top,0),pt(length,top,0),pt(length,bottom,0)],[(0,1,2,3)],stone)
        courses=16
        for j in range(courses):
            l=bottom+(top-bottom)*j/courses+.035;r=bottom+(top-bottom)*(j+1)/courses-.04
            n=max(1,round(length/1.22));step=length/n
            joints=sorted(set([0,length]+[min(length,max(0,(i+(.42 if j%2 else 0))*step)) for i in range(n+1)]))
            for i,(u,v) in enumerate(zip(joints,joints[1:])):
                if v-u<.16:continue
                # Reserve the recessed axial panels on both principal elevations.
                if k in (0,4) and abs((u+v-length)/2)<.91:continue
                dep=.072+.045*(1+cos(i*7+j*3+k))*.5
                q=[(u+.025,l),(v-.025,l),(v-.025,r),(u+.025,r)]
                rim=[pt(uu,yy,.005) for uu,yy in q]
                topface=[pt(uu+(1 if a1 in (0,3) else -1)*.045,yy+(.047 if a1<2 else -.047),dep) for a1,(uu,yy) in enumerate(q)]
                s.mesh('粗凿花岗岩错缝砌块',rim+topface,[(7,6,5,4)]+[(a1,(a1+1)%4,4+(a1+1)%4,4+a1) for a1 in range(4)],(trim,'#d8d3c8','#d0cbc0','#dcd8ce')[(i*5+j+k)%4])
    for hand in (-1,1):
        for side in (-1,1):
            s.box('竖向磨面石肋',x+hand*3.47,(bottom+top)/2,side*3.66,.70,top-bottom,.7,trim)

def approach(s):
    from qd_residence_roofs import surface,walls
    # West-facing approach; positive local Z extends toward the off-campus road.
    bed=box(-4.65,-4,4.65,17.9).buffer(1.1,quad_segs=8)
    surface(s,'中央绿岛路缘',bed,.49,'#c5c2b6')
    walls(s,'中央绿岛路缘立面',bed,.15,.49,'#a9aaa1')
    surface(s,'西门中分绿岛植土',bed.buffer(-.18),.515,'#89a36c')
    for j in range(6):
        z=-4+j*3.67;shape=box(-4.25,z,4.25,z+3.62).buffer(.22,quad_segs=4)
        height=(.88,.98,1.04,1.01,.75,.65)[j]
        color=('#507047','#52692f','#58673c','#764f3a','#908244','#748742')[j]
        surface(s,'绿岛修剪色带',shape,height,color)
        walls(s,'绿岛修剪色带侧缘',shape,.49,height,color)
    for i in range(-14,15):
        if abs(i)<4:continue
        s.box('进门斑马线',i*1.43,.244,22.7,.67,.026,4.3,'#e3e3d9')
    for sign in (-1,1):
        for island in (9.6,17.1):
            x=sign*island
            s.box('车道分隔缘石',x,.31,1.6,.58,.25,10.2,'#c7c5bb')
            s.box('车道小亭基座',x,.45,1.8,1.80,.46,2.84,'#a2a8a7')
            s.box('车道小亭窗',x,1.72,1.8,1.62,2.15,2.65,'#536977')
            s.box('车道小亭顶',x,2.88,1.8,1.99,.20,2.96,'#bfc5c4')
            for corner in (-1,1):
                s.box('值守亭窗框',x+.82*corner,1.70,1.8, .11,2.15,2.65,'#b4b8b4')
        for z in (-5,1,7,13):s.cyl('行车缘柱',sign*5.75,.69,z,.105,.88,'#d1d1c7',8)

def axis(s,w,d):
    # The flag island is a lens within the light paving. The actual flagpoles
    # are authored with the library and share its surveyed east/west axis.
    island=scale(Point(88.4,0).buffer(1,quad_segs=48),6.0,22.0)
    face(s,island,'#8faa70',.214)
    for z in (-9.3,9.3):
        hedge=box(-w*.34-1.35,z-1.45,-w*.34+1.35,z+1.45).buffer(.55)
        from qd_residence_roofs import surface,walls
        surface(s,'校训石侧剪篱',hedge,1.13,'#64824e')
        walls(s,'校训石侧剪篱边',hedge,.24,1.13,'#536f42')

