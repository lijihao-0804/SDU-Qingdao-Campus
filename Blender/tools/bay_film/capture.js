async (plan) => {
  const {width, height, fps, frames, labels, endpoint} = plan;
  const scene = window.qd;
  if (scene.scope !== 'core' || !scene.ready) throw Error('Campus core scene is unavailable.');
  const visible = node => {
    for (let current=node; current; current=current.parent) if (!current.visible) return false;
    let geometryVisible=false;
    node.traverseVisible(child => {if (child.isMesh) geometryVisible=true;});
    return geometryVisible;
  };
  const coverage = {};
  for (const kind of ['sea','surfWater']) {
    const nodes = scene.root.children.filter(node => node.userData.kind===kind);
    coverage[kind] = {total:nodes.length, visible:nodes.filter(visible).length};
  }
  if (!plan.allowFullSea && (!coverage.sea.total || coverage.sea.visible || !coverage.surfWater.visible))
    throw Error('Final scene sea/surf visibility mismatch: ' + JSON.stringify(coverage));
  const raw = scene.renderer.domElement;
  const gl = scene.renderer.getContext();
  const ext = gl.getExtension('WEBGL_debug_renderer_info');
  const gpu = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
  if (/swiftshader|llvmpipe|basic render|software/i.test(gpu)) throw Error('Software GL: ' + gpu);
  if (raw.width !== width || raw.height !== height || gl.drawingBufferWidth !== width ||
      gl.drawingBufferHeight !== height || Math.abs(scene.camera.aspect - width / height) > 1e-8)
    throw Error('Native WebGL resolution or camera aspect mismatch.');
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', {alpha: false, colorSpace: 'srgb'});
  await document.fonts.load('500 23px "Microsoft YaHei"', '青岛校区图书馆');
  const smooth = value => { const x = Math.max(0, Math.min(1, value)); return x*x*(3-2*x); };
  await Promise.all([document.fonts.load('bold 57px "STZhongsong"','青岛校区图书馆'),
                     document.fonts.load('30px "Microsoft YaHei"','青岛校区图书馆')]);
  const drawLowerThird = createXianlinLowerThird(ctx, plan.lowerThirds || [], fps);
  const world = new THREE.Vector3(), view = new THREE.Vector3();
  const titles = labels.map((tag, index) => {
    ctx.font = '500 23px "Microsoft YaHei",sans-serif';
    const titleWidth = ctx.measureText(tag.title).width;
    ctx.font = '17px "Microsoft YaHei",sans-serif';
    const tw = Math.max(titleWidth, tag.subtitle ? ctx.measureText(tag.subtitle).width : 0);
    return {...tag, index, w: tw + 22, h: tag.subtitle ? 57 : 33};
  });
  function paint(tag, i, occupied) {
    world.fromArray(tag.anchor);
    view.copy(world).applyMatrix4(scene.camera.matrixWorldInverse);
    if (view.z > -scene.camera.near) return;
    world.project(scene.camera);
    const x = (world.x + 1)*960, y = (1-world.y)*540;
    if (world.z < -1 || world.z > 1) return;
    const w = tag.w, h = tag.h;
    // Apply any chosen side offset in 1080p screen coordinates; both endpoints track the building.
    const anchorX = x + (tag.dx || 0), anchorY = y - 14 + (tag.dy || 0);
    const left = anchorX-w/2, top = anchorY-h;
    const edge = Math.min(left-12, 1908-left-w, top-12, 1060-y, x-12, 1908-x);
    if (edge <= 0) return;
    const alpha = smooth((i-tag.start+fps/30)/(fps*.36)) * smooth((tag.end-i)/(fps*.36)) * smooth(edge/24);
    if (alpha < .01) return;
    if (occupied.some(box => left < box[2]+5 && left+w > box[0]-5 && top < box[3]+5 && top+h > box[1]-5)) return;
    occupied.push([left,top,left+w,top+h]);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = tag.kind === 'public' ? 'rgba(29,38,39,.58)' : 'rgba(26,37,38,.66)';
    ctx.beginPath(); ctx.roundRect(left,top,w,h,4); ctx.fill();
    ctx.lineWidth=1.45; ctx.strokeStyle='rgba(251,250,240,.84)';
    ctx.beginPath(); ctx.moveTo(anchorX,anchorY); ctx.lineTo(x,y); ctx.stroke();
    ctx.fillStyle='#f8f6ea'; ctx.beginPath(); ctx.arc(x,y,2.25,0,2*Math.PI); ctx.fill();
    ctx.font='500 23px "Microsoft YaHei",sans-serif';
    ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText(tag.title,anchorX,top+17);
    if (tag.subtitle) {
      ctx.font='17px "Microsoft YaHei",sans-serif';
      ctx.fillStyle='#e7ecdd'; ctx.fillText(tag.subtitle,anchorX,top+41);
    }
    return alpha > .25;
  }
  function draw(i, hits) {
    const p = frames[i];
    scene.renderPose(p.eye, p.target, p.fov, i/fps);
    if (gl.isContextLost()) throw Error('WebGL context lost on frame ' + i);
    ctx.globalAlpha = 1;
    ctx.drawImage(raw,0,0);
    ctx.save();
    ctx.scale(width/1920,height/1080);
    const occupied = [];
    for (const tag of titles) {
      if (tag.start <= i && i < tag.end && paint(tag,i,occupied) && hits) {
        hits[tag.index] = (hits[tag.index] || 0)+1;
      }
    }
    ctx.restore();
    const intro = drawLowerThird(i);
    if (hits && intro.index>=0 && intro.opacity>.25) {
      const key='intro/'+intro.index;
      hits[key]=(hits[key] || 0)+1;
    }
    return canvas;
  }
  // Match the Xianlin film's lower-left composition in 1920 × 1080 coordinates.
  // Integer frame ranges are [start, end). Call once after the film fonts have loaded.
  function createXianlinLowerThird(ink, cues, fps) {
    const { width, height } = ink.canvas;
    const layer = document.createElement('canvas');
    layer.width = width;
    layer.height = height;
    const g = layer.getContext('2d');
    let cached = -1;

    function drawLayer(cue) {
      g.clearRect(0, 0, width, height);
      g.save();
      g.scale(width / 1920, height / 1080);
      const grad = g.createLinearGradient(0, 745, 0, 1080);
      grad.addColorStop(0, 'rgba(14,27,26,0)');
      grad.addColorStop(.65, 'rgba(12,24,23,.43)');
      grad.addColorStop(1, 'rgba(12,24,23,.70)');
      g.fillStyle = grad;
      g.fillRect(0, 745, 1920, 335);
      g.fillStyle = '#e4c5a3';
      g.fillRect(102, 873, 34, 3);
      g.font = 'bold 57px "STZhongsong","SimSun",serif';
      g.fillStyle = '#fffdf5';
      g.shadowColor = 'rgba(8,17,19,.6)';
      // Canvas shadow distances are expressed in backing-store pixels.
      g.shadowBlur = 5 * height / 1080;
      g.shadowOffsetY = 2 * height / 1080;
      g.fillText(cue.title, 99, 941, 1450);
      g.font = '30px "Microsoft YaHei",sans-serif';
      g.fillStyle = '#f3f1e7';
      g.fillText(cue.caption, 101, 994, 1620);
      g.restore();
    }

    return function drawLowerThird(frame) {
      const index = cues.findIndex(cue => frame >= cue.start && frame < cue.end);
      if (index < 0) return { index: -1, opacity: 0 };
      const cue = cues[index];
      if (index !== cached) {
        drawLayer(cue);
        cached = index;
      }
      const fade = .24 * fps;
      const u = Math.min(1, (frame - cue.start + fps / 30) / fade, (cue.end - frame) / fade);
      const opacity = u * u * (3 - 2 * u);
      ink.save();
      ink.setTransform(1, 0, 0, 1, 0, 0);
      ink.globalAlpha = opacity;
      ink.drawImage(layer, 0, 0);
      ink.restore();
      return { index, opacity };
    };
  }

  const pixels = plan.backend === 'rgba' ? new Uint8Array(width*height*4) : null;
  async function render(start, end) {
    const hits = {};
    for (let i=start;i<end;i++) {
      const frame = new VideoFrame(draw(i,hits),{timestamp:Math.round(i*1e6/fps)});
      try {
        const options = {format:'RGBA', layout:[{offset:0,stride:width*4}], colorSpace:'srgb'};
        await frame.copyTo(pixels,options);
      } finally {frame.close();}
      const response = await fetch(endpoint+'/'+i,{method:'POST',body:pixels});
      if (!response.ok) throw Error('Frame '+i+' rejected: '+await response.text());
    }
    return hits;
  }
  let encoderConfig = null;
  if (plan.backend==='webcodecs') {
    if (typeof VideoEncoder !== 'function' || typeof VideoEncoder.isConfigSupported !== 'function')
      throw Error('H.264 WebCodecs encoder API unavailable; use --backend rgba.');
    const level = Number(plan.h264Level.replace('.', '')).toString(16).padStart(2,'0');
    // Preserve the original 1080p30 Main/Baseline fallback profile strings.
    const fallbackLevel = level === '29' ? '2a' : level;
    const candidates = ['avc1.6400'+level,'avc1.4d40'+fallbackLevel,'avc1.4200'+fallbackLevel];
    // Some hardware encoders accept a level request but signal a lower level.
    // Inspect the probe keyframe's Annex B sequence parameter set before capture.
    function usableKeyframe(chunk) {
      if (chunk.type !== 'key' || !chunk.byteLength) return false;
      if (height !== 2160) return true;
      const bytes = new Uint8Array(chunk.byteLength);
      chunk.copyTo(bytes);
      for (let i = 0; i + 6 < bytes.length; i++) {
        if (bytes[i] === 0 && bytes[i+1] === 0 && bytes[i+2] === 1 && (bytes[i+3] & 31) === 7)
          return bytes[i+6] >= parseInt(level, 16);
      }
      return false;
    }
    // On UHD, Chrome can decline a forced hardware encoder even when its
    // default H.264 path can produce the required SPS, as in the Xianlin film.
    const modes = height === 2160 ? ['prefer-hardware', 'no-preference'] : ['prefer-hardware'];
    const configs = candidates.flatMap(codec => modes.map(hardwareAcceleration => ({
      codec, width, height, framerate:fps,
      bitrate:height === 2160 && fps === 60 && hardwareAcceleration === 'no-preference'
        ? 80000000 : plan.bitrate,
      latencyMode:'realtime', hardwareAcceleration, avc:{format:'annexb'}
    })));
    for (const candidate of configs) {
      let encoder, key=false, failure=null;
      try {
        if (!(await VideoEncoder.isConfigSupported(candidate)).supported) continue;
        encoder=new VideoEncoder({output:c=>{key=usableKeyframe(c);},error:e=>{failure=e;}});
        encoder.configure(candidate);
        const probe=new VideoFrame(canvas,{timestamp:0,duration:Math.round(1e6/fps)});
        try {encoder.encode(probe,{keyFrame:true});} finally {probe.close();}
        await encoder.flush();
        if (key&&!failure) {encoderConfig=candidate;break;}
      } catch (_) {} finally {if (encoder && encoder.state!=='closed') encoder.close();}
    }
    if (!encoderConfig) throw Error('No D3D11-capable native H.264 WebCodecs encoder succeeded; use --backend rgba.');
  }
  async function encode(begin,end) {
    const packets=[], hits={};
    let failure=null;
    const encoder=new VideoEncoder({output:chunk=>{
      const bytes=new Uint8Array(chunk.byteLength);
      chunk.copyTo(bytes);
      packets.push({bytes,pts:chunk.timestamp,type:chunk.type});
    },error:e=>{failure=e;}});
    try {
      encoder.configure(encoderConfig);
      for(let i=begin;i<end;i++) {
        const timestamp=Math.round(i*1e6/fps),duration=Math.round((i+1)*1e6/fps)-timestamp;
        const frame=new VideoFrame(draw(i,hits),{timestamp,duration});
        try {encoder.encode(frame,{keyFrame:(i-begin)%(2*fps)===0});}
        finally {frame.close();}
        if (encoder.encodeQueueSize>4) await encoder.flush();
        if (failure) throw failure;
      }
      await encoder.flush();
      if (failure) throw failure;
    } finally {if(encoder.state!=='closed') encoder.close();}
    if (packets.length!==end-begin || packets[0].type!=='key' ||
        packets.some((p,k)=>p.pts!==Math.round((begin+k)*1e6/fps)))
      throw Error('Native H.264 encoder lost or reordered pictures.');
    const blob=new Blob(packets.map(p=>p.bytes));
    const data=await new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>resolve(reader.result.split(',')[1]);
      reader.onerror=reject;reader.readAsDataURL(blob);
    });
    return {hits,data};
  }
  window.film = {render,encode, still(i) {
    const hits = {};
    const data = draw(i,hits).toDataURL('image/jpeg',.96).split(',')[1];
    return {data,hits};
  }};
  return {gpu,scope:scene.scope,coverage,glSize:[gl.drawingBufferWidth,gl.drawingBufferHeight],
      samples:gl.getParameter(gl.SAMPLES),pixelRatio:scene.renderer.getPixelRatio(),
      renderer:scene.renderer.info.render,encoderConfig,
      method:encoderConfig?'WebGL renderPose + WebCodecs H.264 + ffmpeg stream copy':'WebGL renderPose + RGBA + ffmpeg libx264'};
}

