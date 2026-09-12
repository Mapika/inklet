// Keep the established identity, picking, state and revision contracts. Only
// mark execution changes; measured axes and selection outlines remain on top.
class CompiledFigureRenderer extends ScatterRenderer{
  setBackend(name){
    if(!['auto','webgl2','canvas','svg'].includes(name))throw Error('Unsupported backend');
    this.backend=name;this.render();
  }
  render(){
    if(this.disposed||!this.frameImage?.complete||!this.frameImage.naturalWidth)return;
    if(!this.compiled){
      this.compiledHost=document.createElement('div');
      this.compiledHost.style.cssText='position:absolute;inset:0;pointer-events:none';
      this.host.insertBefore(this.compiledHost,this.svg);
      this.compiledHost.addEventListener('inklet-render',event=>{
        if(this.host.id!=='stage')return;
        const report=event.detail,counts={};
        for(const layer of report.layers)counts[layer.backend]=(counts[layer.backend]??0)+1;
        const reasons=[...new Set(report.layers.map(layer=>layer.reason).filter(Boolean))];
        document.getElementById('renderer-status').textContent=(Object.entries(counts).map(([backend,count])=>`${count} ${backend} layers`).join(' · ')||'Native SVG')+
          (reasons.length?' · '+reasons.join('; '):'')+(report.layers.some(layer=>layer.reducedResolution)?' · display resolution limited':'');
      });
      this.compiled=new CompiledSceneViewer(this.compiledHost,{...this.scene.compiled,backend:this.backend});
      this.nativeMarks=[...this.compiled.svg.querySelectorAll('[data-inklet-linked]')];
      this.compiledVisible=undefined;
    }
    this.svg.setAttribute('viewBox',this.viewport.join(' '));
    this.canvas.style.display='none';this.markGroup.replaceChildren();
    // The transparent compiled mark surface sits beneath the measured frame.
    for(const node of this.frameNodes)node.style.display=node===this.background?'none':'';
    if(this.compiled.backend!==this.backend)this.compiled.setBackend(this.backend);
    if(this.compiledVisible!==this.visible){
      this.compiled.setMarkerVisibility(this.scene.compiled.batches.map(batch=>this.visible===null?null:
        Uint8Array.from(batch.row_ids,ids=>ids.every(id=>this.shown(id))?1:0)));
      for(const node of this.nativeMarks){
        const ids=this.scene.compiled.native_marks[Number(node.getAttribute('data-inklet-linked'))];
        node.style.display=ids.every(id=>this.shown(id))?'':'none';
      }
      this.compiledVisible=this.visible;
    }
    this.compiled.setViewport(this.viewport);this.renderSelection();
  }
  renderSelection(){
    if(this.disposed)return;
    this.overlay.replaceChildren();this.svgMarks(this.overlay,true,'selection-clip-');
  }
  report(){return this.compiled?.report()??null;}
  dispose(){
    if(this.disposed)return;
    this.compiled?.dispose();this.compiledHost?.remove();super.dispose();
  }
}
DocumentRenderer=CompiledFigureRenderer;
window.CompiledFigureRenderer=CompiledFigureRenderer;
