"""Yinghai Lake, from its exact v6 shoreline. Uses scene-linear colour and a tiled wind normal."""
import argparse
import json
import math
import os
from pathlib import Path
import struct
import tempfile

import mapbox_earcut as ear
import numpy as np
from PIL import Image
import shapely
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from qd_geometry import CampusFile
from qd_natural_finishes import WATER_IOR as IOR, WATER_SETTINGS, apply_water
from qd_spring_surfaces import add_image

LAKE_NAME = "樱海湖"
LAKE_ID = "way/982180787"
MATERIAL = "樱海湖 · 浅岸与青碧湖心"
TILE_METRES = 36.0
PERIOD = 11.2
# UV travel over one cycle. Two staggered samples hide the texture resets.
FLOW = (0.106, 0.043)
ROUGHNESS = WATER_SETTINGS['lake'][0]


def _array(scene, index):
    entry = scene.doc["accessors"][index]
    view = scene.doc["bufferViews"][entry["bufferView"]]
    dtype = {5126: "<f4", 5123: "<u2", 5125: "<u4"}[entry["componentType"]]
    width = {"SCALAR": 1, "VEC3": 3}[entry["type"]]
    offset = view.get("byteOffset", 0) + entry.get("byteOffset", 0)
    return np.frombuffer(scene.raw, dtype, count=entry["count"] * width, offset=offset).reshape(-1, width).copy()


def wind_normal(size=512):
    """A periodic height field in metres. Its derivatives give tangent-space slopes."""
    rng = np.random.default_rng(72014)
    z, x = (np.indices((size, size), dtype=float) + .5) * math.tau / size
    warp = 1.18 * np.sin(x + 2*z + .7) + .72 * np.sin(3*x - z + 2.4)
    gust = .79 + .12*np.sin(2*x - z + 1.3) + .10*np.cos(x + 3*z)
    height = np.zeros_like(x)
    # Spectral bands from broad wind ruffles to capillary ripples. Integer
    # wave vectors keep both the height and its slope seamless at the tile edges.
    for lo, hi, count, rms_slope, angle, spread in (
        (4, 12, 11, .042, .28, .39),
        (13, 33, 17, .038, .47, .25),
        (34, 74, 22, .024, .40, .17),
        (15, 50, 8, .014, -.73, .28),
    ):
        for _ in range(count):
            radius = np.exp(rng.uniform(np.log(lo), np.log(hi)))
            theta = rng.normal(angle, spread)
            kx, kz = np.rint(radius * np.array([np.cos(theta), np.sin(theta)])).astype(int)
            wave_number = math.tau * math.hypot(kx, kz) / TILE_METRES
            amplitude = rms_slope / (wave_number * math.sqrt(count / 2))
            phase = rng.uniform(0, math.tau)
            height += amplitude * np.sin(kx*x + kz*z + phase + warp * rng.uniform(.28, .95))
    height *= gust
    step = TILE_METRES / size
    sx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2 * step)
    sz = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2 * step)
    # UV U points east, V points south. Explicit mesh tangents carry handedness.
    slope = np.stack((-sx, -sz, np.ones_like(sx)), axis=-1)
    slope /= np.linalg.norm(slope, axis=-1, keepdims=True)
    return Image.fromarray(np.rint((slope + 1) * 127.5).astype("uint8"))


def _polygons(part):
    if part.geom_type == "Polygon":
        if part.area > 1e-8:
            yield part
    elif hasattr(part, "geoms"):
        for child in part.geoms:
            yield from _polygons(child)


def shore_mesh(footprint, step=2.25):
    """Clip a small grid to the original mesh, sharing all neighbouring vertices."""
    x0, z0, x1, z1 = footprint.bounds
    index, points, triangles = {}, [], []
    for x in np.arange(math.floor(x0/step)*step, x1, step):
        for z in np.arange(math.floor(z0/step)*step, z1, step):
            cut = footprint.intersection(box(x, z, x+step, z+step))
            for part in _polygons(cut):
                rings = [np.asarray(r.coords)[:-1] for r in (part.exterior, *part.interiors)]
                flat = np.ascontiguousarray(np.concatenate(rings), dtype=np.float64)
                ends = np.cumsum([len(r) for r in rings], dtype=np.uint32)
                faces = ear.triangulate_float64(flat, ends).reshape(-1, 3)
                ids = []
                for point in flat:
                    key = tuple(np.round(point, 7))
                    if key not in index:
                        index[key] = len(points)
                        points.append(point)
                    ids.append(index[key])
                for a, b, c in faces:
                    # earcut is counterclockwise in x,z; glTF's up axis is Y.
                    triangles.append((ids[c], ids[b], ids[a]))
    points = np.array(points)
    triangles = np.asarray(triangles, dtype=np.uint32)
    tri = points[triangles]
    signed = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    keep = signed < -1e-8
    if np.any(signed > 1e-8) or not np.isclose(-.5*signed[keep].sum(), footprint.area, atol=.001):
        raise ValueError("The lake surface no longer matches the source shoreline.")
    return points, triangles[keep]


def _linear(rgb):
    srgb = np.asarray(rgb, dtype=float) / 255
    return np.where(srgb < .04045, srgb / 12.92, ((srgb + .055)/1.055)**2.4)


def water_colours(points, footprint):
    x, z = points.T
    distance = shapely.distance(shapely.points(points), footprint.boundary)
    # The extra attenuation near the bank represents the shallow, visible bed.
    # This describes effective water colour; it is not a surveyed depth map.
    shelf = 3.7 + 1.15*np.sin(.055*x + .032*z) + .75*np.cos(.087*z)
    deep = 1 - np.exp(-np.maximum(0., distance) / (shelf+3.4))
    bed = np.exp(-np.maximum(0., distance) / shelf)
    broad = .54*np.sin(.063*x+.030*z+.9*np.sin(.081*z)) + .46*np.cos(.108*z-.046*x+1.6)
    deep_colour = _linear([47, 92, 96])
    middle = _linear([78, 126, 119])
    edge = _linear([132, 152, 131])
    body = middle + (deep_colour-middle)*deep[:, None]
    body += (edge-middle)*bed[:, None]
    body *= (1 + broad * (.052 + .075 * bed))[:, None]
    return body.astype("<f4")


def refine(scene):
    targets = [n for n in scene.doc["nodes"] if n.get("name") == LAKE_NAME and
               n.get("extras", {}).get("kind") == "water"]
    if len(targets) != 1:
        raise ValueError("Expected one mapped Yinghai Lake mesh.")
    node = targets[0]
    if node["extras"].get("lakeWater") == LAKE_ID:
        slot = scene.doc['meshes'][node['mesh']]['primitives'][0]['material']
        mat = scene.doc['materials'][slot]
        previous = json.dumps(mat, sort_keys=True)
        apply_water(mat, 'lake')
        return {'waterFinishUpdated': True} if previous != json.dumps(mat, sort_keys=True) else None
    if sum(n.get("mesh") == node["mesh"] for n in scene.doc["nodes"]) != 1:
        raise ValueError("The target water geometry unexpectedly became shared.")
    mesh = scene.doc["meshes"][node["mesh"]]
    original, = mesh["primitives"]
    pos = _array(scene, original["attributes"]["POSITION"])
    idx = _array(scene, original["indices"]).reshape(-1, 3)
    if np.ptp(pos[:, 1]) > .001:
        raise ValueError("The source lake water level is not horizontal.")
    footprint = unary_union([Polygon(pos[ids][:, [0, 2]]) for ids in idx])
    points, faces = shore_mesh(footprint)
    colours = water_colours(points, footprint)
    y = float(pos[0, 1])
    p = np.column_stack((points[:, 0], np.full(len(points), y), points[:, 1]))
    normal = np.tile([0, 1, 0], (len(points), 1))
    tangent = np.tile([1, 0, 0, -1], (len(points), 1))
    # A local origin preserves sample precision on mobile GPUs.
    uv = (points - np.array(footprint.bounds[:2])) / TILE_METRES
    tex = add_image(scene, "樱海湖 · 36米微风波纹法线", wind_normal(), "PNG", True)
    mat = {
        "name": MATERIAL, "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1],
        "metallicFactor": 0, "roughnessFactor": ROUGHNESS}, "normalTexture": tex,
        "doubleSided": False, "extensions": {"KHR_materials_ior": {"ior": IOR}},
        "extras": {"lakeWater": LAKE_ID, "periodSeconds": PERIOD, "flowUV": list(FLOW),
                   "tileMetres": TILE_METRES},
    }
    apply_water(mat, 'lake')
    if "KHR_materials_ior" not in scene.doc.setdefault("extensionsUsed", []):
        scene.doc["extensionsUsed"].append("KHR_materials_ior")
    m = len(scene.doc["materials"])
    scene.doc["materials"].append(mat)
    attributes = {name: scene.accessor(values, "<f4", kind, 5126, 34962) for name, values, kind in (
        ("POSITION", p, "VEC3"), ("NORMAL", normal, "VEC3"), ("TANGENT", tangent, "VEC4"),
        ("COLOR_0", colours, "VEC3"), ("TEXCOORD_0", uv, "VEC2"))}
    ni = scene.accessor(faces.ravel(), "<u2", "SCALAR", 5123, 34963)
    mesh["primitives"] = [{"attributes": attributes, "indices": ni, "material": m}]
    node["extras"].update(lakeWater=LAKE_ID)
    return {"sourceArea": round(footprint.area, 4), "waterLevel": y, "vertices": len(points),
            "triangles": len(faces), "bbox": list(footprint.bounds)}


def install_blender(scene):
    """Keep the imported vertex colour and PBR specular, animate the packed normal only."""
    targets = [o for o in scene.objects if o.get("lakeWater") == LAKE_ID]
    if len(targets) != 1:
        raise ValueError("Missing editable Yinghai Lake surface.")
    obj = targets[0]
    mat, = obj.data.materials
    if mat.get("风纹循环秒") == PERIOD:
        return
    nt = mat.node_tree
    normal = next(n for n in nt.nodes if n.type == "NORMAL_MAP")
    tex = normal.inputs["Color"].links[0].from_node
    if tex.type != "TEX_IMAGE" or not tex.image or not tex.image.packed_file:
        raise ValueError("Missing packed lake micro-normal.")
    shader = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if not shader.inputs["Base Color"].is_linked or not obj.data.color_attributes:
        raise ValueError("Missing shoreline-distance colours.")
    mat.diffuse_color = tuple(_linear([62, 110, 109])) + (1.,)

    def new(kind, label, x, y):
        n = nt.nodes.new(kind)
        n.label = label
        n.location = (x, y)
        return n

    def maths(operation, label, x, y, a, b=None):
        n = new("ShaderNodeMath", label, x, y)
        n.operation = operation
        for socket, value in zip(n.inputs, (a, b)):
            if value is None:
                continue
            if isinstance(value, (float, int)):
                socket.default_value = value
            else:
                nt.links.new(value, socket)
        return n.outputs[0]

    offset = new("ShaderNodeValue", "时间相位 · 0–1", -1490, -40)
    start = scene.frame_start
    end = start + PERIOD*scene.render.fps/scene.render.fps_base
    value = offset.outputs[0]
    value.default_value = 0
    value.keyframe_insert(data_path="default_value", frame=start)
    value.default_value = 1
    value.keyframe_insert(data_path="default_value", frame=end)
    action = nt.animation_data.action
    action.name = "樱海湖 · 微风起伏"
    for curve in action.fcurves:
        for k in curve.keyframe_points:
            k.interpolation = "LINEAR"
        curve.modifiers.new("CYCLES")
    uv = new("ShaderNodeUVMap", "36米 · 风纹坐标", -905, -720)
    uv.uv_map = obj.data.uv_layers.active.name
    a = maths("ADD", "半周期错开", -1300, -50, value, .5)
    a = maths("FRACT", "纹理周期", -1120, -50, a)
    a = maths("SUBTRACT", "风纹 A", -940, -50, a, .5)
    b = maths("SUBTRACT", "风纹 B", -940, -290, value, .5)
    phase = maths("MULTIPLY", "余弦相位", -1270, 160, value, math.tau)
    wave = maths("COSINE", "连续过渡", -1080, 160, phase)
    wave = maths("MULTIPLY", "过渡振幅", -895, 160, wave, -.5)
    weight = maths("ADD", "两层权重", -710, 160, wave, .5)
    second = new("ShaderNodeTexImage", "风纹 B · 同一张法线", -180, -510)
    second.image = tex.image
    tex.label = "风纹 A · 嵌入式法线"
    tex.location = (-180, -180)
    for i, (amount, image) in enumerate(((a, tex), (b, second))):
        row = -180 - 310*i
        motion = new("ShaderNodeVectorMath", "风向 · 位移", -700, row)
        motion.operation = "SCALE"
        # glTF's downward V becomes Blender's upward V on import.
        motion.inputs[0].default_value = (-FLOW[0], FLOW[1], 0.)
        nt.links.new(amount, motion.inputs["Scale"])
        add = new("ShaderNodeVectorMath", "采样位置", -450, row)
        add.operation = "ADD"
        nt.links.new(uv.outputs[0], add.inputs[0])
        nt.links.new(motion.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], image.inputs["Vector"])
    mix = new("ShaderNodeMixRGB", "循环交叉 · 抑制接缝", 105, -200)
    nt.links.new(weight, mix.inputs[0])
    nt.links.new(tex.outputs["Color"], mix.inputs[1])
    nt.links.new(second.outputs["Color"], mix.inputs[2])
    nt.links.new(mix.outputs[0], normal.inputs["Color"])
    normal.location = (310, -210)
    mat["风纹循环秒"] = PERIOD
    mat["岸线依据"] = LAKE_ID
    scene.frame_set(scene.frame_current)


def patch_file(source, output):
    """Incremental build for a copied v6 GLB. All other meshes keep their indices."""
    scene = CampusFile()
    with Path(source).open("rb") as f:
        magic, version, length, count, tag = struct.unpack("<4sIII4s", f.read(20))
        assert (magic, version, tag) == (b"glTF", 2, b"JSON")
        scene.doc = json.loads(f.read(count))
        count, tag = struct.unpack("<I4s", f.read(8))
        assert tag == b"BIN\0" and length == Path(source).stat().st_size
        scene.raw = bytearray(f.read(count))
    result = refine(scene)
    output = Path(output)
    if result is None and Path(source).resolve() == output.resolve():
        return result
    fd, temporary = tempfile.mkstemp(prefix=output.stem + "-", suffix=".glb", dir=output.parent)
    os.close(fd)
    try:
        scene.save(temporary)
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    print(json.dumps(patch_file(args.input, args.output), ensure_ascii=False))
