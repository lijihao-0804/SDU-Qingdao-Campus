"""Build or reopen the editable Qingdao campus with Blender 4.3+.
Run with a Python environment containing bpy, or Blender --background --python.
"""
from pathlib import Path
import collections
import contextlib
import hashlib
import io
import json
import math
import os
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = "山东大学青岛校区"
GLB = ROOT / (BASE + ".glb")
BLEND = ROOT / (BASE + ".blend")
WORK = ROOT / ".jobs" / "blender"
WORK.mkdir(parents=True, exist_ok=True)
for variable, directory in {
    "BLENDER_USER_RESOURCES": "resources", "BLENDER_USER_CONFIG": "config",
    "BLENDER_USER_EXTENSIONS": "extensions", "TEMP": "temp", "TMP": "temp",
}.items():
    output = WORK / directory
    output.mkdir(exist_ok=True)
    os.environ[variable] = str(output)

import bpy
from mathutils import Vector

def source_header():
    with GLB.open("rb") as stream:
        magic, version, length, count, section = struct.unpack("<4sIII4s", stream.read(20))
        if magic != b"glTF" or version != 2 or section != b"JSON" or length != GLB.stat().st_size:
            raise RuntimeError("Source GLB is invalid or still being written.")
        return json.loads(stream.read(count))

def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib,"file_digest") else stream_hash(stream)

def stream_hash(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(2**20), b""):
        digest.update(block)
    return digest.hexdigest()

def group(parent, name):
    col = bpy.data.collections.new(name)
    parent.children.link(col)
    return col

def set_variation(mat, shader, scale, contrast, bump_depth, second_scale):
    tree=mat.node_tree
    coord=tree.nodes.new("ShaderNodeNewGeometry")
    coord.label="世界空间位置 · 单位米"; coord.location=(-760,40)
    pat=tree.nodes.new("ShaderNodeTexNoise")
    pat.label="表面色差"; pat.location=(-530,150)
    pat.inputs["Scale"].default_value=scale;pat.inputs["Detail"].default_value=3.8
    tree.links.new(coord.outputs["Position"],pat.inputs["Vector"])
    ramp=tree.nodes.new("ShaderNodeValToRGB")
    ramp.label="色调范围";ramp.location=(-260,170)
    base=tuple(shader.inputs["Base Color"].default_value)[:3]
    for stop, falloff in zip(ramp.color_ramp.elements,(1-contrast,1+contrast)):
        stop.color=tuple(min(.98,max(.003,c*falloff)) for c in base)+(1.,)
    tree.links.new(pat.outputs["Fac"],ramp.inputs["Fac"])
    base_socket=shader.inputs["Base Color"]
    if base_socket.is_linked:
        original=base_socket.links[0].from_socket
        blend=tree.nodes.new("ShaderNodeMixRGB");blend.blend_type="MULTIPLY";blend.inputs[0].default_value=1.
        for stop,t in zip(ramp.color_ramp.elements,(1.-contrast,1.)):
            stop.color=(t,t,t,1.)
        tree.links.new(original,blend.inputs[1]);tree.links.new(ramp.outputs["Color"],blend.inputs[2])
        tree.links.new(blend.outputs[0],base_socket)
    else:tree.links.new(ramp.outputs["Color"],base_socket)
    grain=tree.nodes.new("ShaderNodeTexNoise")
    grain.label="微表面颗粒";grain.location=(-530,-100);grain.inputs["Scale"].default_value=second_scale
    grain.inputs["Detail"].default_value=2
    tree.links.new(coord.outputs["Position"],grain.inputs["Vector"])
    bump=tree.nodes.new("ShaderNodeBump")
    bump.label="微表面法线";bump.location=(-250,-100);bump.inputs["Strength"].default_value=.24
    bump.inputs["Distance"].default_value=bump_depth
    normal = shader.inputs["Normal"]
    if normal.is_linked:
        tree.links.new(normal.links[0].from_socket, bump.inputs["Normal"])
    tree.links.new(grain.outputs["Fac"],bump.inputs["Height"]);tree.links.new(bump.outputs["Normal"],normal)

GLASS_COLORS={"glass","#526d78","#304852","#567d8a","#708b92","#506d7b","#778b7b","#5f7269"}
FINISHES={"#d2b89b":"图书馆 · 暖色石材","#e6d2b5":"图书馆 · 浅色石材","#f0dec0":"图书馆 · 檐口石材",
          "#ae937b":"图书馆 · 阴影石材","#974e45":"砖红饰面","#a45e53":"陶瓦屋顶",
          "#e6e4da":"博物馆 · 白色饰面","#a66555":"公寓 · 砖红外墙","#ac7160":"教学楼 · 红砖",
          "#687e7d":"屋面灰瓦","#c4b49f":"石质基座","#ddcfb9":"窗台与线脚",
          "stone":"石材铺装","leaf":"植物叶片"}

def finish_materials(source):
    source_materials={m["name"]:m for m in source["materials"]}
    for material in list(bpy.data.materials):
        if not material.use_nodes:continue
        shader=next((n for n in material.node_tree.nodes if n.type=="BSDF_PRINCIPLED"),None)
        if shader is None:continue
        name=material.name.lower()
        material["源材质"]=material.name
        rec = source_materials.get(material.name, {})
        if rec.get("extensions", {}).get("KHR_materials_specular", {}).get("specularFactor") == 0:
            # An explicit factor of zero nulls even a linked specular texture.
            # Preserve all colour, normal and roughness connections.
            level = shader.inputs["Specular IOR Level"]
            for link in list(level.links):
                material.node_tree.links.remove(link)
            level.default_value = 0.0
        rgba=tuple(shader.inputs["Base Color"].default_value)
        material.diffuse_color=rgba
        if source_materials.get(material["源材质"],{}).get("extras",{}).get("archFinish"):
            for key,val in source_materials[material["源材质"]]["extras"].items():material[key]=val
            # The glTF importer can wire a tint through a texture node. Set the
            # solid-mode viewport swatch from the same calibrated linear tint.
            rec=source_materials[material["源材质"]]
            material.diffuse_color=rec["pbrMetallicRoughness"]["baseColorFactor"]
            continue
        if name=="grass":
            material.name="地表 · 混合草地"
            set_variation(material,shader,.12,.10,.004,19.)
        elif name=="asphalt":
            material.name="路面 · 沥青"
            set_variation(material,shader,.40,.12,.013,20.)
        elif name=="water":
            material.name="水体 · 海面与湖面"
            tree=material.node_tree; coord=tree.nodes.new("ShaderNodeNewGeometry");coord.location=(-810,40)
            warp=tree.nodes.new("ShaderNodeVectorMath");warp.operation="MULTIPLY";warp.location=(-605,30)
            warp.inputs[1].default_value=(.35,1.6,1);tree.links.new(coord.outputs["Position"],warp.inputs[0])
            noise=tree.nodes.new("ShaderNodeTexNoise");noise.label="随风水纹";noise.location=(-410,30)
            noise.inputs["Scale"].default_value=.67;noise.inputs["Detail"].default_value=2.5
            tree.links.new(warp.outputs[0],noise.inputs["Vector"])
            bump=tree.nodes.new("ShaderNodeBump");bump.location=(-190,10)
            bump.inputs["Strength"].default_value=.14;bump.inputs["Distance"].default_value=.07
            tree.links.new(noise.outputs["Fac"],bump.inputs["Height"]);tree.links.new(bump.outputs[0],shader.inputs["Normal"])
        elif name in GLASS_COLORS or name in ('#405766','#3c6072','#465966','#516671','#687b83'):
            material.name="玻璃 · "+name
        elif name in ('#ded4bf','#d9cbb7','#e2d9c9','#eee3ce','#b1aaa0'):
            set_variation(material,shader,1.2,.10,.004,33.)
            material.name="石材 · "+name.upper()
        elif name in ('#bd684f','#b65e4b'):
            set_variation(material,shader,.7,.085,.008,13.)
            material.name="陶瓦 · "+name.upper()
        elif name in FINISHES:
            material.name=FINISHES[name]
        elif name.startswith("#"):
            material.name="饰面 "+name.upper()

def sync_surface_display(source, verify=False):
    """Audit actual Principled inputs and give Workbench the same average finish."""
    from PIL import Image, ImageStat

    records = {m["name"]: m for m in source["materials"]}
    maps, packed_hashes = {}, {}
    checked = 0
    matte = set()
    with GLB.open("rb") as stream:
        stream.seek(12)
        binary_start = 28 + struct.unpack("<I", stream.read(4))[0]

        def channel_value(socket, factor, texture=None, channel=0):
            # Follow the live importer graph. A linked input ignores its default.
            tag = (socket.id_data.name, socket.name)
            if texture is None:
                assert not socket.is_linked and abs(socket.default_value - factor) < 1e-5, tag
                return factor
            link = socket.links[0]
            if link.from_node.type == "MATH":
                multiply = link.from_node
                assert multiply.operation == "MULTIPLY", tag
                assert not multiply.inputs[1].is_linked and abs(multiply.inputs[1].default_value - factor) < 1e-5, tag
                link = multiply.inputs[0].links[0]
            else:
                assert factor == 1.0, tag
            separate = link.from_node
            assert separate.type == "SEPARATE_COLOR" and separate.mode == "RGB", tag
            assert link.from_socket.name == ("Red", "Green", "Blue")[channel], tag
            image = separate.inputs[0].links[0].from_node.image
            assert image.packed_file and image.colorspace_settings.name == "Non-Color", tag
            image_id = source["textures"][texture["index"]]["source"]
            if image_id not in maps:
                view = source["bufferViews"][source["images"][image_id]["bufferView"]]
                stream.seek(binary_start + view.get("byteOffset", 0))
                encoded = stream.read(view["byteLength"])
                with Image.open(io.BytesIO(encoded)) as bitmap:
                    means = ImageStat.Stat(bitmap.convert("RGB")).mean
                maps[image_id] = hashlib.sha256(encoded).digest(), means
            if image not in packed_hashes:
                packed_hashes[image] = hashlib.sha256(image.packed_file.data).digest()
            digest, means = maps[image_id]
            assert packed_hashes[image] == digest, tag
            return factor * means[channel] / 255.0

        for mat in bpy.data.materials:
            rec = records.get(mat.get("源材质"))
            if rec is None or not mat.node_tree:
                continue
            shader = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if shader is None:
                continue
            pbr = rec["pbrMetallicRoughness"]
            mr = pbr.get("metallicRoughnessTexture")
            ext = rec.get("extensions", {})
            coat = ext.get("KHR_materials_clearcoat", {})
            specular = ext.get("KHR_materials_specular", {}).get("specularFactor", 1)
            inputs = shader.inputs
            rough = channel_value(inputs["Roughness"], pbr.get("roughnessFactor", 1), mr, 1)
            metal = channel_value(inputs["Metallic"], pbr.get("metallicFactor", 1), mr, 2)
            spec = channel_value(inputs["Specular IOR Level"], specular * .5)
            channel_value(inputs["IOR"], ext.get("KHR_materials_ior", {}).get("ior", 1.5))
            coat_weight = channel_value(inputs["Coat Weight"], coat.get("clearcoatFactor", 0), coat.get("clearcoatTexture"))
            if specular == 0:
                # Zero in the base BRDF alone would still allow a second coat,
                # a metallic lobe, or a separate glossy shader to reflect light.
                assert metal == 0 and coat_weight == 0, mat.name
                for key in ("Sheen Weight", "Transmission Weight"):
                    channel_value(inputs[key], 0.0)
                output = next(n for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
                assert output.inputs["Surface"].links[0].from_node == shader, mat.name
                matte.add(rec["name"])
            if "clearcoatRoughnessFactor" in coat:
                channel_value(inputs["Coat Roughness"], coat["clearcoatRoughnessFactor"], coat.get("clearcoatRoughnessTexture"), 1)
            if verify:
                assert max(abs(a-b) for a,b in zip((mat.roughness,mat.metallic,mat.specular_intensity),
                                                   (rough,metal,spec))) < 1e-5, mat.name
            else:
                mat.roughness, mat.metallic, mat.specular_intensity = rough, metal, spec
            checked += 1
    used_meshes = {node["mesh"] for node in source["nodes"] if "mesh" in node}
    used_slots = {prim["material"] for index in used_meshes for prim in source["meshes"][index]["primitives"]
                  if "material" in prim}
    used_materials = (source["materials"][i] for i in used_slots)
    expected_matte = {m["name"] for m in used_materials
                      if m.get("extensions", {}).get("KHR_materials_specular", {}).get("specularFactor") == 0}
    assert expected_matte <= matte, sorted(expected_matte - matte)
    return {"materials": checked, "packedSurfaceMaps": len(maps), "zeroSpecularMaterials": len(matte)}

def component_groups(objects):
    """Attach the authored construction parts to the exact imported landmark faces."""
    import numpy as np
    from qd_geometry import Shape
    import qd_landmarks, qd_civic

    class ComponentShape(Shape):
        def __init__(self, name):
            super().__init__(name)
            self.spans = collections.defaultdict(list)

        def mesh(self, name, vertices, faces, material):
            indices=self.parts[material][2]
            start=len(indices)//3
            super().mesh(name,vertices,faces,material)
            end=len(indices)//3
            if end>start:
                self.spans[material].append((name,start,end))

    specs={s["key"]:(mod,s) for mod in (qd_landmarks,qd_civic) for s in mod.SPECS}
    counts={}
    for obj in objects:
        key=obj.get("key","")
        if obj.get("kind")!="landmark" or key not in specs:
            continue
        mod,spec=specs[key]; construction=ComponentShape(obj.name)
        mod.build(construction,key,spec["w"],spec["d"],spec["h"])
        geo=obj.data
        face_slots=np.empty(len(geo.polygons),np.int32)
        centers=np.empty(3*len(geo.polygons),np.float32)
        geo.polygons.foreach_get("material_index",face_slots)
        geo.polygons.foreach_get("center",centers)
        centers=centers.reshape(-1,3)
        faces_by_name=collections.defaultdict(list)
        for slot_index,slot in enumerate(geo.materials):
            matkey=slot.get("sourceSurface",slot.get("源材质",slot.name))
            if matkey not in construction.spans:
                continue
            positions,_,indices=construction.parts[matkey]
            expected=np.asarray(positions,dtype=np.float32)[np.asarray(indices).reshape(-1,3)].mean(axis=1)[:,[0,2,1]]
            expected[:,1]*=-1
            imported=np.flatnonzero(face_slots==slot_index)
            if len(imported)!=len(expected):
                continue
            if not np.allclose(expected,centers[imported],atol=.015,rtol=1e-5):
                # Geometry can be reordered by importer optimisations. Never assign unverified spans.
                continue
            for name,start,end in construction.spans[matkey]:
                faces_by_name[name].append(imported[start:end])
        if not faces_by_name:continue
        face_codes=np.zeros(len(geo.polygons),dtype=np.int32)
        corners=np.empty(len(geo.loops),np.int32);geo.loops.foreach_get("vertex_index",corners)
        loop_starts=np.empty(len(geo.polygons),np.int32);geo.polygons.foreach_get("loop_start",loop_starts)
        for code,(name,sections) in enumerate(faces_by_name.items(),start=1):
            face_indices=np.concatenate(sections)
            face_codes[face_indices]=code
            indices=corners[(loop_starts[face_indices,None]+np.arange(3)).ravel()]
            obj.vertex_groups.new(name=name).add(np.unique(indices).tolist(),1.,"REPLACE")
        face_data=geo.attributes.new("component_id","INT","FACE")
        face_data.data.foreach_set("value",face_codes)
        obj["构件面组"]=json.dumps({str(i):v for i,v in enumerate(faces_by_name,start=1)},ensure_ascii=False)
        obj["可按构件选择"]="编辑模式中选择顶点组，或按面属性 component_id 精确筛选。"
        counts[key]=[len(faces_by_name),int(np.count_nonzero(face_codes)),len(face_codes)]
    print("Verified named landmark component groups",counts,flush=True)
    return counts

def configure_scene(scene):
    scene.render.engine="CYCLES"
    scene.cycles.samples=32
    # Preview nearby buildings and shoreline in low-roughness surfaces; keep
    # full-scene Cycles transport for the saved renders.
    scene.eevee.use_raytracing = True
    scene.eevee.ray_tracing_method = "SCREEN"
    scene.eevee.ray_tracing_options.resolution_scale = "2"
    # Rays through layered alpha foliage must reach the lit leaves and sky.
    scene.cycles.transparent_max_bounces=48
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1800; scene.render.resolution_y=1080; scene.render.resolution_percentage=100
    scene.render.film_transparent=False;scene.render.filepath="//preview/Blender-"
    scene.unit_settings.system="METRIC"
    scene.unit_settings.length_unit="METERS"
    scene.view_settings.view_transform="AgX"
    from v6_sunset import HDR, SETTINGS
    scene.view_settings.look=SETTINGS["blenderLook"]
    scene.view_settings.exposure=SETTINGS["blenderExposureEV"]
    world=bpy.data.worlds.new("鳌山湾 · 夕照天空");world.use_nodes=True;scene.world=world
    # The HDR already contains the visible disk. The native SUN supplies direct sunlight.
    world.sun_threshold = 0.0
    scene.display.shading.color_type = "MATERIAL"
    # Workbench studio highlights ignore per-material Specular IOR Level.
    # Physical glass and water reflections are shown in Material/Rendered view.
    scene.display.shading.show_specular_highlight = False
    nodes=world.node_tree.nodes
    bg=nodes.get("Background")
    bg.label="黄昏环境补光";bg.inputs["Strength"].default_value=SETTINGS["blenderWorldStrength"]
    texture=nodes.new("ShaderNodeTexEnvironment");texture.location=(-340,100)
    texture.label="西方晚霞和东方海天 · 线性 HDR"
    texture.image=bpy.data.images.load(str(HDR),check_existing=True)
    texture.image.pack()
    world.node_tree.links.new(texture.outputs["Color"],bg.inputs["Color"])
    scene["太阳方位角（度，自北顺时针）"]=SETTINGS["azimuthDeg"]
    scene["太阳高度角（度）"]=SETTINGS["elevationDeg"]
    scene["日照设定"]=SETTINGS["interpretation"]

    # Surface mist gives distance cues over the bay. The depth mask leaves the
    # emitting sky itself untouched, including the small western solar disc.
    layer=scene.view_layers[0]
    layer.use_pass_mist=True;layer.use_pass_z=True
    world.mist_settings.start=120.0;world.mist_settings.depth=8200.0
    world.mist_settings.falloff="QUADRATIC"
    scene.use_nodes=True
    tree=scene.node_tree;tree.nodes.clear()
    render=tree.nodes.new("CompositorNodeRLayers");render.location=(-570,130)
    geometry=tree.nodes.new("CompositorNodeMath");geometry.operation="LESS_THAN"
    geometry.inputs[1].default_value=28000.;geometry.location=(-345,-170);geometry.label="仅地表、海陆和建筑"
    tree.links.new(render.outputs["Depth"],geometry.inputs[0])
    mask=tree.nodes.new("CompositorNodeMath");mask.operation="MULTIPLY";mask.location=(-135,-110)
    tree.links.new(geometry.outputs[0],mask.inputs[0]);tree.links.new(render.outputs["Mist"],mask.inputs[1])
    fade=tree.nodes.new("CompositorNodeMath");fade.operation="MULTIPLY";fade.location=(55,-100)
    fade.inputs[1].default_value=.56;tree.links.new(mask.outputs[0],fade.inputs[0])
    veil=tree.nodes.new("CompositorNodeMixRGB");veil.location=(280,130);veil.label="鳌山湾 · 远景暮霭"
    veil.inputs[2].default_value=(.42,.40,.44,1.)
    tree.links.new(fade.outputs[0],veil.inputs[0]);tree.links.new(render.outputs["Image"],veil.inputs[1])
    final=tree.nodes.new("CompositorNodeComposite");final.location=(500,130);tree.links.new(veil.outputs[0],final.inputs[0])

def camera(parent,name,focus,offset,scale,ortho=True):
    data=bpy.data.cameras.new(name);data.type="ORTHO" if ortho else "PERSP"
    data.ortho_scale=scale;data.lens=45;data.clip_end=18000;data.clip_start=.3
    obj=bpy.data.objects.new(name,data);parent.objects.link(obj);obj.location=focus+Vector(offset)
    obj.rotation_euler=(focus-obj.location).to_track_quat("-Z","Y").to_euler()
    obj["视点目标"]=tuple(focus)
    obj.hide_select=True
    return obj

def lighting_and_cameras(scene,rig,site,locations):
    from v6_sunset import SETTINGS, sun_enu
    sunlight=bpy.data.lights.new("落日 · 西南偏西","SUN")
    sunlight.energy=SETTINGS["blenderSunEnergy"]
    sunlight.angle=math.radians(SETTINGS["sunDiameterDeg"])
    sunlight.color=SETTINGS["sunLinearRGB"]
    sun=bpy.data.objects.new("落日 · 西南偏西",sunlight);rig.objects.link(sun)
    sun.location=Vector(sun_enu())*2200
    sun.rotation_euler=(-sun.location).to_track_quat("-Z","Y").to_euler()
    # West-facing architectural fronts overlook the campus approach. The bay lies in the distance.
    focus=Vector((15,0,10))
    overview=camera(rig,"全校 · 西南鸟瞰",focus,(-2450,-1500,2100),3150)
    basis=overview.rotation_euler.to_quaternion()
    right,up=basis@Vector((1,0,0)),basis@Vector((0,1,0))
    pts=[Vector((x,-z,25)) for x,z in site["boundary"]]
    xx=[p.dot(right) for p in pts]; yy=[p.dot(up) for p in pts]
    target=focus+right*((max(xx)+min(xx))/2-focus.dot(right))+up*((max(yy)+min(yy))/2-focus.dot(up))
    overview.location+=target-focus
    overview["视点目标"]=tuple(target)
    aspect=scene.render.resolution_x/scene.render.resolution_y
    overview.data.ortho_scale=1.23*max(max(xx)-min(xx),(max(yy)-min(yy))*aspect)
    scene.camera=overview
    camera(rig,"南区 · 教学与博物馆",Vector((120,-290,20)),(-850,-500,710),1700)
    library=next((p for p in locations if p["key"]=="library"),None)
    if library:
        at=Vector((library["x"],-library["z"],library["y"]+25))
        camera(rig,"图书馆 · 西立面",at,(-220,-102,84),200,False)
    locations=list(locations)
    known={place["key"] for place in locations}
    locations.extend(place for place in SETTINGS.get("viewpoints",[]) if place["key"] not in known)
    for place in locations:
        poses=place.get('views') or ({('影像' if place.get('group')=='航拍影像对照' else 'visit' if place.get('group') in ('校园场地','运动场地','体育场地') else 'coast'):place['viewpoint']} if 'viewpoint' in place else {})
        for mode,pose in poses.items():
            destination=Vector((pose['target'][0],-pose['target'][2],pose['target'][1]))
            eye=Vector((pose['eye'][0],-pose['eye'][2],pose['eye'][1]))
            label=pose.get('label') or {'entrance':'门前','facade':'立面','roof':'屋顶','roof_plan':'正俯屋顶','roof_edge':'檐口近景','coast':'海岸','visit':'实景视角','影像':'航拍对照'}[mode]
            label=pose.get('label') or ('花木' if place['group']=='春日花木' else '实景视角' if place['group']=='院楼与生活区' else '夕照' if place['group']=='夕照时分' else label)
            ob=camera(rig,place['name']+' · '+label,destination,eye-destination,50,False)
            ob.data.angle=2*math.atan(math.tan(math.radians(pose.get('fov',42))/2)*scene.render.resolution_x/scene.render.resolution_y)
    return overview,target

def layer_for(obj):
    if obj.get("sceneRegion")=="surroundings":return "hinterland"
    if obj.get("sceneRegion")=="cutEdge":return "cutEdge"
    kind=obj.get("kind","")
    if kind=="signage":return "signage"
    if kind.startswith("waterfront"):return "waterfront"
    if kind=="groundcover":return "grass"
    if kind=="flora":return "shrub" if obj.get("shrub") else "tree"
    if kind in ("sea","water","surfWater"):return "water"
    if kind in ("context","background","terrain","coast","regional","coastal_context","terrainContext"):return "ground"
    if kind=="landmark":
        if "track" in obj.get("key",""):return "sport"
        return "landmark"
    if kind=="building":return "building"
    if kind=="sport":return "sport"
    if kind=="ground" and any(a in obj.name for a in ("路","车","桥","步行","街")):return "roads"
    if kind=="ground" and "球场" in obj.name:return "sport"
    if kind in ("plaza","landscape","furniture"):return "landscape"
    if kind=="hinterland":return "hinterland"
    return "ground" if kind=="ground" else "landscape"

def verify_glb_sun(source, settings, expected_enu):
    """Check the single active glTF key light, including its world orientation."""
    from mathutils import Matrix, Quaternion
    lights=source.get("extensions",{}).get("KHR_lights_punctual",{}).get("lights",[])
    nodes=source["nodes"]
    active=set()
    queue=list(source["scenes"][source.get("scene",0)]["nodes"])
    parents={}
    while queue:
        index=queue.pop()
        if index in active:
            continue
        active.add(index)
        for child in nodes[index].get("children",[]):
            parents[child]=index
            queue.append(child)
    suns=[]
    for index in active:
        reference=nodes[index].get("extensions",{}).get("KHR_lights_punctual")
        if reference is not None and lights[reference["light"]]["type"]=="directional":
            suns.append((index,lights[reference["light"]]))
    assert len(suns)==1,("default-scene glTF directional lights",len(suns))
    index,light=suns[0];node=nodes[index]
    assert node.get("name")=="SDU_Sunset_Key" and node.get("extras",{}).get("kind")=="sunsetRig"
    colour=light.get("color",[1.,1.,1.])
    assert max(abs(a-b) for a,b in zip(colour,settings["sunLinearRGB"]))<1e-5
    assert abs(light.get("intensity",1.)-settings["threeSunIntensity"])<1e-5
    orientation=Matrix.Identity(4)
    while True:
        item=nodes[index]
        if "matrix" in item:
            flat=item["matrix"]
            local=Matrix([flat[k:k+4] for k in range(0,16,4)]).transposed()
        else:
            x,y,z,w=item.get("rotation",[0,0,0,1])
            local=Matrix.LocRotScale(Vector(item.get("translation",[0,0,0])),Quaternion((w,x,y,z)),
                                     Vector(item.get("scale",[1,1,1])))
        orientation=local @ orientation
        if index not in parents:
            break
        index=parents[index]
    # -Z emits light in glTF. +Z points towards the sun.
    direction=(orientation.to_3x3() @ Vector((0,0,1))).normalized()
    expected=Vector((expected_enu[0],expected_enu[2],-expected_enu[1]))
    assert (direction-expected).length<1e-5,("glTF sun direction",tuple(direction),tuple(expected))
    return {"name":node["name"],"directionGLTF":list(direction),"linearRGB":list(colour),
            "intensity":light.get("intensity",1.),"activeDirectionalLights":len(suns)}

def verify():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene=bpy.context.scene
    source=source_header()
    meshes=[o for o in scene.objects if o.type=="MESH"]
    mesh_count=sum(1 for n in source["nodes"] if "mesh" in n)
    sections=[o for o in meshes if o.get("sceneRegion")=="coreSeaCut"]
    assert len(sections)==1 and len(meshes)-len(sections)==mesh_count,(len(meshes),mesh_count)
    assert scene.get("GLB SHA256")==checksum(GLB),"BLEND and GLB differ"
    assert scene.cycles.transparent_max_bounces>=48
    assert scene.camera and scene.camera.type=="CAMERA" and scene.camera.data.type=="ORTHO"
    assert scene.world and sum(o.type=="LIGHT" and o.data.type=="SUN" for o in scene.objects)==1
    from v6_sunset import HDR, SETTINGS, sun_enu
    expected_enu=sun_enu()
    glb_sun=verify_glb_sun(source,SETTINGS,expected_enu)
    lamp=next(o for o in scene.objects if o.type=="LIGHT" and o.data.type=="SUN")
    assert ((lamp.matrix_world.to_quaternion() @ Vector((0,0,1))) - Vector(expected_enu)).length<1e-5
    assert max(abs(a-b) for a,b in zip(lamp.data.color,SETTINGS["sunLinearRGB"]))<1e-5
    assert abs(lamp.data.energy-SETTINGS["blenderSunEnergy"])<1e-4
    assert abs(lamp.data.angle-math.radians(SETTINGS["sunDiameterDeg"]))<1e-6
    output=next(n for n in scene.world.node_tree.nodes if n.type=="OUTPUT_WORLD" and n.is_active_output)
    background=output.inputs["Surface"].links[0].from_node
    assert background.type=="BACKGROUND" and abs(background.inputs["Strength"].default_value-SETTINGS["blenderWorldStrength"])<1e-5
    sky=background.inputs["Color"].links[0].from_node
    assert sky.type=="TEX_ENVIRONMENT" and sky.image and sky.image.packed_file
    packed_sky_sha=hashlib.sha256(sky.image.packed_file.data).hexdigest()
    assert packed_sky_sha==checksum(HDR),("embedded Blender HDR",packed_sky_sha)
    assert abs(scene.view_settings.exposure-SETTINGS["blenderExposureEV"])<1e-5
    for preset in SETTINGS["viewpoints"]:
        assert any(o.type=="CAMERA" and o.name.startswith(preset["name"]) for o in scene.objects),preset["key"]
    assert scene["模型版本"]=="夕照校园-v6"
    assert all(m.polygons and m.materials for m in bpy.data.meshes if m.users)
    source_flora=[n for n in source["nodes"] if n.get("extras",{}).get("kind")=="flora"]
    flora=[o for o in meshes if o.get("kind")=="flora"]
    assert len(flora)==len(source_flora)
    assert len({o.data.as_pointer() for o in flora})==len({n["mesh"] for n in source_flora})
    packed_images=[im for im in bpy.data.images if im.packed_file]
    from bpy_extras.object_utils import world_to_camera_view
    site=json.loads((ROOT/"data/map/campus.json").read_text(encoding="utf8"))
    frame=[world_to_camera_view(scene,scene.camera,Vector((x,-z,25))) for x,z in site["boundary"]]
    assert min(min(p.x,p.y) for p in frame)>.04 and max(max(p.x,p.y) for p in frame)<.96, "Campus perimeter does not fit the overview camera"
    if source.get("images"):
        context_meshes=[o for o in meshes if o.get("kind")=="terrainContext"]
        assert context_meshes and context_meshes[0].data.uv_layers, "Distant terrain UVs are missing"
        assert any(n.type=="TEX_IMAGE" and n.image and n.image.packed_file for obj in context_meshes for mat in obj.data.materials for n in mat.node_tree.nodes), "Coast image is unlinked or unpacked"
        assert len(packed_images)>=len(source["images"]), "Missing embedded environment textures"
    swash=next(o for o in meshes if o.get("kind")=="surfWater")
    assert len(swash.data.shape_keys.key_blocks)==5 and swash.data.shape_keys.animation_data.action
    surf_material=swash.data.materials[0]
    surf_shader=next(n for n in surf_material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    assert surf_shader.inputs['Base Color'].is_linked and surf_shader.inputs['Normal'].is_linked
    assert not surf_shader.inputs['Emission Strength'].is_linked and surf_shader.inputs['Emission Strength'].default_value==0
    assert not surf_shader.inputs['Emission Color'].is_linked and max(surf_shader.inputs['Emission Color'].default_value[:3])==0
    wave_vectors=[a for a in swash.data.attributes if a.name.startswith('BayWaveNormal')]
    assert len(wave_vectors)==5 and all(a.data_type=='FLOAT_VECTOR' and len(a.data)==len(swash.data.vertices) for a in wave_vectors)
    drivers=surf_material.node_tree.animation_data.drivers
    assert len([d for d in drivers if any(v.targets[0].id==swash.data.shape_keys for v in d.driver.variables)])==4
    from qd_yinghai_lake import LAKE_ID, PERIOD
    lake,=[o for o in meshes if o.get("lakeWater")==LAKE_ID]
    lake_mat,=lake.data.materials
    lake_maps=[n.image for n in lake_mat.node_tree.nodes if n.type=="TEX_IMAGE" and n.image]
    assert lake.data.color_attributes and len(lake_maps)==2 and lake_maps[0]==lake_maps[1] and lake_maps[0].packed_file
    assert lake_mat.get("风纹循环秒")==PERIOD and lake_mat.node_tree.animation_data.action
    cover=[o for o in meshes if o.get("kind")=="groundcover"]
    assert len(cover)==sum(n.get("extras",{}).get("kind")=="groundcover" for n in source["nodes"])
    required={"地表 · 混合草地","路面 · 沥青","水体 · 海面与湖面"}
    assert all(bpy.data.materials.get(n) and any(k.type=="BUMP" for k in bpy.data.materials[n].node_tree.nodes) for n in required)
    assert all(o.get("key") for o in meshes if o.get("kind")=="landmark")
    academic=json.loads(scene["院楼构件分组统计"])
    assert len(academic)==14 and all(v["faces"] and v["groups"]>=3 for v in academic.values()),academic
    assert sum(o.get("kind")=="signage" for o in meshes)==sum(n.get("extras",{}).get("kind")=="signage" for n in source["nodes"])
    living=json.loads(scene['生活区构件分组统计'])
    assert len(living)==17 and all(v['groups']>=3 and v['faces']>0 for v in living.values()),living
    finish_specs={m['name']:m for m in source['materials'] if m.get('extras',{}).get('archFinish')}
    finish_mats={m.get('源材质'):m for m in bpy.data.materials if m.get('archFinish')}
    assert set(finish_specs)==set(finish_mats),(len(finish_specs),len(finish_mats))
    for name,rec in finish_specs.items():
        mat=finish_mats[name];pbr=rec['pbrMetallicRoughness']
        assert max(abs(a-b) for a,b in zip(mat.diffuse_color,pbr['baseColorFactor']))<.0012,name
        if 'baseColorTexture' in pbr:
            assert sum(node.type=='TEX_IMAGE' and bool(node.image and node.image.packed_file) for node in mat.node_tree.nodes)>=2,name
    info={"v4_surface_materials":len(finish_mats),"residence_components":living,"academic_components":academic,"blend":BLEND.name,"verified_bpy_version":bpy.app.version_string,"size":BLEND.stat().st_size,
          "source_sha256":scene.get("GLB SHA256"),"mesh_objects":len(meshes),"shared_mesh_datablocks":len(bpy.data.meshes),
          "tree_and_shrub_instances":len(flora),"tree_and_shrub_meshes":len({o.data.as_pointer() for o in flora}),
          "landmark_component_groups":json.loads(scene.get("地标构件分组统计","{}")),
          "surf_shape_keys":len(swash.data.shape_keys.key_blocks),"packed_images":[im.name for im in packed_images],"groundcover_instances":len(cover),
          "materials":len(bpy.data.materials),"cameras":len(bpy.data.cameras),"collections":{c.name:len(c.objects) for c in bpy.data.collections if c.objects}}
    outside=bpy.data.collections["周边环境 · 山地、村落与外围路网"]
    outside_mesh=[o for o in outside.objects if o.type=='MESH']
    expected=sum(n.get('extras',{}).get('sceneRegion')=='surroundings' for n in source['nodes'])
    assert len(outside_mesh)==expected and expected>52
    assert all(o.get("sceneRegion")=="surroundings" for o in outside_mesh)
    focused=scene.view_layers["仅看建模区"]
    assert focused.layer_collection.children[outside.name].exclude
    assert not focused.layer_collection.children["建模区土层断面"].exclude
    assert scene.view_layers[0].layer_collection.children["建模区土层断面"].exclude
    assert not scene.view_layers[0].layer_collection.children[outside.name].exclude
    from qd_nearshore_scope import verify_blender
    info['nearshoreScope']=verify_blender(scene)
    info["surroundingsObjects"]=expected
    # Test the packed beach colour image on the live base-colour path. A
    # matching GLB stamp alone would not catch an old texture left in the blend.
    sand_record = next(m for m in source['materials'] if m.get('extras',{}).get('naturalFinish')=='sand'
                       and 'baseColorTexture' in m['pbrMetallicRoughness'])
    sand_mat = next(m for m in bpy.data.materials if m.get('源材质') == sand_record['name'])
    sand_shader = next(n for n in sand_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    todo = [link.from_node for link in sand_shader.inputs['Base Color'].links]
    found = set()
    while todo:
        current = todo.pop()
        if current in found:
            continue
        found.add(current)
        todo.extend(link.from_node for socket in current.inputs for link in socket.links)
    packed_sand = [n.image for n in found if n.type=='TEX_IMAGE' and n.image and n.image.packed_file]
    tex = source['textures'][sand_record['pbrMetallicRoughness']['baseColorTexture']['index']]
    view = source['bufferViews'][source['images'][tex['source']]['bufferView']]
    with GLB.open('rb') as glb:
        glb.seek(12)
        binary_start = 28+struct.unpack('<I',glb.read(4))[0]
        glb.seek(binary_start+view.get('byteOffset',0))
        expected_sand_hash = hashlib.sha256(glb.read(view['byteLength'])).digest()
    assert any(hashlib.sha256(im.packed_file.data).digest()==expected_sand_hash for im in packed_sand)
    info['beachColourMapSHA256'] = expected_sand_hash.hex()
    info["surfaceDisplay"] = sync_surface_display(source, verify=True)
    assert scene.eevee.use_raytracing and scene.eevee.ray_tracing_method == "SCREEN"
    assert scene.render.engine == "CYCLES" and scene.cycles.glossy_bounces > 0
    assert scene.world.sun_threshold == 0 and scene.display.shading.color_type == "MATERIAL"
    assert not scene.display.shading.show_specular_highlight
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                shading = area.spaces.active.shading
                assert shading.color_type == "MATERIAL" and shading.use_scene_world and shading.use_scene_lights
                assert not shading.show_specular_highlight
                assert shading.use_scene_world_render and shading.use_scene_lights_render
    info["sunsetRig"]={"glb":glb_sun,"nativeDirectionalLights":1,"azimuthDeg":SETTINGS["azimuthDeg"],
                       "elevationDeg":SETTINGS["elevationDeg"],"environmentSHA256":packed_sky_sha,
                       "cameraKeys":[record["key"] for record in SETTINGS["viewpoints"]]}
    (WORK/"verification.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(info,ensure_ascii=False),flush=True)

def build():
    source=source_header();site=json.loads((ROOT/"data/map/campus.json").read_text(encoding="utf8"))
    locations=json.loads((ROOT/"data/locations.json").read_text(encoding="utf8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;configure_scene(scene)
    print("Importing GLB with original material slots and linked mesh data.",flush=True)
    # Suppress the importer’s per-object informational messages; Python exceptions still propagate.
    with (WORK/"import.log").open("w",encoding="utf8") as log, contextlib.redirect_stdout(log):
        imported=bpy.ops.import_scene.gltf(filepath=str(GLB),merge_vertices=True,import_pack_images=True,loglevel=4)
    if "FINISHED" not in imported:raise RuntimeError(imported)
    # The bare GLB carries a sun for generic viewers. Recreate it through the
    # single native rig, which also supplies the calibrated angular diameter.
    for imported_obj in list(scene.objects):
        if imported_obj.type=="LIGHT" and (imported_obj.get("kind")=="sunsetRig" or imported_obj.name.startswith("SDU_Sunset_Key") or imported_obj.data.name.startswith("SDU_Sunset_Key")):
            bpy.data.objects.remove(imported_obj,do_unlink=True)
    original=list(bpy.data.collections);objects=list(scene.objects)
    collections_by_kind={key:group(scene.collection,name) for key,name in [
        ("hinterland","周边环境 · 山地、村落与外围路网"),("cutEdge","建模区土层断面"),("signage","学院入口实物题字"),("waterfront","滨海公园与潮岸"),("landmark","地标建筑与校门"),("building","学院与生活区楼宇"),("ground","地形与海岸"),
        ("roads","道路与步行系统"),("landscape","广场与景观设施"),("sport","田径场与球场"),
        ("water","水域"),("grass","草叶与地被 · 共享网格"),("tree","乔木 · 共享网格"),("shrub","灌木 · 共享网格"),("rig","摄影机与日照")]}
    for obj in objects:
        destination=collections_by_kind[layer_for(obj)]
        for col in list(obj.users_collection):col.objects.unlink(obj)
        destination.objects.link(obj)
    for col in original:
        if not col.objects and not col.children:bpy.data.collections.remove(col)
    finish_materials(source)
    for mat in bpy.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type=="TEX_IMAGE" and node.image:
                    mat.node_tree.nodes.active=node
                    break
    from qd_blender_surf import install
    surf=install(scene)
    assert surf.get('water_objects')==1,surf
    from qd_yinghai_lake import install_blender
    install_blender(scene)
    print("Matched native and solid-view finishes", sync_surface_display(source), flush=True)
    components=component_groups(objects)
    from qd_editable import group_academic_parts
    academic_groups=group_academic_parts(source,GLB,objects)
    residences=group_academic_parts(source,GLB,objects,'refinedResidence')
    scene['生活区构件分组统计']=json.dumps(residences,ensure_ascii=False)
    scene["院楼构件分组统计"]=json.dumps(academic_groups,ensure_ascii=False)
    scene["地标构件分组统计"]=json.dumps(components,ensure_ascii=False)
    overview,target=lighting_and_cameras(scene,collections_by_kind["rig"],site,locations)
    scene["模型版本"]="夕照校园-v6"
    scene["GLB SHA256"]=checksum(GLB)
    scene["公开地理数据"]="© OpenStreetMap contributors · ODbL 1.0 / Contains modified Copernicus Sentinel data 2026. / 3D-GloBFP · CC BY 4.0（详见 data/v5_horizon.json）"
    scene["地形"]="Mapzen Terrain Tiles / AWS Open Data"
    scene["本地米制坐标"]="X 东，Y 北，Z 上；WGS84 原点 120.68204°E，36.36559°N"
    scene["参照依据"]="data/map/campus.json；学院照片见 data/huiwen_sources.json 与 dizhou_sources.json；滨海见 waterfront_sources.json；地标见 landmarks_sources.json 与 civic_sources.json"
    scene["植被"]="同种乔木及灌木实例共享网格，可批量编辑同种形态。"
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type!="VIEW_3D":continue
            space=area.spaces.active;space.clip_start=.18;space.clip_end=20000
            space.shading.type="MATERIAL";space.shading.use_scene_lights=True;space.shading.use_scene_world=True
            space.shading.use_scene_lights_render=True;space.shading.use_scene_world_render=True
            space.shading.color_type="MATERIAL"
            space.shading.show_specular_highlight=False
            space.shading.show_shadows=True;space.shading.show_cavity=True;space.shading.cavity_type="WORLD"
            space.shading.cavity_ridge_factor=.72;space.shading.cavity_valley_factor=.62
            space.overlay.show_overlays=False
            region=space.region_3d;region.view_perspective="ORTHO";region.view_rotation=overview.rotation_euler.to_quaternion()
            region.view_distance=overview.data.ortho_scale*.82;region.view_location=target
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active=None
    main_layer=bpy.context.view_layer
    focused=scene.view_layers.new("仅看建模区")
    main_layer.layer_collection.children[collections_by_kind['cutEdge'].name].exclude=True
    focused.layer_collection.children[collections_by_kind['hinterland'].name].exclude=True
    from qd_nearshore_scope import install_blender
    install_blender(scene)
    focused.use=False
    scene.render.use_single_layer=True
    bpy.context.preferences.filepaths.save_version=0
    temporary=WORK/"campus-new.blend"
    print("Saving editable .blend",len(objects),"scene objects",flush=True)
    op=bpy.ops.wm.save_as_mainfile(filepath=str(temporary),compress=True,relative_remap=False)
    if "FINISHED" not in op:raise RuntimeError(op)
    os.replace(temporary,BLEND)
    print("Saved",BLEND,BLEND.stat().st_size,flush=True)

if __name__=="__main__":
    if "--verify" in sys.argv:verify()
    else:build()
