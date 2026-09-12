let selectedPath='/',zoom=1,panMode=false,spaceHeld=false,pan=null;
function niceName(path){return path==='/'?'Composition':path.split('/').pop().replaceAll('_',' ').replaceAll('-',' ').replace(/^./,s=>s.toUpperCase());}
function markDirty(key,input){dirty.set(key,input);input.classList.add('is-dirty');syncUI();}
function selectTarget(path){if(busy)return false;if(dirty.size){byId('target').value=selectedPath;status('Apply or discard pending changes before selecting another object.',true);return false;}byId('target').value=path;fields();return true;}
function syncUI(){
  if(!state)return;selectedPath=byId('target').value;
  byId('selection-name').textContent=niceName(selectedPath);byId('selection-path').textContent=selectedPath;
  byId('pending-label').textContent=dirty.size?dirty.size+' pending '+(dirty.size===1?'change':'changes'):'All changes applied';
  byId('discard').hidden=!dirty.size;byId('apply').disabled=busy||!dirty.size;
  byId('undo').disabled=busy||!state.undo;byId('redo').disabled=busy||!state.redo;
  byId('revision-label').textContent='Revision '+state.revision;
  const page=state.targets['/'].page;byId('page-size').textContent=(page.width*page.unit).toFixed(0)+' × '+(page.height*page.unit).toFixed(0)+' mm';
  const box=state.geometry[selectedPath]?.box;byId('selection-size').textContent=niceName(selectedPath)+(box?' · '+box[2].toFixed(1)+' × '+box[3].toFixed(1)+' mm':'');
  drawTree();
}
function drawTree(){if(!state)return;const tree=byId('object-tree'),focused=tree.contains(document.activeElement)?document.activeElement.title:null;tree.replaceChildren();const query=byId('search').value.toLowerCase();const paths=Object.keys(state.targets);byId('object-count').textContent=paths.length-1;
  for(const path of paths){if(query&&!path.toLowerCase().includes(query)&&!niceName(path).toLowerCase().includes(query))continue;
    const button=document.createElement('button');button.className='object-row';button.setAttribute('aria-current',String(path===selectedPath));button.title=path;button.disabled=busy;button.style.paddingLeft=(8+Math.max(0,path.split('/').length-2)*13)+'px';
    const icon=document.createElement('span');icon.className='object-icon';icon.setAttribute('aria-hidden','true');const target=state.targets[path],kinds=Object.values(target.styles||{}).map(x=>x.kind);
    icon.textContent=target.page?'▧':kinds.some(x=>x.startsWith('plot-'))?'⌁':kinds.includes('component-text')?'T':kinds.includes('module-box')?'▭':'◇';const name=document.createElement('span');name.textContent=niceName(path);button.append(icon,name);button.onclick=()=>{if(selectTarget(path))tree.querySelector('[aria-current=true]')?.focus({preventScroll:true});};tree.append(button);
  }
  if(focused)[...tree.children].find(button=>button.title===focused)?.focus({preventScroll:true});
  if(!tree.children.length){const note=document.createElement('p');note.className='note';note.textContent='No matching objects.';tree.append(note);}
}
function decorateFields(){
  byId('fields').querySelectorAll('input[data-group="styles"][type="text"]').forEach(input=>{
    const row=document.createElement('span');row.className='colour-control';input.before(row);row.append(input);const picker=document.createElement('input');picker.type='color';picker.setAttribute('aria-label','Pick '+input.dataset.key+' colour for '+input.dataset.label);
    function update(){const context=document.createElement('canvas').getContext('2d');let colour=null;
      if(input.value&&CSS.supports('color',input.value)){context.fillStyle=input.value;if(/^#[0-9a-f]{6}$/i.test(context.fillStyle))colour=context.fillStyle;}
      picker.value=colour||'#000000';picker.style.opacity=colour?'1':'.25';picker.title=colour?'Choose colour':'Automatic or transparent; choose an explicit colour';}
    update();picker.oninput=()=>{input.value=picker.value;input.dispatchEvent(new Event('input'));};input.addEventListener('input',update);row.prepend(picker);
  });
}
function sizeCanvas(){if(!state||!previewReady)return;const viewport=byId('viewport'),ratio=state.viewbox[2]/state.viewbox[3],padding=innerWidth<=680?96:128;
  const fitted=Math.max(80,Math.min(viewport.clientWidth-padding,(viewport.clientHeight-padding)/ (1/ratio)));
  byId('stage').style.width=fitted*zoom+'px';byId('zoom-label').textContent=Math.round(zoom*100)+'%';drawOverlay();
}
function setZoom(value){if(gesture||pan)return;const viewport=byId('viewport'),oldWidth=byId('stage').clientWidth,centreX=viewport.scrollLeft+viewport.clientWidth/2,centreY=viewport.scrollTop+viewport.clientHeight/2;
  zoom=Math.max(.25,Math.min(4,value));sizeCanvas();const ratio=byId('stage').clientWidth/Math.max(1,oldWidth);viewport.scrollLeft=centreX*ratio-viewport.clientWidth/2;viewport.scrollTop=centreY*ratio-viewport.clientHeight/2;
}
function typing(event){return event.target.closest?.('input,textarea,select,[contenteditable=true]');}
function updatePan(){document.body.classList.toggle('panning',panMode||spaceHeld);byId('pan-tool').classList.toggle('active',panMode);byId('select-tool').classList.toggle('active',!panMode);byId('pan-tool').setAttribute('aria-pressed',panMode);byId('select-tool').setAttribute('aria-pressed',!panMode);}
byId('search').oninput=drawTree;
byId('open-file').onclick=()=>{if(dirty.size){status('Apply or discard pending changes before opening a file.',true);return;}byId('load').click();};
byId('apply').querySelector('kbd').textContent=navigator.platform.includes('Mac')?'⌘ ↵':'Ctrl ↵';
byId('discard').onclick=()=>{fields();status('Pending changes discarded.');};
for(const button of document.querySelectorAll('[data-tab]'))button.onclick=()=>{byId('inspector').value=button.dataset.tab;showSection();};
byId('zoom-in').onclick=()=>setZoom(zoom*1.2);byId('zoom-out').onclick=()=>setZoom(zoom/1.2);byId('fit').onclick=()=>{zoom=1;sizeCanvas();byId('viewport').scrollTo(0,0);};
byId('pan-tool').onclick=()=>{panMode=true;updatePan();};byId('select-tool').onclick=()=>{panMode=false;updatePan();};
byId('help-button').onclick=()=>byId('help').showModal();byId('close-help').onclick=()=>byId('help').close();
for(const id of ['save','svg','pdf'])byId(id).addEventListener('click',event=>{if(busy||dirty.size){event.preventDefault();status('Apply or discard pending changes before saving or exporting.',true);}});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape')endPan();
  if(byId('help').open)return;
  if(event.code==='Space'&&!typing(event)&&!byId('help').open){event.preventDefault();spaceHeld=true;updatePan();}
  if(!(event.ctrlKey||event.metaKey))return;
  if(event.key==='Enter'){event.preventDefault();byId('apply').click();}
  if(event.key.toLowerCase()==='s'){event.preventDefault();byId('save').click();}
  if(!typing(event)&&event.key.toLowerCase()==='z'){event.preventDefault();byId(event.shiftKey?'redo':'undo').click();}
});
document.addEventListener('keyup',event=>{if(event.code==='Space'){spaceHeld=false;updatePan();}});
window.addEventListener('blur',()=>{spaceHeld=false;endPan();updatePan();});
function endPan(){if(!pan)return;const id=pan.id;pan=null;const viewport=byId('viewport');if(viewport.hasPointerCapture(id))viewport.releasePointerCapture(id);document.body.classList.remove('dragging-pan');}
const viewport=byId('viewport');
viewport.addEventListener('pointerdown',event=>{if(busy||gesture||!(panMode||spaceHeld||event.button===1)||event.button>1)return;event.preventDefault();event.stopPropagation();pan={id:event.pointerId,x:event.clientX,y:event.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(event.pointerId);document.body.classList.add('dragging-pan');},true);
viewport.addEventListener('pointermove',event=>{if(pan&&pan.id===event.pointerId){viewport.scrollLeft=pan.left-(event.clientX-pan.x);viewport.scrollTop=pan.top-(event.clientY-pan.y);}});
for(const name of ['pointerup','pointercancel','lostpointercapture'])viewport.addEventListener(name,endPan);
viewport.addEventListener('wheel',event=>{if(event.ctrlKey||event.metaKey){event.preventDefault();setZoom(zoom*Math.exp(-event.deltaY*.002));}},{passive:false});
new ResizeObserver(sizeCanvas).observe(viewport);

window.addEventListener('beforeunload',event=>{if(dirty.size){event.preventDefault();event.returnValue='';}});
