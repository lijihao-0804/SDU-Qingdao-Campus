"""Package the viewer with local geometry and scripts for direct file:// use."""
from pathlib import Path
import base64,gzip,json,hashlib
root=Path(__file__).resolve().parents[1]
def window_probes(model_digest):
    directory=root/'assets/校园窗景'
    manifest=json.loads((directory/'位置.json').read_text('utf8'))
    from qd_nearshore_scope import CORE_SCOPE
    if manifest.get('coreScope')!=CORE_SCOPE:
        raise ValueError('近岸显示范围已变更，请运行 tools/bake_window_probes.py --core-only')
    sky=root/json.loads((root/'data/夕照光照.json').read_text('utf8'))['panorama']
    if manifest['environmentSHA256']!=hashlib.sha256(sky.read_bytes()).hexdigest():
        raise ValueError('窗景与当前夕照环境不一致，请重新烘焙')
    if manifest['modelSHA256']!=model_digest:
        raise ValueError('窗玻璃反射与模型不一致，请运行 tools/bake_window_probes.py')
    result=[]
    for item in manifest['probes']:
        row=dict(name=item['name'],centre=item['centre'])
        for key,file_key,sha_key in [('data','file','sha256'),('coreData','coreFile','coreSHA256')]:
            path=(directory/item[file_key]).resolve()
            assert path.is_relative_to(directory.resolve())
            radiance=path.read_bytes()
            assert hashlib.sha256(radiance).hexdigest()==item[sha_key],path
            row[key]=base64.b64encode(gzip.compress(radiance,compresslevel=6,mtime=0)).decode('ascii')
        result.append(row)
    assert result
    return result


def main(output=None,probe_bake=False):
    viewer=root/'viewer';page=(viewer/'campus.html').read_text('utf-8')
    data=(root/'山东大学青岛校区.glb').read_bytes()
    probes=[] if probe_bake else window_probes(hashlib.sha256(data).hexdigest())
    pane_script='' if probe_bake else (viewer/'window-probes.js').read_text('utf8')
    page=page.replace('/*WINDOW_REFLECTIONS*/',pane_script.replace('</script','<\\/script'))
    for key,name in [('THREE','three.min.js'),('ORBIT','OrbitControls.js'),('LOADER','GLTFLoader.js'),('SURF','shore-wave.js'),('NAVIGATION','navigation.js'),('CAMPUS','campus.js')]:
        script=(viewer/name).read_text('utf-8').replace('</script','<\\/script')
        if key=='CAMPUS':
            script=script.replace('/*WINDOW_PROBES*/[]',json.dumps(probes,separators=(',',':')))
            from qd_nearshore_scope import section_layout
            script=script.replace('/*NEARSHORE_SECTION*/null',json.dumps(section_layout(),separators=(',',':')))
            boundary=json.loads((root/'data/map/campus.json').read_text('utf8'))['boundary']
            script=script.replace('/*CAMPUS_BOUNDARY*/[]',json.dumps(boundary,separators=(',',':')))
            settings=json.loads((root/'data/夕照光照.json').read_text('utf8'))
            sky=base64.b64encode(gzip.compress((root/settings['panorama']).read_bytes(),compresslevel=6,mtime=0)).decode('ascii')
            script=script.replace('/*SUNSET_SETTINGS*/{}',json.dumps(settings,ensure_ascii=False))
            script=script.replace('/*SUNSET_PANORAMA*/""',json.dumps(sky))
        page=page.replace('/*'+key+'*/',script)
    places=json.loads((root/'data'/'locations.json').read_text('utf-8'))
    place_keys={p['key'] for p in places}
    places.extend(p for p in settings.get('viewpoints',[]) if p['key'] not in place_keys)
    page=page.replace('@PLACES@',json.dumps(places,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
    packed=base64.b64encode(gzip.compress(data,compresslevel=6,mtime=0)).decode('ascii')
    out=Path(output) if output else root/'打开青岛校区.html';out.write_text(page.replace('@MODEL@',packed),'utf8')
    print(out.name,out.stat().st_size)
if __name__=='__main__':main()

