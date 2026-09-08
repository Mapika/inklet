"""Statistical views preserve row identity and explicit reference populations."""
from dataclasses import FrozenInstanceError
import html
import json
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

import pytest

from inklet.experimental.browser import (
    BrowserFigure, ECDFView, FacetView, IntervalView, RevisionOption, TimeAxis,
)
from inklet.experimental.selection import KeyedTable, SelectionState


def observations():
    return KeyedTable('statistics', dict(
        id=list('abcdefg'), x=[0, 1, 2, 3, None, 5, 6],
        y=[3, 1, 3, None, 2, 2, 4],
        lower=[2, 1, None, 0, 1, 1, 3], upper=[4, 1, 4, 5, 3, None, 5],
        group=['north', 'south', 'north', 'north', 'south', 'north', 'other'],
    ))


def interval(**kwargs):
    args=dict(name='uncertainty', x='x', y='y', x_domain=(-1, 7), y_domain=(0, 6),
              lower='lower', upper='upper', interval_label='Reported range')
    args.update(kwargs)
    return IntervalView(**args)


def scene(reverse=False):
    return BrowserFigure(observations(), [
        interval(x_domain=(7, -1) if reverse else (-1, 7),
                 y_domain=(6, 0) if reverse else (0, 6)),
        ECDFView('distribution', 'y', (6, 0) if reverse else (0, 6)),
    ])


def project(layer, x, y, xd, yd):
    left, top, width, height=layer['clip']
    return [left+(x-xd[0])/(xd[1]-xd[0])*width,
            top+(yd[1]-y)/(yd[1]-yd[0])*height]


def circles(layer):
    return [mark for mark in layer['marks'] if mark['kind']=='circle']


def references(layer):
    return [mark for mark in layer['marks'] if mark.get('reference')]


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('orientation', ['vertical', 'horizontal'])
def test_intervals_project_absolute_bounds_and_keep_each_row_identity(reverse, orientation):
    xd=(7, -1) if reverse else (-1, 7); yd=(6, 0) if reverse else (0, 6)
    args=dict(x_domain=xd, y_domain=yd)
    if orientation=='horizontal':
        args.update(x='y', y='x', x_domain=yd, y_domain=xd)
    view=interval(orientation=orientation, **args)
    layer=BrowserFigure(observations(), [view]).payload()['layers'][0]
    assert [mark['ids'] for mark in circles(layer)]==[[key] for key in 'abcfg']
    assert [point[0] for point in layer['points']]==list('abcfg')
    assert layer['missing']==2
    assert layer['statistics']['kind']=='interval'
    assert layer['statistics']['label']=='Reported range'
    assert layer['statistics']['missing_intervals']==2
    for key, x, y, lo, hi in zip(observations().row_ids, observations().columns['x'],
                                observations().columns['y'], observations().columns['lower'],
                                observations().columns['upper']):
        marks=[mark for mark in layer['marks'] if key in mark['ids']]
        if x is None or y is None:
            assert marks==[]
            continue
        center=next(mark for mark in marks if mark['kind']=='circle')
        px, py=project(layer, x, y, xd, yd) if orientation=='vertical' else project(layer, y, x, yd, xd)
        assert center['geometry']==pytest.approx([px, py, .6], abs=1e-6)
        pieces=[mark for mark in marks if mark['kind']=='line']
        if lo is None or hi is None:
            assert pieces==[]
            continue
        assert len(pieces)==3
        assert all(mark['ids']==[key,key] and mark['width']==.3 for mark in pieces)
        a=project(layer, x, lo, xd, yd) if orientation=='vertical' else project(layer, lo, x, yd, xd)
        b=project(layer, x, hi, xd, yd) if orientation=='vertical' else project(layer, hi, x, yd, xd)
        # The stem joins absolute bounds, including a valid zero-length range.
        assert any(mark['geometry']==pytest.approx(a+b, abs=1e-6) for mark in pieces)
        caps=[mark for mark in pieces if mark['geometry']!=pytest.approx(a+b, abs=1e-6)]
        assert len(caps)==2
        for cap in caps:
            g=cap['geometry']
            assert abs(g[2]-g[0] if orientation=='vertical' else g[3]-g[1])==pytest.approx(2,abs=1e-6)


@pytest.mark.parametrize('kwargs', [
    {'lower':''}, {'upper':None}, {'interval_label':''}, {'orientation':'diagonal'},
    {'cap_width_mm':-1}, {'cap_width_mm':True}, {'radius_mm':0},
    {'line_width_mm':float('inf')}, {'color':'red'},
])
def test_invalid_interval_definitions(kwargs):
    with pytest.raises((ValueError,TypeError)): interval(**kwargs)


@pytest.mark.parametrize('lo, center, hi', [(3,2,4), (1,2,1), (3,2,1), ('1',2,3), (1,2,True)])
def test_invalid_numeric_bounds_rejected(lo,center,hi):
    table=KeyedTable('statistics',dict(id=['a'],x=[0],y=[center],lower=[lo],upper=[hi]))
    with pytest.raises(ValueError): BrowserFigure(table,[interval()])


def test_interval_requires_explicit_bounds_and_meaning():
    with pytest.raises(TypeError): IntervalView('uncertainty','x','y',(0,1),(0,1))
    view=interval()
    with pytest.raises(FrozenInstanceError): view.interval_label='Changed'
    table=KeyedTable('statistics',dict(id=['a'],x=[0],y=[1],lower=[0]))
    with pytest.raises(ValueError): BrowserFigure(table,[view])


@pytest.mark.parametrize('x,y', [(None,2),(0,None),(None,None)])
def test_reversed_bounds_rejected_even_for_rows_without_centers(x,y):
    table=KeyedTable('statistics',dict(id=['a'],x=[x],y=[y],lower=[3],upper=[1]))
    with pytest.raises(ValueError): BrowserFigure(table,[interval()])


@pytest.mark.parametrize('orientation',['vertical','horizontal'])
def test_temporal_position_axis_supported_but_temporal_intervals_rejected(orientation):
    axis=TimeAxis(('2024-02-28','2024-03-02'))
    table=KeyedTable('statistics',dict(id=['a','b'],x=['2024-02-28','2024-02-29'],
                                    y=[2,3],lower=[1,2],upper=[3,4]))
    args=dict(orientation=orientation,x_domain=axis)
    if orientation=='horizontal':args.update(x='y',y='x',x_domain=(0,6),y_domain=axis)
    layer=BrowserFigure(table,[interval(**args)]).payload()['layers'][0]
    positions=[mark['geometry'][0 if orientation=='vertical' else 1] for mark in circles(layer)]
    extent=layer['clip'][2 if orientation=='vertical' else 3]
    assert abs(positions[1]-positions[0])==pytest.approx(extent/3,abs=1e-6)
    args.update(y_domain=axis if orientation=='vertical' else (0,6),x_domain=(0,6) if orientation=='vertical' else axis)
    with pytest.raises(ValueError): interval(**args)


@pytest.mark.parametrize('reverse',[False,True])
def test_ecdf_ties_use_maximum_rank_and_source_order_is_unchanged(reverse):
    figure=scene(reverse); payload=figure.payload(); layer=payload['layers'][1]
    assert payload['row_ids']==list(observations().row_ids)
    assert payload['columns']=={key:list(values) for key,values in observations().columns.items()}
    assert payload['data_digest']==observations().digest
    assert [mark['ids'] for mark in circles(layer)]==[[key] for key in 'abcefg']
    assert layer['missing']==1
    assert layer['statistics']['kind']=='ecdf'
    assert layer['statistics']['n']==6 and layer['statistics']['missing']==1
    ranks={'a':5/6,'b':1/6,'c':5/6,'e':3/6,'f':3/6,'g':1}
    values=dict(zip(observations().row_ids,observations().columns['y']))
    for mark in circles(layer):
        key=mark['ids'][0]
        assert mark['geometry'][:2]==pytest.approx(project(layer,values[key],ranks[key],(6,0) if reverse else (0,6),(0,1.05)),abs=1e-6)
    assert references(layer)
    assert all(mark['ids']==[] and mark['kind']=='line' for mark in references(layer))
    assert all(mark.get('color')!=layer['color'] for mark in references(layer))


@pytest.mark.parametrize('values',[[],[None,None],[2],[2,2,2]])
def test_ecdf_empty_and_single_distinct_value(values):
    table=KeyedTable('statistics',dict(id=[f'row-{n}' for n in range(len(values))],y=values))
    layer=BrowserFigure(table,[ECDFView('distribution','y',(0,4))]).payload()['layers'][0]
    n=sum(value is not None for value in values)
    assert len(circles(layer))==n
    assert layer['missing']==len(values)-n
    assert layer['statistics']['n']==n
    if not n:
        assert layer['marks']==[]
    else:
        assert all(mark['geometry'][1]==pytest.approx(project(layer,2,1,(0,4),(0,1.05))[1],abs=1e-6) for mark in circles(layer))


@pytest.mark.parametrize('value',['2024-01-01','3',True])
def test_ecdf_numeric_values_are_explicit(value):
    table=KeyedTable('statistics',dict(id=['a'],y=[value]))
    with pytest.raises(ValueError): BrowserFigure(table,[ECDFView('distribution','y',(0,6))])


def test_ecdf_temporal_axis_rejected():
    with pytest.raises((ValueError,TypeError)):
        ECDFView('distribution','y',TimeAxis(('2024-01-01','2024-01-02')))


@pytest.mark.parametrize('domain',[(0,6),(6,0),(1.5,3.5),(8,9),(-3,-2)])
def test_ecdf_reference_is_a_right_continuous_staircase_across_domain_clipping(domain):
    layer=BrowserFigure(observations(),[ECDFView('distribution','y',domain)]).payload()['layers'][0]
    # The domain is only a viewport: it must not change ranks or discard tails.
    expected=[(min(*domain,1),0,1,0),(1,0,1,1/6),
              (1,1/6,2,1/6),(2,1/6,2,.5),
              (2,.5,3,.5),(3,.5,3,5/6),
              (3,5/6,4,5/6),(4,5/6,4,1),
              (4,1,max(*domain,4),1)]
    actual=references(layer)
    assert len(actual)==len(expected)
    for mark,(a,b,c,d) in zip(actual,expected):
        assert mark['geometry']==pytest.approx(project(layer,a,b,domain,(0,1.05))+project(layer,c,d,domain,(0,1.05)),abs=1e-6)
    assert layer['statistics']['n']==6


def test_interval_method_label_cannot_inject_script():
    label='</script><script>window.injected=true</script>'
    figure=BrowserFigure(observations(),[interval(interval_label=label)])
    assert figure.payload()['layers'][0]['statistics']['label']==label
    assert '<script>window.injected=true</script>' not in figure.to_html()


def test_facet_denominators_are_per_category_and_empty_panels_survive():
    definitions=[FacetView(ECDFView('distribution','y',(0,6)),'group',('south','north','empty')),
                 FacetView(interval(),'group',('south','north','empty'))]
    figure=BrowserFigure(observations(),definitions,columns=3,width=240)
    layers=figure.payload()['layers']
    assert [len(circles(layer)) for layer in layers]==[2,3,0,1,3,0]
    assert [layer['statistics']['n'] for layer in layers[:3]]==[2,3,0]
    assert layers[2]['marks']==layers[5]['marks']==[]
    assert [point[0] for point in layers[0]['points']]==list('be')
    assert [point[0] for point in layers[1]['points']]==list('acf')
    for layer,ranks in zip(layers[:2],[{'b':.5,'e':1},{'a':1,'c':1,'f':1/3}]):
        for mark in circles(layer):
            expected_y=project(layer,0,ranks[mark['ids'][0]],(0,6),(0,1.05))[1]
            assert mark['geometry'][1]==pytest.approx(expected_y,abs=1e-6)
    assert figure.payload()['facet_groups'][0]['unassigned_ids']==['g']


def svg_geometry(svg):
    root=ET.fromstring(svg); result=[]
    for group in (root[1],root[-1]):
        for element in group.iter():
            tag=element.tag.rsplit('}',1)[-1]
            if tag not in ('line','circle') or ('fill' not in element.attrib and 'stroke' not in element.attrib):continue
            attrs={}
            for key,value in element.attrib.items():
                try:attrs[key]=float(value)
                except ValueError:attrs[key]=value
            result.append((tag,attrs))
    return root.attrib['viewBox'].split(),result


def test_filtering_preserves_reference_population_and_replacement_recomputes_it():
    original=scene(); before=original.payload()
    state=original.state(SelectionState.for_table(original.table,selected=['a','c'],visible=['a']))
    svg=ET.fromstring(original.to_svg(state)); ns={'s':'http://www.w3.org/2000/svg'}
    # Only two row centers remain, plus their selected overlays; reference
    # lines remain even when every row circle is hidden.
    assert len(svg.findall('.//s:circle',ns))==4
    empty=original.to_svg(original.state(SelectionState.for_table(original.table,visible=[])))
    empty_root=ET.fromstring(empty)
    assert empty_root.findall('.//s:circle',ns)==[]
    assert len(empty_root.findall('.//s:line',ns))==len(references(before['layers'][1]))
    revised=original.replace_data(KeyedTable(original.table.name,original.table.subset(['a','b','d'])),state=state,missing='drop')
    assert revised.state()['selection']['selected_ids']==['a']
    assert revised.state()['selection']['visible_ids']==['a']
    assert original.payload()==before
    layer=revised.figure.payload()['layers'][1]
    assert [mark['ids'] for mark in circles(layer)]==[['a'],['b']]
    assert circles(layer)[0]['geometry'][1]==pytest.approx(project(layer,3,1,(0,6),(0,1.05))[1],abs=1e-6)
    with pytest.raises(ValueError): revised.figure.validate_state(state)


CHECKS=r'''
(async()=>{
 await inkletDocument.ready;
 const ok=(c,m)=>{if(!c)throw Error(m);}, exports=[];let queries=0;
 ok(!document.getElementById('statistics-status').hidden,'statistical methods hidden');
 ok(JSON.parse(document.getElementById('statistics-report').textContent)[1].n===6,'original population metadata');
 function oracle(r,x,y,tol){
  let best=null,score=Infinity;
  for(const [layerIndex,l] of r.scene.layers.entries()){
   const b=l.clip;if(x<b[0]||x>b[0]+b[2]||y<b[1]||y>b[1]+b[3])continue;
   for(const m of l.marks){
    if(m.reference||!m.ids.length||!m.ids.every(id=>r.visible===null||r.visible.has(id)))continue;
    const g=m.geometry;let d,id=m.ids[0],limit=tol;
    if(m.kind==='circle'){d=Math.hypot(x-g[0],y-g[1]);limit+=g[2];}
    else{const dx=g[2]-g[0],dy=g[3]-g[1],den=dx*dx+dy*dy;
     const t=den?Math.max(0,Math.min(1,((x-g[0])*dx+(y-g[1])*dy)/den)):1;
     d=Math.hypot(x-g[0]-t*dx,y-g[1]-t*dy);id=m.ids[t<.5-1e-12?0:1];limit+=m.width/2;}
    if(d<=limit&&(d<score-1e-10||Math.abs(d-score)<1e-10)){score=d;best={id,layerIndex};}
   }
  }return best;
 }
 for(const backend of ['svg','canvas','hybrid']){
  const r=inklet;r.setBackend(backend);
  for(const visible of [null,['a','b','f'],[]]){
   r.setVisible(visible);r.select(['a','b','d']);
   const positions=[];
   for(const l of r.scene.layers)for(const m of l.marks){
    const g=m.geometry;positions.push([g[0],g[1]]);
    if(m.kind==='line')positions.push([(g[0]+g[2])/2,(g[1]+g[3])/2]);
   }
   for(let n=0;n<300;n++)positions.push([(n*37.317)%r.scene.width,(n*17.219)%r.scene.height]);
   for(const [x,y] of positions)for(const tolerance of [0,.4]){
    const want=oracle(r,x,y,tolerance),got=r.pick(x,y,tolerance);queries++;
    ok((want?.id??null)===(got?.id??null)&&(want?.layerIndex??null)===(got?.layerIndex??null),'statistical pick mismatch '+JSON.stringify({x,y,want,got:got&&{id:got.id,layerIndex:got.layerIndex}}));
   }
   r.setViewport([5,8,r.scene.width/1.3,r.scene.height/1.3]);
   const state=r.state();r.select([]);r.loadState(state);
   exports.push({state,svg:r.exportSVG()});
   if(visible&&visible.length===0){
    ok(!r.overlay.querySelector('circle,line'),'hidden selected rows or reference lines highlighted');
    const svg=new DOMParser().parseFromString(r.exportSVG(),'image/svg+xml');
    ok(svg.documentElement.children[1].querySelectorAll('line').length===r.scene.layers[1].marks.filter(m=>m.reference).length,'empty filtering removed reference population');
   }
  }
 }
 inklet.setVisible(['a','b']);inklet.select(['a','c']);
 await inkletDocument.switchRevision(1,{missing:'drop'});
 ok(inklet.selected.size===1&&inklet.selected.has('a'),'revision selection rebase');
 ok(inklet.scene.layers[1].points.map(p=>p[0]).join('')==='ab','ECDF population did not rebuild');
 ok(JSON.parse(document.getElementById('statistics-report').textContent)[1].n===2,'revised population metadata');
 return {queries,exports,revised:{state:inklet.state(),svg:inklet.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


@pytest.mark.parametrize('dpr,reverse',[(1,False),(2,True)])
def test_browser_reference_picking_clipping_and_export_parity(tmp_path,dpr,reverse):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    # Multiple centers, stems and caps extend beyond these domains. Picking
    # must use the measured clip even with a nonzero tolerance near its edge.
    original=BrowserFigure(observations(),[
        interval(x_domain=(5,0) if reverse else (0,5),y_domain=(4,1) if reverse else (1,4)),
        ECDFView('distribution','y',(3.5,1.5) if reverse else (1.5,3.5)),
    ])
    revised=original.replace_data(KeyedTable(original.table.name,original.table.subset(['a','b','d']))).figure
    page=tmp_path/'index.html'
    page.write_text(original.to_html(revisions=[RevisionOption('Subset',revised,'Explicit subset')])
                    .replace('</html>','<script>'+CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S)
    assert match,result.stdout[-3000:]
    report=json.loads(html.unescape(match[1])); assert 'error' not in report,report
    assert report['queries']>5000
    for exported in report['exports']:
        assert svg_geometry(original.to_svg(exported['state']))==svg_geometry(exported['svg'])
    assert svg_geometry(revised.to_svg(report['revised']['state']))==svg_geometry(report['revised']['svg'])


HOVER_CHECKS=r'''
(async()=>{
 await inkletDocument.ready;
 const ok=(c,m)=>{if(!c)throw Error(m);}, errors=[],hovers=[];
 window.addEventListener('error',event=>{errors.push(event.message);event.preventDefault();});
 const expected={a:.5,b:1,c:1},r=inklet,stage=document.getElementById('stage');
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);
  for(const layer of r.scene.layers){
   for(const [id,x,y] of layer.points){
    const point=new DOMPoint(x,y).matrixTransform(r.svg.getScreenCTM());
    // Dispatch through the DOM so the actual pointer handler and tooltip
    // formatting execute. Calling pick() alone cannot catch these errors.
    stage.dispatchEvent(new PointerEvent('pointermove',{
     bubbles:true,clientX:point.x,clientY:point.y,pointerId:1,pointerType:'mouse',
    }));
    const text=document.getElementById('hover').textContent;
    ok(errors.length===0,'pointermove exception: '+errors.join('; '));
    ok(text.startsWith(id+' · '),'hover lost source row identity: '+text);
    if(layer.statistics?.kind==='ecdf'){
     ok(text.includes('Cumulative fraction: '+expected[id]),'ECDF hover needs derived fraction: '+text);
     ok(!text.includes('999')&&!text.includes('sentinel'),'source column overrode derived ECDF fraction: '+text);
    }else{
     const raw=r.scene.columns.when[r.rowIndex.get(id)];
     ok(text.includes('when: '+raw),'temporal hover lost original date or UTC offset: '+text);
    }
    hovers.push(text);
   }
  }
 }
 return {hovers,errors};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


@pytest.mark.parametrize('collision',[False,True])
@pytest.mark.parametrize('mode',['date','utc'])
def test_dispatched_pointer_hover_handles_derived_ecdf_and_temporal_values(tmp_path,collision,mode):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    dates=['2024-02-28','2024-02-29','2024-03-01','2024-03-02']
    times=dates if mode=='date' else [value+'T10:30:00+01:00' for value in dates]
    endpoints=['2024-02-27','2024-03-03']
    domain=endpoints if mode=='date' else [value+'T10:30:00+01:00' for value in endpoints]
    columns=dict(id=list('abcd'),when=times,y=[1,3,2,None],lower=[0,2,1,None],
                 upper=[2,4,3,None],group=['north','south','north','south'])
    if collision:columns['ecdf_fraction']=[999,'sentinel',999,None]
    table=KeyedTable('hover',columns)
    figure=BrowserFigure(table,[
        FacetView(ECDFView('distribution','y',(0,4)),'group',('north','south')),
        interval(name='temporal',x='when',x_domain=TimeAxis(domain,mode=mode)),
    ],width=240,columns=3)
    layers=figure.payload()['layers']
    assert layers[0]['derived_y']==[.5,None,1,None]
    assert layers[1]['derived_y']==[None,1,None,None]
    assert 'derived_y' not in layers[2]
    if collision:assert figure.payload()['columns']['ecdf_fraction']==columns['ecdf_fraction']
    page=tmp_path/'index.html'
    page.write_text(figure.to_html().replace('</html>','<script>'+HOVER_CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S)
    assert match,result.stdout[-3000:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    assert report['errors']==[] and len(report['hovers'])==18


EDGE_HOVER_CHECKS=r'''
(async()=>{
 await inkletDocument.ready;
 const ok=(c,m)=>{if(!c)throw Error(m);},r=inklet,stage=document.getElementById('stage');
 const layer=r.scene.layers[2],[id,x,y]=layer.points[0];let checked=0;
 ok(x===layer.clip[0],'fixture must place the temporal point at the exact left boundary');
 function hover(px,py){
  const client=new DOMPoint(px,py).matrixTransform(r.svg.getScreenCTM());
  stage.dispatchEvent(new PointerEvent('pointermove',{
   bubbles:true,clientX:client.x,clientY:client.y,pointerId:1,pointerType:'mouse',
  }));
  return document.getElementById('hover').textContent;
 }
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);
  for(const viewport of [[0,0,r.scene.width,r.scene.height],[.23,.17,r.scene.width/1.3,r.scene.height/1.3]]){
   r.setViewport(viewport);
   const text=hover(x,y);
   ok(text.startsWith(id+' · ')&&text.includes('when: 2024-02-28'),'exact-edge roundtrip lost hover: '+text);
   // These positions are inside the marker radius and picking tolerance,
   // but outside the measured data area. Neither may become a row hit.
   ok(r.pick(x-1e-12,y,1)===null,'direct picking must retain strict clipping');
   ok(r.pick(x-.001,y,1)===null,'outside point picked despite clip');
   ok(hover(x-.001,y)==='Point at a mark to inspect its row ID.','pointer snapping admitted a genuinely outside point');
   checked++;
  }
 }
 return {checked};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def test_exact_clip_edge_pointer_roundtrip_keeps_hover_but_rejects_outside(tmp_path):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    dates=['2024-02-28','2024-02-29','2024-03-01','2024-03-02']
    table=KeyedTable('edge-hover',dict(id=list('abcd'),when=dates,y=[1,3,2,None],
        lower=[0,2,1,None],upper=[2,4,3,None],group=['north','south','north','south']))
    figure=BrowserFigure(table,[
        FacetView(ECDFView('distribution','y',(0,4)),'group',('north','south')),
        interval(name='temporal',x='when',x_domain=TimeAxis((dates[0],dates[-1]))),
    ],width=240,columns=3)
    page=tmp_path/'index.html'
    page.write_text(figure.to_html().replace('</html>','<script>'+EDGE_HOVER_CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S)
    assert match,result.stdout[-3000:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    assert report['checked']==6
