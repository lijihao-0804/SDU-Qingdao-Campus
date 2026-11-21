"""Physical lettering. Coordinates are in the owner's metre-scale local frame."""
import math
from qd_geometry import Shape
from qd_architecture import sign


def plaque(shape, building_key, id, text, x, y, z, width, height, yaw, *,
           source, year, carrier, colour='#342f2b', background=None, note=''):
    if not all((building_key, id, text, source, carrier)) or min(width, height) <= 0:
        raise ValueError(f'Missing physical lettering evidence or size: {building_key} {id}')
    entries = shape.__dict__.setdefault('_plaques', [])
    if any(e['id'] == id for _, e in entries):
        raise ValueError(f'Duplicate plaque identifier on {building_key}: {id}')
    nx, nz = math.sin(yaw), math.cos(yaw)
    mesh = Shape(text)
    if background:
        mesh.box(carrier, x - .035*nx, y, z - .035*nz, width, height, .07, background, yaw)
    x, z = x + .012*nx, z + .012*nz
    sign(mesh, id, text, x, y, z, width, height, colour, yaw)
    if not mesh.parts or not mesh.parts[colour][2]:
        raise ValueError(f'Missing glyphs: {text}')
    record = dict(owner=building_key, id=str(id), text=text, source=source, year=year,
                  carrier=carrier, note=note, normal=[nx,nz], center=[x,y,z],
                  width=width, height=height, colour=colour)
    entries.append((mesh, record))
    return mesh


def emit(scene, shape, at, records):
    for mesh, rec in getattr(shape, '_plaques', []):
        pt = [round(float(a)+float(b), 4) for a, b in zip(at,rec['center'])]
        scene.node(rec['owner']+' · '+rec['id']+' · '+rec['text'], shape=mesh, at=at,
                   kind='signage', owner=rec['owner'], signId=rec['id'], text=rec['text'],
                   carrier=rec['carrier'], facing=rec['normal'], source=str(rec['source']))
        records.append(dict(rec, world=pt))

