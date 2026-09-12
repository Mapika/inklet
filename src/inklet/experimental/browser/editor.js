// Commands retain only small, versioned author decisions. Data/view state has
// its own save format. A failed command never replaces the visible renderer.
VisualEditor=class{
  constructor(initial){
    this.value=structuredClone(initial);this.past=[];this.future=[];
    const byId=id=>document.getElementById(id);
    this.target=byId('edit-target');this.inputs={color:byId('edit-color'),radius_mm:byId('edit-radius'),line_width_mm:byId('edit-width')};
    this.target.onchange=()=>this.fields();
    const run=fn=>async()=>{try{await fn();error.textContent='';}catch(e){error.textContent=e.message;}};
    byId('edit-apply').onclick=run(()=>{
      const name=this.target.value,target=scene.editor.targets[name],value=this.overrides();
      const edits={kind:target.kind};
      for(const [key,input] of Object.entries(this.inputs))if(!input.disabled){
        const val=key==='color'?input.value:Number(input.value);
        if(val!==target.defaults[key])edits[key]=val;
      }
      if(Object.keys(edits).length===1)delete value.targets[name];else value.targets[name]=edits;
      return this.apply(value);
    });
    byId('edit-reset').onclick=run(()=>{const value=this.overrides();delete value.targets[this.target.value];return this.apply(value);});
    byId('edit-undo').onclick=run(()=>this.undo());byId('edit-redo').onclick=run(()=>this.redo());
    byId('edit-save').onclick=()=>download(JSON.stringify(this.overrides(),null,2)+'\n','overrides.json','application/json');
    byId('edit-load').onchange=async event=>{
      const file=event.target.files[0];if(!file||busy)return;
      setBusy(true);
      try{if(file.size>65536)throw Error('Overrides file exceeds 64 KB');
        const value=JSON.parse(await file.text());await this.commit(value,'apply');error.textContent='';
      }catch(e){error.textContent=e.message;}finally{event.target.value='';setBusy(false);}
    };
  }
  overrides(){return structuredClone(this.value);}
  validate(value,base,missing='error'){
    const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
    if(!['error','drop'].includes(missing)||!exact(value,['schema','table','targets'])||value.schema!=='inklet.visual-overrides/0.1'||value.table!==base.table||
      !value.targets||typeof value.targets!=='object'||Array.isArray(value.targets)||Object.keys(value.targets).length>12)throw Error('Invalid visual overrides or different table');
    const copy=structuredClone(value),orphaned=[];
    for(const [name,edits] of Object.entries(copy.targets)){
      if(!/^[A-Za-z][A-Za-z0-9_-]*$/.test(name)||/[\r\n]/.test(name)||!edits||typeof edits!=='object'||Array.isArray(edits)||typeof edits.kind!=='string'||Object.keys(edits).length<2)throw Error('Invalid override target');
      for(const [key,val] of Object.entries(edits)){
        if(key==='kind')continue;
        if(key==='color'){if(typeof val!=='string'||val.length!==7||!/^#[0-9a-fA-F]{6}$/.test(val))throw Error('Invalid override colour');}
        else if(!['radius_mm','line_width_mm'].includes(key)||typeof val!=='number'||!Number.isFinite(val)||val<=0||val>10)throw Error('Invalid override size');
      }
      const target=Object.hasOwn(base.editor.targets,name)?base.editor.targets[name]:null;
      if(!target||target.kind!==edits.kind||Object.keys(edits).some(k=>k!=='kind'&&!Object.hasOwn(target.defaults,k)))orphaned.push(name);
    }
    orphaned.sort();if(orphaned.length&&missing==='error')throw Error('Orphaned visual overrides: '+orphaned.join(', '));
    for(const name of orphaned)delete copy.targets[name];
    return {value:copy,report:{orphaned_targets:orphaned,missing_policy:missing}};
  }
  reconcile(base,missing){return this.validate(this.value,base,missing);}
  decorate(base,value){
    value=this.validate(value,base).value;const result=structuredClone(base);
    for(const [name,edits] of Object.entries(value.targets)){
      const layers=base.editor.targets[name].layers;
      for(const layer of result.layers){
        if(!layers.includes(layer.name))continue;
        if('color' in edits)layer.color=edits.color;
        if('radius_mm' in edits&&'radius' in layer)layer.radius=edits.radius_mm;
        for(const mark of layer.marks??[]){
          if(mark.reference)continue;
          if('color' in edits)mark.color=edits.color;
          if(mark.kind==='circle'&&'radius_mm' in edits)mark.geometry[2]=edits.radius_mm;
          if(mark.kind==='line'&&'line_width_mm' in edits){
            if('selected_width' in mark)mark.selected_width+=edits.line_width_mm-mark.width;
            mark.width=edits.line_width_mm;
          }
        }
      }
      if(result.compiled){
        const c=result.compiled,svg=new DOMParser().parseFromString(c.frame,'image/svg+xml').documentElement;
        for(const node of svg.querySelectorAll('[data-inklet-linked]')){
          const index=Number(node.getAttribute('data-inklet-linked'));
          if(!layers.includes(c.native_layers[index])||!c.native_marks[index].length)continue;
          if('color' in edits)node.setAttribute(node.localName==='line'?'stroke':'fill',edits.color);
          if(node.localName==='line'&&'line_width_mm' in edits)node.setAttribute('stroke-width',edits.line_width_mm);
        }
        c.frame=new XMLSerializer().serializeToString(svg);
        for(const batch of c.batches){
          if(!layers.includes(batch.layer))continue;
          if('color' in edits){
            const rgb=[1,3,5].map(start=>parseInt(edits.color.slice(start,start+2),16));
            batch.palette=batch.palette.map(p=>[...rgb,p[3]]);batch.fills=batch.fills.map(()=>edits.color);
          }
          if('radius_mm' in edits){
            const bytes=Uint8Array.from(atob(c.buffers[batch.buffer]),ch=>ch.charCodeAt(0)),view=new DataView(bytes.buffer);
            let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
            for(let k=0;k<batch.count;k++){
              const o=k*36,x=view.getFloat64(o,true),y=view.getFloat64(o+8,true),r=edits.radius_mm;
              view.setFloat64(o+16,r,true);x0=Math.min(x0,x-r);y0=Math.min(y0,y-r);x1=Math.max(x1,x+r);y1=Math.max(y1,y+r);
            }
            const chunks=[];for(let k=0;k<bytes.length;k+=8192)chunks.push(String.fromCharCode(...bytes.subarray(k,k+8192)));
            c.buffers[batch.buffer]=btoa(chunks.join(''));batch.box=[x0-1,y0-1,x1-x0+2,y1-y0+2];
          }
        }
      }
    }
    return result;
  }
  async initialize(){
    this.value=this.validate(this.value,scene).value;
    if(Object.keys(this.value.targets).length)await replaceRenderer(this.decorate(scene,this.value),runtime.state());
    this.refresh();
  }
  async commit(value,operation){
    const next=this.validate(value,scene).value;
    if(JSON.stringify(next)===JSON.stringify(this.value))return;
    await replaceRenderer(this.decorate(scene,next),runtime.state());
    if(operation==='undo'){this.past.pop();this.future.push(this.value);}
    else if(operation==='redo'){this.future.pop();this.past.push(this.value);}
    else{this.past.push(this.value);this.future=[];if(this.past.length>100)this.past.shift();}
    this.value=next;this.refresh();message();
  }
  async command(value,operation){
    if(busy)throw Error('Wait for the current operation to finish');
    setBusy(true);try{await this.commit(value,operation);}finally{setBusy(false);}
  }
  apply(value){return this.command(value,'apply');}
  undo(){if(busy)return Promise.reject(Error('Wait for the current operation to finish'));return this.past.length?this.command(this.past.at(-1),'undo'):Promise.resolve();}
  redo(){if(busy)return Promise.reject(Error('Wait for the current operation to finish'));return this.future.length?this.command(this.future.at(-1),'redo'):Promise.resolve();}
  switched(value){this.value=structuredClone(value);this.past=[];this.future=[];this.refresh();}
  refresh(){
    const selected=this.target.value;this.target.replaceChildren();
    for(const name of Object.keys(scene.editor.targets)){const option=document.createElement('option');option.value=name;option.textContent=name;this.target.append(option);}
    if(Object.hasOwn(scene.editor.targets,selected))this.target.value=selected;
    this.fields();
  }
  fields(){
    const target=scene.editor.targets[this.target.value],edits=this.value.targets[this.target.value]??{};
    for(const [key,input] of Object.entries(this.inputs)){input.disabled=!target||!Object.hasOwn(target.defaults,key);input.value=input.disabled?'':edits[key]??target.defaults[key];}
    document.getElementById('edit-apply').disabled=!target;document.getElementById('edit-reset').disabled=!target;
    document.getElementById('edit-undo').disabled=!this.past.length;document.getElementById('edit-redo').disabled=!this.future.length;
    document.getElementById('edit-status').textContent=`${Object.keys(this.value.targets).length} edited styles · ${this.past.length} undo steps. Revision changes retain compatible styles and start a new undo history.`;
  }
};
