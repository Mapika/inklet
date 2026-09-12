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
