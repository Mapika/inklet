(async()=>{
 const r=inkletScene;await r.ready;
 const frame=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 const records=[];
 for(const backend of ['webgl2','canvas']){
  r.setBackend(backend);await frame();
  const startUploads=r.uploadBytes,times=[];
  for(let k=0;k<7;k++){
   const v=r.original,scale=k%2?1:1.15,start=performance.now();
   r.setViewport([v[0],v[1],v[2]/scale,v[3]/scale]);const submitted=performance.now();
   await frame();times.push({submission_ms:submitted-start,two_frames_ms:performance.now()-start});
  }
  records.push({backend,report:r.report(),samples:times,uploads_during_view_changes:r.uploadBytes-startUploads});
 }
 r.setBackend('auto');r.setViewport(r.original);await frame();
 return JSON.stringify({userAgent:navigator.userAgent,dpr:devicePixelRatio,
  viewport:[innerWidth,innerHeight],stage:host.getBoundingClientRect().toJSON(),
  marker_dom_nodes:r.svg.querySelectorAll('[data-source-index]').length,
  buffers_bytes:r.batches.reduce((sum,b)=>sum+b.records.byteLength,0),records});
})()
