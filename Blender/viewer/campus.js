(async function(){
'use strict';
const el=id=>document.getElementById(id),movie=new URLSearchParams(location.search).has('film');
if(movie)document.body.classList.add('film');
const v=new THREE.Vector3(),look=new THREE.Vector3(),origin=new THREE.Vector3();
const state=window.qd={ready:false,locations},stage=el('stage');
const canvas=document.createElement('canvas');
const contextOptions={alpha:false,depth:true,stencil:true,antialias:true,powerPreference:'high-performance',preserveDrawingBuffer:movie};
const modernGL=canvas.getContext('webgl2',contextOptions);
const context=modernGL||canvas.getContext('webgl',contextOptions);
if(!context)throw new Error('当前浏览器未能建立 WebGL 渲染环境。');
// Per-fragment log depth keeps the 5 mm parking paint and distant façades
// distinct on a camera that also sees the 26.5 km marine horizon.
const logDepth=Boolean(modernGL||context.getExtension('EXT_frag_depth'));
const renderer=new THREE.WebGLRenderer({canvas,context,...contextOptions,logarithmicDepthBuffer:logDepth});
const probeBake=new URLSearchParams(location.search).has('probe');
const sampleCoverage=!probeBake && context.getParameter(context.SAMPLES)>1;
const anisotropy=Math.max(1,renderer.capabilities.getMaxAnisotropy());
stage.prepend(renderer.domElement);
renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;
const world=new THREE.Scene(),cam=new THREE.PerspectiveCamera(41,1,.28,26500),control=new THREE.OrbitControls(cam,renderer.domElement);
control.enableDamping=false;control.minDistance=4;control.maxDistance=5200;control.maxPolarAngle=Math.PI*.78;control.target.set(0,0,0);
const sunset=/*SUNSET_SETTINGS*/{};
renderer.toneMappingExposure=sunset.threeExposure;
const radians=THREE.MathUtils.degToRad;
const azimuth=radians(sunset.azimuthDeg),elevation=radians(sunset.elevationDeg);
const solarDirection=new THREE.Vector3(Math.sin(azimuth)*Math.cos(elevation),Math.sin(elevation),-Math.cos(azimuth)*Math.cos(elevation));

// The source panorama is the same scene-linear RGBE file that Blender packs.
// Three's +Z is south, so its standard equirectangular UVs agree with Blender's.
async function readSunsetTexture(encoded){
 const compressed=Uint8Array.from(atob(encoded),value=>value.charCodeAt(0));
 const decoded=await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
 const bytes=new Uint8Array(decoded),header=new TextDecoder().decode(bytes.subarray(0,100));
 const match=header.match(/^#\?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y (\d+) \+X (\d+)\n/);
 if(!match)throw Error('夕照环境贴图格式有误');
 const height=Number(match[1]),width=Number(match[2]),start=match[0].length;
 if(start+width*height*4!==bytes.length)throw Error('夕照环境贴图尺寸有误');
 const half=new Uint16Array(width*height*4),transfer=new Map();
 for(let y=0;y<height;y++){
   let src=start+(height-y-1)*width*4,dst=y*width*4;
   for(let x=0;x<width;x++,src+=4,dst+=4){
     const exponent=bytes[src+3];
     let table=transfer.get(exponent);
     if(!table){
       const scale=exponent?2**(exponent-136):0;
       table=Uint16Array.from({length:256},(_,i)=>THREE.DataUtils.toHalfFloat((i+.5)*scale));
       transfer.set(exponent,table);
     }
     half[dst]=table[bytes[src]];half[dst+1]=table[bytes[src+1]];half[dst+2]=table[bytes[src+2]];half[dst+3]=0x3c00;
   }
 }
 const texture=new THREE.DataTexture(half,width,height,THREE.RGBAFormat,THREE.HalfFloatType);
 texture.mapping=THREE.EquirectangularReflectionMapping;texture.minFilter=texture.magFilter=THREE.LinearFilter;
 texture.wrapS=THREE.RepeatWrapping;texture.needsUpdate=true;return texture;
}
const eveningSky=await readSunsetTexture(/*SUNSET_PANORAMA*/"");
const pmrem=new THREE.PMREMGenerator(renderer);
const reflections=pmrem.fromEquirectangular(eveningSky);
world.environment=reflections.texture;pmrem.dispose();
world.background=eveningSky;
world.fog=new THREE.FogExp2(0xc6c1ca,.000137);
const hemi=new THREE.HemisphereLight();
hemi.color.setRGB(.70,.81,1.0);hemi.groundColor.setRGB(.39,.34,.31);
hemi.intensity=sunset.threeHemisphereIntensity;world.add(hemi);
const sun=new THREE.DirectionalLight();
sun.color.fromArray(sunset.sunLinearRGB);sun.intensity=sunset.threeSunIntensity;
sun.target.position.set(80,0,20);sun.position.copy(sun.target.position).addScaledVector(solarDirection,4500);
sun.castShadow=true;world.add(sun,sun.target);
// Fit once in the sunset's coordinate system. Every camera sees the same
// shadow texels, including an isolated frame rendered out of sequence.
const shadowCamera=sun.shadow.camera;
shadowCamera.position.copy(sun.position);shadowCamera.lookAt(sun.target.position);shadowCamera.updateMatrixWorld();
const shadowBounds=new THREE.Box3(),corner=new THREE.Vector3();
for(const place of locations){
 if(![place.x,place.y,place.z].every(Number.isFinite))continue;
 const radius=place.r||35;
 for(const x of [-radius,radius])for(const z of [-radius,radius])for(const h of [0,place.h||20]){
   corner.set(place.x+x,place.y+h,place.z+z).applyMatrix4(shadowCamera.matrixWorldInverse);
   shadowBounds.expandByPoint(corner);
 }
}
Object.assign(shadowCamera,{left:shadowBounds.min.x-80,right:shadowBounds.max.x+80,
 bottom:shadowBounds.min.y-45,top:shadowBounds.max.y+45,
 near:Math.max(.5,-shadowBounds.max.z-350),far:-shadowBounds.min.z+350});
shadowCamera.updateProjectionMatrix();
const shadowSize=Math.min(4096,renderer.capabilities.maxTextureSize);
sun.shadow.mapSize.set(shadowSize,shadowSize);sun.shadow.bias=-.00006;sun.shadow.normalBias=.13;
state.sunset={azimuthDeg:sunset.azimuthDeg,elevationDeg:sunset.elevationDeg,direction:solarDirection.toArray(),hdrSize:[eveningSky.image.width,eveningSky.image.height]};
const time={value:0},focus={value:new THREE.Vector3()},folFade={value:1};
const patterns = [
'varying vec3 qWorld;',
'float qHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}',
'float qNoise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(qHash(i),qHash(i+vec2(1,0)),f.x),mix(qHash(i+vec2(0,1)),qHash(i+vec2(1,1)),f.x),f.y);}'
].join('\n');
function texture(mat,kind){
 if(mat.userData.qType===kind)return;
 mat.userData.qType=kind;mat.customProgramCacheKey=()=>kind;
 if(kind==='flora')mat.alphaToCoverage=sampleCoverage;
 mat.onBeforeCompile=sh=>{
  sh.uniforms.qTime=time;sh.uniforms.qFocus=focus;sh.uniforms.qFade=folFade;
  sh.vertexShader='varying vec3 qWorld;\n'+sh.vertexShader.replace('#include <worldpos_vertex>','#include <worldpos_vertex>\nvec4 qp=vec4(transformed,1.0);\n#ifdef USE_INSTANCING\nqp=instanceMatrix*qp;\n#endif\nqWorld=(modelMatrix*qp).xyz;');
  sh.fragmentShader=patterns+'\nuniform float qTime;uniform vec3 qFocus;uniform float qFade;\n'+sh.fragmentShader;
  let color='';
  if(kind==='grass'){
   color='float d=length(cameraPosition-qWorld); float m=qNoise(qWorld.xz*.032)*.12+qNoise(qWorld.xz*.114)*.075-.097; float blade=(qNoise(qWorld.xz*vec2(3.,6.))-.5)*(1.-smoothstep(17.,78.,d))*.16; diffuseColor.rgb*=1.+m+blade;diffuseColor.rgb+=vec3(.017,.013,-.008)*(qNoise(qWorld.xz*.012)-.5);';
  }else if(kind==='asphalt'){
   color='diffuseColor.rgb*=.96+.065*qNoise(qWorld.xz*.32)+.06*(qNoise(qWorld.xz*9.)-.5)*(1.-smoothstep(12.,80.,length(cameraPosition-qWorld)));';
  }else if(kind==='water'){
   color='float dist=length(cameraPosition-qWorld);float farFade=1.-smoothstep(50.,550.,dist);float rip=sin(qWorld.x*.29+qWorld.z*.43+qTime*.5609986881+2.*sin(qWorld.z*.08))*.48+sin(qWorld.x*.73-qWorld.z*.62+qTime*1.1219973763)*.23;float fres=pow(1.-abs(normalize(cameraPosition-qWorld).y),2.2);diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.34,.51,.54),fres*.38)+vec3(.013,.02,.021)*rip*farFade;';
   sh.fragmentShader=sh.fragmentShader.replace('#include <normal_fragment_maps>','#include <normal_fragment_maps>\nfloat qr=sin(qWorld.x*.31+qTime*.5609986881)+.63*sin(qWorld.z*.54-qTime*1.1219973763);normal=normalize(normal+mat3(viewMatrix)*vec3(.034*qr,.0,.025*cos(qWorld.x*.47+qWorld.z*.24+qTime*.5609986881))*(1.-smoothstep(60.,430.,length(cameraPosition-qWorld))));');
  }else if(kind==='facade'){
   color='vec3 fn=normalize(cross(dFdx(qWorld),dFdy(qWorld)));vec2 st=vec2(abs(fn.x)>abs(fn.z)?qWorld.z:qWorld.x,qWorld.y);float zoom=1.-smoothstep(16.,58.,length(cameraPosition-qWorld));vec2 tile=st/vec2(.52,.21);tile.x+=.5*mod(floor(tile.y),2.);vec2 grid=abs(fract(tile+.5)-.5)/max(fwidth(tile),vec2(.035));float joint=1.-smoothstep(.12,.65,min(grid.x,grid.y));diffuseColor.rgb*=.982+.036*qNoise(st*1.1)+.15*joint*zoom*(1.-abs(fn.y));';
  }else if(kind==='ashlar'){
   color='vec3 fn=normalize(cross(dFdx(qWorld),dFdy(qWorld)));vec2 st=vec2(abs(fn.x)>abs(fn.z)?qWorld.z:qWorld.x,qWorld.y);float fade=1.-smoothstep(16.,62.,length(cameraPosition-qWorld));vec2 uv=st/vec2(1.28,.61);uv.x+=.50*mod(floor(uv.y),2.);vec2 joint=abs(fract(uv+.5)-.5)/max(fwidth(uv),vec2(.002));float line=(1.-smoothstep(.22,1.05,min(joint.x,joint.y)))*fade*(1.-abs(fn.y));float stone=qNoise(st*1.10)*.035+(qHash(floor(uv))-.5)*.041+(qNoise(st*15.)-.5)*.047*fade;diffuseColor.rgb*=.986+stone-.14*line;';
  }else if(kind==='terracotta'){
   color='float fade=1.-smoothstep(18.,95.,length(cameraPosition-qWorld));vec3 fn=normalize(cross(dFdx(qWorld),dFdy(qWorld)));vec2 st=abs(fn.x)>abs(fn.z)?qWorld.zx:qWorld.xz;float tiles=sin(6.283*st.x/.25)*.026;diffuseColor.rgb*=.985+.030*qNoise(st*.53)+fade*tiles/(1.+5.*fwidth(st.x));';
  }else if(kind==='flora'){
   color=`vec3 arm=qFocus-cameraPosition, delta=qWorld-cameraPosition;
    float len=max(1.,length(arm));vec3 ray=arm/len;float along=dot(delta,ray);
    float perp=length(delta-ray*along);
    float cover=(1.-smoothstep(100.,200.,len))*(1.-smoothstep(1.,3.1,perp))
               *smoothstep(0.,4.,along)*(1.-smoothstep(.80*len,.95*len,along));
    float fade=max(1.-smoothstep(1.,2.8,length(delta)),cover*qFade);
    float coverage=1.-.87*smoothstep(.4,1.,fade);
    vec2 detail=qWorld.xz*2.2+qWorld.y*.6;
    vec2 footprint=fwidth(detail);
    float resolved=1.-smoothstep(.3,1.,max(footprint.x,footprint.y));
    diffuseColor.rgb*=.9975+.095*(qNoise(detail)-.5)*resolved;`;
   if(sampleCoverage){
     // MSAA blends the tree's coverage at the lens while opaque trunks keep
     // writing depth. Subpixel leaf edges use the same coverage samples.
     if(mat.alphaTest>0){
       sh.fragmentShader=sh.fragmentShader.replace('#include <alphatest_fragment>',
        'float leafWidth=max(fwidth(diffuseColor.a),.0001);coverage*=smoothstep(alphaTest-leafWidth*.5,alphaTest+leafWidth*.5,diffuseColor.a);');
     }
     sh.fragmentShader=sh.fragmentShader.replace('#include <output_fragment>',
       '#include <output_fragment>\ngl_FragColor.a=coverage;');
   }else{
     color+='if(coverage<1. && qHash(floor(qWorld.xz*20.+qWorld.y*9.))>coverage)discard;';
   }
  }
  sh.fragmentShader=sh.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\n'+color);
 };
}
let surf=null,lake=null,lakeMirror=null;
function installYinghaiLake(root){
 const matches=root.children.filter(o=>o.userData.lakeWater==='way/982180787');
 if(matches.length!==1)throw new Error('樱海湖水面节点缺失');
 const phase={value:0};
 let material=null,period=0;
 matches[0].traverse(mesh=>{
  if(!mesh.isMesh)return;
  material=mesh.material;
  const spec=material.userData;
  if(spec.lakeWater!=='way/982180787'||!material.normalMap||!mesh.geometry.attributes.color)throw new Error('樱海湖水纹或岸线色缺失');
  period=spec.periodSeconds;
  const flow=new THREE.Vector2().fromArray(spec.flowUV);
  mesh.castShadow=false;mesh.receiveShadow=true;material.envMapIntensity=spec.waterEnvironment??.68;
  material.customProgramCacheKey=()=>'yinghai-lake-wind-v1';
  material.onBeforeCompile=sh=>{
   sh.uniforms.qdLakePhase=phase;sh.uniforms.qdLakeFlow={value:flow};
   sh.fragmentShader='uniform float qdLakePhase; uniform vec2 qdLakeFlow;\n'+sh.fragmentShader;
   const chunk=THREE.ShaderChunk.normal_fragment_maps.replace(
    'vec3 mapN = texture2D( normalMap, vUv ).xyz * 2.0 - 1.0;',
    `float t=qdLakePhase;
     vec2 uvA=vUv-qdLakeFlow*(fract(t+.5)-.5),uvB=vUv-qdLakeFlow*(t-.5);
     vec3 lakeA=texture2D(normalMap,uvA).xyz, lakeB=texture2D(normalMap,uvB).xyz;
     vec3 mapN=mix(lakeA,lakeB,.5-.5*cos(6.28318530718*t))*2.-1.;`);
   sh.fragmentShader=sh.fragmentShader.replace('#include <normal_fragment_maps>',chunk);
  };
  material.needsUpdate=true;
 });
 if(!material||!(period>0))throw new Error('樱海湖材质循环缺失');
 return {period,update(seconds){phase.value=((seconds%period)+period)%period/period;}};
}
let selected=null,flight=null,animTime=0,viewMode='facade',navigation=null;
let hudDirty=true,labelsVisible=true;
let coreOnly=false;
const peripheral=[],cutEdges=[];
function installNearshoreSection(root,data){
 const far=root.children.find(n=>n.userData.kind==='sea');
 const landCut=root.children.find(n=>n.userData.sceneRegion==='cutEdge');
 const level=new THREE.Box3().setFromObject(far).min.y;
 const bottom=new THREE.Box3().setFromObject(landCut).min.y;
 if(!(bottom<level))throw Error('近岸断面高程有误');
 const coords=data.vertices.flatMap(([x,top,z])=>[x,top?level:bottom,z]);
 const geometry=new THREE.BufferGeometry();
 geometry.setAttribute('position',new THREE.Float32BufferAttribute(coords,3));
 geometry.setIndex(data.indices);geometry.computeVertexNormals();
 const mat=new THREE.MeshStandardMaterial({color:new THREE.Color(...data.color),roughness:1,metalness:0,flatShading:true,side:THREE.DoubleSide});
 const cut=new THREE.Mesh(geometry,mat);
 cut.name='近岸海域剖面';cut.userData={kind:'terrainCut',sceneRegion:'coreSeaCut'};
 root.add(cut);
 peripheral.push(far);
 cutEdges.push(cut);
}
const allowsPlace=p=>!coreOnly || p?.sceneRegion!=='surroundings';
function setScope(mode){
 if(!['core','full'].includes(mode))throw Error('未知显示范围');
 coreOnly=mode==='core';state.scope=mode;
 for(const node of peripheral)node.visible=!coreOnly;
 for(const node of cutEdges)node.visible=coreOnly;
 for(const tile of plantTiles.values())tile.scopeHidden=coreOnly && tile.peripheral;
 state.windowProbes?.setScope(mode);
 lakeMirror?.invalidate();renderer.shadowMap.needsUpdate=true;
 el('modelArea').setAttribute('aria-pressed',String(coreOnly));
 if(!allowsPlace(locations.find(p=>p.key===selected)))choose('overview',true);
 menu();navigation?.invalidate();hudDirty=true;
}
state.setScope=setScope;
el('modelArea').onclick=()=>{
 setScope(coreOnly?'full':'core');
 try{localStorage.setItem('sdu-qd-v6-scope',state.scope);}catch{}
};
const needle=el('needle'),offsetA=new THREE.Spherical(),offsetB=new THREE.Spherical();
const poseOffset=new THREE.Vector3(),frameOrbit=new THREE.Spherical();
function panel(open){
 document.body.classList.toggle('panel',open);
 el('mobile').setAttribute('aria-expanded',String(open));
}
function updateHud(){
 if(!navigation||!hudDirty)return;
 hudDirty=false;
 navigation.update(selected,viewMode);
 needle.style.transform='rotate('+THREE.MathUtils.radToDeg(control.getAzimuthalAngle())+'deg)';
}
function travel(eye,target,fov,instant){
 const toEye=new THREE.Vector3().fromArray(eye),toTarget=new THREE.Vector3().fromArray(target);
 flight=null;hudDirty=true;
 if(instant||movie||matchMedia('(prefers-reduced-motion:reduce)').matches){
   cam.position.copy(toEye);control.target.copy(toTarget);cam.fov=fov;
   cam.updateProjectionMatrix();control.update();focus.value.copy(toTarget);return;
 }
 offsetA.setFromVector3(poseOffset.subVectors(cam.position,control.target));
 offsetB.setFromVector3(poseOffset.subVectors(toEye,toTarget));
 const angle=Math.atan2(Math.sin(offsetB.theta-offsetA.theta),Math.cos(offsetB.theta-offsetA.theta));
 const distance=cam.position.distanceTo(toEye);
 flight={start:performance.now(),duration:Math.min(1240,510+Math.sqrt(distance)*14),
    from:control.target.clone(),to:toTarget,fromFov:cam.fov,toFov:fov,
    fromOrbit:offsetA.clone(),toOrbit:offsetB.clone(),angle,
    lift:Math.min(260,distance*.13),eye:toEye};
}
function advanceFlight(t){
 const f=flight,x=THREE.MathUtils.clamp((t-f.start)/f.duration,0,1),p=x*x*(3-2*x);
 control.target.lerpVectors(f.from,f.to,p);
 frameOrbit.set(THREE.MathUtils.lerp(f.fromOrbit.radius,f.toOrbit.radius,p),
                THREE.MathUtils.lerp(f.fromOrbit.phi,f.toOrbit.phi,p),f.fromOrbit.theta+f.angle*p);
 cam.position.copy(control.target).add(poseOffset.setFromSpherical(frameOrbit));
 cam.position.y+=Math.sin(Math.PI*p)*f.lift;
 cam.fov=THREE.MathUtils.lerp(f.fromFov,f.toFov,p);cam.updateProjectionMatrix();
 if(x===1){cam.position.copy(f.eye);flight=null;}
 hudDirty=true;
}
function goPoint(point){
 control.minDistance=4;
 const radius=THREE.MathUtils.clamp(cam.position.distanceTo(control.target)*.42,42,110);
 const bearing=control.getAzimuthalAngle();
 const target=[point.x,point.y+1,point.z], eye=[point.x+Math.sin(bearing)*radius,point.y+radius*.83,point.z+Math.cos(bearing)*radius];
 viewMode=state.viewMode=null;
 describe('point');navigation.setPoint(point);el('switchView').hidden=true;panel(false);
 folFade.value=1;travel(eye,target,44,false);
}
control.addEventListener('change',()=>{hudDirty=true;});
el('showLabels').onclick=()=>{
 labelsVisible=!labelsVisible;el('showLabels').setAttribute('aria-pressed',String(labelsVisible));
 navigation?.setLabels(labelsVisible);hudDirty=true;
};
function cameraFov(pose){
 const fov=pose?.fov||41;
 if(!pose?.minAspect || cam.aspect>=pose.minAspect)return fov;
 return THREE.MathUtils.radToDeg(2*Math.atan(Math.tan(radians(fov/2))*pose.minAspect/cam.aspect));
}
function resize(){
 hudDirty=true;
 const w=stage.clientWidth,h=stage.clientHeight;
 // Match physical display pixels up to one 4K frame. Capture presets already
 // specify their output pixel dimensions through the film-mode viewport.
 const ratio=movie?1:Math.min(window.devicePixelRatio||1, Math.sqrt(8294400/Math.max(1,w*h)));
 if(renderer.getPixelRatio()!==ratio)renderer.setPixelRatio(ratio);
 renderer.setSize(w,h,false);cam.aspect=w/h;
 const pose=locations.find(p=>p.key===selected)?.views?.[viewMode];
 if(pose?.minAspect){
   if(flight)flight.toFov=cameraFov(pose);
   else cam.fov=cameraFov(pose);
 }
 cam.updateProjectionMatrix();
}
window.addEventListener('resize',resize);resize();
function renderPose(eye,target,fov,t){
 cam.position.fromArray(eye);control.target.fromArray(target);cam.lookAt(control.target);cam.fov=fov;cam.updateProjectionMatrix();cam.updateMatrixWorld();focus.value.copy(control.target);time.value=t;renderWorld(t,true);
}
Object.assign(state,{renderer,scene:world,camera:cam,renderPose,resize});
const plantTiles=new Map(),clip=new THREE.Frustum(),clipMatrix=new THREE.Matrix4();
function renderWorld(seconds,exact=false){
 if(surf)surf.update(seconds);
 if(lake)lake.update(seconds);
 if(!logDepth){
   // WebGL 1 without fragment depth needs a longer near plane in wide shots.
   const near=THREE.MathUtils.clamp(cam.position.distanceTo(control.target)*.0015,.28,4.);
   if(cam.near!==near){cam.near=near;cam.updateProjectionMatrix();}
 }
 cam.updateMatrixWorld();clip.setFromProjectionMatrix(clipMatrix.multiplyMatrices(cam.projectionMatrix,cam.matrixWorldInverse));
 for(const tile of plantTiles.values()){
   const inRange=!tile.cutoff||tile.bounds.distanceToPoint(cam.position)<tile.cutoff;
   const show=!tile.scopeHidden&&inRange&&(renderer.shadowMap.needsUpdate||clip.intersectsBox(tile.bounds));
   for(const m of tile.meshes)m.visible=show;
 }
 if(lakeMirror)lakeMirror.update(cam,exact);
 renderer.render(world,cam);
}
function treeBatch(root){
 const groups=new Map(),remove=[];
 root.updateMatrixWorld(true);
 for(const obj of [...root.children]){
  if(!['flora','groundcover'].includes(obj.userData.kind))continue;
  remove.push(obj);
  obj.traverse(m=>{if(!m.isMesh)return;
   const p=new THREE.Vector3().setFromMatrixPosition(m.matrixWorld);
   const grassTier=obj.userData.grassRelief && obj.userData.tier;
   const cutoff=grassTier && ({field:145,verge:95,detail:65}[grassTier]);
   const size=grassTier?32:300;
   const peripheral=obj.userData.sceneRegion==='surroundings';
   const tileKey=(peripheral?'outer:':'')+(grassTier||'canopy')+':'+Math.floor(p.x/size)+','+Math.floor(p.z/size);
   if(!plantTiles.has(tileKey))plantTiles.set(tileKey,{bounds:new THREE.Box3(),meshes:[],cutoff,peripheral});
   const tile=plantTiles.get(tileKey);
   if(!m.geometry.boundingBox)m.geometry.computeBoundingBox();
   tile.bounds.union(m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld));
   const key=tileKey+'/'+m.geometry.uuid+'/'+m.material.uuid;
   if(!groups.has(key))groups.set(key,{geo:m.geometry,mat:m.material,list:[],kind:obj.userData.kind,tile});
   groups.get(key).list.push(m.matrixWorld.clone());});
 }
 for(const o of remove)root.remove(o);
 for(const {geo,mat,list,kind,tile} of groups.values()){
   const mesh=new THREE.InstancedMesh(geo,mat,list.length);
   for(let i=0;i<list.length;i++)mesh.setMatrixAt(i,list[i]);
   mesh.castShadow=kind==='flora';mesh.receiveShadow=true;mesh.frustumCulled=false;mesh.userData.kind=kind;
   if(tile.peripheral)mesh.userData.sceneRegion='surroundings';
   if(kind==='flora')texture(mat,'flora');root.add(mesh);tile.meshes.push(mesh);
 }
}
const info={
 library:'西向正门前的五座拱门对应五列竖窗。上方红色坡屋面围住中央采光庭。',
 museum:'四角铜板取意于出土竹简，深色玻璃与浅石色悬挑展厅围合成方鼎形体。',
 huagang:'华岗苑四翼环绕内院，南北券洞、东西连廊下各有一条进院的路。',
 zhensheng:'从东翼或西翼望去，两端楼身之间各有一处退入的玻璃连廊。沿连廊下的石径可以走进内院。',
 west_gate:'面向校园，右侧门塔上有校徽和竖排“山东大学”题字。两塔之间的道路向东通往育贤广场和图书馆。',
 blue_track:'蓝色跑道环抱训练草坪，东侧邻接体育馆伸出的看台罩棚。',
 song_arena:'宋君复体育馆以连续的白色弧顶连接比赛馆区与游泳馆区。',
 xiyuan:'凤凰居东侧的学生餐厅，红砖墙面与入口的大幅拱窗相接。',
 yuxian:'西门与图书馆之间的育贤广场，中央草坪沿礼仪轴线展开。'
};
function describe(key){const loc=locations.find(p=>p.key===key);selected=key;state.selected=key;hudDirty=true;el('place').textContent=loc?loc.name:(key==='point'?'所选位置':key==='home'?'图书馆中轴':'青岛校区全景');el('detail').textContent=info[key]||loc?.note||(key==='point'?'拖动可环看四周，点击建筑或地名可继续前往。':key==='home'?'从育贤广场向东，望见图书馆朝向西门的五座拱门。':'点击建筑、地名或校园地面前往查看。拖动旋转，滚轮或双指缩放。');document.querySelectorAll('nav button').forEach(b=>b.setAttribute('aria-current',String(b.dataset.id===key)));}
const viewLabels={facade:'返回立面',entrance:'门前近景',roof:'屋顶鸟瞰',roof_plan:'垂直看屋顶',roof_edge:'檐口近景'};
function choose(key,jump=false,mode='facade'){
 const location=locations.find(p=>p.key===key);
 if(!allowsPlace(location) || (!location && key!=='overview' && key!=='home'))return;
 const views=location?.views||{};
 const modes=Object.keys(views).filter(id=>id!=='facade');
 if(views.facade)modes.unshift('facade');
 viewMode=modes.includes(mode)?mode:(modes[0]||'facade');
 state.viewMode=viewMode;
 const toggle=el('switchView');
 toggle.hidden=modes.length<2;
 if(!toggle.hidden){
   const next=modes[(modes.indexOf(viewMode)+1)%modes.length];
   toggle.dataset.mode=next;
   toggle.textContent=location.views[next].label||viewLabels[next];
 }else delete toggle.dataset.mode;
 folFade.value=(location && ['学院楼','院楼与生活区','地标','航拍影像对照'].includes(location.group))?1:0;
 let eye,tar;
 if(key==='overview'){eye=[-1780,1530,2270];tar=[65,6,15];}
 else if(key==='home'){eye=[-184,79,48];tar=[115,19,-67];}
 else if(location?.views?.[viewMode]){const p=location.views[viewMode];eye=p.eye;tar=p.target;}
 else if(location?.viewpoint?.eye){eye=location.viewpoint.eye;tar=location.viewpoint.target;}
 else{const l=location;if(!l)return;
  const a=(l.yaw||0)+.34,h=l.h||16,dist=Math.max(42,l.r*2.24+h*.42);
  eye=[l.x+Math.sin(a)*dist,l.y+h*.8+dist*.32,l.z+Math.cos(a)*dist];tar=[l.x,l.y+h*.38,l.z];}
 const pose=location?.views?.[viewMode]||location?.viewpoint;
 control.minDistance=pose?.minOrbitDistance || 4;
 cam.updateProjectionMatrix();
 navigation?.setPoint(null);
 describe(key);panel(false);
 travel(eye,tar,cameraFov(pose),jump);
}
state.go=choose;
el('switchView').onclick=event=>choose(selected,false,event.currentTarget.dataset.mode);
for(const k of ['overview','home'])el(k).onclick=()=>choose(k);
el('north').onclick=()=>{flight=null;const delta=cam.position.clone().sub(control.target),distance=Math.hypot(delta.x,delta.z);cam.position.copy(control.target).add(new THREE.Vector3(0,delta.y,distance));control.update();};
for(const [id,k] of [['closer',.76],['farther',1.32]])el(id).onclick=()=>{flight=null;v.copy(cam.position).sub(control.target).multiplyScalar(k);if(v.length()>4&&v.length()<5500)cam.position.copy(control.target).add(v);control.update();};
el('mobile').onclick=()=>panel(!document.body.classList.contains('panel'));control.addEventListener('start',()=>flight=null);
const entranceStops = new Set(['west_gate','south_gate','north_gate','east_gate','lake']);
const menuFamily = place => entranceStops.has(place.key) ? '校门与樱海湖' : place.group;
function menu(){const nav=el('menu');nav.replaceChildren();const fold=value=>value.normalize('NFKC').replace(/\s+/g,'').toLowerCase();const text=fold(el('search').value);let count=0;
 for(const family of new Set(['校门与樱海湖','地标','学院楼','滨海公园','校园场地','院楼与生活区','春日花木','景观','夕照时分',...locations.map(p=>p.group)])){
  const list=locations.filter(p=>allowsPlace(p)&&menuFamily(p)===family&&[p.name,...(p.aliases||[])].some(s=>fold(s).includes(text)));if(!list.length)continue;
  const h=document.createElement('h2');h.textContent=family;nav.append(h);
  for(const l of list){const b=document.createElement('button');b.textContent=l.name;b.dataset.id=l.key;b.onclick=()=>choose(l.key);b.setAttribute('aria-current',String(l.key===selected));nav.append(b);count++;}}
 if(!count){const p=document.createElement('p');p.textContent='未找到匹配的地点';nav.append(p);}}
el('search').addEventListener('input',menu);menu();
try{
 const txt=el('glb').textContent.trim(),bin=Uint8Array.from(atob(txt),c=>c.charCodeAt(0));el('glb').remove();
 const raw=await new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
 const gltf=await new Promise((yes,no)=>new THREE.GLTFLoader().parse(raw,'',yes,no));const root=gltf.scene;
 // A plain GLB viewer uses the embedded sun. In this viewer the tracked
 // directional shadow rig supplies that same light once.
 root.traverse(node=>{
    if(node.userData.kind==='sunsetRig'||node.name==='SDU_Sunset_Key'){
      node.traverse(light=>{if(light.isLight)light.visible=false;});
    }
 });
 root.traverse(m=>{if(!m.isMesh)return;const mat=m.material,k=mat.userData.sourceSurface || mat.name;m.castShadow=!mat.userData.sportNet&&k!=='water'&&k!=='grass'&&k!=='asphalt';m.receiveShadow=true;
 for(const map of [mat.map,mat.normalMap,mat.roughnessMap,mat.metalnessMap,mat.clearcoatNormalMap,mat.clearcoatRoughnessMap])if(map)map.anisotropy=anisotropy;
  const finish=mat.userData.rawArchFinish || mat.userData.archFinish;
  if(finish){
    // The GLB supplies the same material response as the editable Blender scene.
    const envByFinish={glass:.84,metal:.57,clay:.34};
    mat.envMapIntensity=envByFinish[finish] ?? .31;
    return;
  }
  if(k.startsWith('园下草土'))texture(mat,'grass');
  else if(['water','asphalt','grass'].includes(k))texture(mat,k);
  else if(['#ded4bf','#d9cbb7','#e2d9c9','#eee3ce','#b1aaa0'].includes(k))texture(mat,'ashlar');
  else if(['#bd684f','#b65e4b'].includes(k))texture(mat,'terracotta');
  else if(/^#(a6|a0|ac|b7|9e|95)/i.test(k))texture(mat,'facade');
  const plainPane=['glass','#405766','#3c6072','#465966','#516671','#687b83'].includes(k);
  mat.envMapIntensity=plainPane ? .84 : (mat.userData.waterEnvironment ?? .29);
  if(k.includes('Sentinel-2'))m.castShadow=false;
 });
 // Pavement, turf and sports markings receive shadows from buildings and trees.
 // Their closely stacked planar surfaces do not need to cast their own shadows.
 for(const node of root.children){
    const ground=['ground','groundcover','sea','water','terrainContext','sport','waterfrontShore','parcelGround'].includes(node.userData.kind);
    const isPlaza=node.userData.key==='yuxian';
    const isParking=node.userData.kind==='parkingDetail';
    if(ground||isPlaza||isParking)node.traverse(mesh=>{
       if(!mesh.isMesh)return;
       const name=mesh.material.name;
       const paint=isParking&&['#dfdbbd','#dad8c4'].includes(name);
       const plazaFloor=isPlaza&&(name.startsWith('广场浅色石板')||['#cac7b6','#8faa70','#93ac72','#91a275'].includes(name));
       if(ground||paint||plazaFloor)mesh.castShadow=false;
    });
 }
 installNearshoreSection(root,/*NEARSHORE_SECTION*/null);
 surf=window.QDShoreWave.install(root,THREE);state.shore=surf;
 lake=installYinghaiLake(root);state.lake=lake;
 treeBatch(root);peripheral.push(...root.children.filter(n=>n.userData.sceneRegion==='surroundings'));cutEdges.push(...root.children.filter(n=>n.userData.sceneRegion==='cutEdge'));world.add(root);state.root=root;renderer.shadowMap.needsUpdate=true;
 const windowProbes=/*WINDOW_PROBES*/[];
 if(windowProbes.length)state.windowProbes=await window.QDWindowProbes.install(root,THREE,renderer,readSunsetTexture,windowProbes);
 if(!probeBake){
    lakeMirror=window.QDShoreWave.installLakeReflection(renderer,world,root,plantTiles);
    state.lakeMirror=lakeMirror;
 }
 if(!movie){
   navigation=window.QDNavigation.install({THREE,root,camera:cam,canvas:renderer.domElement,stage,locations,choose,goPoint,allowsPlace,boundary:/*CAMPUS_BOUNDARY*/[]});
   navigation.setLabels(labelsVisible);
 }
 const params=new URLSearchParams(location.search);
 const requested=params.get('view'),standardView=movie?'film-gate':'overview';
 let initialScope=params.get('scope');
 if(!initialScope && !movie){
   try{initialScope=localStorage.getItem('sdu-qd-v6-scope');}catch{}
   if(locations.find(p=>p.key===requested)?.sceneRegion==='surroundings')initialScope='full';
 }
 setScope(initialScope==='core'?'core':'full');el('modelArea').disabled=false;
 const initialKey=['overview','home'].includes(requested)||locations.some(p=>p.key===requested&&allowsPlace(p))?requested:standardView;
 choose(initialKey,true,params.get('mode')||'facade');renderPose(cam.position.toArray(),control.target.toArray(),cam.fov,0);
 state.ready=true;el('load').hidden=true;
 if(!movie){
  const clock=new THREE.Clock();function draw(t){animTime+=Math.min(.08,clock.getDelta());if(flight)advanceFlight(t);
   control.update();time.value=animTime;focus.value.copy(control.target);renderWorld(animTime);updateHud();requestAnimationFrame(draw);}requestAnimationFrame(draw);
 }
}catch(e){state.error=String(e);el('load').textContent='模型载入失败。请用新版 Edge 或 Chrome 打开。 '+(e.message||e);console.error(e);}
})().catch(e=>{window.qd.error=String(e);document.getElementById('load').textContent=String(e);});

