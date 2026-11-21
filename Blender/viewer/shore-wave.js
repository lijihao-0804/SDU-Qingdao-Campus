/* Native glTF swell, foam envelope and advected air-cell lace share an 11.2 second loop. */
(function(global){
  'use strict';
  function install(root, THREE){
    const surfaces=[],frames=48,period=11.2;
    const first={value:0},next={value:1/frames},blend={value:0},clock={value:0};
    root.traverse(node=>{
      const near=node.userData.kind==='surfWater';
      if(!near&&node.userData.kind!=='sea')return;
      node.traverse(mesh=>{
        if(!mesh.isMesh)return;
        const mat=mesh.material,geo=mesh.geometry;
        if(near){
          const factors=geo.attributes.uv2||geo.attributes.uv1;
          if(!factors||!mat.map||!mat.emissiveMap)throw new Error('Missing packed nearshore depth, crest or air-cell detail.');
          geo.setAttribute('qdSurfFactors',factors);
          surfaces.push(mesh);
        }
        mesh.castShadow=false;mesh.receiveShadow=true;
        mat.envMapIntensity=mat.userData.waterEnvironment??.32;
        mat.customProgramCacheKey=()=>near?'qd-surf-lace-5':'qd-open-sea-5';
        mat.onBeforeCompile=shader=>{
          shader.uniforms.qdSeaTime=clock;
          const varied='varying vec3 qdWorld;varying vec2 qdDepth;varying vec2 qdShoreUV;\n';
          shader.vertexShader=(near?'attribute vec2 qdSurfFactors;\n':'')+varied+shader.vertexShader;
          shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\n'+(near?'qdDepth=qdSurfFactors;qdShoreUV=uv;':'qdDepth=vec2(0.,1.);qdShoreUV=vec2(0.);'));
          shader.vertexShader=shader.vertexShader.replace('#include <worldpos_vertex>','#include <worldpos_vertex>\nqdWorld=(modelMatrix*vec4(transformed,1.)).xyz;');
          let header=varied+'uniform float qdSeaTime;\n';
          if(near){
            Object.assign(shader.uniforms,{qdFoamA:first,qdFoamB:next,qdFoamMix:blend,qdFoamTex:{value:mat.emissiveMap},qdCells:{value:mat.map}});
            header+='uniform sampler2D qdFoamTex,qdCells;uniform float qdFoamA,qdFoamB,qdFoamMix;\n';
          }
          shader.fragmentShader=header+shader.fragmentShader;
          // The body, wind texture and sky reflection have identical equations
          // on both sides of the 108 m boundary, including the far-water mesh.
          shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
            float qRange=length(cameraPosition-qdWorld),qClose=1.-smoothstep(90.,640.,qRange),qReach=smoothstep(.17,.82,qdDepth.y);
            float qRip=.53*sin(qdWorld.x*.29+qdWorld.z*.43+qdSeaTime*.5609986881+2.*sin(qdWorld.z*.08))+.26*sin(qdWorld.x*.73-qdWorld.z*.62+qdSeaTime*1.1219973763);
            float qView=pow(1.-abs(normalize(cameraPosition-qdWorld).y),2.2);
            diffuseColor.rgb=diffuseColor.rgb*(1.+.075*qRip*qClose)+vec3(.018,.027,.034)*qView*(.5+.5*qReach);
            float qFoam=0.;`);
          shader.fragmentShader=shader.fragmentShader.replace('#include <normal_fragment_maps>',`#include <normal_fragment_maps>
            float qDepth=qdDepth.y*108.,qAlong=qdShoreUV.y*223.;
            float qr=sin(qdWorld.x*.31+qdSeaTime*.5609986881)+.63*sin(qdWorld.z*.54-qdSeaTime*1.1219973763);
            float qs=cos(qdWorld.x*.47+qdWorld.z*.24+qdSeaTime*.5609986881);
            float fine=(sin(qAlong*1.19+qDepth*2.+qdSeaTime*1.1219973763)+.46*sin(qAlong*2.36-qDepth*.81-qdSeaTime*1.6829960644));
            vec3 perturb=mix(vec3(.027*fine,.0,.017*fine),vec3(.039*qr,.0,.029*qs),qReach);
            normal=normalize(normal+mat3(viewMatrix)*perturb*qClose);`);
          if(near){
            shader.fragmentShader=shader.fragmentShader.replace('#include <emissivemap_fragment>',`
              float t=qdSeaTime*.5609986881;float crossD=qdDepth.y*108.;float alongS=qdShoreUV.y*223.;
              vec2 foamUV=vec2((crossD+.56*sin(2.*t)+.23*cos(3.*t))/3.7,(alongS+.19*cos(2.*t))/3.7);
              vec2 flowWarp=vec2(.056*sin(foamUV.y*2.4+.4*cos(t)),.034*cos(foamUV.x*2.3+.33*sin(t)));
              float cell=texture2D(qdCells,foamUV+flowWarp).a;
              float torn=texture2D(qdCells,foamUV.yx*.46+vec2(.21,.67)-flowWarp).a;
              float frontJitter=(.33*sin(alongS*1.17+.19*sin(2.*t))+.16*sin(alongS*2.9+.43*cos(3.*t))+.18*(torn-.4))/26.*(77./3840.);
              vec2 fc=vec2(clamp(qdShoreUV.x+frontJitter,1.5/3840.,78.5/3840.),qdShoreUV.y);
              float a=texture2D(qdFoamTex,fc+vec2(qdFoamA,0.)).a,b=texture2D(qdFoamTex,fc+vec2(qdFoamB,0.)).a;
              float body=mix(a,b,qdFoamMix);
              float web=smoothstep(.028,.43,body)*(.06+.94*cell)*(.59+.41*torn);
              float lip=smoothstep(.49,.83,body)*(.18+.69*cell+.13*torn);
              qFoam=clamp((web*.95+lip*.49)*qdDepth.x,0.,.96);
              totalEmissiveRadiance=vec3(0.);`);
          }
          shader.fragmentShader=shader.fragmentShader.replace('#include <output_fragment>',`
            vec3 bay=mix(outgoingLight*vec3(.62,.71,.77),diffuseColor.rgb*1.04,.30);
            outgoingLight=mix(bay,vec3(.79,.85,.84),qFoam);
            #include <output_fragment>`);
        };
        mat.needsUpdate=true;
      });
    });
    function update(seconds){
      const t=((seconds%period)+period)%period,frame=t/period*frames,k=Math.floor(frame);
      first.value=k/frames;next.value=((k+1)%frames)/frames;blend.value=frame-k;clock.value=t;
      const phase=2*Math.PI*t/period;
      for(const mesh of surfaces){
        const w=mesh.morphTargetInfluences;
        w[0]=.5+.5*Math.cos(2*phase);w[1]=.5+.5*Math.sin(2*phase);
        w[2]=.5+.5*Math.cos(3*phase);w[3]=.5+.5*Math.sin(3*phase);
      }
    }
    update(0);
    return {update,count:surfaces.length,period,frames};
  }
  // Project the actual shoreline into Yinghai Lake. The normal map, water body
  // and the directional sun's microfacet lobe stay in the imported PBR shader.
  function installLakeReflection(renderer,scene,root,plantTiles){
    const lake=root.children.find(node=>node.userData.lakeWater==='way/982180787');
    const mesh=lake.isMesh?lake:lake.getObjectByProperty('isMesh',true);
    root.updateMatrixWorld(true);
    const bounds=new THREE.Box3().setFromObject(mesh),level=(bounds.min.y+bounds.max.y)*.5;
    const rc=new THREE.PerspectiveCamera(),dir=new THREE.Vector3(),up=new THREE.Vector3();
    const planeNormal=new THREE.Vector3(0,1,0),shoreClip=new THREE.Plane(planeNormal,-level+.025);
    const frustum=new THREE.Frustum(),vp=new THREE.Matrix4(),lastView=new THREE.Matrix4(),lastProj=new THREE.Matrix4();
    const target=new THREE.WebGLRenderTarget(512,384,{
      type:renderer.capabilities.isWebGL2&&renderer.extensions.has('EXT_color_buffer_float')?THREE.HalfFloatType:THREE.UnsignedByteType,
      minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter,generateMipmaps:false,depthBuffer:true
    });
    target.texture.name='樱海湖 · 岸景反射';
    const coverage={value:0},mirrorMatrix={value:new THREE.Matrix4()};
    const material=mesh.material,sourceCompile=material.onBeforeCompile;
    const sourceKey=material.customProgramCacheKey();
    material.customProgramCacheKey=()=>sourceKey+'-shore-reflection-1';
    material.onBeforeCompile=function(shader,context){
      sourceCompile.call(this,shader,context);
      shader.uniforms.qdMirror={value:target.texture};
      shader.uniforms.qdMirrorMatrix=mirrorMatrix;
      shader.uniforms.qdMirrorCoverage=coverage;
      shader.vertexShader='uniform mat4 qdMirrorMatrix; varying vec4 qdMirrorPos;\n'+shader.vertexShader.replace(
        '#include <worldpos_vertex>',
        '#include <worldpos_vertex>\nqdMirrorPos=qdMirrorMatrix*modelMatrix*vec4(transformed,1.);');
      shader.fragmentShader='varying vec4 qdMirrorPos; uniform sampler2D qdMirror; uniform float qdMirrorCoverage;\n'+shader.fragmentShader.replace(
        '#include <output_fragment>',`
        if(qdMirrorCoverage>0. && qdMirrorPos.w>0.){
          vec3 waterUp=normalize(mat3(viewMatrix)*vec3(0.,1.,0.));
          vec2 slope=(normal-waterUp).xy;
          vec2 uv=.5+.5*qdMirrorPos.xy/qdMirrorPos.w+vec2(-slope.x,slope.y)*.048;
          vec2 edge=min(uv,1.-uv);
          float inFrame=smoothstep(.0,.025,min(edge.x,edge.y))*qdMirrorCoverage;
          vec2 blur=vec2(.0019,.0026);
          vec3 bank=.5*texture2D(qdMirror,uv).rgb+.25*texture2D(qdMirror,uv+blur).rgb+.25*texture2D(qdMirror,uv-blur).rgb;
          // The small solar disc already has its own rough PBR highlight.
          bank*=min(1.,2.2/max(.001,max(max(bank.r,bank.g),bank.b)));
          float nDotV=clamp(dot(normal,normalize(vViewPosition)),0.,1.);
          float fresnel=.0204+.9796*pow(1.-nDotV,5.);
          vec3 body=outgoingLight-reflectedLight.indirectSpecular-reflectedLight.directSpecular;
          vec3 local=mix(body,bank,fresnel)+reflectedLight.directSpecular;
          outgoingLight=mix(outgoingLight,local,inFrame);
        }
        #include <output_fragment>`);
    };
    material.needsUpdate=true;
    const hidden=root.children.filter(n=>['sea','surfWater','water'].includes(n.userData.kind));
    const saved=new Map();
    const setVisible=(node,value)=>{if(node.visible!==value){saved.set(node,node.visible);node.visible=value;}};
    let cached=false,lastTime=-Infinity,passes=0;
    function update(camera,exact=false){
      frustum.setFromProjectionMatrix(vp.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse));
      const distance=bounds.distanceToPoint(camera.position);
      if(!lake.visible||camera.position.y<=level+.04||distance>=520||!frustum.intersectsBox(bounds)){
        coverage.value=0;cached=false;return;
      }
      coverage.value=1-THREE.MathUtils.smoothstep(distance,340,520);
      const now=performance.now();
      if(!exact&&cached&&(lastView.equals(camera.matrixWorld)&&lastProj.equals(camera.projectionMatrix)||now-lastTime<83))return;
      rc.position.copy(camera.position);rc.position.y=2*level-camera.position.y;
      camera.getWorldDirection(dir).reflect(planeNormal);
      up.set(0,1,0).transformDirection(camera.matrixWorld).reflect(planeNormal);rc.up.copy(up);
      rc.lookAt(dir.add(rc.position));rc.updateMatrixWorld();
      rc.near=camera.near;rc.far=camera.far;rc.projectionMatrix.copy(camera.projectionMatrix);
      rc.projectionMatrixInverse.copy(rc.projectionMatrix).invert();
      mirrorMatrix.value.multiplyMatrices(rc.projectionMatrix,rc.matrixWorldInverse);
      frustum.setFromProjectionMatrix(mirrorMatrix.value);

      const previous=renderer.getRenderTarget(),shadow=renderer.shadowMap.needsUpdate;
      const tone=renderer.toneMapping,planes=renderer.clippingPlanes;
      try{
        hidden.forEach(node=>setVisible(node,false));
        for(const tile of plantTiles.values()){
          const show=(!tile.scopeHidden)&&(!tile.cutoff||tile.bounds.distanceToPoint(camera.position)<tile.cutoff)&&frustum.intersectsBox(tile.bounds);
          for(const plant of tile.meshes)setVisible(plant,show);
        }
        renderer.shadowMap.needsUpdate=false;
        // Store linear radiance. Clipping below lake level works even with log depth.
        renderer.toneMapping=THREE.NoToneMapping;
        renderer.clippingPlanes=[...planes,shoreClip];
        renderer.setRenderTarget(target);renderer.clear();renderer.render(scene,rc);
      }finally{
        renderer.setRenderTarget(previous);renderer.clippingPlanes=planes;renderer.toneMapping=tone;
        renderer.shadowMap.needsUpdate=shadow;
        for(const [node,visible] of saved)node.visible=visible;
        saved.clear();
      }
      cached=true;lastView.copy(camera.matrixWorld);lastProj.copy(camera.projectionMatrix);
      lastTime=now;passes++;
    }
    return {update,invalidate(){cached=false;},get passes(){return passes;},get strength(){return coverage.value;}};
  }
  global.QDShoreWave={install,installLakeReflection};
})(window);
