"""Reopen the delivered viewer offline, ray-test each sign, and capture the academic and coastal stills."""
import base64, json, os
from pathlib import Path
from itertools import groupby
from playwright.sync_api import sync_playwright
from PIL import Image,ImageStat
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'preview';OUT.mkdir(exist_ok=True)
WORK=ROOT/'.jobs'/'static-browser';WORK.mkdir(exist_ok=True,parents=True)
os.environ['TEMP']=os.environ['TMP']=str(WORK)
FLAGS=['--use-angle=d3d11','--enable-webgl','--enable-gpu','--ignore-gpu-blocklist','--force-high-performance-gpu','--disable-background-timer-throttling']
def read(name):return json.loads((ROOT/name).read_text('utf8'))
def main():
    locations=read('data/locations.json');signs=read('data/实体题字.json')
    colleges=[p for p in locations if p['group']=='学院楼']; coast=[p for p in locations if p['key'].startswith('waterfront-')]
    assert len(colleges)==14 and len(coast)==4
    captures=[];errors=[]
    with sync_playwright() as api:
        browser=api.chromium.launch(channel='chrome',args=FLAGS,headless=True,timeout=180000)
        try:
            page=browser.new_page(viewport={'width':1440,'height':860},device_scale_factor=1,offline=True,reduced_motion='reduce')
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('console',lambda msg: errors.append(msg.text[:1000]) if msg.type=='error' else None)
            page.goto((ROOT/'打开青岛校区.html').as_uri()+'?film=1',wait_until='domcontentloaded',timeout=240000)
            page.wait_for_function('window.qd?.ready||window.qd?.error',timeout=300000)
            assert page.evaluate('qd.ready'),page.evaluate('qd.error')
            def snap(name,pose):
                blob=page.evaluate("""p=>{qd.camera.near=.28;qd.renderPose(p.eye,p.target,p.fov||44,1.4);
                  return qd.renderer.domElement.toDataURL('image/jpeg',.94).split(',')[1];}""",pose)
                file=OUT/(name+'.jpg');file.write_bytes(base64.b64decode(blob))
                with Image.open(file) as im:
                    assert im.size==(1440,860),file
                    if name.endswith('lettering'):
                        # Pale stone fills most of a plaque closeup. Measure the
                        # photographed central plate and the ink at native resolution.
                        crop=im.crop((440,248,1000,608)).convert('L')
                        low,high=crop.getextrema()
                        assert high-low>42 and ImageStat.Stat(crop).stddev[0]>7,file
                    else:assert max(ImageStat.Stat(im.resize((96,64))).stddev)>9,file
                captures.append(file.name)
            for p in colleges:
                for mode,pose in p['views'].items():snap(p['key']+'-'+mode,pose)
            for p in coast:snap(p['key'],p['viewpoint'])
            for k in ['library','west_gate','north_gate','overview']:
                pose=page.evaluate("""k=>{qd.go(k,true);return {eye:qd.camera.position.toArray(),target:qd.camera.position.clone().add(qd.camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(90)).toArray(),fov:41};}""",k)
                snap(k,pose)
            # Compare the child's actual glyph normals to the outward vector. Test its
            # readable first surface against solid surfaces and other inscription lines.
            rays=page.evaluate("""rows=>{
              const groups=new Map(qd.root.children.filter(n=>n.userData.key).map(n=>[n.userData.key,n]));
              const signNodes=qd.root.children.filter(n=>n.userData.kind==='signage');
              return rows.map(row=>{
                const facing=new THREE.Vector3(row.normal[0],0,row.normal[1]).normalize(),center=new THREE.Vector3(...row.world);
                const matching=signNodes.find(n=>n.userData.owner===row.owner&&n.userData.signId===row.id);
                if(!matching)throw Error(row.id);let probes=[],minDot=1;
                matching.traverse(m=>{
                  if(!m.isMesh||m.material.name!==row.colour)return;
                  const p=m.geometry.attributes.position,idx=m.geometry.index,norm=m.geometry.attributes.normal;
                  const normalMat=new THREE.Matrix3().getNormalMatrix(m.matrixWorld);
                  const step=Math.max(3,Math.floor(idx.count/27/3)*3);
                  for(let j=0;j<idx.count;j+=step){const w=new THREE.Vector3();
                    for(let t=0;t<3;t++)w.add(new THREE.Vector3().fromBufferAttribute(p,idx.getX(j+t)));
                    probes.push(w.multiplyScalar(1/3).applyMatrix4(m.matrixWorld));
                    minDot=Math.min(minDot,new THREE.Vector3().fromBufferAttribute(norm,idx.getX(j)).applyNormalMatrix(normalMat).dot(facing));
                  }
                });
                let visible=0,maxObstruction=0;
                for(const pt of probes){const start=pt.clone().addScaledVector(facing,3);
                  const ray=new THREE.Raycaster(start,facing.clone().negate(),0,3.0005);
                  const hits=ray.intersectObject(groups.get(row.owner),true);const d=hits.length?3-hits[0].distance:0;
                  if(d<.003)visible++;else maxObstruction=Math.max(maxObstruction,d);
                }
                return {owner:row.owner,id:row.id,text:row.text,probes:probes.length,visible,minDot,maxObstruction};
              });}""",signs)
            for owner,grp in groupby(sorted(signs,key=lambda s:s['owner']),lambda s:s['owner']):
                collection=list(grp);carrier=max(collection,key=lambda s:len(s['text']) if any('\u3400'<=c<='\u9fff' for c in s['text']) else 0)
                x,y,z=carrier['world'];nx,nz=carrier['normal'];d=max(1.9,carrier['width']*1.32)
                snap(owner+'-lettering',dict(eye=[x+nx*d,y-.23,z+nz*d],target=[x,y,z],fov=38))
            # Exercise the actual search and view buttons with the film flag removed
            # in the DOM. This is the same menu/controller in the embedded offline page.
            page.evaluate("document.body.classList.remove('film');qd.resize()")
            page.locator('#search').fill('环境科学与工程学院')
            assert page.locator('#menu button').count()==1
            page.locator('#menu button').click()
            assert '淦昌苑E' in page.locator('#place').inner_text()
            page.locator('#switchView').click()
            assert page.locator('#switchView').inner_text()=='屋顶鸟瞰'
            page.locator('#switchView').click()
            assert page.locator('#switchView').inner_text()=='垂直看屋顶'
            page.locator('#switchView').click()
            assert page.locator('#switchView').inner_text()=='檐口近景'
            page.locator('#switchView').click()
            assert page.locator('#switchView').inner_text()=='返回立面'
            page.locator('#switchView').click()
            assert page.locator('#switchView').inner_text()=='门前近景'
            page.locator('#search').fill('滨海步道');assert page.locator('#menu button').count()>=1
            # Open the normal viewer through the same deep link as the photo gallery.
            nav=browser.new_page(viewport={'width':1440,'height':860},device_scale_factor=1,offline=True,reduced_motion='reduce')
            nav.on('pageerror',lambda err:errors.append(str(err)))
            nav.goto((ROOT/'打开青岛校区.html').as_uri()+'?view=way-970257669&mode=entrance',wait_until='domcontentloaded',timeout=240000)
            nav.wait_for_function('window.qd?.ready||window.qd?.error',timeout=240000)
            assert nav.evaluate('qd.ready') and nav.locator('#switchView').inner_text()=='屋顶鸟瞰'
            nav.locator('#search').fill('淦昌苑');nav.screenshot(path=str(OUT/'离线交互界面.jpg'),type='jpeg',quality=93)
            nav.locator('#search').fill('北段弧形');nav.locator('#menu button').click()
            assert nav.evaluate("Math.abs(qd.camera.position.x-qd.locations.find(p=>p.key==='waterfront-overlook').viewpoint.eye[0])<.1")
            nav.close()
            assert not errors,errors
            report=dict(stills=captures,signRays=rays,browserErrors=errors,residentSearch=True,entrySwitch=True)
            (ROOT/'data'/'离线观看核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
            fail=[r for r in rays if not r['probes'] or r['minDot']<.99 or r['visible']<r['probes']*.92]
            if fail:raise ValueError('Obstructed or reversed lettering: '+str(fail))
            print(len(captures),'stills;',len(rays),'lines tested',flush=True)
        finally:browser.close()
if __name__=='__main__':main()

