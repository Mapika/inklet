'use strict';
const NS='http://www.w3.org/2000/svg';
function element(tag,attrs={}){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;}
function inside(x,y,b){return x>=b[0]&&x<=b[0]+b[2]&&y>=b[1]&&y<=b[1]+b[3];}
function polygonPath(rings){return rings.map(r=>'M '+r.map(p=>p.join(' ')).join(' L ')+' Z').join(' ');}
function polygonContains(x,y,rings){
  let contained=false;
  for(const ring of rings)for(let n=1;n<ring.length;n++){
    const a=ring[n-1],b=ring[n],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
    if(length){
      const along=(x-a[0])*(dx/length)+(y-a[1])*(dy/length);
      const across=Math.abs((x-a[0])*(dy/length)-(y-a[1])*(dx/length));
      if(across<=1e-10&&along>=-1e-10&&along<=length+1e-10)return true;
    }
    if((a[1]>y)!==(b[1]>y)&&x<a[0]+(y-a[1])/(b[1]-a[1])*(b[0]-a[0]))contained=!contained;
  }
  return contained;
}
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
    this.layerItems=scene.layers.map(()=>[]);
    this.pickRadius=Math.max(0,...scene.layers.map(l=>l.radius||0));
    for(const [layerIndex,layer] of scene.layers.entries()){
      const marks=layer.marks??layer.points.map(p=>({kind:'circle',ids:[p[0]],geometry:[p[1],p[2],layer.radius]}));
      for(const mark of marks){
        const g=mark.geometry,item={...mark,id:mark.ids[0],x:g[0],y:g[1],layer,layerIndex,order:this.items.length};
        this.items.push(item);this.layerItems[layerIndex].push(item);
        for(const id of item.ids){if(!this.byId.has(id))this.byId.set(id,[]);this.byId.get(id).push(item);}
        // Circle centers retain the original compact index. Extended marks use
        // their clipped bounds, so a long off-page segment cannot explode it.
        let box;
        if(item.kind==='circle'){
          const key=Math.floor(g[0]/this.cellSize)+','+Math.floor(g[1]/this.cellSize);
          if(!this.index.has(key))this.index.set(key,[]);this.index.get(key).push(item);continue;
        }
        else{
          const pad=item.kind==='line'?item.width/2:0,b=layer.clip;
          box=item.kind==='polygon'?item.bounds:item.kind==='rect'?[g[0],g[1],g[0]+g[2],g[1]+g[3]]:
            [Math.min(g[0],g[2])-pad,Math.min(g[1],g[3])-pad,Math.max(g[0],g[2])+pad,Math.max(g[1],g[3])+pad];
          box=[Math.max(box[0],b[0]),Math.max(box[1],b[1]),Math.min(box[2],b[0]+b[2]),Math.min(box[3],b[1]+b[3])];
        }
        if(box[0]>box[2]||box[1]>box[3])continue;
        for(let gx=Math.floor(box[0]/this.cellSize);gx<=Math.floor(box[2]/this.cellSize);gx++)for(let gy=Math.floor(box[1]/this.cellSize);gy<=Math.floor(box[3]/this.cellSize);gy++){
          const key=gx+','+gy;if(!this.index.has(key))this.index.set(key,[]);this.index.get(key).push(item);
        }
      }
    }
    this.frameImage=new Image();
    this.ready=new Promise((resolve,reject)=>{this.rejectReady=reject;
      this.frameImage.onload=()=>{try{this.render();resolve(this);}catch(error){reject(error);}};
      this.frameImage.onerror=()=>reject(Error('Cannot rasterize the measured frame.'));});
    // Explicit pixel dimensions avoid SVG intrinsic-size ambiguity in drawImage.
    const rasterFrame=scene.frame.replace(/<rect id="inklet-background"[^>]*\/>/,'').replace(/width="[^"]+mm"/,`width="${scene.width*5}"`).replace(/height="[^"]+mm"/,`height="${scene.height*5}"`);
    this.frameImage.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(rasterFrame);
    this.resizeObserver=new ResizeObserver(()=>{if(this.frameImage.complete&&this.frameImage.naturalWidth)this.render();});this.resizeObserver.observe(host);
  }
  dispose(){
    if(this.disposed)return;this.disposed=true;this.resizeObserver.disconnect();
    this.frameImage.onload=null;this.frameImage.onerror=null;this.rejectReady(Error('Renderer disposed'));
    this.svg.remove();this.canvas.remove();this.canvas.width=this.canvas.height=this.base.width=this.base.height=0;
    this.index.clear();this.byId.clear();this.items=[];this.layerItems=[];
  }
  mapping(){const r=this.host.getBoundingClientRect(),v=this.viewport,s=Math.min(r.width/v[2],r.height/v[3]);return {width:r.width,height:r.height,scale:s,dx:(r.width-v[2]*s)/2-v[0]*s,dy:(r.height-v[3]*s)/2-v[1]*s};}
  point(clientX,clientY){const m=this.svg.getScreenCTM();if(!m)return null;return new DOMPoint(clientX,clientY).matrixTransform(m.inverse());}
  shown(id){return this.visible===null||this.visible.has(id);}
  markShown(item){return item.ids.every(id=>this.shown(id));}
  selectedItems(){return [...new Set([...this.selected].flatMap(id=>this.byId.get(id)||[]))].sort((a,b)=>a.order-b.order);}
  setBackend(name){if(!['svg','canvas','hybrid'].includes(name))throw Error('Unsupported backend');this.backend=name;this.render();}
  setVisible(ids){if(ids!==null&&(!Array.isArray(ids)||new Set(ids).size!==ids.length||ids.some(id=>!this.rowSet.has(id))))throw Error('Unknown or duplicate visible ID');this.visible=ids===null?null:new Set(ids);this.render();}
  select(ids){if(!Array.isArray(ids)||new Set(ids).size!==ids.length||ids.some(id=>!this.rowSet.has(id)))throw Error('Unknown or duplicate selected ID');this.selected=new Set(ids);this.renderSelection();}
  setViewport(v){if(!Array.isArray(v)||v.length!==4||v.some(n=>typeof n!=='number'||!Number.isFinite(n))||v[2]<=0||v[3]<=0)throw Error('Invalid viewport');
    if(Math.abs(v[0])>this.scene.width*100||Math.abs(v[1])>this.scene.height*100||v[2]<this.scene.width/100||v[3]<this.scene.height/100||v[2]>this.scene.width*100||v[3]>this.scene.height*100)throw Error('Viewport zoom is outside this preview’s 0.01–100× range');
    this.viewport=[...v];this.render();}
  zoom(factor){const [x,y,w,h]=this.viewport;this.setViewport([x+w*(1-1/factor)/2,y+h*(1-1/factor)/2,w/factor,h/factor]);}
  pick(x,y,tolerance=0){
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(tolerance)||tolerance<0||tolerance>Math.max(this.scene.width,this.scene.height)||!this.scene.layers.some(l=>inside(x,y,l.clip)))return null;
    const reach=this.pickRadius+tolerance,seen=new Set();
    let best=null,bestDistance=Infinity;
    for(let gx=Math.floor((x-reach)/this.cellSize);gx<=Math.floor((x+reach)/this.cellSize);gx++)for(let gy=Math.floor((y-reach)/this.cellSize);gy<=Math.floor((y+reach)/this.cellSize);gy++){
      for(const item of this.index.get(gx+','+gy)||[]){
        if(seen.has(item))continue;seen.add(item);
        if(!this.markShown(item)||!inside(x,y,item.layer.clip))continue;
        const g=item.geometry;let distance,allowed=tolerance,id=item.id;
        if(item.kind==='polygon'){if(!polygonContains(x,y,g))continue;distance=0;}
        else if(item.kind==='circle'){distance=Math.hypot(x-g[0],y-g[1]);allowed+=g[2];}
        else if(item.kind==='rect')distance=Math.hypot(Math.max(g[0]-x,0,x-g[0]-g[2]),Math.max(g[1]-y,0,y-g[1]-g[3]));
        else{
          // Normalize before subtraction/dot products to avoid overflow for
          // finite off-domain endpoints. A coincident segment is a round dot.
          const scale=Math.max(1,...g.map(Math.abs),Math.abs(x),Math.abs(y));
          const dx=g[2]/scale-g[0]/scale,dy=g[3]/scale-g[1]/scale,length=dx*dx+dy*dy;
          const t=length?Math.max(0,Math.min(1,((x/scale-g[0]/scale)*dx+(y/scale-g[1]/scale)*dy)/length)):1;
          distance=Math.hypot(x-((1-t)*g[0]+t*g[2]),y-((1-t)*g[1]+t*g[3]));allowed+=item.width/2;
          id=item.ids[t<.5-1e-12?0:1];
        }
        if(distance<=allowed&&(distance<bestDistance-1e-10||(Math.abs(distance-bestDistance)<=1e-10&&(!best||item.order>best.order)))){best={...item,id};bestDistance=distance;}
      }
    }return best;
  }
  clips(target,prefix){const defs=element('defs');target.append(defs);return this.scene.layers.map((layer,n)=>{
    const id=this.prefix+prefix+n,clip=element('clipPath',{id});clip.append(element('rect',Object.fromEntries(['x','y','width','height'].map((k,j)=>[k,layer.clip[j]]))));defs.append(clip);
    const g=element('g',{'clip-path':`url(#${id})`});target.append(g);return g;
  });}
  svgMarks(target,selectedOnly=false,prefix='live-clip-'){
    const groups=this.clips(target,prefix);
    for(const item of selectedOnly?this.selectedItems():this.items){if(!this.markShown(item))continue;
      const g=item.geometry,color=item.color??item.layer.color;let tag=item.kind,attrs;
      if(tag==='polygon'){
        groups[item.layerIndex].append(element('path',{d:polygonPath(g),'fill-rule':'evenodd',fill:selectedOnly?'none':color,
          stroke:selectedOnly?'#bd5636':'#ffffff','stroke-width':selectedOnly?.6:.2,'stroke-linejoin':'round'}));continue;
      }
      if(tag==='circle')attrs={cx:g[0],cy:g[1],r:g[2]+(selectedOnly?.3:0)};
      else if(tag==='rect')attrs={x:g[0],y:g[1],width:g[2],height:g[3]};
      else attrs={x1:g[0],y1:g[1],x2:g[2],y2:g[3],'stroke-width':item.width+(selectedOnly?.6:0),'stroke-linecap':'round',stroke:selectedOnly?'#bd5636':item.layer.color};
      if(tag!=='line')Object.assign(attrs,selectedOnly?{fill:'none',stroke:'#bd5636','stroke-width':.3}:{fill:item.layer.color,'fill-opacity':.65});
      groups[item.layerIndex].append(element(tag,attrs));
    }
  }
  prepareCanvas(canvas){const m=this.mapping(),dpr=devicePixelRatio||1;
    canvas.width=Math.max(1,Math.round(m.width*dpr));canvas.height=Math.max(1,Math.round(m.height*dpr));
    const ctx=canvas.getContext('2d');ctx.setTransform(canvas.width/m.width*m.scale,0,0,canvas.height/m.height*m.scale,canvas.width/m.width*m.dx,canvas.height/m.height*m.dy);return ctx;}
  canvasMarks(ctx,selectedOnly=false){
    for(const [n,layer] of this.scene.layers.entries()){ctx.save();ctx.beginPath();ctx.rect(...layer.clip);ctx.clip();
      ctx.fillStyle=layer.color;ctx.lineCap='round';
      for(const item of this.layerItems[n]){
        if(!this.markShown(item)||(selectedOnly&&!item.ids.some(id=>this.selected.has(id))))continue;
        const g=item.geometry;ctx.beginPath();ctx.fillStyle=item.color??layer.color;ctx.strokeStyle=selectedOnly?'#bd5636':layer.color;
        if(item.kind==='polygon'){
          for(const ring of g){ctx.moveTo(...ring[0]);for(const p of ring.slice(1))ctx.lineTo(...p);ctx.closePath();}
          ctx.globalAlpha=1;ctx.lineWidth=selectedOnly?.6:.2;ctx.lineJoin='round';ctx.strokeStyle=selectedOnly?'#bd5636':'#ffffff';
          if(!selectedOnly)ctx.fill('evenodd');ctx.stroke();continue;
        }
        ctx.globalAlpha=selectedOnly||item.kind==='line'?1:.65;ctx.lineWidth=.3;
        if(item.kind==='circle')ctx.arc(g[0],g[1],g[2]+(selectedOnly?.3:0),0,2*Math.PI);
        else if(item.kind==='rect')ctx.rect(...g);
        else{ctx.moveTo(g[0],g[1]);ctx.lineTo(g[2],g[3]);ctx.lineWidth=item.width+(selectedOnly?.6:0);}
        if(selectedOnly||item.kind==='line')ctx.stroke();else ctx.fill();
      }
      ctx.restore();
    }
  }
  render(){
    if(this.disposed)return;
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
    if(this.disposed)return;
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
window.FigureRenderer=ScatterRenderer;
let scene=JSON.parse(document.getElementById('scene').textContent);
let runtime=new ScatterRenderer(document.getElementById('stage'),scene);window.inklet=runtime;
runtime.backend=/*DEFAULT_BACKEND*/'svg';document.getElementById('backend').value=runtime.backend;
const status=document.getElementById('status'),error=document.getElementById('error'),tableBody=document.getElementById('rows');let page=0;
function message(){const visible=scene.row_ids.filter(id=>runtime.shown(id));const hidden=[...runtime.selected].filter(id=>!runtime.shown(id)).length;
  status.textContent=`${visible.length} rows visible · ${runtime.selected.size} selected${hidden?` (${hidden} hidden)`:''} · ${Math.round(scene.width/runtime.viewport[2]*100)}% page zoom`;
  const unassigned=(scene.facet_groups??[]).filter(group=>group.unassigned_ids.length);
  document.getElementById('facet-status').hidden=!unassigned.length;
  document.getElementById('facet-rows').textContent=unassigned.length?JSON.stringify(unassigned,null,2):'';
  const start=page*20;if(start>=visible.length&&page)page=0;tableBody.replaceChildren();
  for(const id of visible.slice(page*20,page*20+20)){const n=runtime.rowIndex.get(id),tr=document.createElement('tr');
    const th=document.createElement('th');th.scope='row';th.textContent=id;tr.append(th);
    for(const column of Object.keys(scene.columns).filter(c=>c!==(scene.key??'id'))){const td=document.createElement('td');const value=scene.columns[column][n];td.textContent=typeof value==='number'?(Number.isInteger(value)?String(value):Number(value.toPrecision(6)).toString()):(value??'Missing');tr.append(td);}
    const td=document.createElement('td'),button=document.createElement('button');button.textContent=runtime.selected.has(id)?'Deselect':'Select';button.setAttribute('aria-label',button.textContent+' '+id);button.setAttribute('aria-pressed',runtime.selected.has(id));
    button.onclick=()=>{toggle(id,true);document.getElementById('id-filter').focus();};td.append(button);tr.append(td);tableBody.append(tr);
  }
  document.getElementById('page').textContent=`Rows ${visible.length?page*20+1:0}–${Math.min((page+1)*20,visible.length)} of ${visible.length}`;
  document.getElementById('previous').disabled=page===0;document.getElementById('next').disabled=(page+1)*20>=visible.length;
}
function toggle(id,multi){const selected=multi?new Set(runtime.selected):new Set();if(selected.has(id))selected.delete(id);else selected.add(id);runtime.select([...selected]);message();}
function action(fn){if(busy)return;try{fn();error.textContent='';message();}catch(e){error.textContent=e.message;}}
function updateHeaders(){const headers=document.getElementById('headers');headers.replaceChildren();for(const label of ['Row ID',...Object.keys(scene.columns).filter(c=>c!==(scene.key??'id')),'Selection']){const th=document.createElement('th');th.scope='col';th.textContent=label;headers.append(th);}}
updateHeaders();
document.getElementById('backend').onchange=e=>action(()=>runtime.setBackend(e.target.value));
let searchColumns=/*SEARCH_COLUMNS*/[];
document.getElementById('id-filter').oninput=e=>action(()=>{const q=e.target.value.toLowerCase();page=0;
  runtime.setVisible(q?scene.row_ids.filter((id,n)=>[id,...searchColumns.map(c=>scene.columns[c][n])].some(v=>String(v??'').toLowerCase().includes(q))):null);
});
document.getElementById('clear').onclick=()=>action(()=>runtime.select([]));
document.getElementById('zoom-in').onclick=()=>action(()=>runtime.zoom(1.5));document.getElementById('zoom-out').onclick=()=>action(()=>runtime.zoom(1/1.5));
document.getElementById('reset-view').onclick=()=>action(()=>runtime.setViewport([0,0,scene.width,scene.height]));
document.getElementById('previous').onclick=()=>{page--;message();};document.getElementById('next').onclick=()=>{page++;message();};
document.getElementById('save').onclick=()=>download(JSON.stringify(runtime.state(),null,2)+'\n','view.json','application/json');
document.getElementById('svg').onclick=()=>download(runtime.exportSVG(),'view.svg','image/svg+xml');
document.getElementById('load').onchange=async e=>{const file=e.target.files[0];if(!file||busy)return;setBusy(true);try{if(file.size>8e6)throw Error('State file exceeds 8 MB');runtime.loadState(JSON.parse(await file.text()));document.getElementById('id-filter').value='';page=0;message();error.textContent='';}catch(err){error.textContent=err.message;}finally{e.target.value='';setBusy(false);}};
const stage=document.getElementById('stage');let drag=null,moved=false;
stage.onpointerdown=e=>{if(busy||e.button!==0)return;stage.focus({preventScroll:true});drag={x:e.clientX,y:e.clientY,viewport:[...runtime.viewport]};moved=false;stage.setPointerCapture(e.pointerId);};
stage.onpointermove=e=>{if(busy)return;const p=runtime.point(e.clientX,e.clientY);if(!p)return;
  if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>3)moved=true;if(moved){const s=runtime.mapping().scale;action(()=>runtime.setViewport([drag.viewport[0]-dx/s,drag.viewport[1]-dy/s,drag.viewport[2],drag.viewport[3]]));}}
  else{const hit=runtime.pick(p.x,p.y,4/runtime.mapping().scale);
    const fields=hit?(hit.kind==='polygon'?[hit.layer.value].filter(Boolean):[hit.layer.x,hit.layer.y]):[];
    const values=fields.map(column=>{const value=scene.columns[column][runtime.rowIndex.get(hit.id)];return `${column}: ${value===null?'Missing':Number(value.toPrecision(6))}`;});
    document.getElementById('hover').textContent=hit?[hit.id,...values].join(' · '):'Point at a mark to inspect its row ID.';
  }
};
stage.onpointerup=e=>{if(busy||!drag)return;drag=null;if(!moved){const p=runtime.point(e.clientX,e.clientY),hit=p&&runtime.pick(p.x,p.y,4/runtime.mapping().scale);if(hit)toggle(hit.id,e.ctrlKey||e.metaKey||e.shiftKey);}stage.releasePointerCapture(e.pointerId);};
stage.onpointercancel=()=>{drag=null;};
stage.onkeydown=e=>{if(busy)return;const [x,y,w,h]=runtime.viewport;const moves={ArrowLeft:[x-w*.1,y,w,h],ArrowRight:[x+w*.1,y,w,h],ArrowUp:[x,y-h*.1,w,h],ArrowDown:[x,y+h*.1,w,h]};
  if(moves[e.key]){e.preventDefault();action(()=>runtime.setViewport(moves[e.key]));}else if(['+','=','-','0'].includes(e.key)){e.preventDefault();action(()=>e.key==='0'?runtime.setViewport([0,0,scene.width,scene.height]):runtime.zoom(e.key==='-'?1/1.5:1.5));}};
const revisionCatalog=/*REVISION_CATALOG*/null;
const revisions=[{scene,attribution:document.getElementById('attribution').textContent,search_columns:searchColumns},...revisionCatalog.alternatives];
let revisionIndex=0,lastReport=null,busy=true,busyFocus=null;
function setBusy(value){
  if(value&&!busy)busyFocus=document.activeElement;
  busy=value;const app=document.getElementById('app');app.inert=value;app.setAttribute('aria-busy',String(value));
  if(value)drag=null;
  else if(busyFocus){const target=busyFocus;busyFocus=null;if(target.isConnected&&!target.disabled)target.focus({preventScroll:true});}
}
const revisionTarget=document.getElementById('revision-target');
for(const [index,label] of revisionCatalog.labels.entries()){const option=document.createElement('option');option.value=index;option.textContent=label;revisionTarget.append(option);}
document.getElementById('revision-controls').hidden=revisions.length<2;
function revisionStatus(){document.getElementById('revision-current').textContent='Current data: '+revisionCatalog.labels[revisionIndex];}
function showReport(){
  document.getElementById('revision-report').textContent=`${lastReport.added_ids.length} added, ${lastReport.removed_ids.length} removed, ${lastReport.changed_ids.length} changed. Dropped selected IDs: ${lastReport.removed_selected.join(', ')||'none'}. Dropped visible IDs: ${lastReport.removed_visible.join(', ')||'none'}. Viewport: ${lastReport.viewport_policy}.`;
  document.getElementById('revision-details').textContent=JSON.stringify(lastReport,null,2);
  document.getElementById('save-revision-report').disabled=false;
}
async function switchRevision(index,{missing='error',viewport='reset'}={}){
  if(busy)throw Error('Wait for the current operation to finish');
  if(!Number.isInteger(index)||index<0||index>=revisions.length)throw Error('Unknown revision');
  if(!['error','drop'].includes(missing)||!['reset','preserve'].includes(viewport))throw Error('Invalid revision policy');
  if(index===revisionIndex)return null;
  const target=revisions[index],oldState=runtime.state(),ids=new Set(target.scene.row_ids),s=oldState.selection;
  // Python's canonical ID order differs from JS UTF-16 sorting for some
  // Unicode IDs. Filter the precomputed report to preserve the shared order.
  const selectedSet=new Set(s.selected_ids),visibleSet=new Set(s.visible_ids??[]);
  const removedIds=revisionCatalog.reports[revisionIndex][index].removed_ids;
  const removedSelected=removedIds.filter(id=>selectedSet.has(id)),removedVisible=removedIds.filter(id=>visibleSet.has(id));
  if(missing==='error'&&(removedSelected.length||removedVisible.length))throw Error(`Revision removes selected IDs: ${removedSelected.join(', ')||'none'}; visible IDs: ${removedVisible.join(', ')||'none'}. Choose Drop removed IDs to apply it.`);
  const nextState={schema:oldState.schema,scene_digest:target.scene.scene_digest,
    selection:{...s,table:target.scene.table,data_digest:target.scene.data_digest,selected_ids:s.selected_ids.filter(id=>ids.has(id)),
      visible_ids:s.visible_ids===null?null:s.visible_ids.filter(id=>ids.has(id))},
    viewport:viewport==='preserve'?oldState.viewport:[0,0,target.scene.width,target.scene.height]};
  const report={...revisionCatalog.reports[revisionIndex][index],removed_selected:removedSelected,removed_visible:removedVisible,missing_policy:missing,viewport_policy:viewport};
  setBusy(true);let candidate=null;const staging=document.createElement('div');
  staging.className='revision-staging';staging.setAttribute('aria-hidden','true');staging.inert=true;
  const rect=stage.getBoundingClientRect(),minHeight=parseFloat(getComputedStyle(stage).minHeight)||0;
  Object.assign(staging.style,{position:'fixed',left:'-100000px',top:'0',width:rect.width+'px',height:Math.max(minHeight,rect.width*target.scene.height/target.scene.width)+'px',visibility:'hidden'});
  document.body.append(staging);
  try{
    candidate=new ScatterRenderer(staging,target.scene);candidate.backend=runtime.backend;
    await candidate.ready;candidate.loadState(nextState);
    // Prepare all geometry and state offscreen before replacing the active scene.
    const previous=runtime;
    stage.style.aspectRatio=target.scene.width+'/'+target.scene.height;
    candidate.resizeObserver.disconnect();stage.replaceChildren(...staging.childNodes);candidate.host=stage;
    runtime=candidate;scene=target.scene;searchColumns=target.search_columns;window.inklet=runtime;
    revisionIndex=index;lastReport=report;previous.dispose();candidate.resizeObserver.observe(stage);
    document.getElementById('attribution').textContent=target.attribution;
    document.getElementById('filter-label').textContent=searchColumns.length?'Search rows':'Row ID contains';
    document.getElementById('id-filter').value='';document.getElementById('hover').textContent='Point at a mark to inspect its row ID.';
    page=0;revisionTarget.value=index;updateHeaders();revisionStatus();showReport();message();error.textContent='';
    return JSON.parse(JSON.stringify(report));
  }catch(e){if(candidate&&candidate!==runtime)candidate.dispose();throw e;}
  finally{staging.remove();setBusy(false);}
}
document.getElementById('apply-revision').onclick=async()=>{try{await switchRevision(Number(revisionTarget.value),{missing:document.getElementById('revision-missing').value,viewport:document.getElementById('revision-viewport').value});}catch(e){error.textContent=e.message;}};
document.getElementById('save-revision-report').onclick=()=>{if(lastReport)download(JSON.stringify(lastReport,null,2)+'\n','revision.json','application/json');};
const documentReady=runtime.ready.then(()=>{const initial=/*INITIAL_STATE*/null;if(initial)runtime.loadState(initial);revisionStatus();message();setBusy(false);});
documentReady.catch(e=>{error.textContent=e.message;setBusy(false);
  status.textContent='Figure could not be loaded. Reload this page to try again.';
  for(const control of document.querySelectorAll('#app button,#app input,#app select'))control.disabled=true;
  stage.inert=true;
});
window.inkletDocument={ready:documentReady,switchRevision,get revisionIndex(){return revisionIndex;},report:()=>lastReport===null?null:JSON.parse(JSON.stringify(lastReport))};
