(async()=>{
const r=window.inklet;await r.ready;
const frame=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
const quantile=(values,q)=>[...values].sort((a,b)=>a-b)[Math.floor((values.length-1)*q)];
const measure=async fn=>{const start=performance.now();fn();const submitted=performance.now()-start;await frame();return {submit_ms:submitted,settled_ms:performance.now()-start};};
const records=[];
for(const count of [100,3000,20000])for(const backend of ['svg','canvas','hybrid']){
 r.select([]);r.setBackend(backend);r.setVisible(r.scene.row_ids.slice(0,count));await frame();
 const redraw=[],selection=[];
 for(let n=0;n<7;n++){
   redraw.push(await measure(()=>r.render()));
   selection.push(await measure(()=>r.select([r.scene.row_ids[n%count]])));
 }
 const times=[];let mismatches=0;
 const visible=new Set(r.scene.row_ids.slice(0,count));
 const candidates=r.scene.layers.flatMap((l,layer)=>l.points.map((p,n)=>({id:p[0],x:p[1],y:p[2],radius:l.radius,clip:l.clip,layer,n}))).filter(p=>visible.has(p.id));
 const queries=candidates.slice(0,100).map(p=>[p.x,p.y]);
 for(let n=0;n<100;n++)queries.push([(n*37.17)%r.scene.width,(n*11.31)%r.scene.height]);
 for(const [x,y] of queries){
   let expected=null,best=Infinity;
   for(const p of candidates){const b=p.clip;if(x<b[0]||x>b[0]+b[2]||y<b[1]||y>b[1]+b[3])continue;const d=Math.hypot(x-p.x,y-p.y);if(d<=p.radius&&d<=best){best=d;expected=p;}}
   const start=performance.now(),actual=r.pick(x,y,0);times.push(performance.now()-start);
   if((actual?.id??null)!==(expected?.id??null)||(actual?.layerIndex??null)!==(expected?.layer??null))mismatches++;
 }
 records.push({rows:count,backend,redraw:{submit_median_ms:quantile(redraw.map(v=>v.submit_ms),.5),settled_median_ms:quantile(redraw.map(v=>v.settled_ms),.5)},selection:{submit_median_ms:quantile(selection.map(v=>v.submit_ms),.5),settled_median_ms:quantile(selection.map(v=>v.settled_ms),.5)},pick:{queries:queries.length,p50_ms:quantile(times,.5),p95_ms:quantile(times,.95),mismatches},svg_nodes:r.svg.querySelectorAll('*').length,canvas_backing_bytes:r.backend==='svg'?0:(r.canvas.width*r.canvas.height+r.base.width*r.base.height)*4});
}
r.setVisible(null);r.select(['row-00000','row-00001']);r.setBackend('hybrid');
const oldState=r.state();r.setViewport([10,5,r.scene.width/2,r.scene.height/2]);
const point=r.scene.layers[0].points[8];const screen=new DOMPoint(point[1],point[2]).matrixTransform(r.svg.getScreenCTM());const back=r.point(screen.x,screen.y);
const transform_error_mm=Math.hypot(back.x-point[1],back.y-point[2]);
const invalid={...r.state(),viewport:[0,0,0,1]};const before=JSON.stringify(r.state());let rejected=false;try{r.loadState(invalid);}catch{rejected=true;}
const invalid_load_preserves_state=rejected&&JSON.stringify(r.state())===before;r.loadState(oldState);
const result={schema:'inklet.browser-study/0.1',browser:navigator.userAgent,viewport:[innerWidth,innerHeight],device_pixel_ratio:devicePixelRatio,stage:[r.mapping().width,r.mapping().height],scene_digest:r.scene.scene_digest,method:'Seven warm repeats; submission CPU duration and two requestAnimationFrame callbacks (not isolated GPU time); each row appears in two views except one missing coordinate. All backends use the same Python-outlined frame. Index query timing excludes DOM events/table updates; backing bytes cover the two canvas buffers only, not process memory.',records,transform_error_mm,invalid_load_preserves_state,external_resources:performance.getEntriesByType('resource').map(e=>e.name).filter(n=>/^https?:/.test(n))};
window.browserStudy=result;return JSON.stringify(result);
})()
