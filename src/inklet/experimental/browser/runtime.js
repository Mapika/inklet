'use strict';
const NS='http://www.w3.org/2000/svg';
function element(tag,attrs={}){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;}
function inside(x,y,b){return x>=b[0]&&x<=b[0]+b[2]&&y>=b[1]&&y<=b[1]+b[3];}
function download(value,name,type){const url=URL.createObjectURL(new Blob([value],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
let rendererId=0;
class ScatterRenderer{
  constructor(host,scene){
    this.host=host;this.scene=scene;this.prefix='inklet-scatter-'+(++rendererId)+'-';this.backend='svg';this.visible=null;this.selected=new Set();
    this.viewport=[0,0,scene.width,scene.height];this.rowSet=new Set(scene.row_ids);this.rowIndex=new Map(scene.row_ids.map((id,n)=>[id,n]));
    this.canvas=document.createElement('canvas');this.canvas.setAttribute('aria-hidden','true');host.append(this.canvas);
    this.svg=new DOMParser().parseFromString(scene.frame,'image/svg+xml').documentElement;
    this.background=this.svg.querySelector('#inklet-background');
    const ids=new Map([...this.svg.querySelectorAll('[id]')].map(e=>[e.id,this.prefix+e.id]));
    for(const e of this.svg.querySelectorAll('*'))for(const attr of [...e.attributes]){
      let value=attr.value;
      if(attr.name==='id')value=ids.get(value);
      else if(attr.localName==='href'&&value.startsWith('#')&&ids.has(value.slice(1)))value='#'+ids.get(value.slice(1));
      else value=value.replace(/url\(#([^)]*)\)/g,(all,id)=>ids.has(id)?'url(#'+ids.get(id)+')':all);
      if(value!==attr.value)e.setAttributeNS(attr.namespaceURI,attr.name,value);
    }
    this.svg.removeAttribute('width');this.svg.removeAttribute('height');this.svg.setAttribute('aria-hidden','true');host.append(this.svg);
    this.markGroup=element('g');this.svg.insertBefore(this.markGroup,this.svg.children[1]);
    this.overlay=element('g');this.svg.append(this.overlay);
    this.frameNodes=[...this.svg.children].filter(n=>n!==this.markGroup&&n!==this.overlay);
    this.base=document.createElement('canvas');this.index=new Map();this.cellSize=4;this.items=[];this.byId=new Map();
    for(const [layerIndex,layer] of scene.layers.entries())for(const p of layer.points){
      const item={id:p[0],x:p[1],y:p[2],layer,layerIndex,order:this.items.length};this.items.push(item);if(!this.byId.has(item.id))this.byId.set(item.id,[]);this.byId.get(item.id).push(item);
      // Off-domain centers can still contribute a clipped edge; retain them.
      const key=Math.floor(item.x/this.cellSize)+','+Math.floor(item.y/this.cellSize);
      if(!this.index.has(key))this.index.set(key,[]);this.index.get(key).push(item);
    }
    this.frameImage=new Image();
    this.ready=new Promise((resolve,reject)=>{this.frameImage.onload=()=>{this.render();resolve(this);};this.frameImage.onerror=()=>reject(Error('Cannot rasterize the measured frame.'));});
    // Explicit pixel dimensions avoid SVG intrinsic-size ambiguity in drawImage.
    const rasterFrame=scene.frame.replace(/<rect id="inklet-background"[^>]*\/>/,'').replace(/width="[^"]+mm"/,`width="${scene.width*5}"`).replace(/height="[^"]+mm"/,`height="${scene.height*5}"`);
    this.frameImage.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(rasterFrame);
    this.resizeObserver=new ResizeObserver(()=>{if(this.frameImage.complete&&this.frameImage.naturalWidth)this.render();});this.resizeObserver.observe(host);
  }
  mapping(){const r=this.host.getBoundingClientRect(),v=this.viewport,s=Math.min(r.width/v[2],r.height/v[3]);return {width:r.width,height:r.height,scale:s,dx:(r.width-v[2]*s)/2-v[0]*s,dy:(r.height-v[3]*s)/2-v[1]*s};}
  point(clientX,clientY){const m=this.svg.getScreenCTM();if(!m)return null;return new DOMPoint(clientX,clientY).matrixTransform(m.inverse());}
  shown(id){return this.visible===null||this.visible.has(id);}
  setBackend(name){if(!['svg','canvas','hybrid'].includes(name))throw Error('Unsupported backend');this.backend=name;this.render();}
  setVisible(ids){if(ids!==null&&(!Array.isArray(ids)||new Set(ids).size!==ids.length||ids.some(id=>!this.rowSet.has(id))))throw Error('Unknown or duplicate visible ID');this.visible=ids===null?null:new Set(ids);this.render();}
  select(ids){if(!Array.isArray(ids)||new Set(ids).size!==ids.length||ids.some(id=>!this.rowSet.has(id)))throw Error('Unknown or duplicate selected ID');this.selected=new Set(ids);this.renderSelection();}
  setViewport(v){if(!Array.isArray(v)||v.length!==4||v.some(n=>typeof n!=='number'||!Number.isFinite(n))||v[2]<=0||v[3]<=0)throw Error('Invalid viewport');
    if(Math.abs(v[0])>this.scene.width*100||Math.abs(v[1])>this.scene.height*100||v[2]<this.scene.width/100||v[3]<this.scene.height/100||v[2]>this.scene.width*100||v[3]>this.scene.height*100)throw Error('Viewport zoom is outside this preview’s 0.01–100× range');
    this.viewport=[...v];this.render();}
  zoom(factor){const [x,y,w,h]=this.viewport;this.setViewport([x+w*(1-1/factor)/2,y+h*(1-1/factor)/2,w/factor,h/factor]);}
  pick(x,y,tolerance=0){
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(tolerance)||tolerance<0||tolerance>Math.max(this.scene.width,this.scene.height)||!this.scene.layers.some(l=>inside(x,y,l.clip)))return null;
    const reach=Math.max(...this.scene.layers.map(l=>l.radius))+tolerance;
    let best=null,bestDistance=Infinity;
    for(let gx=Math.floor((x-reach)/this.cellSize);gx<=Math.floor((x+reach)/this.cellSize);gx++)for(let gy=Math.floor((y-reach)/this.cellSize);gy<=Math.floor((y+reach)/this.cellSize);gy++){
      for(const item of this.index.get(gx+','+gy)||[]){
        if(!this.shown(item.id)||!inside(x,y,item.layer.clip))continue;
        const distance=Math.hypot(x-item.x,y-item.y);
        if(distance<=item.layer.radius+tolerance&&(distance<bestDistance||(distance===bestDistance&&(!best||item.order>best.order)))){best=item;bestDistance=distance;}
      }
    }return best;
  }
  clips(target,prefix){const defs=element('defs');target.append(defs);return this.scene.layers.map((layer,n)=>{
    const id=this.prefix+prefix+n,clip=element('clipPath',{id});clip.append(element('rect',Object.fromEntries(['x','y','width','height'].map((k,j)=>[k,layer.clip[j]]))));defs.append(clip);
    const g=element('g',{'clip-path':`url(#${id})`});target.append(g);return g;
  });}
  svgMarks(target,selectedOnly=false,prefix='live-clip-'){
    const groups=this.clips(target,prefix);
    for(const item of selectedOnly?[...this.selected].flatMap(id=>this.byId.get(id)||[]):this.items){if(!this.shown(item.id))continue;
      groups[item.layerIndex].append(element('circle',{cx:item.x,cy:item.y,r:item.layer.radius+(selectedOnly?.3:0),fill:selectedOnly?'none':item.layer.color,
        ...(selectedOnly?{stroke:'#bd5636','stroke-width':.3}:{'fill-opacity':.65})}));
    }
  }
  prepareCanvas(canvas){const m=this.mapping(),dpr=devicePixelRatio||1;
    canvas.width=Math.max(1,Math.round(m.width*dpr));canvas.height=Math.max(1,Math.round(m.height*dpr));
    const ctx=canvas.getContext('2d');ctx.setTransform(canvas.width/m.width*m.scale,0,0,canvas.height/m.height*m.scale,canvas.width/m.width*m.dx,canvas.height/m.height*m.dy);return ctx;}
  canvasMarks(ctx,selectedOnly=false){
    for(const layer of this.scene.layers){ctx.save();ctx.beginPath();ctx.rect(...layer.clip);ctx.clip();
      ctx.fillStyle=layer.color;ctx.strokeStyle='#bd5636';ctx.lineWidth=.3;ctx.globalAlpha=selectedOnly?1:.65;
      for(const p of layer.points){if(!this.shown(p[0])||(selectedOnly&&!this.selected.has(p[0])))continue;
        ctx.beginPath();ctx.arc(p[1],p[2],layer.radius+(selectedOnly?.3:0),0,2*Math.PI);if(selectedOnly)ctx.stroke();else ctx.fill();}
      ctx.restore();
    }
  }
  render(){
    if(!this.frameImage.complete||!this.frameImage.naturalWidth)return;
    this.svg.setAttribute('viewBox',this.viewport.join(' '));this.markGroup.replaceChildren();this.overlay.replaceChildren();
    const isSVG=this.backend==='svg',isCanvas=this.backend==='canvas';this.canvas.style.display=isSVG?'none':'block';
    for(const n of this.frameNodes)n.style.display=isCanvas?'none':'';
    const background=this.background;if(background)background.style.display=this.backend==='hybrid'||isCanvas?'none':'';
    if(isSVG)this.svgMarks(this.markGroup);
    else{
      const ctx=this.prepareCanvas(this.base);
      if(isCanvas){ctx.fillStyle='white';ctx.fillRect(...this.viewport);}
      this.canvasMarks(ctx);
      if(isCanvas){
        // Frame background would erase marks: draw a transparent frame image.
        ctx.drawImage(this.frameImage,0,0,this.scene.width,this.scene.height);
      }
    }
    this.renderSelection();
  }
  renderSelection(){
    this.overlay.replaceChildren();
    if(this.backend==='svg'||this.backend==='hybrid')this.svgMarks(this.overlay,true,'selection-clip-');
    if(this.backend!=='svg'){
      this.canvas.width=this.base.width;this.canvas.height=this.base.height;
      const ctx=this.canvas.getContext('2d');ctx.drawImage(this.base,0,0);
      if(this.backend==='canvas'){
        const m=this.mapping();ctx.setTransform(this.canvas.width/m.width*m.scale,0,0,this.canvas.height/m.height*m.scale,this.canvas.width/m.width*m.dx,this.canvas.height/m.height*m.dy);this.canvasMarks(ctx,true);
      }
    }
  }
  state(){return {schema:'inklet.browser-view/0.1',scene_digest:this.scene.scene_digest,selection:{schema:'inklet.selection/0.1',table:this.scene.table,data_digest:this.scene.data_digest,
    selected_ids:[...this.selected].sort(),visible_ids:this.visible===null?null:[...this.visible].sort()},viewport:[...this.viewport]};}
  loadState(value){
    const exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).length===keys.length&&keys.every(k=>Object.hasOwn(o,k));
    if(!exact(value,['schema','scene_digest','selection','viewport'])||value.schema!=='inklet.browser-view/0.1'||value.scene_digest!==this.scene.scene_digest)throw Error('State belongs to a different scene revision');
    const s=value.selection;
    if(!exact(s,['schema','table','data_digest','selected_ids','visible_ids'])||s.schema!=='inklet.selection/0.1'||s.table!==this.scene.table||s.data_digest!==this.scene.data_digest)throw Error('State belongs to different data');
    const valid=ids=>Array.isArray(ids)&&new Set(ids).size===ids.length&&ids.every(id=>typeof id==='string'&&this.rowSet.has(id));
    if(!valid(s.selected_ids)||(s.visible_ids!==null&&!valid(s.visible_ids)))throw Error('Unknown or duplicate row IDs');
    // Validate the viewport before applying any selection/filter changes.
    const old=this.viewport;try{this.setViewport(value.viewport);}catch(error){this.viewport=old;throw error;}
    this.visible=s.visible_ids===null?null:new Set(s.visible_ids);this.selected=new Set(s.selected_ids);this.render();
  }
  exportSVG(){
    const root=new DOMParser().parseFromString(this.scene.frame,'image/svg+xml').documentElement;
    root.setAttribute('viewBox',this.viewport.join(' '));root.setAttribute('width',this.viewport[2]+'mm');root.setAttribute('height',this.viewport[3]+'mm');
    const marks=element('g');root.insertBefore(marks,root.children[1]);this.svgMarks(marks,false,'export-mark-');
    const chosen=element('g');root.append(chosen);this.svgMarks(chosen,true,'export-selection-');
    return new XMLSerializer().serializeToString(root);
  }
}
window.ScatterRenderer=ScatterRenderer;
const scene=JSON.parse(document.getElementById('scene').textContent);
const runtime=new ScatterRenderer(document.getElementById('stage'),scene);window.inklet=runtime;
runtime.backend=/*DEFAULT_BACKEND*/'svg';document.getElementById('backend').value=runtime.backend;
const status=document.getElementById('status'),error=document.getElementById('error'),tableBody=document.getElementById('rows');let page=0;
function message(){const visible=scene.row_ids.filter(id=>runtime.shown(id));const hidden=[...runtime.selected].filter(id=>!runtime.shown(id)).length;
  status.textContent=`${visible.length} rows visible · ${runtime.selected.size} selected${hidden?` (${hidden} hidden)`:''} · ${Math.round(scene.width/runtime.viewport[2]*100)}% page zoom`;
  const start=page*20;if(start>=visible.length&&page)page=0;tableBody.replaceChildren();
  for(const id of visible.slice(page*20,page*20+20)){const n=runtime.rowIndex.get(id),tr=document.createElement('tr');
    const th=document.createElement('th');th.scope='row';th.textContent=id;tr.append(th);
    for(const column of Object.keys(scene.columns).filter(c=>c!=='id')){const td=document.createElement('td');const value=scene.columns[column][n];td.textContent=typeof value==='number'?Number(value.toPrecision(6)).toString():(value??'Missing');tr.append(td);}
    const td=document.createElement('td'),button=document.createElement('button');button.textContent=runtime.selected.has(id)?'Deselect':'Select';button.setAttribute('aria-label',button.textContent+' '+id);button.setAttribute('aria-pressed',runtime.selected.has(id));
    button.onclick=()=>{toggle(id,true);document.getElementById('id-filter').focus();};td.append(button);tr.append(td);tableBody.append(tr);
  }
  document.getElementById('page').textContent=`Rows ${visible.length?page*20+1:0}–${Math.min((page+1)*20,visible.length)} of ${visible.length}`;
  document.getElementById('previous').disabled=page===0;document.getElementById('next').disabled=(page+1)*20>=visible.length;
}
function toggle(id,multi){const selected=multi?new Set(runtime.selected):new Set();if(selected.has(id))selected.delete(id);else selected.add(id);runtime.select([...selected]);message();}
function action(fn){try{fn();error.textContent='';message();}catch(e){error.textContent=e.message;}}
const headers=document.getElementById('headers');for(const label of ['Row ID',...Object.keys(scene.columns).filter(c=>c!=='id'),'Selection']){const th=document.createElement('th');th.scope='col';th.textContent=label;headers.append(th);}
document.getElementById('backend').onchange=e=>action(()=>runtime.setBackend(e.target.value));
document.getElementById('id-filter').oninput=e=>action(()=>{const q=e.target.value;page=0;runtime.setVisible(q?scene.row_ids.filter(id=>id.includes(q)):null);});
document.getElementById('clear').onclick=()=>action(()=>runtime.select([]));
document.getElementById('zoom-in').onclick=()=>action(()=>runtime.zoom(1.5));document.getElementById('zoom-out').onclick=()=>action(()=>runtime.zoom(1/1.5));
document.getElementById('reset-view').onclick=()=>action(()=>runtime.setViewport([0,0,scene.width,scene.height]));
document.getElementById('previous').onclick=()=>{page--;message();};document.getElementById('next').onclick=()=>{page++;message();};
document.getElementById('save').onclick=()=>download(JSON.stringify(runtime.state(),null,2)+'\n','view.json','application/json');
document.getElementById('svg').onclick=()=>download(runtime.exportSVG(),'view.svg','image/svg+xml');
document.getElementById('load').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>8e6)throw Error('State file exceeds 8 MB');runtime.loadState(JSON.parse(await file.text()));document.getElementById('id-filter').value='';page=0;message();error.textContent='';}catch(err){error.textContent=err.message;}finally{e.target.value='';}};
const stage=document.getElementById('stage');let drag=null,moved=false;
stage.onpointerdown=e=>{if(e.button!==0)return;stage.focus();drag={x:e.clientX,y:e.clientY,viewport:[...runtime.viewport]};moved=false;stage.setPointerCapture(e.pointerId);};
stage.onpointermove=e=>{const p=runtime.point(e.clientX,e.clientY);if(!p)return;
  if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>3)moved=true;if(moved){const s=runtime.mapping().scale;action(()=>runtime.setViewport([drag.viewport[0]-dx/s,drag.viewport[1]-dy/s,drag.viewport[2],drag.viewport[3]]));}}
  else{const hit=runtime.pick(p.x,p.y,4/runtime.mapping().scale);document.getElementById('hover').textContent=hit?`${hit.id} · ${hit.layer.x}: ${Number(scene.columns[hit.layer.x][runtime.rowIndex.get(hit.id)].toPrecision(6))} · ${hit.layer.y}: ${Number(scene.columns[hit.layer.y][runtime.rowIndex.get(hit.id)].toPrecision(6))}`:'Point at a mark to inspect its row ID.';}
};
stage.onpointerup=e=>{if(!drag)return;drag=null;if(!moved){const p=runtime.point(e.clientX,e.clientY),hit=p&&runtime.pick(p.x,p.y,4/runtime.mapping().scale);if(hit)toggle(hit.id,e.ctrlKey||e.metaKey||e.shiftKey);}stage.releasePointerCapture(e.pointerId);};
stage.onpointercancel=()=>{drag=null;};
stage.onkeydown=e=>{const [x,y,w,h]=runtime.viewport;const moves={ArrowLeft:[x-w*.1,y,w,h],ArrowRight:[x+w*.1,y,w,h],ArrowUp:[x,y-h*.1,w,h],ArrowDown:[x,y+h*.1,w,h]};
  if(moves[e.key]){e.preventDefault();action(()=>runtime.setViewport(moves[e.key]));}else if(['+','=','-','0'].includes(e.key)){e.preventDefault();action(()=>e.key==='0'?runtime.setViewport([0,0,scene.width,scene.height]):runtime.zoom(e.key==='-'?1/1.5:1.5));}};
runtime.ready.then(message).catch(e=>{error.textContent=e.message;});
