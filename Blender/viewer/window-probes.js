// Local scene radiance feeds the same PBR BRDF as the rest of the campus.
window.QDWindowProbes = {
 async install(root, THREE, renderer, readTexture, records) {
  if (!records.length) return {probes:0, meshes:0, materials:0};
  const generator = new THREE.PMREMGenerator(renderer);
  const sites = [];
  try {
   for (const record of records) {
    const targets={};
    for(const [mode,data] of [['full',record.data],['core',record.coreData]]){
     const source=await readTexture(data);
     try{
      targets[mode]=generator.fromEquirectangular(source);
      targets[mode].texture.name='校园窗景 · '+record.name+' · '+mode;
     }finally{source.dispose();}
    }
    sites.push({record,targets,materials:new Map()});
   }
  } finally { generator.dispose(); }
  const plainGlass = new Set(['glass','#405766','#3c6072','#465966','#516671','#687b83']);
  const isGlass = m => m && ((m.userData.rawArchFinish || m.userData.archFinish || (plainGlass.has(m.name.toLowerCase()) ? 'glass' : '')) === 'glass');
  const bounds = new THREE.Box3(), centre = new THREE.Vector3();
  let meshes = 0;
  root.updateMatrixWorld(true);
  for (const owner of root.children) {
   const parts = [];
   owner.traverse(o => {
    if (o.isMesh && (Array.isArray(o.material) ? o.material.some(isGlass) : isGlass(o.material))) parts.push(o);
   });
   if (!parts.length) continue;
   bounds.setFromObject(owner).getCenter(centre);
   let nearest = null, distance = Infinity;
   for (const site of sites) {
    const [x,,z] = site.record.centre;
    const d = (x-centre.x)**2 + (z-centre.z)**2;
    if (d < distance) { distance = d; nearest = site; }
   }
   const local = original => {
    if (!isGlass(original)) return original;
    if (!nearest.materials.has(original)) {
     const material = original.clone();
     material.onBeforeCompile = original.onBeforeCompile;
     material.customProgramCacheKey = original.customProgramCacheKey;
     material.envMap = nearest.targets.full.texture;
     material.userData.windowProbe = nearest.record.name;
     nearest.materials.set(original, material);
    }
    return nearest.materials.get(original);
   };
   for (const mesh of parts) {
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(local) : local(mesh.material);
    meshes++;
   }
  }
  function setScope(mode){
   for(const site of sites)for(const m of site.materials.values())m.envMap=site.targets[mode].texture;
  }
  return {setScope,probes:sites.length, meshes, materials:sites.reduce((n,s)=>n+s.materials.size,0)};
 }
};
