"""Opaque, cupped flowers on short pedicels. Coordinates are metres, Y up."""
from functools import lru_cache
import math

from qd_geometry import lin
from qd_spring import _twig


# One batched primitive carries both petal colours and warm flower centres.
PETAL_MATERIAL = '#fffefd'
PEDICEL = '#907b67'


def leaf_blade(shape, root, angle, length, half_width, rise, colour):
    """A narrow rib, curved sides and a toothed outline are visible edge-on."""
    co,si=math.cos(angle),math.sin(angle)
    vv,nn,ii=shape.parts[colour]
    start=len(vv)
    vv.append(root);nn.append((0.,1.,0.))
    # The blade broadens in the middle, bends down again near the tapered tip.
    profiles=((.16,.40),(.29,.72),(.40,.69),(.50,1.),(.62,.82),(.72,.84),(.86,.41))
    for j,(t,w) in enumerate(profiles):
        x,y,z=root[0]+co*length*t,root[1]+rise*t,root[2]+si*length*t
        lift=.16*length*math.sin(math.pi*t)
        for side in (-1,0,1):
            width=side*half_width*w
            vv.append((x-si*width,y+lift-(.33*abs(width)),z+co*width))
            nn.append((-si*side*.3162,.94869,co*side*.3162) if side else (0.,1.,0.))
        i=start+1+3*j
        if j==0:
            ii.extend((start,i+1,i,start,i+2,i+1))
        else:
            for k in (i,i+1):
                ii.extend((k-3,k+1,k,k-3,k-2,k+1))
    end=len(vv)
    vv.append((root[0]+length*co,root[1]+rise,root[2]+length*si));nn.append((0.,1.,0.))
    ii.extend((end-3,end-2,end,end-2,end-1,end))


@lru_cache(maxsize=None)
def _colour(hex_value):
    return tuple(lin(int(hex_value[i:i+2], 16)/255) for i in (1, 3, 5))


def _cup(shape, base, radius, azimuth, elevation, phase, pigment, petals, double):
    """Each petal curls at its sides; a shallow notch divides its outer lip."""
    co, si = math.cos(azimuth), math.sin(azimuth)
    ce, se = math.cos(elevation), math.sin(elevation)
    axis = (co*ce, se, si*ce)
    right = (si, 0., -co)
    up = (-co*se, ce, -si*se)
    vv, nn, ii = shape.parts[PETAL_MATERIAL]
    tints = shape.vertex_tints.setdefault(PETAL_MATERIAL, [])
    def vertex(theta, reach, height, slope, tint):
        radial = tuple(math.cos(theta)*right[k]+math.sin(theta)*up[k] for k in range(3))
        vv.append(tuple(base[k]+radius*(reach*radial[k]+height*axis[k]) for k in range(3)))
        norm = math.sqrt(1+slope*slope)
        nn.append(tuple((axis[k]-slope*radial[k])/norm for k in range(3)))
        tints.append(tint)
        return len(vv)-1
    # A continuous centre closes the backs of the individual petals.
    heart = _colour('#d9ae77')
    center = vertex(phase, 0., .12 if double else .05, 0., heart)
    half = math.pi/petals
    roots = [vertex(phase+(2*j-1)*half,.155,.06,0.,heart) for j in range(petals)]
    pigment = _colour(pigment)
    whorls = (1., .66) if double else (1.,)
    for ring, scale in enumerate(whorls):
        for j in range(petals):
            angle = phase+2*j*half+ring*half
            if ring == 0:
                left, right_root = roots[j], roots[(j+1)%petals]
                ii.extend((center, left, right_root))
            else:
                left = vertex(angle-half,.12,.10,0.,pigment)
                right_root = vertex(angle+half,.12,.10,0.,pigment)
            throat=tuple(c*s for c,s in zip(pigment,(.94,.77,.82)))
            interior = vertex(angle,.49*scale,.08+.19*ring,.14,throat)
            rim = [left]
            for offset,reach,rise in ((-.89,.63,.26),(-.52,1.,.35),
                                      (0.,.92,.27),(.52,1.,.37),(.89,.63,.26)):
                # Slightly clearer outer lips frame the warmer petal throat.
                rim_colour=tuple(min(1.,c*(1.018+.018*abs(offset))) for c in pigment)
                rim.append(vertex(angle+offset*half,reach*scale,rise+.22*ring,.38,rim_colour))
            rim.append(right_root)
            for first, second in zip(rim, rim[1:]):
                ii.extend((interior, first, second))
            ii.extend((interior, right_root, left))
    # Four short tapered stamens stand in the actual corolla. A small amber
    # three-sided anther stays attached to each filament, using the same opaque
    # primitive and mip-free vertex colours as the surrounding petals.
    if math.sin(phase*2.)<.28:
        return
    for j in range(4):
        t=phase+j*math.tau/4+.13*math.sin(j+phase)
        lo=vertex(t,.066,.105 if double else .056,0.,_colour('#c59974'))
        hi=vertex(t,.14,.27+.035*math.sin(t),0.,_colour('#e5be83'))
        bulge=[vertex(t+offset,.14+rad,.285+dz,.24,_colour('#dfb169'))
               for offset,rad,dz in ((-.22,0.,0.),(.20,0.,0.),(0.,.037,.004))]
        root_l=vertex(t-.16,.063,.088 if double else .05,0.,_colour('#b48a6b'))
        ii.extend((lo,root_l,hi,root_l,bulge[0],hi,hi,bulge[0],bulge[1],
                   hi,bulge[1],bulge[2],hi,bulge[2],bulge[0],*bulge))


def flowering_spur(shape, origin, angle, size, palette, rng, count=4, petals=5,
                   double=False, pendulous=False):
    """Flowers face around a shared attachment, at different depths and inclinations."""
    if not hasattr(shape, 'vertex_tints'):
        shape.vertex_tints = {}
    for j in range(count):
        a = angle+j*2.399963+rng.uniform(-.38,.38)
        reach = size*rng.uniform(.19,.54)
        rise = size*(rng.uniform(-.17,.32) if pendulous else rng.uniform(.06,.56))
        p = (origin[0]+math.cos(a)*reach, origin[1]+rise, origin[2]+math.sin(a)*reach)
        _twig(shape,origin,p,.0032,.0017,PEDICEL)
        radius = size*rng.uniform(.19,.285)
        tilt = rng.uniform(-.80,.85) if pendulous else rng.uniform(-.36,1.28)
        _cup(shape,p,radius,a,tilt,rng.random()*math.tau,rng.choice(palette),petals,
             double and j%3==0)
