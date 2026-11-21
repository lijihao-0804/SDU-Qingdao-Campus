(function () {
  'use strict';

  // Stable priority keeps nearby labels from exchanging places as the camera moves.
  const featured = [
    ['library','图书馆'],['west_gate','西门'],['museum','博物馆'],['lake','樱海湖'],
    ['coastal-red-tower','红顶观景塔'],['song_arena','宋君复体育馆'],['assembly','学生会堂'],
    ['huagang','华岗苑'],['east_gate','东门'],['north_gate','北门'],['south_gate','南门'],
    ['way-970257672','会文北楼'],['waterfront-overlook','观海廊桥'],['zhensheng','振声苑'],
    ['yuxian','育贤广场'],['s2-research-m','工程技术研究院 M区'],['xiyuan','曦园餐厅'],
    ['way-970257670','淦昌苑A座'],['way-868015919','第周苑A座'],['blue_track','蓝色田径场'],
    ['s2-b6','晨园餐厅'],['waterfront-beach','鳌山湾潮滩'],['waterfront-promenade','滨海步道'],
    ['v6-north-courts','北区匹克球场'],['v6-alumni-garden','校友文化林']
  ];

  function inCampus(point, boundary) {
    let inside = false;
    for (let i = 0, j = boundary.length - 1; i < boundary.length; j = i++) {
      const [x1, z1] = boundary[i], [x2, z2] = boundary[j];
      if ((z1 > point.z) !== (z2 > point.z) &&
          point.x < x1 + (point.z - z1) * (x2 - x1) / (z2 - z1)) inside = !inside;
    }
    return inside;
  }

  function install({THREE, root, camera, canvas, stage, locations, choose, goPoint, allowsPlace, boundary = []}) {
    const layer = stage.querySelector('#labels');
    const pin = stage.querySelector('#focusPin') || document.createElement('span');
    pin.id = 'focusPin';
    if (!pin.parentNode) layer.appendChild(pin);
    pin.hidden = true;
    const byKey = new Map(locations.map(place => [place.key, place]));
    const modelKeys = new Set();
    const picks = [];
    const ignored = new Set(['flora','groundcover','waterfrontFurniture','parkingVehicle','sunsetRig','terrainCut']);
    root.updateMatrixWorld(true);
    root.traverse(node => {
      if (!node.isMesh || node.isInstancedMesh) return;
      let key, kind, surface, owner;
      for (let parent = node; parent && parent !== root; parent = parent.parent) {
        if (!parent.visible) return;
        const data = parent.userData;
        if (!kind && data.kind) { kind = data.kind; owner = parent; }
        if (!key) key = [data.owner, data.key, data.parcel, data.site].find(id => byKey.has(id));
        if (!surface && data.surface) surface = data.surface;
      }
      if (!kind || ignored.has(kind)) return;
      // The original lake node has its real name but no catalogue key.
      if (!key && kind === 'water' && owner.name === '樱海湖' && byKey.has('lake')) key = 'lake';
      if (key) modelKeys.add(key);
      if (!node.geometry.boundingBox) node.geometry.computeBoundingBox();
      if (!node.geometry.boundingBox || node.geometry.boundingBox.isEmpty()) return;
      const box = node.geometry.boundingBox.clone().applyMatrix4(node.matrixWorld);
      picks.push({node, owner, key, kind, surface, box});
    });

    const raycaster = new THREE.Raycaster();
    const cursor = new THREE.Vector2(), intersection = new THREE.Vector3();
    function pick(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      cursor.set((clientX - rect.left) / rect.width * 2 - 1, 1 - (clientY - rect.top) / rect.height * 2);
      camera.updateMatrixWorld();
      raycaster.setFromCamera(cursor, camera);
      const ray = raycaster.ray, candidates = [];
      for (const item of picks) {
        if (!item.owner.visible || !item.node.visible || !ray.intersectBox(item.box, intersection)) continue;
        const distance = item.box.containsPoint(ray.origin) ? 0 : ray.origin.distanceTo(intersection);
        candidates.push({item, distance});
      }
      candidates.sort((a, b) => a.distance - b.distance);
      let nearest = null, best = Infinity;
      const hits = [];
      for (const {item, distance} of candidates) {
        if (distance > best + 0.012) break;
        hits.length = 0;
        item.node.raycast(raycaster, hits);
        for (const hit of hits) {
          // Coplanar markings / signage belong to their named surface.
          if (hit.distance < best - 0.012 || (Math.abs(hit.distance - best) <= 0.012 && item.key && !nearest?.item.key)) {
            best = hit.distance;
            nearest = {item, point: hit.point};
          }
        }
      }
      if (!nearest) return;
      const {item, point} = nearest;
      if (item.key) {
        const place = byKey.get(item.key);
        // The promenade is a single mesh along the shore. Keep a distant tap at its actual spot.
        if (item.surface === 'walk' && Math.hypot(point.x-place.x, point.z-place.z) > 150) goPoint(point.clone());
        else choose(item.key);
        return;
      }
      if (item.kind === 'surfWater' || (item.kind === 'waterfrontShore' && item.surface === 'sand')) {
        const key = item.kind === 'surfWater' ? 'spring_surf' : 'waterfront-beach';
        const place = byKey.get(key);
        if (place && Math.hypot(point.x-place.x, point.z-place.z) < 150) {
          choose(key); return;
        }
      }
      const coastalSite = item.kind === 'waterfront' || item.kind === 'surfWater' ||
        (item.kind === 'waterfrontShore' && ['land','sand','wall'].includes(item.surface));
      // Distant sea and satellite relief can be visible through large parts of the viewport.
      if (coastalSite || (item.kind !== 'sea' && inCampus(point, boundary))) goPoint(point.clone());
    }

    const fingers = new Set();
    let press = null;
    canvas.addEventListener('pointerdown', event => {
      fingers.add(event.pointerId);
      const primary = event.isPrimary !== false && event.button === 0 && fingers.size === 1;
      press = primary && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey ?
        {id:event.pointerId, x:event.clientX, y:event.clientY, t:performance.now(), slop:event.pointerType === 'touch' ? 9 : 5} : null;
    }, true);
    function moved(event) {
      if (press?.id === event.pointerId && Math.hypot(event.clientX - press.x, event.clientY - press.y) > press.slop) press = null;
    }
    canvas.addEventListener('pointermove', moved, true);
    function cancel(event) {
      fingers.delete(event.pointerId);
      if (press?.id === event.pointerId) press = null;
    }
    canvas.addEventListener('pointercancel', cancel, true);
    canvas.addEventListener('lostpointercapture', cancel, true);
    canvas.addEventListener('pointerleave', event => {
      if (!canvas.hasPointerCapture(event.pointerId)) cancel(event);
    }, true);
    canvas.addEventListener('pointerup', event => {
      moved(event);
      const shortTap = press?.id === event.pointerId && fingers.size === 1 && event.button === 0 &&
        performance.now() - press.t < 750;
      cancel(event);
      if (shortTap) pick(event.clientX, event.clientY);
    }, true);

    const names = new Map(featured);
    const labels = [];
    const anchors = new Map();
    function anchorFor(place) {
      const {x, y, z, h} = place;
      if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z)) {
        return new THREE.Vector3(x, y + Math.max(3, h || 0) + 2, z);
      }
      const target = place.viewpoint?.target || place.views?.facade?.target;
      return target ? new THREE.Vector3(...target) : null;
    }
    for (const place of locations) {
      const anchor = anchorFor(place);
      if (anchor) anchors.set(place.key, anchor);
    }
    // Use the named locations which own real geometry, plus the signed coastal and lake viewpoints.
    const order = [...new Set([...names.keys(), ...modelKeys])];
    const measure = document.createElement('canvas').getContext('2d');
    if (measure) measure.font = '12px "Microsoft YaHei UI","Microsoft YaHei",sans-serif';
    const widthOf = text => Math.ceil(measure ? measure.measureText(text).width : text.length * 12) + 22;
    for (const key of order) {
      const place = byKey.get(key), anchor = anchors.get(key);
      if (!place || !anchor) continue;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'map-label';
      button.dataset.place = key;
      button.textContent = names.get(key) || place.name;
      button.setAttribute('aria-label', '前往' + place.name);
      button.title = '前往' + place.name;
      button.hidden = true;
      button.addEventListener('click', () => choose(key));
      layer.appendChild(button);
      labels.push({key, anchor, button, width:widthOf(button.textContent)});
    }

    const projected = new THREE.Vector3(), currentMatrix = new THREE.Matrix4(), lastMatrix = new THREE.Matrix4();
    const controls = Array.from(stage.querySelectorAll('#buttons,#mobile,#credits,#notes,#showLabels,#north,#mapTools,#navTools'));
    let freePoint = null, labelsOn = true, dirty = true, lastSelection, lastMode, lastWidth, lastHeight;
    function setPoint(point) { freePoint = point ? point.clone() : null; dirty = true; }
    function setLabels(enabled) { labelsOn = Boolean(enabled); dirty = true; }
    function project(anchor, width, height) {
      if (!anchor) return null;
      projected.copy(anchor).project(camera);
      if (!(projected.z >= -1 && projected.z <= 1 && Math.abs(projected.x) <= 1 && Math.abs(projected.y) <= 1)) return null;
      return {x: (1 + projected.x) * width / 2, y: (1 - projected.y) * height / 2};
    }
    function position(element, point) {
      element.style.left = Math.round(point.x) + 'px';
      element.style.top = Math.round(point.y) + 'px';
      element.hidden = false;
    }
    function update(selected, mode) {
      const width = stage.clientWidth, height = stage.clientHeight;
      if (!width || !height) return;
      camera.updateMatrixWorld();
      currentMatrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
      if (!dirty && selected === lastSelection && mode === lastMode && width === lastWidth && height === lastHeight && currentMatrix.equals(lastMatrix)) return;
      lastSelection = selected; lastMode = mode; lastWidth = width; lastHeight = height; lastMatrix.copy(currentMatrix); dirty = false;
      const stageBox = stage.getBoundingClientRect(), occupied = [];
      for (const control of controls) {
        const box = control.getBoundingClientRect();
        if (box.width && box.height) occupied.push([box.left-stageBox.left, box.top-stageBox.top, box.right-stageBox.left, box.bottom-stageBox.top]);
      }
      const place = byKey.get(selected);
      const namedView = place && !modelKeys.has(selected) && place.viewpoint?.target;
      const anchor = freePoint || (namedView ? new THREE.Vector3(...namedView) : anchors.get(selected));
      let point = project(anchor,width,height);
      if (!point && place?.views) {
        // At a doorway the roof anchor may leave the frame. Use the nearest authored camera's target.
        let near = Infinity, target = null;
        for (const pose of Object.values(place.views)) {
          if (!pose.eye || !pose.target) continue;
          const d = camera.position.distanceToSquared(intersection.fromArray(pose.eye));
          if (d < near) { near = d; target = pose.target; }
        }
        if (target) point = project(intersection.fromArray(target),width,height);
      }
      // The centre of a detail camera is often the lettering itself. Its place name is already in the notes.
      const hideMapLabels = place?.views?.[mode]?.hideMapLabels;
      if (point && !hideMapLabels) {
        const title = freePoint ? '所选位置' : names.get(selected) || place.name;
        if (pin.textContent !== title) pin.textContent = title;
        if (freePoint) delete pin.dataset.place; else pin.dataset.place = selected;
        position(pin,point);
        const half = widthOf(title) / 2;
        occupied.push([point.x-half,point.y-34,point.x+half,point.y+8]);
      } else {
        pin.hidden = true;
        delete pin.dataset.place;
      }
      let count = 0;
      const limit = width < 620 ? 6 : 14;
      for (const entry of labels) {
        const button = entry.button;
        if (!allowsPlace(byKey.get(entry.key)) || !labelsOn || hideMapLabels || entry.key === selected || count >= limit ||
            (camera.position.y < 75 && camera.position.distanceToSquared(entry.anchor) > 650 * 650)) {
          button.hidden = true; continue;
        }
        const p = project(entry.anchor,width,height);
        if (!p) { button.hidden = true; continue; }
        const left = p.x - entry.width/2, right = p.x + entry.width/2, top = p.y - 32, bottom = p.y + 5;
        if (left < 5 || right > width-5 || top < 5 || bottom > height-5 ||
            occupied.some(b => left < b[2]+5 && right > b[0]-5 && top < b[3]+4 && bottom > b[1]-4)) {
          button.hidden = true; continue;
        }
        position(button,p); occupied.push([left,top,right,bottom]); count++;
      }
    }
    return {update, setLabels, setPoint, invalidate(){dirty=true;}};
  }
  window.QDNavigation = {install};
})();

