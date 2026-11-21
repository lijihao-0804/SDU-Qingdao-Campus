"""Sunset surface response for water, planted ground and individual plant organs."""

from collections import Counter, defaultdict


WATER_IOR = 1.333
WATER_SETTINGS = {
    # The near and far bay meet along a single unbroken water surface.
    'bay': (.32, .32),
    'pond': (.32, .55),
    'lake': (.255, .68),
}

# Minimum roughness and glTF dielectric specular weight. Leaf cuticles retain
# a broader visible reflection than petals, grass fibres, bark and exposed soil.
PLANT_SETTINGS = {
    'leaf': (.84, .62),
    'petal': (.89, .34),
    'bark': (.92, .40),
    'grass': (.95, .34),
    'soil': (.96, .29),
}

# Older plant prototypes encode bark, pedicels and petals as palette keys.
# Interpret these colours only on meshes dedicated to planting.
BARK = set("""
#706653 #80725e #75624d #725c56 #846c5d #8c7364 #82685a #967d69 #987e69
#715e50 #9b8868 #685749 #887260 #8a7965 #957e67 #dad9ca #887565 #907b67
#c7c7bc #77756e #655950 #d9d9c9 #9a9686 #70665e #887165 #91786d #70614b
#deded0 #696256 #776f60 #776951
""".split())
PETALS = set("""
#f6eee7 #fffefd #a589ad #806c9b #987aa4 #e4dfc9 #ede8db #ded9c6 #c77689
""".split())
PLANT_KINDS = {'flora', 'groundcover', 'walkPlanting', 'plazaPlanting'}


def apply_water(material, role):
    roughness, environment = WATER_SETTINGS[role]
    material['pbrMetallicRoughness'].update(roughnessFactor=roughness, metallicFactor=0.)
    material.setdefault('extensions', {})['KHR_materials_ior'] = {'ior': WATER_IOR}
    material.setdefault('extras', {}).update(naturalFinish=role, waterEnvironment=environment)


def plant_role(material, mesh_name, kinds):
    name = material['name']
    if name in {'grass', '校园草地 · 地表湿度与林下色泽'}:
        return 'grass'
    if name.startswith('园下草土') or name == '南弯裸土 · 枯草壤土':
        return 'soil'
    if name.startswith('图书馆方篱·') or mesh_name.endswith('绿篱与内缘'):
        return 'leaf'
    if mesh_name == '滨海公路及东田径场外 · 道路乔木':
        return 'bark' if name in BARK else 'leaf'
    if not kinds or not kinds <= PLANT_KINDS:
        return None
    if name in BARK:
        return 'bark'
    if name in PETALS or name in {'南弯草花 · 五裂花冠', '南弯草花 · 深红花眼'}:
        return 'petal'
    if name.startswith('南弯草花'):
        return 'leaf'
    return 'grass' if 'groundcover' in kinds or mesh_name == '初春低草' else 'leaf'


def bind(scene):
    """Finish either a full assembly or its existing GLB, leaving mesh data intact."""
    doc = scene.doc
    materials = doc['materials']
    kinds_by_mesh = defaultdict(set)
    for node in doc['nodes']:
        if 'mesh' in node:
            kinds_by_mesh[node['mesh']].add(node.get('extras', {}).get('kind'))

    roles_by_material = defaultdict(set)
    for index, mesh in enumerate(doc['meshes']):
        kinds = kinds_by_mesh[index]
        for primitive in mesh['primitives']:
            slot = primitive['material']
            material = materials[slot]
            if kinds and kinds <= {'sea', 'surfWater'}:
                role = 'bay'
            elif kinds == {'water'}:
                role = 'lake' if material.get('extras', {}).get('lakeWater') else 'pond'
            elif material['pbrMetallicRoughness'].get('baseColorTexture') is not None:
                texture = material['pbrMetallicRoughness']['baseColorTexture']['index']
                image = doc['images'][doc['textures'][texture]['source']]['name']
                role = {'春草 · 修剪草皮': 'grass', '南弯地被 · 玫红花冠与春草': 'petal'}.get(image)
                if role is None:
                    role = plant_role(material, mesh['name'], kinds)
            else:
                role = plant_role(material, mesh['name'], kinds)
            roles_by_material[slot].add(role)

    counts = Counter()
    used = doc.setdefault('extensionsUsed', [])
    for slot, roles in roles_by_material.items():
        # A reused colour may also belong to a kerb or building detail.
        if len(roles) != 1 or None in roles:
            continue
        role, = roles
        material = materials[slot]
        if role in WATER_SETTINGS:
            apply_water(material, role)
            extension = 'KHR_materials_ior'
        else:
            roughness, specular = PLANT_SETTINGS[role]
            pbr = material['pbrMetallicRoughness']
            pbr['roughnessFactor'] = max(pbr.get('roughnessFactor', 1.), roughness)
            pbr['metallicFactor'] = 0.
            extension = 'KHR_materials_specular'
            material.setdefault('extensions', {})[extension] = {'specularFactor': specular}
            material.setdefault('extras', {})['naturalFinish'] = role
        if extension not in used:
            used.append(extension)
        counts[role] += 1
    return dict(counts)
