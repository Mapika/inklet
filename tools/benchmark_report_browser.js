(async()=>{
  await inkletDocument.ready;
  const r=inklet, rows=r.scene.row_ids, first=rows[0], visible=rows.slice(0,Math.ceil(rows.length/2));
  const frames=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  const assert=(condition,message)=>{if(!condition)throw Error(message);};
  await frames();
  const records={ready:[performance.now()]};
  async function measure(name,action){
    const start=performance.now();action();const submitted=performance.now()-start;
    await frames();
    (records[name+'_submit']??=[]).push(submitted/1000);
    (records[name+'_settled']??=[]).push((performance.now()-start)/1000);
  }
  records.ready[0]/=1000;
  const original=r.state();
  for(let n=0;n<7;n++){
    r.select([]);r.setVisible(null);await frames();
    await measure('select',()=>r.select([first]));
    assert(r.selected.has(first),'selection was lost');
    await measure('filter',()=>r.setVisible(visible));
    assert(r.state().selection.visible_ids.length===visible.length,'filter was lost');
    const saved=JSON.parse(JSON.stringify(r.state()));
    r.select([]);r.setVisible(null);
    await measure('restore',()=>r.loadState(saved));
    assert(r.selected.has(first)&&r.state().selection.visible_ids.length===visible.length,'restore differs');
    const v=original.viewport;
    await measure('viewport',()=>r.setViewport([v[0],v[1],v[2]*.8,v[3]*.8]));
    assert(Math.abs(r.state().viewport[2]-v[2]*.8)<1e-8,'viewport differs');
    r.loadState(original);await frames();
    await measure('export',()=>{assert(r.exportSVG().includes('<svg'),'SVG export missing');});
  }
  r.loadState(original);
  assert(JSON.stringify(r.state())===JSON.stringify(original),'original state changed');
  const before=JSON.stringify(r.state());let rejected=false;
  try{r.loadState({...original,viewport:[0,0,0,1]});}catch{rejected=true;}
  assert(rejected&&JSON.stringify(r.state())===before,'invalid state changed the figure');
  return {records,backend:r.backend,rows:rows.length,user_agent:navigator.userAgent,dpr:devicePixelRatio,
    viewport:[innerWidth,innerHeight],svg:r.exportSVG(),state:r.state(),
    external_resources:performance.getEntriesByType('resource').filter(e=>/^https?:/.test(e.name)&&new URL(e.name).origin!==location.origin).map(e=>e.name)};
})()
