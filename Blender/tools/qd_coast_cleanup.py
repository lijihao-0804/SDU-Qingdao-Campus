"""Repair legacy coastal overlays and verify the authored sand/sea boundary."""

import json
from pathlib import Path

import mapbox_earcut as ear
import numpy as np
import shapely as sh
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from qd_coast import sealine
from qd_waterfront import Waterfront


ROOT = Path(__file__).resolve().parents[1]
GRID = .001


def coastal_domains(waterfront):
    from qd_campus_park import land_regions
    local, _ = land_regions(waterfront)
    ocean = sealine(ROOT/'assets/海陆掩膜.png').difference(waterfront.outer).union(waterfront.ocean).buffer(0)
    excluded = sh.union(ocean, local, grid_size=GRID)
    return ocean, excluded


def set_matte_sand(doc, mat):
    pbr = mat['pbrMetallicRoughness']
    legacy = pbr.pop('metallicRoughnessTexture', None)
    pbr.update(roughnessFactor=1., metallicFactor=0.)
    ext = mat.setdefault('extensions', {})
    ext['KHR_materials_specular'] = {'specularFactor': 0.}
    ext['KHR_materials_ior'] = {'ior': 1.}
    mat.setdefault('extras', {})['naturalFinish'] = 'sand'
    for key in ('KHR_materials_specular', 'KHR_materials_ior'):
        if key not in doc.setdefault('extensionsUsed', []):
            doc['extensionsUsed'].append(key)
    return legacy


def _texture_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith('Texture') and isinstance(child, dict) and 'index' in child:
                yield child
            else:
                yield from _texture_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _texture_refs(child)


def _discard_wet_film(doc, slot):
    # A v6 GLB used a dedicated wet-to-dry film image. Remove just its record
    # when unused, and preserve every surviving material-to-image association.
    refs = list(_texture_refs(doc['materials']))
    if any(r['index'] == slot for r in refs):
        return
    tex = doc['textures'][slot]
    if tex.get('name') != '湿砂粗糙度':
        return
    image = tex['source']
    del doc['textures'][slot]
    for ref in refs:
        if ref['index'] > slot:
            ref['index'] -= 1
    if any(t.get('source') == image for t in doc['textures']):
        return
    del doc['images'][image]
    for texture in doc['textures']:
        if texture.get('source', -1) > image:
            texture['source'] -= 1


def _array(scene, index):
    a = scene.doc['accessors'][index]
    b = scene.doc['bufferViews'][a['bufferView']]
    typ = {5126: '<f4', 5123: '<u2', 5125: '<u4'}[a['componentType']]
    width = {'VEC3': 3, 'VEC2': 2, 'SCALAR': 1}[a['type']]
    return np.frombuffer(scene.raw, typ, a['count']*width,
                         b.get('byteOffset', 0)+a.get('byteOffset', 0)).reshape(-1, width).copy()


def footprint_overlap(triangles, excluded):
    """Find actual projected face area, including spikes whose centroid is on land."""
    polys = sh.polygons(np.ascontiguousarray(triangles[:, :, [0, 2]]))
    ids = sh.STRtree(polys).query(excluded, predicate='intersects')
    if not len(ids):
        return ids, np.array([]), polys
    overlap = sh.area(sh.intersection(polys[ids], excluded, grid_size=GRID))
    # Vertices in a GLB use float32. At 10 km allow its one-millimetre
    # rounding strip on a triangle edge, never a triangle-width allowance.
    valid = overlap > (.002 + sh.length(polys[ids])*GRID)
    return ids[valid], overlap[valid], polys


def _triangulate(part):
    for poly in sh.get_parts(part):
        if poly.geom_type == 'GeometryCollection':
            yield from _triangulate(poly)
        elif poly.geom_type == 'Polygon' and poly.area > GRID**2:
            poly = orient(poly, sign=1.)
            rings = [np.asarray(r.coords)[:-1] for r in (poly.exterior, *poly.interiors)]
            xz = np.ascontiguousarray(np.concatenate(rings), dtype='float64')
            ends = np.cumsum([len(ring) for ring in rings], dtype=np.uint32)
            indices = ear.triangulate_float64(xz, ends).reshape(-1, 3)[:, ::-1]
            yield xz, indices


def _trim_context(scene, primitive, excluded):
    attrs = primitive['attributes']
    positions = _array(scene, attrs['POSITION'])
    faces = _array(scene, primitive['indices']).reshape(-1, 3)
    invalid, areas, polys = footprint_overlap(positions[faces], excluded)
    report = dict(sourceTriangles=len(faces), clippedTriangles=len(invalid),
                  excludedOverlapM2=round(float(areas.sum()), 5))
    if not len(invalid):
        return report
    original = {name: _array(scene, index) for name, index in attrs.items()}
    extras = {name: [] for name in attrs}
    keep = np.ones(len(faces), dtype=bool)
    keep[invalid] = False
    pieces = [faces[keep]]
    next_vertex = len(positions)
    for i in invalid:
        part = sh.difference(polys[i], excluded, grid_size=GRID)
        # An entire legacy tile can overlay the detailed park and the water.
        if part.area <= .002 + polys[i].length*GRID:
            continue
        corners = positions[faces[i]][:, [0, 2]].astype(float)
        for xz, indices in _triangulate(part):
            ab = (corners[1:] - corners[0]).T
            uv = np.linalg.solve(ab, (xz-corners[0]).T).T
            weights = np.column_stack((1-uv.sum(axis=1), uv))
            for name, values in original.items():
                selected = weights @ values[faces[i]]
                if name == 'NORMAL':
                    selected /= np.maximum(np.linalg.norm(selected, axis=1, keepdims=True), 1.e-10)
                if name == 'POSITION':
                    selected[:, [0, 2]] = xz
                extras[name].append(selected)
            pieces.append(indices + next_vertex)
            next_vertex += len(xz)
    if next_vertex > len(positions):
        for name, values in original.items():
            kind = scene.doc['accessors'][attrs[name]]['type']
            attrs[name] = scene.accessor(np.concatenate([values, *extras[name]]), '<f4', kind, 5126, 34962)
    new_faces = np.concatenate(pieces).ravel()
    comp, dtype = (5125, '<u4') if next_vertex > 65535 else (5123, '<u2')
    primitive['indices'] = scene.accessor(new_faces, dtype, 'SCALAR', comp, 34963)
    report['resultTriangles'] = len(new_faces)//3
    return report


def finish(scene, waterfront=None):
    """Apply to an assembled legacy glTF or to the freshly generated full model."""
    if waterfront is None:
        waterfront = Waterfront(json.loads((ROOT/'data/map/campus.json').read_text('utf8')))
    _, excluded = coastal_domains(waterfront)
    doc = scene.doc
    reports = []
    sand_slots = set()
    for node in doc['nodes']:
        if 'mesh' not in node:
            continue
        ex = node.get('extras', {})
        prims = doc['meshes'][node['mesh']]['primitives']
        if ex.get('kind') == 'terrainContext':
            reports.extend(_trim_context(scene, p, excluded) for p in prims)
        if ex.get('surface') in {'sand', 'subtidal'} or node['name'] == '沙岸':
            sand_slots.update(p['material'] for p in prims)
    if len(reports) != 1 or not sand_slots:
        raise ValueError('Missing coastal context or sand.')
    legacy = []
    for slot in sorted(sand_slots):
        old = set_matte_sand(doc, doc['materials'][slot])
        if old:
            legacy.append(old['index'])
    for slot in sorted(set(legacy), reverse=True):
        _discard_wet_film(doc, slot)
    return {'regionalTerrain': reports[0], 'matteSand': [doc['materials'][i]['name'] for i in sorted(sand_slots)]}
