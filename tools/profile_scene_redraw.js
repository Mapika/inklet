// Diagnostic instrumentation for a compiled viewer; adds timing overhead.
// Run against the saved before figure with agent-browser eval --stdin.
(async()=>{
 const r=inkletScene; r.setBackend('webgl2');
 const timings={},originals=[];
 function wrap(object,key){const original=object[key];originals.push(()=>object[key]=original);object[key]=function(...args){const start=performance.now();try{return original.apply(this,args);}finally{(timings[key]??=[]).push(performance.now()-start);}};}
 for(const layer of r.layers){for(const name of ['getError','isContextLost','viewport','clear','drawArraysInstanced','uniform2f'])wrap(layer.gpu.gl,name);wrap(layer.foreign,'getScreenCTM');}
 for(const key of ['width','height']){const proto=HTMLCanvasElement.prototype,descriptor=Object.getOwnPropertyDescriptor(proto,key);Object.defineProperty(proto,key,{...descriptor,set(value){const start=performance.now();try{return descriptor.set.call(this,value);}finally{(timings[key]??=[]).push(performance.now()-start);}}});originals.push(()=>Object.defineProperty(proto,key,descriptor));}
 const samples=[];
 for(let k=0;k<7;k++){const b=r.original,s=k%2?1:1.15,t=performance.now();r.setViewport([b[0],b[1],b[2]/s,b[3]/s]);samples.push(performance.now()-t);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));}
 for(const undo of originals)undo();r.setViewport(r.original);
 return JSON.stringify({renderer:r.report().layers[0].renderer,samples,timings});
})()
