'use strict';
const SVG_NS='http://www.w3.org/2000/svg', XHTML_NS='http://www.w3.org/1999/xhtml';
function surfaceCanvas(){const canvas=document.createElementNS(XHTML_NS,'canvas');canvas.style.cssText='display:block;width:100%;height:100%';return canvas;}
function svgElement(tag,attrs={}){const e=document.createElementNS(SVG_NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;}
const VERTEX=`#version 300 es
precision highp float;
layout(location=0) in vec3 instance;
layout(location=1) in vec4 color;
uniform vec2 extent;
uniform vec2 origin;
uniform vec2 pixels;
uniform vec4 markerBounds;
out vec2 radial;
out vec4 paint;
void main(){
 vec2 corners[6]=vec2[6](vec2(-1,-1),vec2(1,-1),vec2(-1,1),vec2(-1,1),vec2(1,-1),vec2(1,1));
 vec2 corner=corners[gl_VertexID];
 vec2 offset=mix(markerBounds.xy,markerBounds.zw,(corner+1.0)*0.5)*instance.z+corner*extent/pixels;
 radial=offset/instance.z;
 vec2 p=(instance.xy-origin+offset)/extent;
 gl_Position=vec4(p.x*2.0-1.0,1.0-p.y*2.0,0,1);
 paint=color;
}`;
const FRAGMENT=`#version 300 es
precision highp float;
in vec2 radial;
in vec4 paint;
uniform float unitRadius;
uniform int vertexCount;
uniform vec2 vertices[16];
uniform bool evenodd;
out vec4 outputColor;
float boundaryDistance(vec2 p){
 if(vertexCount==0)return length(p)-unitRadius;
 float distanceSquared=1e30;int winding=0;
 for(int k=0;k<16;k++){
  if(k>=vertexCount)break;
  vec2 a=vertices[k],b=vertices[(k+1)%vertexCount],edge=b-a,q=p-a;
  vec2 nearest=q-edge*clamp(dot(q,edge)/dot(edge,edge),0.0,1.0);
  distanceSquared=min(distanceSquared,dot(nearest,nearest));
  float side=edge.x*q.y-edge.y*q.x;
  if(a.y<=p.y&&b.y>p.y&&side>0.0)winding++;
  if(a.y>p.y&&b.y<=p.y&&side<0.0)winding--;
 }
 bool inside=evenodd?(abs(winding)%2==1):(winding!=0);
 return sqrt(distanceSquared)*(inside?-1.0:1.0);
}
void main(){
 float d=boundaryDistance(radial);
 float aa=max(fwidth(d)*0.5,0.00001);
 float alpha=paint.a*(1.0-smoothstep(-aa,aa,d));
 outputColor=vec4(paint.rgb*alpha,alpha);
}`;
function makeGPU(canvas,batch,allowSoftware=false){
 const gl=canvas.getContext('webgl2',{alpha:true,premultipliedAlpha:true,antialias:false,preserveDrawingBuffer:true});
 if(!gl)throw Error('WebGL2 unavailable');
 let program,buffer;
 try{
  const info=gl.getExtension('WEBGL_debug_renderer_info'),renderer=info?gl.getParameter(info.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
  if(!allowSoftware&&/swiftshader|llvmpipe|softpipe|software rasterizer|microsoft basic render/i.test(renderer))throw Error('Software WebGL renderer detected');
  const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(s);gl.deleteShader(s);throw Error(message);}return s;};
  const vertex=shader(gl.VERTEX_SHADER,VERTEX);let fragment;
  try{fragment=shader(gl.FRAGMENT_SHADER,FRAGMENT);program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);}finally{gl.deleteShader(vertex);if(fragment)gl.deleteShader(fragment);}
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
  const data=new Float32Array(batch.count*7),view=batch.records,b=batch.box;
  for(let k=0;k<batch.count;k++){
   const offset=k*36,j=k*7,c=batch.palette[view.getUint32(offset+24,true)];
   data[j]=view.getFloat64(offset,true)-b[0];data[j+1]=view.getFloat64(offset+8,true)-b[1];data[j+2]=view.getFloat64(offset+16,true);
   data[j+3]=c[0]/255;data[j+4]=c[1]/255;data[j+5]=c[2]/255;data[j+6]=c[3];
  }
  if(data.some(v=>!Number.isFinite(v)))throw Error('Geometry exceeds WebGL float range');
  buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
  gl.useProgram(program);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,3,gl.FLOAT,false,28,0);gl.vertexAttribDivisor(0,1);
  gl.enableVertexAttribArray(1);gl.vertexAttribPointer(1,4,gl.FLOAT,false,28,12);gl.vertexAttribDivisor(1,1);
  gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
  const origin=gl.getUniformLocation(program,'origin'),extent=gl.getUniformLocation(program,'extent'),pixels=gl.getUniformLocation(program,'pixels'),radius=gl.getUniformLocation(program,'unitRadius');
  gl.uniform4fv(gl.getUniformLocation(program,'markerBounds'),batch.bounds);
  gl.uniform1i(gl.getUniformLocation(program,'vertexCount'),batch.vertices.length);
  gl.uniform1i(gl.getUniformLocation(program,'evenodd'),batch.fill_rule==='evenodd');
  if(batch.vertices.length)gl.uniform2fv(gl.getUniformLocation(program,'vertices[0]'),batch.vertices.flat());
  if(gl.getError()!==gl.NO_ERROR)throw Error('WebGL buffer allocation failed');
  return {gl,renderer,bytes:data.byteLength,limit:Math.min(4096,gl.getParameter(gl.MAX_RENDERBUFFER_SIZE)),
   draw(window){if(gl.isContextLost())throw Error('WebGL context lost');gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.useProgram(program);gl.uniform2f(origin,window[0]-b[0],window[1]-b[1]);gl.uniform2f(extent,window[2],window[3]);gl.uniform2f(pixels,canvas.width,canvas.height);gl.uniform1f(radius,batch.radius);gl.drawArraysInstanced(gl.TRIANGLES,0,6,batch.count);if(gl.getError()!==gl.NO_ERROR)throw Error('WebGL draw failed');},
   dispose(){gl.deleteBuffer(buffer);gl.deleteProgram(program);gl.getExtension('WEBGL_lose_context')?.loseContext();}
  };
 }catch(error){if(buffer)gl.deleteBuffer(buffer);if(program)gl.deleteProgram(program);gl.getExtension('WEBGL_lose_context')?.loseContext();throw error;}
}
function intersectBox(a,b){
 const x=Math.max(a[0],b[0]),y=Math.max(a[1],b[1]),right=Math.min(a[0]+a[2],b[0]+b[2]),bottom=Math.min(a[1]+a[3],b[1]+b[3]);
 return right>x&&bottom>y?[x,y,right-x,bottom-y]:null;
}
function visibleBox(matrix,viewport,bounds){
 const inverse=matrix.inverse();
 const points=[[viewport.left,viewport.top],[viewport.right,viewport.top],[viewport.right,viewport.bottom],[viewport.left,viewport.bottom]];
 const xs=points.map(([x,y])=>inverse.a*x+inverse.c*y+inverse.e),ys=points.map(([x,y])=>inverse.b*x+inverse.d*y+inverse.f);
 if([...xs,...ys].some(n=>!Number.isFinite(n)))return null;
 return intersectBox([Math.min(...xs),Math.min(...ys),Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys)],bounds);
}
function surfaceWindow(visible,current,bounds){
 const [x,y,w,h]=visible;
 if(current&&current[0]<=x&&current[1]<=y&&current[0]+current[2]>=x+w&&current[1]+current[3]>=y+h&&current[2]*current[3]<=w*h*4)return current;
 return intersectBox([x-w*.2,y-h*.2,w*1.4,h*1.4],bounds);
}
function surfaceSize(width,height,canvas,limit){
 // Reuse sufficient backing resolution until a view needs less than one
 // quarter of its pixels. Small zoom changes must not reallocate every layer.
 if(canvas.width>=width&&canvas.height>=height&&width*height>canvas.width*canvas.height/4)return [canvas.width,canvas.height];
 const w=Math.min(limit,Math.ceil(width/128)*128),h=Math.min(limit,Math.ceil(height/128)*128);
 return w*h<=4000000?[w,h]:[width,height];
}
let viewerCounter=0;
class CompiledSceneViewer{
 constructor(host,scene){
  if(scene.schema!=='inklet.compiled-viewer/1')throw Error('Unsupported compiled scene');
  this.host=host;this.scene=scene;this.backend=scene.backend;this.layers=[];this.uploadBytes=0;this.drawCalls=0;this.surfacePaints=0;this.surfaceResizes=0;this.reusedSurfaces=0;this.disposed=false;this.frame=0;
  const buffers=scene.buffers.map(data=>Uint8Array.from(atob(data),c=>c.charCodeAt(0)));
  this.batches=scene.batches.map(b=>{const bytes=buffers[b.buffer];if(!bytes||bytes.byteLength!==b.count*36)throw Error('Invalid marker buffer');return {...b,records:new DataView(bytes.buffer)};});
  this.svg=new DOMParser().parseFromString(scene.frame,'image/svg+xml').documentElement;
  if(this.svg.localName!=='svg')throw Error('Invalid SVG frame');
  const prefix='inklet-viewer-'+(++viewerCounter)+'-',ids=new Map([...this.svg.querySelectorAll('[id]')].map(e=>[e.id,prefix+e.id]));
  for(const e of this.svg.querySelectorAll('*'))for(const attr of [...e.attributes]){
   let value=attr.value;
   if(attr.name==='id')value=ids.get(value);
   else if(attr.localName==='href'&&value.startsWith('#'))value='#'+(ids.get(value.slice(1))||value.slice(1));
   else value=value.replace(/url\(#([^)]*)\)/g,(all,id)=>ids.has(id)?'url(#'+ids.get(id)+')':all);
   if(value!==attr.value)e.setAttributeNS(attr.namespaceURI,attr.name,value);
  }
  this.original=['x','y','width','height'].map(k=>this.svg.viewBox.baseVal[k]);
  this.viewport=[...this.original];this.host.style.aspectRatio=this.original[2]+'/'+this.original[3];
  this.svg.removeAttribute('width');this.svg.removeAttribute('height');this.svg.style.cssText='display:block;width:100%;height:100%';host.append(this.svg);
  this.resizeObserver=new ResizeObserver(()=>this.schedule());this.resizeObserver.observe(host);
  this.resize=()=>this.schedule();window.addEventListener('resize',this.resize);
  this.setBackend(this.backend);
  this.ready=Promise.resolve(this);
 }
 vector(batch,target){
  const fragment=document.createDocumentFragment(),view=batch.records;
  for(let k=0;k<batch.count;k++){
   const o=k*36,index=view.getUint32(o+24,true),fill=batch.fills[index];
   const x=view.getFloat64(o,true),y=view.getFloat64(o+8,true),size=view.getFloat64(o+16,true);
   const attrs=batch.vertices.length?{points:batch.vertices.map(p=>`${x+p[0]*size},${y+p[1]*size}`).join(' '),'fill-rule':batch.fill_rule}:{cx:x,cy:y,r:size*batch.radius};
   attrs['data-source-index']=view.getBigUint64(o+28,true).toString();
   if(fill!==null)attrs.fill=fill;
   fragment.append(svgElement(batch.vertices.length?'polygon':'circle',attrs));
  }target.append(fragment);
 }
 canvasLayer(layer,reason){
  if(layer.gpu){layer.canvas.removeEventListener('webglcontextlost',layer.lost);layer.gpu.dispose();layer.gpu=null;}
  layer.canvas?.remove();const canvas=surfaceCanvas();layer.foreign.append(canvas);layer.canvas=canvas;
  layer.context=canvas.getContext('2d');if(!layer.context)throw Error('Canvas 2D unavailable');layer.reason=reason;layer.actual='canvas';layer.painted=false;
 }
 setBackend(name){
  if(!['auto','webgl2','canvas','svg'].includes(name))throw Error('Unsupported backend');
  if(this.disposed)throw Error('Viewer disposed');
  for(const layer of this.layers){if(layer.gpu){layer.canvas.removeEventListener('webglcontextlost',layer.lost);layer.gpu.dispose();}}
  this.layers=[];this.backend=name;let contexts=0;
  for(const [index,batch] of this.batches.entries()){
   const target=this.svg.querySelector(`[data-inklet-batch="${index}"]`);target.replaceChildren();
   const layer={batch,target,window:batch.box,actual:'svg',reason:null};this.layers.push(layer);
   if(name==='svg'){this.vector(batch,target);continue;}
   const [x,y,width,height]=batch.box;
   // Keep the HTML surface origin integral. Chromium rounds fractional
   // foreignObject layout origins before SVG transforms are applied.
   // Enlarging its CSS coordinate frame also bounds layout quantization.
   const carrier=layer.carrier=svgElement('g',{transform:`translate(${x} ${y}) scale(0.015625)`});
   layer.foreign=svgElement('foreignObject',{x:0,y:0,width:width*64,height:height*64});carrier.append(layer.foreign);target.append(carrier);
   if(['auto','webgl2'].includes(name)&&contexts<8){
    layer.canvas=surfaceCanvas();layer.foreign.append(layer.canvas);
    try{layer.gpu=makeGPU(layer.canvas,batch,name==='webgl2');this.uploadBytes+=layer.gpu.bytes;layer.actual='webgl2';contexts++;
     layer.lost=event=>{event.preventDefault();if(this.disposed)return;this.canvasLayer(layer,'WebGL context lost');this.schedule();};
     layer.canvas.addEventListener('webglcontextlost',layer.lost);
    }catch(error){this.canvasLayer(layer,error.message);}
   }else this.canvasLayer(layer,['auto','webgl2'].includes(name)?'WebGL context budget reached':null);
  }
  this.render();
 }
 schedule(){if(this.disposed||this.frame)return;this.frame=requestAnimationFrame(()=>{this.frame=0;if(!this.disposed)this.render();});}
 render(){
  if(this.disposed)return;
  // Read all SVG transforms before changing canvas dimensions: writes must
  // not force repeated layout while measuring subsequent layers.
  const viewport=this.svg.getBoundingClientRect();
  const placements=this.layers.filter(layer=>layer.actual!=='svg').map(layer=>({layer,m:layer.target.getScreenCTM()}));
  for(const {layer,m} of placements){
   if(!m)continue;
   const visible=visibleBox(m,viewport,layer.batch.box);layer.visible=!!visible;
   if(!visible){layer.reduced=false;continue;}
   const b=surfaceWindow(visible,layer.window,layer.batch.box);
   const moved=b.some((v,k)=>v!==layer.window[k]);
   if(moved){layer.window=b;layer.carrier.setAttribute('transform',`translate(${b[0]} ${b[1]}) scale(0.015625)`);layer.foreign.setAttribute('width',b[2]*64);layer.foreign.setAttribute('height',b[3]*64);}
   const scale=Math.max(Math.hypot(m.a,m.b),Math.hypot(m.c,m.d))*(devicePixelRatio||1);
   const limit=layer.gpu?.limit||4096;
   const reduction=Math.min(1,limit/(b[2]*scale),limit/(b[3]*scale),Math.sqrt(4000000/(b[2]*b[3]*scale*scale)));
   const neededWidth=Math.max(1,Math.floor(b[2]*scale*reduction)),neededHeight=Math.max(1,Math.floor(b[3]*scale*reduction));
   const [width,height]=surfaceSize(neededWidth,neededHeight,layer.canvas,limit);
   layer.reduced=reduction<.999999;
   if(layer.gpu?.gl.isContextLost())this.canvasLayer(layer,'WebGL context lost');
   const resized=layer.canvas.width!==width||layer.canvas.height!==height;
   if(resized){if(layer.canvas.width!==width)layer.canvas.width=width;if(layer.canvas.height!==height)layer.canvas.height=height;this.surfaceResizes++;}
   if(layer.painted&&!resized&&!moved){this.reusedSurfaces++;continue;}
   if(layer.gpu){try{layer.gpu.draw(b);layer.painted=true;this.surfacePaints++;this.drawCalls++;continue;}catch(error){this.canvasLayer(layer,error.message);layer.canvas.width=width;layer.canvas.height=height;}}
   const ctx=layer.context;ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,width,height);ctx.setTransform(width/b[2],0,0,height/b[3],-b[0]*width/b[2],-b[1]*height/b[3]);
   const data=layer.batch.records;
   for(let k=0;k<layer.batch.count;k++){const o=k*36,c=layer.batch.palette[data.getUint32(o+24,true)];if(!c[3])continue;ctx.fillStyle=`rgb(${c[0]},${c[1]},${c[2]})`;ctx.globalAlpha=c[3];ctx.beginPath();const x=data.getFloat64(o,true),y=data.getFloat64(o+8,true),size=data.getFloat64(o+16,true),vertices=layer.batch.vertices;
    if(vertices.length){for(const [j,p] of vertices.entries())ctx[j?'lineTo':'moveTo'](x+p[0]*size,y+p[1]*size);ctx.closePath();}
    else ctx.arc(x,y,size*layer.batch.radius,0,Math.PI*2);
    ctx.fill(layer.batch.fill_rule);}
   layer.painted=true;this.surfacePaints++;
  }
  this.host.dispatchEvent(new CustomEvent('inklet-render',{detail:this.report()}));
 }
 report(){return {backend:this.backend,layers:this.layers.map(l=>({backend:l.actual,count:l.batch.count,reason:l.reason,renderer:l.gpu?.renderer||null,reducedResolution:!!l.reduced,surfacePixels:l.canvas?l.canvas.width*l.canvas.height:0,visible:l.actual==='svg'?null:!!l.visible,displayBox:l.actual==='svg'?null:[...l.window]})),native:this.scene.native,uploadBytes:this.uploadBytes,drawCalls:this.drawCalls,surfacePaints:this.surfacePaints,surfaceResizes:this.surfaceResizes,reusedSurfaces:this.reusedSurfaces};}
 setViewport(v){
  if(!Array.isArray(v)||v.length!==4||v.some(n=>typeof n!=='number'||!Number.isFinite(n))||v[2]<=0||v[3]<=0)throw Error('Invalid viewport');
  const b=this.original;
  if(v[2]<b[2]/100||v[2]>b[2]*100||v[3]<b[3]/100||v[3]>b[3]*100||Math.abs(v[0]-b[0])>b[2]*100||Math.abs(v[1]-b[1])>b[3]*100)throw Error('Viewport outside supported range');
  this.viewport=[...v];this.svg.setAttribute('viewBox',v.join(' '));this.render();
 }
 zoom(factor){const [x,y,w,h]=this.viewport;this.setViewport([x+w*(1-1/factor)/2,y+h*(1-1/factor)/2,w/factor,h/factor]);}
 exportSVG(){const svg=new DOMParser().parseFromString(this.scene.frame,'image/svg+xml').documentElement;svg.setAttribute('viewBox',this.viewport.join(' '));for(const [index,batch] of this.batches.entries())this.vector(batch,svg.querySelector(`[data-inklet-batch="${index}"]`));return new XMLSerializer().serializeToString(svg);}
 dispose(){if(this.disposed)return;this.disposed=true;this.resizeObserver.disconnect();window.removeEventListener('resize',this.resize);cancelAnimationFrame(this.frame);for(const layer of this.layers){if(layer.gpu){layer.canvas.removeEventListener('webglcontextlost',layer.lost);layer.gpu.dispose();}if(layer.canvas)layer.canvas.width=layer.canvas.height=0;}this.layers=[];this.batches=[];this.svg.remove();}
}
const host=document.getElementById('stage'),error=document.getElementById('error');
function attempt(action){try{error.textContent='';action();}catch(e){error.textContent=e.message;}}
host.addEventListener('inklet-render',event=>{const r=event.detail,counts={};for(const l of r.layers)counts[l.backend]=(counts[l.backend]||0)+1;document.getElementById('status').textContent=(Object.entries(counts).map(([k,v])=>`${v} ${k} layers`).join(' · ')||'Native SVG artwork')+` · ${r.native.length} native SVG marker layers`+(r.layers.some(l=>l.reason)?' · '+[...new Set(r.layers.map(l=>l.reason).filter(Boolean))].join('; '):'')+(r.layers.some(l=>l.reducedResolution)?' · display resolution limited':'');});
const scene=JSON.parse(document.getElementById('scene').textContent);window.inkletScene=new CompiledSceneViewer(host,scene);
document.getElementById('backend').value=scene.backend;
document.getElementById('backend').onchange=e=>attempt(()=>inkletScene.setBackend(e.target.value));
document.getElementById('zoom-in').onclick=()=>attempt(()=>inkletScene.zoom(1.25));
document.getElementById('zoom-out').onclick=()=>attempt(()=>inkletScene.zoom(.8));
document.getElementById('fit').onclick=()=>attempt(()=>inkletScene.setViewport(inkletScene.original));
document.getElementById('download').onclick=()=>attempt(()=>{const url=URL.createObjectURL(new Blob([inkletScene.exportSVG()],{type:'image/svg+xml'})),a=document.createElement('a');a.href=url;a.download='inklet-figure.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
let drag=null;
host.addEventListener('pointerdown',e=>{if(e.button!==0)return;host.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY,viewport:[...inkletScene.viewport],inverse:inkletScene.svg.getScreenCTM().inverse()};});
host.addEventListener('pointermove',e=>{if(!drag)return;const m=drag.inverse,dx=e.clientX-drag.x,dy=e.clientY-drag.y,v=drag.viewport;attempt(()=>inkletScene.setViewport([v[0]-m.a*dx-m.c*dy,v[1]-m.b*dx-m.d*dy,v[2],v[3]]));});
for(const name of ['pointerup','pointercancel','lostpointercapture'])host.addEventListener(name,()=>{drag=null;});
