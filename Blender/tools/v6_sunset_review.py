"""Measure sunset exposure from the offline viewer or the saved Cycles scene.

Run with 'web' or 'blend'. --draft builds an isolated preview using the
previous geometry, without altering the deliverable blend or HTML.
"""
import argparse
import base64
import gzip
import hashlib
import mmap
import re
import json
import math
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from v6_sunset import ROOT, HDR, SETTINGS, sun_enu


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def packed_gzip_sha(encoded):
    with gzip.GzipFile(fileobj=BytesIO(base64.b64decode(encoded,validate=True))) as decoded:
        return hashlib.file_digest(decoded,"sha256").hexdigest()


def offline_asset_hashes(page_path, glb_sha, hdr_sha):
    """Bind the actual embedded payloads to the files used by the other runtimes."""
    with page_path.open("rb") as page:
        with mmap.mmap(page.fileno(),0,access=mmap.ACCESS_READ) as contents:
            sky=re.search(rb'const eveningSky\s*=\s*await readSunsetTexture\(\s*"([A-Za-z0-9+/=]+)"\s*\)',contents)
            model=re.search(rb'<script id="glb"[^>]*>([A-Za-z0-9+/=]+)</script>',contents)
            assert sky and model,"Missing embedded sunset HDR or GLB"
            embedded_sky=packed_gzip_sha(sky[1]);embedded_model=packed_gzip_sha(model[1])
    assert embedded_sky==hdr_sha,("web HDR",embedded_sky,hdr_sha)
    assert embedded_model==glb_sha,("web GLB",embedded_model,glb_sha)
    return {"environmentSHA256":embedded_sky,"embeddedGLBSHA256":embedded_model}


def pose_for(key, places):
    if key in places:
        return places[key]["viewpoint"]
    direction = sun_enu()
    if key == "east-sky":
        direction[:2] *= -1
    eye = np.array([0.0, 1750.0, 0.0])
    target = eye + 150 * np.array([direction[0], direction[2], -direction[1]])
    return {"eye": eye.tolist(), "target": target.tolist(), "fov": 14}


def measurements(image):
    pixels = np.asarray(image.convert("RGB"), dtype=float)
    luma = pixels @ np.array([.2126, .7152, .0722])
    h, w = luma.shape
    middle = pixels[h//2-2:h//2+3, w//2-2:w//2+3]
    return {
        "lumaP01P10P50P90P99": np.percentile(luma, [1, 10, 50, 90, 99]).round(1).tolist(),
        "lumaBelow12Percent": round(100 * np.mean(luma < 12), 3),
        "lumaAbove245Percent": round(100 * np.mean(luma > 245), 3),
        "centerMedianSRGB": np.median(middle, axis=(0, 1)).astype(int).tolist(),
    }


def browser_frames(poses, folder, draft, glb_sha, hdr_sha):
    from playwright.sync_api import sync_playwright
    from v2_stills import FLAGS
    source = ROOT / "打开青岛校区.html"
    if draft:
        from pack_viewer import main as pack
        source = folder / "sunset-with-current-geometry.html"
        pack(source)
    identity=offline_asset_hashes(source,glb_sha,hdr_sha)
    identity["renderAssetSHA256"]=file_sha(source)
    report = {}
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="chrome", args=FLAGS, headless=True, timeout=180000)
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 675},
                                    device_scale_factor=1, offline=True, reduced_motion="reduce")
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda msg: errors.append(msg.text[:900]) if msg.type == "error" else None)
            page.goto(source.as_uri() + "?film=1", wait_until="domcontentloaded", timeout=300000)
            page.wait_for_function("window.qd?.ready||window.qd?.error", timeout=300000)
            assert page.evaluate("qd.ready"), page.evaluate("qd.error")
            lamps = page.evaluate("""()=>{const lights=[];qd.scene.traverse(o=>{
                if(!o.isDirectionalLight)return;
                const p=o.getWorldPosition(new THREE.Vector3()),q=o.target.getWorldPosition(new THREE.Vector3());
                let visible=true;
                for(let parent=o;parent;parent=parent.parent)visible=visible&&parent.visible;
                lights.push({name:o.name,visible,direction:p.sub(q).normalize().toArray(),
                             linearRGB:o.color.toArray(),intensity:o.intensity});});
                return lights;}""")
            enabled=[lamp for lamp in lamps if lamp["visible"]]
            assert len(enabled)==1,lamps
            if not draft:
                imported=[lamp for lamp in lamps if lamp["name"]=="SDU_Sunset_Key"]
                assert len(imported)==1 and not imported[0]["visible"],lamps
            enu=sun_enu();expected=np.array([enu[0],enu[2],-enu[1]])
            assert np.linalg.norm(np.asarray(enabled[0]["direction"])-expected)<1e-5,lamps
            assert np.allclose(enabled[0]["linearRGB"],SETTINGS["sunLinearRGB"],atol=1e-5),lamps
            assert abs(enabled[0]["intensity"]-SETTINGS["threeSunIntensity"])<1e-5,lamps
            for key, pose in poses.items():
                data = page.evaluate("""([key,p])=>{if(qd.locations.some(x=>x.key===key))qd.go(key,true);
                    qd.renderPose(p.eye,p.target,p.fov,1.4);
                    return qd.renderer.domElement.toDataURL('image/png').split(',')[1];
                }""", [key, pose])
                im = Image.open(BytesIO(base64.b64decode(data))).convert("RGB")
                report[key] = measurements(im)
                if key not in ("east-sky", "west-sun"):
                    im.save(folder / ("网页-" + key + ".jpg"), quality=95, subsampling=0)
            meta = {"rig": page.evaluate("qd.sunset"), "directionalLights": lamps, "browserErrors": errors, **identity}
            assert not errors, errors
        finally:
            browser.close()
    return report, meta


def blender_frames(poses, folder, draft, glb_sha, hdr_sha):
    from make_blend import bpy, BLEND, configure_scene
    from mathutils import Vector
    render_sha=file_sha(BLEND)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    lamps = [obj for obj in scene.objects if obj.type == "LIGHT" and obj.data.type == "SUN"]
    assert len(lamps) == 1
    lamp = lamps[0]
    if draft:
        configure_scene(scene)
        lamp.location = Vector(sun_enu()) * 2200
        lamp.rotation_euler = (-lamp.location).to_track_quat("-Z", "Y").to_euler()
        lamp.data.color = SETTINGS["sunLinearRGB"];lamp.data.energy = SETTINGS["blenderSunEnergy"]
        lamp.data.angle = math.radians(SETTINGS["sunDiameterDeg"])
    else:
        assert scene["模型版本"] == "夕照校园-v6" and scene["GLB SHA256"]==glb_sha
    actual = lamp.rotation_euler.to_quaternion() @ Vector((0, 0, 1))
    assert (actual-Vector(sun_enu())).length < 1e-5, actual
    tex = next(n for n in scene.world.node_tree.nodes if n.type == "TEX_ENVIRONMENT")
    assert tex.image.packed_file
    packed_sha=hashlib.sha256(tex.image.packed_file.data).hexdigest()
    assert packed_sha==hdr_sha,("Blender packed HDR",packed_sha,hdr_sha)
    scene.render.resolution_x=1200;scene.render.resolution_y=675;scene.render.resolution_percentage=100
    scene.cycles.samples = 7 if draft else 16
    scene.cycles.max_bounces = 4;scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED";scene.render.threads = 6
    devices = bpy.context.preferences.addons["cycles"].preferences
    try:
        devices.compute_device_type = "OPTIX";devices.refresh_devices()
        for device in devices.devices:
            device.use = device.type == 'OPTIX'
        if any(d.use for d in devices.devices):
            scene.cycles.device = "GPU"
    except (TypeError, RuntimeError):
        pass
    scene.render.use_persistent_data = True
    cam = bpy.data.cameras.new("夕照光度核验")
    ob = bpy.data.objects.new(cam.name, cam);scene.collection.objects.link(ob);scene.camera=ob
    cam.clip_start=.28;cam.clip_end=28000
    scene.render.image_settings.file_format="PNG"
    def blender(p):
        return Vector((p[0], -p[2], p[1]))
    report={}
    for key, pose in poses.items():
        ob.location=blender(pose['eye'])
        ob.rotation_euler=(blender(pose['target'])-ob.location).to_track_quat('-Z','Y').to_euler()
        cam.angle=2*math.atan(math.tan(math.radians(pose['fov'])/2)*1200/675)
        path=folder / (".render-" + key + ".png")
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        with Image.open(path) as im:
            report[key]=measurements(im)
            if key not in ("east-sky","west-sun"):
                im.convert("RGB").save(folder / ("Blender-" + key + ".jpg"), quality=95, subsampling=0)
        path.unlink()
    return report, {"world":scene.world.name, "sunDirectionENU":list(actual), "sunRGB":list(lamp.data.color),
                    "worldImagePacked":bool(tex.image.packed_file),"environmentSHA256":packed_sha,
                    "packedHdrSHA256":packed_sha,"renderAssetSHA256":render_sha, "device":scene.cycles.device,
                    "samples":scene.cycles.samples, "directionalLightCount":len(lamps)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', choices=['web','blend']);parser.add_argument('--draft',action='store_true')
    args=parser.parse_args()
    places={p['key']:p for p in json.loads((ROOT/'data/locations.json').read_text('utf8'))+SETTINGS['viewpoints']}
    keys=['sunset-library','sunset-glaze','film-bay','film-library','film-roof','film-ridge','west-sun','east-sky']
    folder=ROOT/('.jobs/sunset-study' if args.draft else 'preview/夕照核验')
    folder.mkdir(parents=True,exist_ok=True)
    poses={key:pose_for(key,places) for key in keys}
    glb_sha=file_sha(ROOT/"山东大学青岛校区.glb");hdr_sha=file_sha(HDR)
    fn=browser_frames if args.engine=='web' else blender_frames
    measures,meta=fn(poses,folder,args.draft,glb_sha,hdr_sha)
    report={'settings':SETTINGS['name'],'canvas':[1200,675],'glbSHA256':glb_sha,
            'captures':measures,**meta}
    west=np.array(measures['west-sun']['centerMedianSRGB'])
    east=np.array(measures['east-sky']['centerMedianSRGB'])
    assert west[0]>east[0]+20 and west[1]>east[1]+15, (west,east)
    assert east[2]>east[0]+6,(west,east)
    for key in keys[:-2]:
        assert measures[key]['lumaBelow12Percent']<3 and measures[key]['lumaAbove245Percent']<3, (key,measures[key])
    report["passed"]=True
    reportpath=(folder if args.draft else ROOT/'data')/('夕照画面核验-'+args.engine+'.json')
    temporary=reportpath.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    temporary.replace(reportpath)
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
