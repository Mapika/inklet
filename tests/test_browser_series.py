"""Wide series preserve entity IDs, sample values and static/browser geometry."""
import html
import json
import re
import shutil
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from inklet.experimental.browser import BrowserFigure, FacetView, SeriesView, TimeAxis
from inklet.experimental.selection import KeyedTable, SelectionState


def table():
    return KeyedTable('entities',dict(id=['a','b'],jan=[1,4],feb=[None,3],mar=[2,2],group=['A','B']))


def view(**kwargs):
    options=dict(name='history',samples=[(1,'jan'),(2,'feb'),(3,'mar')],x_domain=(0,4),y_domain=(0,5))
    options.update(kwargs);return SeriesView(**options)


@pytest.mark.parametrize('reverse',[False,True])
def test_wide_samples_have_independent_geometry_and_one_identity(reverse):
    v=view(x_domain=(4,0) if reverse else (0,4),y_domain=(5,0) if reverse else (0,5))
    figure=BrowserFigure(table(),[v]);layer=figure.payload()['layers'][0]
    lines=[m for m in layer['marks'] if m['kind']=='line']
    points=[m for m in layer['marks'] if m['kind']=='circle']
    assert len(lines)==2 and all(m['ids']==['b','b'] for m in lines)
    assert len(points)==5 and layer['missing']==1
    for mark in points:
        x,y=mark['sample']['x'],mark['sample']['y'];left,top,w,h=layer['clip']
        assert mark['geometry'][:2]==pytest.approx([left+(x-v.x_domain[0])/(v.x_domain[1]-v.x_domain[0])*w,
            top+(v.y_domain[1]-y)/(v.y_domain[1]-v.y_domain[0])*h],abs=1e-6)
    state=figure.state(SelectionState.for_table(table(),selected=['a'],visible=['b']))
    assert 'stroke="#bd5636"' not in figure.to_svg(state)
    assert figure.validate_state(state)[0].selected_ids==('a',)


@pytest.mark.parametrize('kwargs',[
    {'samples':[]},{'samples':'bad'},{'samples':{(1,'jan')}},{'samples':[(1,'jan'),(1,'feb')]},
    {'samples':[(2,'jan'),(1,'feb')]},{'samples':[(1,'jan'),(2,'jan')]},
    {'samples':[(None,'jan')]},{'samples':[(True,'jan')]},{'samples':[(float('inf'),'jan')]},
    {'samples':[(1,'')]},{'samples':[(1,3)]},{'samples':[(1,)]},
    {'samples':[(1,'jan','extra')]},{'radius_mm':0},{'line_width_mm':0},
    {'color':'red'},{'max_gap_seconds':1},{'y_domain':TimeAxis(('2025-01-01','2025-02-01'))},
])
def test_invalid_series_contract(kwargs):
    with pytest.raises(ValueError): view(**kwargs)


def test_snapshot_missing_columns_and_nonnumeric_cells():
    samples=[[1,'jan'],[2,'feb']];v=view(samples=samples);samples[0][1]='changed'
    assert v.samples==((1,'jan'),(2,'feb'))
    with pytest.raises(FrozenInstanceError):v.samples=()
    with pytest.raises(ValueError,match='unknown series column'):BrowserFigure(table(),[view(samples=[(1,'unknown')])])
    bad=KeyedTable('entities',dict(id=['a'],jan=['1']))
    with pytest.raises(ValueError,match="column 'jan', row 0"):BrowserFigure(bad,[view(samples=[(1,'jan')])])


def test_temporal_positions_precision_gaps_and_duplicate_instants():
    axis=TimeAxis(('2025-01-01T00:00:00Z','2025-01-01T00:00:03Z'),mode='utc')
    samples=[('2025-01-01T01:00:00+01:00','jan'),('2025-01-01T00:00:01.001Z','feb'),
             ('2025-01-01T00:00:02.003Z','mar')]
    layer=BrowserFigure(table(),[view(samples=samples,x_domain=axis,max_gap_seconds=1.001)]).payload()['layers'][0]
    lines=[m for m in layer['marks'] if m['kind']=='line']
    assert len(lines)==1 and layer['time_gaps']==1
    assert lines[0]['samples'][0]['x']=='2025-01-01T00:00:00.000Z'
    with pytest.raises(ValueError,match='strictly increasing'):
        view(samples=[samples[0],('2025-01-01T00:00:00Z','feb')],x_domain=axis)
    with pytest.raises(ValueError):view(samples=[(None,'jan')],x_domain=axis)


def test_series_facets_empty_rows_and_replacement():
    original=BrowserFigure(table(),[FacetView(view(),'group',('A','B','Empty'))])
    layers=original.payload()['layers']
    assert len(layers[0]['marks'])==2 and len(layers[1]['marks'])==5 and layers[2]['marks']==[]
    assert layers[0]['clip'][2:]==layers[1]['clip'][2:]
    replacement=KeyedTable('entities',dict(id=['a'],jan=[1],feb=[1.5],mar=[2],group=['A']))
    state=original.state(SelectionState.for_table(table(),selected=['b']))
    with pytest.raises(ValueError):original.replace_data(replacement,state=state)
    revised=original.replace_data(replacement,state=state,missing='drop',width=160)
    assert len(revised.figure.payload()['layers'][0]['marks'])==5
    assert original.payload()['layers'][0]['missing']==1
    assert revised.figure.validate_state(revised.state())[0].selected_ids==()


CHECKS=r'''
(async()=>{
 await inklet.ready;const r=inklet,ok=(c,m)=>{if(!c)throw Error(m);},exports=[];
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);r.setVisible(null);
  const point=r.items.find(m=>m.kind==='circle'&&m.id==='a'),g=point.geometry;
  const hit=r.pick(g[0],g[1],0);ok(hit.id==='a'&&hit.sample.column==='jan'&&hit.sample.y===1,'sample picking');
  const line=r.items.find(m=>m.kind==='line'),q=line.geometry;
  const middle=r.pick((q[0]+q[2])/2,(q[1]+q[3])/2,0);
  ok(middle.id==='b'&&middle.sample.column==='feb','segment endpoint sample');
  const screen=new DOMPoint(g[0],g[1]).matrixTransform(r.svg.getScreenCTM());
  document.getElementById('stage').dispatchEvent(new PointerEvent('pointermove',{clientX:screen.x,clientY:screen.y,bubbles:true}));
  ok(document.getElementById('hover').textContent.includes('jan: 1'),'sample hover');
  r.select(['a']);r.setVisible(['b']);const saved=r.state();
  r.select([]);r.loadState(saved);ok(r.selected.has('a'),'hidden selection lost');
  exports.push({state:r.state(),svg:r.exportSVG()});
  r.setVisible(null);r.setViewport([3,2,r.scene.width/1.2,r.scene.height/1.2]);
  exports.push({state:r.state(),svg:r.exportSVG()});r.setViewport([0,0,r.scene.width,r.scene.height]);
 }
 return exports;
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def browser_result(tmp_path,figure,checks,**html_options):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    page=tmp_path/'index.html';page.write_text(figure.to_html(**html_options).replace('</html>','<script>'+checks+'</script></html>'))
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S);assert match,result.stdout[-2000:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    return report


def test_browser_sample_hover_pick_and_export(tmp_path):
    from test_browser_statistics import svg_geometry
    figure=BrowserFigure(table(),[view()])
    exports=browser_result(tmp_path,figure,CHECKS)
    assert len(exports)==6
    for exported in exports:
        assert svg_geometry(figure.to_svg(exported['state']))==svg_geometry(exported['svg'])
