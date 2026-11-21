"""Bake six fixed, scene-linear window environments from the real offline campus."""
import argparse
import base64
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from playwright.sync_api import sync_playwright
from scipy.ndimage import map_coordinates

from qd_nearshore_scope import CORE_SCOPE
from v2_stills import FLAGS
from v6_sunset import HDR, ROOT
from v6_sunset_review import file_sha, offline_asset_hashes

# Positions are in GLB coordinates (east, height, south), in metres. Each lies
# outside a facade in a courtyard, on a promenade, or beside the lake.
PROBES = [
    ("华岗振声庭院", [-27, 12, 222]),
    ("凤凰居中轴花圃", [309, 24, 888]),
    ("图书馆前广场", [91, 13, -64]),
    ("淦昌苑樱花庭院", [345, 10, 130]),
    ("北区湖畔", [32, 7, -1050]),
    ("研究院室外庭院", [89, 11, -455]),
]
FACES = [
    ([1,0,0], [0,1,0]), ([-1,0,0], [0,1,0]),
    ([0,0,1], [0,1,0]), ([0,0,-1], [0,1,0]),
    ([0,1,0], [0,0,-1]), ([0,-1,0], [0,0,1]),
]
SIDE = 192
WIDTH, HEIGHT = 512, 256
CAPTURE = """([eye, forward, up, side]) => {
 const {renderer:r, camera:c} = qd;
 const target = new THREE.WebGLRenderTarget(side,side,{
   type:THREE.FloatType,format:THREE.RGBAFormat,encoding:THREE.LinearEncoding,
   minFilter:THREE.NearestFilter,magFilter:THREE.NearestFilter});
 const previous = r.getRenderTarget(), tone = r.toneMapping;
 const oldUp = c.up.clone(), aspect = c.aspect;
 try {
   r.toneMapping=THREE.NoToneMapping;
   c.aspect=1;c.up.fromArray(up);
   r.setRenderTarget(target);
   const gl=r.getContext();
   if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)
     throw Error('当前系统无法建立场景线性浮点采样目标。');
   qd.renderPose(eye, eye.map((x,i)=>x+forward[i]*180),90,1.4);
   const pixels=new Float32Array(side*side*4);
   r.readRenderTargetPixels(target,0,0,side,side,pixels);
   const bytes=new Uint8Array(pixels.length);
   for(let i=0;i<pixels.length;i+=4){
     const peak=Math.max(pixels[i],pixels[i+1],pixels[i+2]);
     if(peak<1e-12)continue;
     const e=Math.floor(Math.log2(peak))+1, scale=2**(8-e);
     for(let k=0;k<3;k++)bytes[i+k]=Math.min(255,Math.max(0,pixels[i+k]*scale));
     bytes[i+3]=128+e;
   }
   let out='';
   for(let at=0;at<bytes.length;at+=8192)out+=String.fromCharCode(...bytes.subarray(at,at+8192));
   return btoa(out);
 } finally { r.setRenderTarget(previous);r.toneMapping=tone;c.up.copy(oldUp);c.aspect=aspect;target.dispose(); }
}"""


def projection():
    longitude = (np.arange(WIDTH)+.5)/WIDTH*2*np.pi-np.pi
    latitude = np.pi/2-(np.arange(HEIGHT)+.5)/HEIGHT*np.pi
    lon, lat = np.meshgrid(longitude, latitude)
    rays = np.stack((np.cos(lat)*np.cos(lon), np.sin(lat), np.cos(lat)*np.sin(lon)), axis=-1)
    face_id = np.argmax(rays @ np.array([f for f,_ in FACES]).T, axis=-1)
    result = []
    for index, (fwd, up) in enumerate(FACES):
        mask = face_id == index
        visible = rays[mask]
        depth = visible @ fwd
        u = .5 + .5*(visible @ np.cross(fwd,up))/depth
        # WebGL readback starts at the lower left.
        v = .5 + .5*(visible @ up)/depth
        result.append((mask, np.array([v,u])*SIDE-.5))
    return result


def write_hdr(path, pixels):
    peak = pixels.max(axis=2)
    mantissa, exponent = np.frexp(peak)
    scale = np.divide(mantissa*256.,peak,where=peak>0,out=np.zeros_like(peak))
    data = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    data[:,:,:3] = np.clip(pixels*scale[:,:,None],0,255)
    data[:,:,3] = np.where(peak>0,exponent+128,0)
    path.write_bytes(f"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {HEIGHT} +X {WIDTH}\n".encode()+data.tobytes())


def main(source_page=None, output=None, core_only=False):
    out = Path(output).resolve() if output else ROOT/'assets/校园窗景'
    work = ROOT/'.jobs/window-probes'
    work.mkdir(parents=True,exist_ok=True)
    model = ROOT/'山东大学青岛校区.glb'
    sha = file_sha(model)
    sky_sha = file_sha(HDR)
    maps = projection()
    with TemporaryDirectory(dir=work) as scratch:
        staging = Path(scratch)
        if source_page:
            page_file = Path(source_page).resolve()
        else:
            from pack_viewer import main as pack
            page_file = staging/'无窗景采样页.html'
            pack(output=page_file,probe_bake=True)
        # A copied or stale viewer must never label an environment with today's GLB hash.
        offline_asset_hashes(page_file,sha,sky_sha)
        records, errors = [], []
        if core_only:
            previous=json.loads((out/'位置.json').read_text('utf8'))
            assert previous['modelSHA256']==sha and previous['environmentSHA256']==sky_sha
            records=previous['probes']
            assert [(r['name'],r['centre']) for r in records]==PROBES
            assert all(file_sha(out/r['file'])==r['sha256'] for r in records)
        modes=('core',) if core_only else ('full','core')
        with sync_playwright() as api:
            chrome = os.environ.get("SDU_CHROME")
            browser=api.chromium.launch(channel=None if chrome else "chrome", executable_path=chrome, args=FLAGS, headless=True, timeout=180000)
            try:
                page=browser.new_page(viewport={"width":320,"height":320},device_scale_factor=1,
                                      offline=True,reduced_motion="reduce")
                page.on("pageerror",lambda error: errors.append(str(error)))
                page.on("console",lambda msg: errors.append(msg.text[:1000]) if msg.type=="error" else None)
                page.goto(page_file.as_uri()+"?film=1&probe=1",wait_until="domcontentloaded",timeout=300000)
                page.wait_for_function("window.qd?.ready||window.qd?.error",timeout=300000)
                assert page.evaluate("qd.ready"),page.evaluate("qd.error")
                assert not page.evaluate("qd.windowProbes?.probes"), "Bake source already uses local reflections"
                for mode,name,centre in ((mode,name,c) for mode in modes for name,c in PROBES):
                    page.evaluate('mode=>qd.setScope(mode)',mode)
                    panorama=np.zeros((HEIGHT,WIDTH,3),np.float32)
                    for (fwd,up),(mask,coords) in zip(FACES,maps):
                        data=page.evaluate(CAPTURE,[centre,fwd,up,SIDE])
                        raw=np.frombuffer(base64.b64decode(data),np.uint8).reshape(SIDE,SIDE,4)
                        rgb=np.ldexp(raw[:,:,:3].astype(np.float32)+.5,raw[:,:,3,None].astype(np.int16)-136)
                        rgb[raw[:,:,3]==0]=0
                        for i in range(3):
                            panorama[:,:,i][mask]=map_coordinates(rgb[:,:,i],coords,order=1,mode='nearest')
                    if errors: raise RuntimeError(errors)
                    if not np.isfinite(panorama).all() or panorama.max()<=1 or np.percentile(panorama,50)<=.001:
                        raise RuntimeError(f"Missing scene-linear HDR capture: {name}")
                    file=staging/(name+('-建模区' if mode=='core' else '')+'.hdr')
                    write_hdr(file,panorama)
                    if mode=='full':
                        records.append({'name':name,'centre':centre,'file':file.name,'sha256':file_sha(file)})
                    else:
                        rec=next(r for r in records if r['name']==name)
                        rec.update(coreFile=file.name,coreSHA256=file_sha(file))
                    print('Sampled',name,'linear RGB peak',round(float(panorama.max()),2),flush=True)
            finally:
                browser.close()
        assert file_sha(model)==sha, "Model changed while baking window probes."
        assert file_sha(HDR)==sky_sha, "Sky changed while baking window probes."
        manifest={'coreScope':CORE_SCOPE,'modelSHA256':sha,'environmentSHA256':sky_sha,'probes':records}
        (staging/'位置.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
        out.mkdir(parents=True,exist_ok=True)
        updated=('coreFile',) if core_only else ('file','coreFile')
        for filename in [r[k] for r in records for k in updated]+['位置.json']:
            (staging/filename).replace(out/filename)
    print('Saved',out,flush=True)


if __name__ == '__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-page',type=Path)
    cli.add_argument('--output',type=Path)
    cli.add_argument('--core-only',action='store_true',help='Reuse verified full-mode panoramas and rebake only the model-area views.')
    opts=cli.parse_args()
    main(opts.source_page,opts.output,opts.core_only)
