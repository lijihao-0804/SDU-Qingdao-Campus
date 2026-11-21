"""Shared, metre-scale leafy shoots on branching spring trees and low shrubs."""
import math
import random
import numpy as np
from qd_geometry import Shape

LEAF='春梢叶片'
BARK=('#706653','#80725e','#75624d')
def shoot(shape,start,heading,width,length,tilt,roll,tint):
    cx,cy,cz=start
    along=np.array([math.sin(heading)*math.cos(tilt),math.sin(tilt),math.cos(heading)*math.cos(tilt)])
    cross=np.array([math.cos(heading),0,-math.sin(heading)])
    normal=np.cross(along,cross)
    cross=cross*math.cos(roll)+normal*math.sin(roll)
    normal=np.cross(along,cross)
    spine=np.array([cx,cy,cz])
    verts,norms,indices=shape.parts[LEAF];offset=len(verts)
    for u,v in [(0,0),(1,0),(.5,.52),(0,1),(1,1)]:
        bend=.13*length if v==.52 else -.10*length*v*v
        point=spine+along*length*v+cross*((u-.5)*width)+normal*bend
        verts.append(tuple(point))
        # The two sides of the folded spray see slightly different light.
        # Bias toward the broad crown normal to keep its distant mass stable.
        lit=np.array([.28*math.sin(heading),.96,.28*math.cos(heading)])
        outward=normal if normal[1]>0 else -normal
        lit=.73*lit+.27*outward+.12*(u-.5)*cross-.10*(v-.5)*along
        norms.append(tuple(lit/np.linalg.norm(lit)))
        shape.uvs[LEAF].append((u,1-v))
        shape.vertex_tints[LEAF].append(tuple(min(1.,c*(.87+.12*v)) for c in tint))
    indices.extend(offset+i for i in (0,1,2,1,4,2,4,3,2,3,0,2))


def make(k,small):
    from qd_planting import branch
    shape=Shape(('灌丛' if small else '乔木')+str(k+1));rng=random.Random(72061+31*k+int(small))
    shape.uvs={LEAF:[]};shape.vertex_tints={LEAF:[]}
    bark=BARK[k%3];height=(6.6+.55*(k%3)) if not small else .92
    width=(2.45+.18*(k%3)) if not small else 1.12
    axis=(.10,height*.87,-.11) if not small else (.03,.68,.04)
    branch(shape,(0,-.07,0),axis,.19 if not small else .057,.045 if not small else .012,bark)
    shades=((.82,1.,.77),(.96,1.,.77),(.76,.91,.73),(.96,.94,.64))
    limbs=16 if not small else 10
    for j in range(limbs):
        f=(j+.6)/limbs;a=j*2.399963+rng.uniform(-.20,.20)
        reach=width*(.28+.79*math.sin(math.pi*(.11+.85*f)))
        base=height*((.30 if not small else .08)+f*(.46 if not small else .32))
        end=height*(.47+.48*f)
        mid=(reach*.48*math.sin(a-.08),base+(end-base)*.65,reach*.48*math.cos(a-.08))
        endpt=(reach*math.sin(a),end,reach*math.cos(a))
        branch(shape,(axis[0]*f,base,axis[2]*f),mid,.065 if not small else .018,.038 if not small else .012,bark)
        branch(shape,mid,endpt,.04 if not small else .011,.012 if not small else .006,bark)
        r=width*(.35 if small else .40)*rng.uniform(.78,1.06)
        for fork in range(4):
            ha=a+(fork-1.5)*1.16+rng.uniform(-.2,.2)
            anchor=mid if fork==0 else endpt
            origin=(anchor[0]+r*.46*math.sin(ha),anchor[1]+r*rng.uniform(.10,.66),anchor[2]+r*.46*math.cos(ha))
            branch(shape,anchor,origin,.017 if not small else .007,.006 if not small else .003,bark)
            for leaf in range(6 if not small else 5):
                hd=ha+(leaf-2)*.86+rng.uniform(-.35,.35)
                rad=r*rng.uniform(.20,.70);q=(origin[0]+rad*math.sin(hd),origin[1]+r*rng.uniform(-.25,.36),origin[2]+rad*math.cos(hd))
                # Anchor each foliar fan with a tapering twig.
                if leaf%2==0:branch(shape,origin,q,.012 if not small else .004,.004 if not small else .002,bark)
                source=shades[(j+fork+leaf+k)%len(shades)]
                species=((.86,.96,.87),(.98,.95,.75),(.72,.90,.90),(.75,.91,.80),(.90,.99,.81))[k%5]
                tint=tuple(a*b for a,b in zip(source,species))
                shoot(shape,q,hd,r*(1.20 if not small else 1.30),r*rng.uniform(1.1,1.54),
                      rng.uniform(-.32,.99),rng.uniform(-1.10,1.10),tint)
    return shape

