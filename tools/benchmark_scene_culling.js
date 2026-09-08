// Compare full-view initialization, the first index query, and later moving windows.
// The two animation-frame callbacks are not an isolated GPU timer.
(async()=>{
 const r=inkletScene;await r.ready;
 const frame=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 const result=[];
 for(const backend of ['webgl2','canvas']){
  r.setViewport(r.original);r.spatialIndexes?.clear();
  const init=performance.now();r.setBackend(backend);const initialization_ms=performance.now()-init;await frame();
  const before=r.report(),samples=[];
  for(let repeat=0;repeat<3;repeat++)for(const position of [.3,.4,.5,.6,.7,.5,.3]){
   const b=r.original,scale=8,t=performance.now();
   r.setViewport([b[0]+b[2]*(position-.5/scale),b[1]+b[3]*(.5-.5/scale),b[2]/scale,b[3]/scale]);
   const submitted=performance.now();await frame();samples.push({repeat,position,submission_ms:submitted-t,two_frames_ms:performance.now()-t,report:r.report()});
  }
  result.push({backend,initialization_ms,before,samples});
 }
 r.setBackend('auto');r.setViewport(r.original);await frame();
 return JSON.stringify({userAgent:navigator.userAgent,dpr:devicePixelRatio,viewport:[innerWidth,innerHeight],stage:host.getBoundingClientRect().toJSON(),result});
})()
