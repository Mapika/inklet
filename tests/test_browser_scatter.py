"""Contracts for the bounded, offline scatter-renderer experiment."""
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
from inklet.experimental.selection import KeyedTable, SelectionState
from inklet.experimental.browser import BrowserScatter, ScatterView


def scene(*, reverse=False):
    table=KeyedTable('samples',dict(id=['edge','inside','outside','missing'],x=[0,5,-1,3],y=[0,1,0,None]))
    return BrowserScatter(table,[ScatterView('left','x','y',(10,0) if reverse else (0,10),(-2,2)),
                                 ScatterView('right','x','y',(0,10),(-2,2))])


@pytest.mark.parametrize('reverse',[False,True])
def test_geometry_uses_measured_panel_area_and_preserves_outside_identity(reverse):
    s=scene(reverse=reverse);layer=s.payload()['layers'][0];bounds=layer['clip']
    points={p[0]:p[1:] for p in layer['points']}
    assert points['edge'][0]==pytest.approx(bounds[0]+(bounds[2] if reverse else 0),abs=1e-6)
    assert points['inside'][0]==pytest.approx(bounds[0]+bounds[2]/2,abs=1e-6)
    assert points['edge'][1]==pytest.approx(bounds[1]+bounds[3]/2,abs=1e-6)
    assert layer['missing']==1 and 'missing' not in points and 'outside' in points
    copy=s.payload();copy['layers'][0]['clip'][0]=999
    assert s.payload()['layers'][0]['clip'][0]!=999


def test_saved_view_requires_exact_scene_and_data_and_exports_filtered_geometry():
    s=scene();selection=SelectionState.for_table(s.table,selected=['inside','outside'],visible=['inside'])
    state=s.state(selection,viewport=[10,5,90,35])
    restored=json.loads(json.dumps(state))
    assert s.to_svg(restored)==s.to_svg(state)
    root=ET.fromstring(s.to_svg(state));ns={'s':'http://www.w3.org/2000/svg'}
    circles=root.findall('.//s:circle',ns)
    assert len(circles)==4  # One base mark and selection ring in each view.
    assert root.attrib['viewBox']=='10 5 90 35'
    broken=dict(state,scene_digest='0'*64)
    with pytest.raises(ValueError,match='revision'):s.validate_state(broken)
    broken=json.loads(json.dumps(state));broken['selection']['selected_ids']=['removed']
    with pytest.raises(ValueError,match='unknown'):s.validate_state(broken)


@pytest.mark.parametrize('viewport',[[0,0,0,1],[0,0,-1,1],[True,0,1,1],[float('inf'),0,1,1],[1e300,0,1,1],[0,0,1e-12,1],[]])
def test_bad_viewports_fail_before_export(viewport):
    with pytest.raises(ValueError):scene().state(viewport=viewport)


@pytest.mark.parametrize('domain',[(0,0),(0,float('nan')),(-1e308,1e308)])
def test_invalid_or_overflowing_domains_fail(domain):
    with pytest.raises(ValueError):ScatterView('plot','x','y',domain,(0,1))


def test_bad_columns_and_unsafe_colours_fail():
    with pytest.raises(ValueError):ScatterView('plot','x','y',(0,1),(0,1),color='url(javascript:bad)')
    table=KeyedTable('samples',dict(id=['a'],x=[True],y=[1]))
    with pytest.raises(ValueError,match='numeric'):BrowserScatter(table,[ScatterView('plot','x','y',(0,1),(0,1))])


def test_html_is_self_contained_and_escapes_authored_text():
    s=scene();page=s.to_html(title='</title><script>bad</script>')
    assert '<title>&lt;/title&gt;' in page and '<script>bad</script>' not in page
    assert '/*RUNTIME*/' not in page and '/*PAYLOAD*/' not in page
    assert 'class ScatterRenderer' in page


BROWSER_CHECKS=r'''
<script>
inklet.ready.then(()=>{
 try{
  const r=inklet,ok=(condition,message)=>{if(!condition)throw Error(message);};
  ok(r.svg.querySelectorAll('use').length>0,'measured glyphs disappeared');
  ok(document.getElementById('page').tagName==='SPAN','frame IDs collide with HTML');
  const p=r.scene.layers[0].points.find(p=>p[0]==='inside'),b=r.scene.layers[0].clip;
  for(const backend of ['svg','canvas','hybrid']){
   r.setBackend(backend);r.setVisible(null);r.select(['inside']);
   ok(r.pick(p[1],p[2])?.id==='inside','pick mismatch: '+backend);
   ok(r.pick(b[0]-.01,b[1]+b[3]/2,5)===null,'pick outside clip: '+backend);
   r.setVisible(['edge']);ok(r.pick(p[1],p[2])===null,'hidden point picked');
   ok(r.selected.has('inside'),'hidden selection lost');
   r.setVisible([]);ok(r.pick(p[1],p[2])===null,'empty filter picked');
  }
  r.setVisible(null);r.setViewport([10,5,r.scene.width/2,r.scene.height/2]);
  const point=new DOMPoint(p[1],p[2]).matrixTransform(r.svg.getScreenCTM()),back=r.point(point.x,point.y);
  ok(Math.hypot(back.x-p[1],back.y-p[2])<1e-8,'coordinate conversion failed');
  const state=r.state(),before=JSON.stringify(state);let rejected=false;
  try{r.loadState({...state,viewport:[0,0,0,1]});}catch{rejected=true;}
  ok(rejected&&before===JSON.stringify(r.state()),'invalid load changed state');
  r.select([]);r.loadState(state);ok(r.selected.has('inside'),'state reload failed');
  ok(r.exportSVG().includes('clipPath'),'export lost clipping');
  const secondHost=document.createElement('div');secondHost.style.cssText='width:500px;height:200px';document.body.append(secondHost);
  const second=new ScatterRenderer(secondHost,r.scene);
  second.ready.then(()=>{
   const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
   ok(new Set(ids).size===ids.length,'multiple instances have duplicate IDs');
   document.body.dataset.browserTest='passed';
  }).catch(error=>{document.body.dataset.browserTest=error.message;});
 }catch(error){document.body.dataset.browserTest=error.message;}
}).catch(error=>{document.body.dataset.browserTest=error.message;});
</script>
'''


@pytest.mark.parametrize('dpr',[1,2])
def test_headless_browser_backends_state_clipping_and_instance_ids(tmp_path,dpr):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    page=tmp_path/'index.html';page.write_text(scene().to_html().replace('</html>',BROWSER_CHECKS+'</html>'))
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=3000',f'--force-device-scale-factor={dpr}',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    assert 'data-browser-test="passed"' in result.stdout,result.stdout[-5000:]
