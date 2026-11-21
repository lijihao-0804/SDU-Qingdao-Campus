"""Install editable Cycles/EEVEE foam and looping Blender shape-key animation."""
import math
import bpy

PERIOD=11.2
FRAMES=48


def keyed_curve(action,path,frames,values,index=0):
    curve=action.fcurves.new(data_path=path,index=index)
    curve.keyframe_points.add(len(frames))
    for key,t,v in zip(curve.keyframe_points,frames,values):
        key.co=(t,v);key.interpolation='LINEAR'
    curve.modifiers.new('CYCLES')
    curve.update()
    return curve


def wave_normal_attributes(obj):
    """Match each exported morph-normal vector to its editable Blender basis vertex."""
    import json
    from pathlib import Path
    import struct
    import numpy as np

    model = Path(__file__).resolve().parents[1] / '山东大学青岛校区.glb'
    with model.open('rb') as stream:
        magic, version, _, size, kind = struct.unpack('<4sIII4s', stream.read(20))
        if (magic, version, kind) != (b'glTF', 2, b'JSON'):
            raise ValueError('Invalid coastal GLB header.')
        doc = json.loads(stream.read(size))
        start = stream.tell()+8
        island, = [n for n in doc['nodes'] if n.get('extras',{}).get('kind') == 'surfWater']
        mesh = doc['meshes'][island['mesh']]
        primitive, = mesh['primitives']

        def vectors(accessor):
            a = doc['accessors'][accessor]
            view = doc['bufferViews'][a['bufferView']]
            if (a['type'], a['componentType'], view.get('byteStride',12)) != ('VEC3',5126,12):
                raise ValueError('Unexpected coastal vector layout.')
            stream.seek(start + view.get('byteOffset',0) + a.get('byteOffset',0))
            gltf = np.frombuffer(stream.read(a['count']*12), '<f4').reshape(-1,3)
            local = gltf[:,[0,2,1]].copy()
            local[:,1] *= -1
            return local

        keys = obj.data.shape_keys.key_blocks
        shape = (len(obj.data.vertices),3)
        def key_positions(key):
            result = np.empty(shape, np.float32)
            key.data.foreach_get('co',result.ravel())
            return result

        positions = vectors(primitive['attributes']['POSITION'])
        source = {tuple(point):i for i,point in enumerate(positions)}
        if len(source) != len(positions):
            raise ValueError('The surf basis contains ambiguous coincident vertices.')
        order = np.array([source[tuple(point)] for point in key_positions(keys[0])], dtype=np.intp)
        data = [('BayWaveNormal', vectors(primitive['attributes']['NORMAL'])[order])]
        for i,(name,target) in enumerate(zip(mesh['extras']['targetNames'],primitive['targets'])):
            key = keys[i+1]
            if key.name != name or not np.allclose(key_positions(key),
                    (positions+vectors(target['POSITION']))[order],rtol=0,atol=.00015):
                raise ValueError('The surf shape key does not match its glTF normal target.')
            data.append((f'BayWaveNormal{i+1}',vectors(target['NORMAL'])[order]))
        if len(data)!=len(keys):
            raise ValueError('Incomplete surf morph-normal targets.')
    for name,values in data:
        attr = obj.data.attributes.get(name) or obj.data.attributes.new(name,'FLOAT_VECTOR','POINT')
        attr.data.foreach_set('vector',np.ascontiguousarray(values).ravel())
    return [name for name,_ in data]


def finish_native_foam(obj, mat, shader):
    # Removing the portable emissive foam atlas exposes a white socket default.
    # Native foam is lit by the real sun and sky through the base colour.
    tree = mat.node_tree
    for key,value in (('Emission Color',(0.,0.,0.,1.)),('Emission Strength',0.)):
        socket = shader.inputs[key]
        for link in list(socket.links):
            tree.links.remove(link)
        socket.default_value = value

    # glTF animates NORMAL as well as POSITION. Blender shape keys retain
    # positions alone, and deforming imported split normals produces triangular
    # reflections on the narrow, moving shoreline faces. Use the authored
    # vertex normals with the live editable key weights, before the micro-bump.
    labels = wave_normal_attributes(obj)
    keys = obj.data.shape_keys
    def source(name, row):
        node = tree.nodes.new('ShaderNodeAttribute')
        node.attribute_name=name
        node.label='波面法线 · '+name
        node.location=(-1560,row)
        return node.outputs['Vector']

    result=source(labels[0],-1430)
    for i,name in enumerate(labels[1:],1):
        row=-1430-i*260
        delta=source(name,row)
        scale=tree.nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.location=(-1200,row)
        key=keys.key_blocks[i]
        scale.label=key.name+' · 法线变化'
        tree.links.new(delta,scale.inputs[0])
        driver=scale.inputs['Scale'].driver_add('default_value').driver
        driver.type='AVERAGE'
        variable=driver.variables.new();variable.type='SINGLE_PROP'
        target=variable.targets[0];target.id_type='KEY';target.id=keys;target.data_path=key.path_from_id('value')
        add=tree.nodes.new('ShaderNodeVectorMath');add.operation='ADD';add.location=(-950+i*185,row)
        tree.links.new(result,add.inputs[0]);tree.links.new(scale.outputs[0],add.inputs[1])
        result=add.outputs[0]
    normal=tree.nodes.new('ShaderNodeVectorTransform')
    normal.vector_type='NORMAL';normal.convert_from='OBJECT';normal.convert_to='WORLD'
    normal.label='动态波面法线';normal.location=(10,-1800)
    tree.links.new(result,normal.inputs['Vector'])
    bump=shader.inputs['Normal'].links[0].from_node
    if bump.type!='BUMP':
        raise ValueError('Missing native water micro-normal input.')
    tree.links.new(normal.outputs['Vector'],bump.inputs['Normal'])
    mat['春日潮浪版本']=6


def install(scene):
    obj=next((o for o in scene.objects if o.get('kind')=='surfWater' and o.type=='MESH'),None)
    if obj is None:return {'water_objects':0}
    mat=obj.data.materials[0];keys=obj.data.shape_keys
    revision = mat.get('春日潮浪版本', 0)
    if revision >= 4:
        if revision < 6:
            shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            finish_native_foam(obj, mat, shader)
        return {'water_objects':1,'period_seconds':PERIOD}
    if not keys or len(keys.key_blocks)!=5:raise RuntimeError('Shore swell has lost its four editable shape keys.')
    fps=scene.render.fps/scene.render.fps_base
    start=scene.frame_start
    tvals=[PERIOD*i/112 for i in range(113)]
    frames=[start+t*fps for t in tvals]
    keys.animation_data_clear();action=bpy.data.actions.new('鳌山湾 · 可编辑循环波形')
    keys.animation_data_create().action=action
    for n,key in enumerate(list(keys.key_blocks)[1:]):
        frequency=2 if n<2 else 3
        fun=math.cos if n%2==0 else math.sin
        keyed_curve(action,key.path_from_id('value'),frames,[.5+.5*fun(t*2*math.pi/PERIOD*frequency) for t in tvals])
    mat.use_nodes=True;tree=mat.node_tree;nodes=tree.nodes
    foam_image=next((n.image for n in nodes if n.type=='TEX_IMAGE' and n.image and '循环浪沫' in n.image.name),None)
    if foam_image is None:raise RuntimeError('The packed foam atlas is unavailable.')
    cell_image=next((n.image for n in nodes if n.type=='TEX_IMAGE' and n.image and '泡孔细网' in n.image.name),None)
    if cell_image is None:raise RuntimeError('The packed air-cell mask is unavailable.')
    foam_image.alpha_mode='CHANNEL_PACKED';cell_image.alpha_mode='CHANNEL_PACKED'
    # Keep the imported dielectric, roughness, and IOR. Only its foam,
    # colour and bump inputs need a native time-driven network.
    bs=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    for old_node in list(nodes):
        if old_node != bs:
            nodes.remove(old_node)
    def node(kind,name,x,y):
        item=nodes.new(kind);item.label=name;item.location=(x,y);return item
    def connect(a,b):tree.links.new(a,b)
    bs.label='浅海、沙底色与白沫';bs.location=(590,100)
    out=node('ShaderNodeOutputMaterial','材质输出',890,100);connect(bs.outputs['BSDF'],out.inputs['Surface'])
    color=node('ShaderNodeVertexColor','水深渐变色',30,280)
    color.layer_name=obj.data.color_attributes[0].name
    mix=node('ShaderNodeMixRGB','浪脊的泡沫量',315,170)
    mix.inputs[2].default_value=(.8,.85,.77,1);connect(color.outputs['Color'],mix.inputs[1]);connect(mix.outputs[0],bs.inputs['Base Color'])
    uv=node('ShaderNodeUVMap','近岸周期图集坐标',-920,170);uv.uv_map=obj.data.uv_layers[0].name
    if len(obj.data.uv_layers)<2:raise RuntimeError('The surf energy UV layer is missing.')
    energy=node('ShaderNodeUVMap','防波区与外海衰减',-495,-350);energy.uv_map=obj.data.uv_layers[1].name
    ec=node('ShaderNodeSeparateXYZ','可信浪区权重',-275,-350);connect(energy.outputs[0],ec.inputs[0])
    timer=node('ShaderNodeValue','动画图集帧 · 可编辑',-1170,610);timer.name='FoamPhase'
    tree.animation_data_clear();ta=bpy.data.actions.new('鳌山湾 · 白沫推进消退');tree.animation_data_create().action=ta
    keyed_curve(ta,timer.outputs[0].path_from_id('default_value'),[start,start+PERIOD*fps],[0,FRAMES])
    def op(name,mode,a,b,x,y):
        n=node('ShaderNodeMath',name,x,y);n.operation=mode
        if isinstance(a,(int,float)):n.inputs[0].default_value=a
        else:connect(a,n.inputs[0])
        if b is not None:
            if isinstance(b,(int,float)):n.inputs[1].default_value=b
            else:connect(b,n.inputs[1])
        return n.outputs[0]
    time=timer.outputs[0]
    floor=op('当前图帧','FLOOR',time,None,-965,620)
    fac=op('相邻帧连续过渡','FRACT',time,None,-935,810)
    def sample(step,y):
        a=op('帧偏移','ADD',floor,step,-770,y)
        a=op('首尾循环','MODULO',a,FRAMES,-585,y)
        a=op('图集横坐标','DIVIDE',a,FRAMES,-410,y)
        pos=node('ShaderNodeCombineXYZ','横移采样',-250,y);connect(a,pos.inputs['X'])
        add=node('ShaderNodeVectorMath','保留沿岸坐标',-90,y);add.operation='ADD';connect(uv.outputs[0],add.inputs[0]);connect(pos.outputs[0],add.inputs[1])
        im=node('ShaderNodeTexImage','图集 · 当前' if not step else '图集 · 下一帧',75,y)
        im.image=foam_image;im.interpolation='Linear';im.extension='REPEAT';connect(add.outputs[0],im.inputs[0])
        return im.outputs['Alpha']
    a=sample(0,660);b=sample(1,425)
    blend=node('ShaderNodeMixRGB','时间内插',310,570);connect(fac,blend.inputs[0]);connect(a,blend.inputs[1]);connect(b,blend.inputs[2])
    # Sample a second packed image at physical metre scale. The moving foam
    # envelope follows the wave crest, while the net stretches in the water.
    fine_uv=node('ShaderNodeSeparateXYZ','沿岸距离',-1060,-760);connect(uv.outputs[0],fine_uv.inputs[0])
    depth=op('离岸米值','SUBTRACT',1,ec.outputs['Y'],-845,-550)
    depth=op('米至网孔尺度','MULTIPLY',depth,108/3.7,-660,-550)
    along=op('沿岸米值','SUBTRACT',1,fine_uv.outputs['Y'],-845,-770)
    along=op('沿岸至网孔尺度','MULTIPLY',along,223/3.7,-660,-770)
    phase=op('同步相位','MULTIPLY',time,math.tau*2/FRAMES,-1070,-1010)
    sine=op('向岸水粒摆动','SINE',phase,None,-860,-1000)
    cosine=op('沿岸水粒摆动','COSINE',phase,None,-860,-1120)
    depth=op('横向推进','ADD',depth,op('横向小振幅','MULTIPLY',sine,.56/3.7,-630,-980),-420,-550)
    along=op('沿岸伸缩','ADD',along,op('纵向小振幅','MULTIPLY',cosine,.19/3.7,-630,-1110),-420,-770)
    vec=node('ShaderNodeCombineXYZ','米制泡孔纹理坐标',-230,-560);connect(depth,vec.inputs['X']);connect(along,vec.inputs['Y'])
    cell=node('ShaderNodeTexImage','峰口的碎化气泡与孔洞',0,-660);cell.image=cell_image;cell.extension='REPEAT';connect(vec.outputs[0],cell.inputs[0])
    def ramp(name,src,lo,hi,x,y):
        rng=node('ShaderNodeMapRange',name,x,y);rng.clamp=True;rng.interpolation_type='SMOOTHSTEP'
        rng.inputs['From Min'].default_value=lo;rng.inputs['From Max'].default_value=hi;connect(src,rng.inputs[0])
        return rng.outputs[0]
    raw=blend.outputs[0];c=cell.outputs['Alpha']
    web=ramp('破碎浪爬升',raw,.028,.43,555,575)
    lip=ramp('浪脊泛白',raw,.49,.83,560,790)
    lace=op('薄沫有孔','ADD',op('气泡壁','MULTIPLY',c,.94,245,-650),.06,430,-650)
    web=op('退浪细网','MULTIPLY',web,lace,745,575)
    lip=op('波峰卷沫','MULTIPLY',lip,op('峰口间隙','ADD',.18,op('浪唇明暗','MULTIPLY',c,.72,230,-840),430,-840),745,790)
    total=op('并合薄沫','ADD',op('主沫','MULTIPLY',web,.75,945,575),op('次沫','MULTIPLY',lip,.49,945,790),1140,650)
    f=op('浪区权重','MULTIPLY',total,ec.outputs['X'],1330,650);connect(f,mix.inputs[0])
    geo=node('ShaderNodeNewGeometry','表面微褶',-210,-520)
    grain=node('ShaderNodeTexNoise','春日海风微波',0,-475);grain.inputs['Scale'].default_value=2.2;grain.inputs['Detail'].default_value=2
    connect(geo.outputs['Position'],grain.inputs['Vector'])
    bump=node('ShaderNodeBump','低幅风纹',222,-370);bump.inputs['Strength'].default_value=.12;bump.inputs['Distance'].default_value=.042
    connect(grain.outputs['Fac'],bump.inputs['Height']);connect(bump.outputs['Normal'],bs.inputs['Normal'])
    far=next((o for o in scene.objects if o.get('kind')=='sea' and o.type=='MESH'),None)
    if far:
        far_mat=far.data.materials[0];far_tree=far_mat.node_tree;far_bs=next(n for n in far_tree.nodes if n.type=='BSDF_PRINCIPLED')
        fg=far_tree.nodes.new('ShaderNodeNewGeometry');fg.location=(-670,-90)
        fn=far_tree.nodes.new('ShaderNodeTexNoise');fn.location=(-420,-90);fn.inputs['Scale'].default_value=2.2;fn.inputs['Detail'].default_value=2
        fb=far_tree.nodes.new('ShaderNodeBump');fb.location=(-180,-90);fb.inputs['Strength'].default_value=.12;fb.inputs['Distance'].default_value=.042
        far_tree.links.new(fg.outputs['Position'],fn.inputs['Vector']);far_tree.links.new(fn.outputs['Fac'],fb.inputs['Height']);far_tree.links.new(fb.outputs['Normal'],far_bs.inputs['Normal'])
    finish_native_foam(obj, mat, bs)
    obj['循环秒数']=PERIOD
    scene.frame_end=max(scene.frame_end,math.ceil(start+PERIOD*fps))
    scene.frame_set(start)
    return {'water_objects':1,'period_seconds':PERIOD,'morph_keys':4,'foam_frames':FRAMES,'atlas':foam_image.name}

