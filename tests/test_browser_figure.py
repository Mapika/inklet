"""Independent geometry, picking and saved-vector checks for mixed browser marks."""
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
from inklet.experimental.browser import BrowserFigure, BarView, LineView, ScatterView
from inklet.experimental.selection import KeyedTable, SelectionState


def scene(reverse=False):
    table=KeyedTable('mixed',dict(id=list('abcdefghij'),
        x=[0,1,2,3,4,4,6,7,8,9],y=[0,2,-2,None,2,2,1,2,-2,0]))
    xd=(8,1) if reverse else (1,8)
    yd=(3,-3) if reverse else (-3,3)
    return BrowserFigure(table,[
        LineView('line','x','y',xd,yd),
        BarView('bars','x','y',xd,yd,baseline=1),
        ScatterView('points','x','y',xd,yd),
        BarView('horizontal','y','x',yd,xd,baseline=1,orientation='horizontal'),
    ])


@pytest.mark.parametrize('reverse',[False,True])
def test_source_order_missing_breaks_and_normalized_signed_bars(reverse):
    s=scene(reverse);layers=s.payload()['layers']
    segments=layers[0]['marks']
    assert [m['ids'] for m in segments]==[list(pair) for pair in ('ab','bc','ef','fg','gh','hi','ij')]
    assert segments[2]['geometry'][:2]==segments[2]['geometry'][2:]  # coincident endpoints
    for layer in (layers[1],layers[3]):
        marks={m['ids'][0]:m['geometry'] for m in layer['marks']}
        assert 'g' not in marks and 'd' not in marks  # baseline/null rows
        assert all(g[2]>0 and g[3]>0 for g in marks.values())
        # Both signed extents meet the same nonzero baseline.
        if layer is layers[1]:
            positive,negative=marks['b'],marks['c']
            assert (positive[1] if reverse else positive[1]+positive[3])==pytest.approx(
                negative[1]+negative[3] if reverse else negative[1],abs=1e-6)
    state=s.state(SelectionState.for_table(s.table,selected=['e','f'],visible=['b','e','f']))
    root=ET.fromstring(s.to_svg(state));ns={'s':'http://www.w3.org/2000/svg'}
    lines=root.findall('.//s:line',ns)
    assert len(lines)==2  # e-f and one highlight, with no bridge b-e
    assert lines[1].attrib['stroke']=='#bd5636'


@pytest.mark.parametrize('kind,kwargs',[(BarView,{'bar_width':0}),(BarView,{'baseline':float('inf')}),
    (BarView,{'orientation':'diagonal'}),(LineView,{'line_width_mm':-1}),
    (LineView,{'line_width_mm':True})])
def test_invalid_geometry_parameters(kind,kwargs):
    with pytest.raises(ValueError):kind('view','x','y',(0,1),(0,1),**kwargs)


def test_initial_html_state_is_validated_and_embedded():
    s=scene();state=s.state(SelectionState.for_table(s.table,selected=['b'],visible=['a','b']))
    page=s.to_html(state=state)
    assert '/*INITIAL_STATE*/' not in page and '"selected_ids": ["b"]' in page
    with pytest.raises(ValueError):s.to_html(state=dict(state,scene_digest='bad'))
    table=KeyedTable('tokens',dict(id=['/*RUNTIME*/'],x=[0],y=[1]))
    other=BrowserFigure(table,[ScatterView('view','x','y',(0,1),(0,2))])
    page=other.to_html(title='/*PAYLOAD*/',state=other.state())
    payload=json.loads(re.search(r'id="scene">(.*?)</script>',page,re.S)[1])
    assert payload['row_ids']==['/*RUNTIME*/']
    assert '<title>/*PAYLOAD*/' in page


# Exhaustive reference uses unindexed primitive geometry. Normal-size fixtures
# allow direct projection arithmetic, independently of the runtime's normalized
# segment calculation and cell index. Check every backend, filters and zooms.
CHECKS=r'''
(async()=>{
 await inklet.ready;const r=inklet,ok=(c,m)=>{if(!c)throw Error(m);};
 ok(r.selected.has('b'),'embedded initial state not restored');
 const exports=[];let queries=0;
 function oracle(x,y,tol){
  let best=null,score=Infinity;
  for(const [layerIndex,l] of r.scene.layers.entries()){
   const b=l.clip;if(x<b[0]||x>b[0]+b[2]||y<b[1]||y>b[1]+b[3])continue;
   const marks=l.marks??l.points.map(p=>({kind:'circle',ids:[p[0]],geometry:[p[1],p[2],l.radius]}));
   for(const m of marks){
    if(!m.ids.every(id=>r.visible===null||r.visible.has(id)))continue;
    const g=m.geometry;let d,limit=tol,id=m.ids[0];
    if(m.kind==='circle'){d=Math.sqrt((x-g[0])**2+(y-g[1])**2);limit+=g[2];}
    else if(m.kind==='rect'){
     const qx=Math.min(Math.max(x,g[0]),g[0]+g[2]),qy=Math.min(Math.max(y,g[1]),g[1]+g[3]);d=Math.hypot(x-qx,y-qy);
    }else{
     const vx=g[2]-g[0],vy=g[3]-g[1],den=vx*vx+vy*vy;
     const t=den?Math.max(0,Math.min(1,((x-g[0])*vx+(y-g[1])*vy)/den)):1;
     d=Math.hypot(x-g[0]-t*vx,y-g[1]-t*vy);limit+=m.width/2;id=m.ids[t<.5-1e-12?0:1];
    }
    if(d<=limit&&(d<score-1e-10||Math.abs(d-score)<1e-10)){score=d;best={id,layerIndex};}
   }
  }return best;
 }
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);
  for(const visible of [null,['a','b','e','f'],[]]){
   r.setVisible(visible);r.select(['b','e','f']);
   const positions=[];
   for(const item of r.items){
    const g=item.geometry;
    positions.push([g[0],g[1]],item.kind==='line'?[(g[0]+g[2])/2,(g[1]+g[3])/2]:
      item.kind==='rect'?[g[0]+g[2]/2,g[1]+g[3]/2]:[g[0],g[1]]);
   }
   for(let n=0;n<600;n++)positions.push([(n*37.317)%r.scene.width,(n*17.219)%r.scene.height]);
   for(const [x,y] of positions)for(const tol of [0,.7]){
    const want=oracle(x,y,tol),got=r.pick(x,y,tol);queries++;
    ok((want?.id??null)===(got?.id??null)&&(want?.layerIndex??null)===(got?.layerIndex??null),
       'pick mismatch '+JSON.stringify({x,y,tol,want,got:got&&{id:got.id,layerIndex:got.layerIndex}}));
   }
   r.setViewport([10,5,r.scene.width/1.5,r.scene.height/1.5]);
   const state=r.state();r.select([]);r.loadState(state);
   ok(r.selected.size===3,'lost selection');exports.push({state,svg:r.exportSVG()});
  }
 }
 r.setVisible(null);r.setBackend('svg');r.select(['e','f']);
 const duplicate=r.items.find(i=>i.kind==='line'&&i.ids[0]==='e');
 ok(r.pick(duplicate.geometry[0],duplicate.geometry[1]).id==='f','coincident line endpoint tie');
 const lines=r.overlay.querySelectorAll('line');ok(lines.length===2,'duplicate shared-segment highlight');
 // Exercise focus on an actual tall document without requiring an active
 // native pointer for setPointerCapture. Selection's focus must not scroll it.
 const host=r.host,capture=host.setPointerCapture;host.style.height='1800px';
 host.setPointerCapture=()=>{};window.scrollTo(0,0);document.getElementById('clear').focus({preventScroll:true});
 const beforeScroll=scrollY;host.onpointerdown({button:0,clientX:100,clientY:200,pointerId:1});
 ok(scrollY===beforeScroll,'pointer focus scrolled a tall plot');
 host.onpointercancel();host.setPointerCapture=capture;
 return {exports,queries};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def geometry(svg):
    root=ET.fromstring(svg)
    # Compare only generated mark groups; ignore frame definitions and IDs.
    result=[]
    for group in (root[1],root[-1]):
        for e in group.iter():
            tag=e.tag.rsplit('}',1)[-1]
            if tag not in ('circle','line','rect') or ('fill' not in e.attrib and 'stroke' not in e.attrib):continue
            attrs={}
            for k,v in e.attrib.items():
                try:attrs[k]=float(v)
                except ValueError:attrs[k]=v
            result.append((tag,attrs))
    return root.attrib['viewBox'].split(),result


@pytest.mark.parametrize('dpr,reverse',[(1,False),(2,True)])
def test_browser_mixed_picking_and_python_export_agree(tmp_path,dpr,reverse):
    browser=next((p for n in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(n))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    s=scene(reverse)
    page=tmp_path/'index.html';page.write_text(s.to_html(state=s.state(SelectionState.for_table(s.table,selected=['b']))).replace('</html>','<script>'+CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S)
    assert match,result.stdout[-3000:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    assert report['queries']>10000
    for exported in report['exports']:
        assert geometry(s.to_svg(exported['state']))==geometry(exported['svg'])
