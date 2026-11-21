"""The low planted spectator terraces between the red track and Xiyuan."""
import math

def terraces(s,w,d):
    # Three planted sections are separated by two pale passages in V3 01:38.5.
    # The rows follow the short southern curve and do not cross the outermost lane.
    r=w*.49; rz=w*.48; straight=d*.5-rz
    def p(a,offset,height):
        return ((r+offset)*math.sin(a),height,straight+(rz+offset)*math.cos(a))
    for row in range(4):
        start=.90+row*1.22;end=start+1.19;top=.39+row*.38
        for bay in range(40):
            a=(bay-20)*.039;b=a+.039
            step=bay in (12,13,26,27)
            s.mesh('田径场南端看台草阶' if not step else '分区石阶踏面',
                   [p(a,start,top),p(b,start,top),p(b,end,top),p(a,end,top)],[(0,2,1),(0,3,2)],
                   ('#85a36b','#91ac76')[row%2] if not step else '#c7c0ab')
            s.mesh('低阶石材踢面',[p(a,start,top-.38),p(b,start,top-.38),p(b,start,top),p(a,start,top)],
                   [(0,1,2,3)],'#b5b39d')

