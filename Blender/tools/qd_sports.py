import math
from shapely.geometry import LineString
from qd_geometry import Shape
def court(row,p):
    ring=list(p.minimum_rotated_rectangle.exterior.coords)[:4]
    a,b,c=ring[:3];s1=math.dist(a,b);s2=math.dist(b,c)
    if s1>s2:a,b=b,c;s1,s2=s2,s1
    w,d=s1,s2; angle=-math.atan2(b[1]-a[1],b[0]-a[0])
    group=Shape(row.get('name') or row['kind']);kind=row['kind']
    col={'basketball':'#ac755d','soccer':'#81a868','tennis':'#296ca5','badminton':'#84a899','volleyball':'#ba927a'}.get(kind,'#87a385')
    if kind=='basketball' and p.centroid.x>280:col='#599cad'
    group.box('场面',0,.01,0,w,.06,d,col)
    ink='#f3eedb'
    def bar(a,b,c,e,th=.105):
        dx,dz=c-a,e-b
        group.box('体育划线',(a+c)/2,.072,(b+e)/2,math.hypot(dx,dz),.029,th,ink,-math.atan2(dz,dx))
    def circle(x,z,r,ang1=0,ang2=math.tau):
        pts=[(x+r*math.cos(ang1+(ang2-ang1)*i/40),z+r*math.sin(ang1+(ang2-ang1)*i/40)) for i in range(41)]
        for a,b in zip(pts,pts[1:]):bar(*a,*b)
    W=min(w*.92,68 if kind=='soccer' else 15 if kind=='basketball' else w*.91)/2
    D=min(d*.93,105 if kind=='soccer' else 28 if kind=='basketball' else d*.9)/2
    if kind=='tennis':
        W=min(W,10.97/2);D=min(D,23.77/2)
        group.box('网球场青绿色界内面',0,.048,0,2*W,.015,2*D,'#328e7d')
        from qd_video_courts import tennis
        tennis(group,w,d)
    if kind=='basketball' and p.centroid.x>280:
        group.box('篮球场蓝绿界内',0,.048,0,W*2,.015,D*2,'#6ca49c')
    if kind=='soccer':
        for i in range(14):
            group.box('练习场修剪草带',0,.047,(i-6.5)*2*D/14,2*W,.012,2*D/14,('#5d985e','#76ac66')[i%2])
    def rect(w,z1,z2):
        bar(-w,z1,w,z1);bar(w,z1,w,z2);bar(w,z2,-w,z2);bar(-w,z2,-w,z1)
    rect(W,-D,D)
    if kind!='tennis':bar(-W,0,W,0)
    if kind=='soccer':
        circle(0,0,min(D*.17,9.15))
        for side in [-1,1]:
            rect(W*.57,side*D,side*D*.69);rect(W*.28,side*D,side*D*.89)
            for x in [-3.6,3.6]:
                group.cyl('球门柱',x,1.21,side*D,.075,2.42,ink,8)
            group.box('门横梁',0,2.42,side*D,7.34,.12,.12,ink)
    elif kind=='basketball':
        circle(0,0,1.78)
        for side in [-1,1]:
            rect(min(W*.49,2.45),side*D,side*(D-5.8))
            circle(0,side*(D-5.8),1.78,0,math.pi if side>0 else -math.pi)
            group.cyl('篮球架',0,1.6,side*(D+.5),.09,3.2,'#587c78',8)
            group.box('篮板',0,3.46,side*(D-.84),1.8,1.02,.1,ink)
            for j in range(16):
                a=j*math.tau/16;b=(j+1)*math.tau/16
                x1,z1=.235*math.cos(a),side*(D-1.18)+.235*math.sin(a)
                x2,z2=.235*math.cos(b),side*(D-1.18)+.235*math.sin(b)
                group.box('篮筐',(x1+x2)/2,3.05,(z1+z2)/2,math.hypot(x2-x1,z2-z1),.035,.035,'#c26842',-math.atan2(z2-z1,x2-x1))
    elif kind in ('tennis','badminton','volleyball'):
        if kind=='tennis':
            for side in (-1,1):bar(-W*.75,side*6.4,W*.75,side*6.4)
            bar(0,-6.4,0,6.4)
        if kind=='tennis':
            for u in (-1,1):bar(u*W*.75,-D,u*W*.75,D)
        elif kind=='badminton':
            rect(W*.75,-D,D);bar(0,-D*.52,0,D*.52)
            for z in (-D*.52,D*.52):bar(-W*.75,z,W*.75,z)
        ht=1.0 if kind=='tennis' else 1.55 if kind=='badminton' else 2.35
        for x in [-W-.2,W+.2]:group.cyl('网柱',x,ht/2,0,.058,ht,'#566c68',8)
        group.box('网带',0,ht,0,W*2+.4,.065,.05,ink)
        for j in range(4):group.box('球网',0,ht-j*.11,0,W*2,.02,.03,'#718281')
    return group,angle

