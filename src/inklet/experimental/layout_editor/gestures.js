const overlay=byId('overlay');let gesture=null;
const svgNS='http://www.w3.org/2000/svg';
function shape(tag,attributes){const node=document.createElementNS(svgNS,tag);for(const [key,value] of Object.entries(attributes))node.setAttribute(key,value);return node;}
function selection(box,path,ghost=false){
  const [x,y,w,h]=box,group=shape('g',{'data-selection':'true'});
  group.append(shape('rect',{x,y,width:w,height:h,class:'selection'+(ghost?' ghost':''),'data-path':path}));
  const units=state.viewbox[2]/Math.max(1,overlay.getBoundingClientRect().width),size=10*units;
  for(const [corner,cx,cy] of [['nw',x,y],['ne',x+w,y],['sw',x,y+h],['se',x+w,y+h]]){
    const handle=shape('rect',{x:cx-size/2,y:cy-size/2,width:size,height:size,class:'handle','data-path':path,'data-corner':corner});
    if(corner==='ne'||corner==='sw')handle.style.cursor='nesw-resize';group.append(handle);
  }
  return group;
}
function drawOverlay(){
  if(!state)return;overlay.setAttribute('viewBox',state.viewbox.join(' '));overlay.replaceChildren();
  for(const [path,geometry] of Object.entries(state.geometry)){
    const [x,y,w,h]=geometry.box;if(w<=0||h<=0)continue;
    const hit=shape('rect',{x,y,width:w,height:h,class:'hit','data-path':path});const title=shape('title',{});title.textContent=path;hit.append(title);overlay.append(hit);
  }
  const path=byId('target').value;if(state.geometry[path])overlay.append(selection(state.geometry[path].box,path));
}
function pointerPoint(event){const point=overlay.createSVGPoint();point.x=event.clientX;point.y=event.clientY;return point.matrixTransform(overlay.getScreenCTM().inverse());}
function cancelGesture(){if(!gesture)return;const id=gesture.pointerId;gesture=null;if(overlay.hasPointerCapture(id))overlay.releasePointerCapture(id);lock(false);drawOverlay();status('Drag cancelled.');}
overlay.addEventListener('pointerdown',event=>{
  if(busy||gesture||!previewReady||event.button!==0||event.isPrimary===false)return;
  const hit=event.target.closest('[data-path]');if(!hit){selectTarget('/');return;}
  let path=hit.dataset.path,corner=hit.dataset.corner;
  if(event.altKey){const parent=path.slice(0,path.lastIndexOf('/'));if(state.geometry[parent]){path=parent;corner=null;}}
  const box=state.geometry[path]?.box;if(!box||box[2]<=0||box[3]<=0)return;
  event.preventDefault();if(!selectTarget(path))return;overlay.focus({preventScroll:true});
  const point=pointerPoint(event);gesture={path,corner,box:[...box],start:point,client:[event.clientX,event.clientY],pointerId:event.pointerId,dx:0,dy:0,factor:1,moved:false};
  overlay.setPointerCapture(event.pointerId);lock(true);status(corner?'Scale artwork; release to apply. Escape cancels.':'Move content; release to apply. Escape cancels.');
});
function updateGesture(event){
  if(!gesture||event.pointerId!==gesture.pointerId)return;event.preventDefault();
  const g=gesture,point=pointerPoint(event),dx=point.x-g.start.x,dy=point.y-g.start.y;
  g.moved=Math.hypot(event.clientX-g.client[0],event.clientY-g.client[1])>=3;
  let box=[g.box[0]+dx,g.box[1]+dy,g.box[2],g.box[3]];
  if(g.corner){
    const sx=g.corner.includes('w')?-1:1,sy=g.corner.includes('n')?-1:1;
    const vx=sx*g.box[2],vy=sy*g.box[3];g.factor=Math.max(.05,Math.min(20,1+(vx*dx+vy*dy)/(vx*vx+vy*vy)));
    const px=g.box[0]+(sx<0?g.box[2]:0),py=g.box[1]+(sy<0?g.box[3]:0);
    box=[px+(g.box[0]-px)*g.factor,py+(g.box[1]-py)*g.factor,g.box[2]*g.factor,g.box[3]*g.factor];
  }else{g.dx=dx;g.dy=dy;}
  overlay.querySelector('[data-selection]')?.remove();overlay.append(selection(box,g.path,true));
}
overlay.addEventListener('pointermove',updateGesture);
overlay.addEventListener('pointerup',event=>{
  if(!gesture||event.pointerId!==gesture.pointerId)return;updateGesture(event);const g=gesture;gesture=null;
  if(overlay.hasPointerCapture(event.pointerId))overlay.releasePointerCapture(event.pointerId);lock(false);drawOverlay();
  if(!g.moved){status('Content selected.');return;}
  const value={path:g.path,dx:g.dx,dy:g.dy};if(g.corner){value.factor=g.factor;value.corner=g.corner;}
  request('gesture',value);
});
overlay.addEventListener('pointercancel',cancelGesture);
overlay.addEventListener('lostpointercapture',()=>{if(gesture)cancelGesture();});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&gesture){event.preventDefault();cancelGesture();}});
overlay.addEventListener('keydown',event=>{
  if(busy||gesture||!previewReady||dirty.size)return;const path=byId('target').value;if(!state.geometry[path])return;
  const step=event.shiftKey?10:1,keys={ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,-step],ArrowDown:[0,step]};
  if(keys[event.key]){event.preventDefault();request('gesture',{path,dx:keys[event.key][0],dy:keys[event.key][1]});}
});
new ResizeObserver(()=>{if(!gesture)drawOverlay();}).observe(byId('stage'));
