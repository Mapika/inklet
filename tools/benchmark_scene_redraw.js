// Run with agent-browser eval --stdin. Frame callbacks are not GPU timers.
(async()=>{
 const r=inkletScene;await r.ready;
 const frame=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 const records=[];
 for(const backend of ['webgl2','canvas']){
  r.setBackend(backend);r.setViewport(r.original);await frame();
  for(const workload of ['zoom','pan','unchanged']){
   const viewport=k=>{const b=r.original,s=workload==='zoom'&&(k%2===0)?1.15:1;return [b[0]+(workload==='pan'?k%2*b[2]*.02:0),b[1],b[2]/s,b[3]/s];};
   for(let k=0;k<4;k++){r.setViewport(viewport(k));await frame();}
   const before=r.report(),samples=[];
   for(let k=0;k<9;k++){
    const start=performance.now();r.setViewport(viewport(k));const submitted=performance.now();
    await frame();samples.push({submission_ms:submitted-start,two_frames_ms:performance.now()-start});
   }
   records.push({backend,workload,before,after:r.report(),samples});
  }
 }
 r.setBackend('auto');r.setViewport(r.original);await frame();
 return JSON.stringify({userAgent:navigator.userAgent,dpr:devicePixelRatio,viewport:[innerWidth,innerHeight],stage:host.getBoundingClientRect().toJSON(),records});
})()
