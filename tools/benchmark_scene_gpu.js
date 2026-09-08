// Optional GPU draw timing via EXT_disjoint_timer_query_webgl2.
// Measures instanced draws, excluding index uploads, clearing and compositing.
(async()=>{
 const r=inkletScene;await r.ready;r.setBackend('webgl2');
 const layer=r.layers[0],gl=layer.gpu?.gl,ext=gl?.getExtension('EXT_disjoint_timer_query_webgl2');
 if(!ext)return JSON.stringify({available:false,report:r.report()});
 const frame=()=>new Promise(resolve=>requestAnimationFrame(resolve));
 const move=p=>{const b=r.original,s=8;r.setViewport([b[0]+b[2]*(p-.5/s),b[1]+b[3]*(.5-.5/s),b[2]/s,b[3]/s]);};
 move(.3);await frame();move(.4);await frame();
 const original=gl.drawArraysInstanced,queries=[],samples=[];
 gl.getParameter(ext.GPU_DISJOINT_EXT);
 gl.drawArraysInstanced=function(...args){const q=gl.createQuery();gl.beginQuery(ext.TIME_ELAPSED_EXT,q);original.apply(gl,args);gl.endQuery(ext.TIME_ELAPSED_EXT);queries.push({q,count:args[3]});};
 try{
  for(const p of [.5,.6,.7,.3,.4,.5,.6,.7,.3]){
   const start=queries.length;move(p);gl.flush();
   for(let k=start;k<queries.length;k++){
    const item=queries[k],deadline=performance.now()+5000;
    while(!gl.getQueryParameter(item.q,gl.QUERY_RESULT_AVAILABLE)){
     if(gl.isContextLost()||performance.now()>deadline)throw Error('GPU timing unavailable');
     await frame();
    }
    if(gl.getParameter(ext.GPU_DISJOINT_EXT))throw Error('Disjoint GPU timing; discard this study');
    samples.push({position:p,count:item.count,gpu_draw_ms:gl.getQueryParameter(item.q,gl.QUERY_RESULT)/1e6});
   }
  }
  return JSON.stringify({available:true,renderer:layer.gpu.renderer,samples,report:r.report()});
 }finally{gl.drawArraysInstanced=original;for(const {q} of queries)gl.deleteQuery(q);r.setViewport(r.original);}
})()
