"""Close the nearshore model cut at the surveyed surf boundary (metres)."""
from pathlib import Path
import json

import mapbox_earcut
import numpy as np
from shapely.geometry import Point
from shapely.geometry.polygon import orient

from qd_terrain import polygons
from qd_waterfront import Waterfront

CORE_SCOPE = "surveyed-nearshore-108m-v1"
OFFSHORE = "外海 · 仅全景"
SECTION = "近岸海域剖面"
# Scene-linear colour of the illustrative cross-section.
SECTION_RGB = [.12, .185, .19]


def section_layout():
    """Emit a watertight base and outward-facing end/sea walls, leaving the beach open."""
    root = Path(__file__).resolve().parents[1]
    coast = Waterfront(json.loads((root / 'data/map/campus.json').read_text('utf8')))
    vertices, indices = [], []
    for part in polygons(coast.surf.area):
        shape = orient(part, sign=1)
        rings = [list(ring.coords)[:-1] for ring in (shape.exterior, *shape.interiors)]
        points = np.array([p for ring in rings for p in ring], dtype=np.float64)
        ends = np.cumsum([len(ring) for ring in rings], dtype=np.uint32)
        start = len(vertices)
        # Two copies of the unmodified shore outline, at the base and at sea level.
        for top in (0, 1):
            vertices.extend([round(x, 5), top, round(z, 5)] for x, z in points)
        indices.extend(int(i) + start for i in mapbox_earcut.triangulate_float64(points, ends))
        offset = 0
        for ring in rings:
            for i, a in enumerate(ring):
                j = (i + 1) % len(ring)
                b = ring[j]
                mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if coast.shore.distance(mid) < .0001:
                    continue
                lo, end = start + offset + i, start + offset + j
                top, top_end = lo + len(points), end + len(points)
                indices.extend((top, top_end, end, top, end, lo))
            offset += len(ring)
    return dict(vertices=vertices, indices=indices, color=SECTION_RGB)


def install_blender(scene):
    import bpy

    offshore, = [o for o in scene.objects if o.get('kind') == 'sea']
    ground_cut, = [o for o in scene.objects if o.get('sceneRegion') == 'cutEdge']
    focus = scene.view_layers["仅看建模区"]
    cut_collection, = ground_cut.users_collection
    full_only = bpy.data.collections.new(OFFSHORE)
    scene.collection.children.link(full_only)
    for col in list(offshore.users_collection):
        col.objects.unlink(offshore)
    full_only.objects.link(offshore)
    focus.layer_collection.children[full_only.name].exclude = True

    def elevation(obj):
        return min((obj.matrix_world @ v.co).z for v in obj.data.vertices)

    bottom, level = elevation(ground_cut), elevation(offshore)
    assert bottom < level
    data = section_layout()
    coords = [(x, -z, level if top else bottom) for x, top, z in data['vertices']]
    idx = data['indices']
    mesh = bpy.data.meshes.new(SECTION)
    mesh.from_pydata(coords, [], list(zip(idx[::3], idx[1::3], idx[2::3])))
    mesh.update()
    section = bpy.data.objects.new(SECTION, mesh)
    section['kind'] = 'terrainCut'
    section['sceneRegion'] = 'coreSeaCut'
    cut_collection.objects.link(section)
    material = bpy.data.materials.new(SECTION)
    material.diffuse_color = (*SECTION_RGB, 1.)
    material.use_nodes = True
    shader = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = material.diffuse_color
    shader.inputs['Roughness'].default_value = 1
    shader.inputs['Specular IOR Level'].default_value = 0
    mesh.materials.append(material)
    return verify_blender(scene)


def verify_blender(scene):
    focused = scene.view_layers["仅看建模区"]
    full = scene.view_layers[0]
    far, = [o for o in scene.objects if o.get('kind') == 'sea']
    surf, = [o for o in scene.objects if o.get('kind') == 'surfWater']
    section, = [o for o in scene.objects if o.get('sceneRegion') == 'coreSeaCut']
    full.update()
    focused.update()
    assert far.name in full.objects and far.name not in focused.objects, (far.name, [c.name for c in far.users_collection], [(layer.name, far.name in layer.objects, layer.layer_collection.children[OFFSHORE].exclude) for layer in (full,focused)])
    assert surf.name in full.objects and surf.name in focused.objects
    assert section.name not in full.objects and section.name in focused.objects
    assert len(surf.data.shape_keys.key_blocks) == 5
    return dict(offshoreFull=True, offshoreFocused=False, swashInBoth=True,
                sectionTriangles=len(section.data.polygons), surfShapeKeys=5)
