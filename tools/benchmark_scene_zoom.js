// Growth and deep-zoom workload; frame callbacks are not GPU timers.
(async()=>{
 const r=inkletScene;await r.ready;
 const frame=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 const records=[];
 for(const backend of ['webgl2','canvas']){
  r.setBackend(backend);r.setViewport(r.original);await frame();
  const before=r.report(),samples=[];
  for(let repeat=0;repeat<3;repeat++)for(const scale of [1,1.25,1.6,2,3,4,6,8,4,2,1]){
   const b=r.original,t=performance.now();r.setViewport([scale===1?b[0]:b[0]+b[2]*(.22-.5/scale),scale===1?b[1]:b[1]+b[3]*(.25-.5/scale),b[2]/scale,b[3]/scale]);
   const submitted=performance.now();await frame();samples.push({repeat,scale,submission_ms:submitted-t,two_frames_ms:performance.now()-t,report:r.report()});
  }
  records.push({backend,before,samples});
 }
 r.setBackend('auto');r.setViewport(r.original);await frame();
 return JSON.stringify({userAgent:navigator.userAgent,dpr:devicePixelRatio,viewport:[innerWidth,innerHeight],stage:host.getBoundingClientRect().toJSON(),records});
})()
