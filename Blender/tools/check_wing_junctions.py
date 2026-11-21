"""Confirm the four additional cut-throughs on each teaching court in the exported GLB."""
import json
from pathlib import Path
import numpy as np
from qd_landmarks import SPECS
from qd_teaching_courts import dimensions
from qd_wing_junctions import GAP, CLEAR, END_BAY
from v2_entrance_audit import Scene, exact_segment

ROOT=Path(__file__).resolve().parents[1]


def audit(path):
    model=Scene(path)
    report={}
    for spec in (s for s in SPECS if s['key'] in ('zhensheng','huagang')):
        key=spec['key']
        node,= [i for i,n in enumerate(model.nodes) if n.get('extras',{}).get('key')==key and 'mesh' in n]
        ox,oz,ix,iz=dimensions(key,spec['w'],spec['d'])
        origin=np.asarray(model.nodes[node]['translation'])
        tri=np.concatenate([t-origin for t,_ in model.triangles(node)])
        def cast(a,b):
            a,b=np.array(a),np.array(b)
            nearby=tri[np.all((tri.max(1)>=np.minimum(a,b)-1e-5)&(tri.min(1)<=np.maximum(a,b)+1e-5),axis=1)]
            return exact_segment(a,b,nearby)
        doors=[]
        for sx in (-1,1):
            for sz in (-1,1):
                z=sz*(iz-GAP/2)
                checks=0
                for h in (.42,1.68,2.75,4.31):
                    for dz in (-2.35,-1.15,0,1.15,2.35):
                        assert cast((sx*(ox+2),h,z+dz),(sx*(ix-.28),h,z+dz)) is None,(key,sx,sz,h,dz)
                        checks+=1
                bx=sx*(ix+.48*(ox-ix))
                v=cast((bx,.50,z),(bx,26,z))
                assert v is not None
                roof=.5+25.5*v
                assert abs(roof-CLEAR)<.025,(key,sx,sz,roof)
                for x in (ix+3,ox-3):
                    assert cast((sx*x,.40,z),(sx*x,28,z)) is None,(key,sx,sz,x)
                for dz in (-2.50,0,2.50):
                    assert cast((sx*(ix+2),.45,z+dz),(sx*(ix+2),-.30,z+dz)) is not None
                # The framed end elevation next to each slot also opens at
                # grade. Walk in through its stone piers, then turn into the slot.
                gable=sz*(iz+oz)/2
                turn=sx*(ox-END_BAY/2)
                for dz in (-2.8,0,2.8):
                    for y in (.55,1.72,3.95):
                        assert cast((sx*(ox+1),y,gable+dz),(turn,y,gable+dz)) is None
                assert cast((turn,1.72,gable),(turn,1.72,z)) is None
                # Compare the exposed return at skirting height with the
                # higher stone wall. Equal depths produced speckling in the browser.
                x=sx*(ix+.24*(ox-ix))
                edge=iz-GAP
                first,last=sz*(edge+1.0),sz*(edge-.40)
                low=cast((x,.62,first),(x,.62,last))
                high=cast((x,1.8,first),(x,1.8,last))
                assert low is not None and high is not None
                projection=(high-low)*abs(first-last)
                assert .04<projection<.075,(key,sx,sz,projection)
                doors.append(dict(plinthReturnM=round(projection,4),endPorticoClearRays=10,end=('东' if sx==1 else '西')+('南' if sz==1 else '北'),
                                  horizontalClearRays=checks,soffitM=round(roof,3),
                                  skyGaps=2,pavementSamples=3))
        report[key]=doors
    return dict(glbSHA256=model.digest,passages=report)


if __name__=='__main__':
    result=audit(ROOT/'山东大学青岛校区.glb')
    (ROOT/'data/翼端通廊实测.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('8 end connections checked')
