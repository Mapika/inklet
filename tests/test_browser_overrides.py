"""Author choices survive commands, source changes and Python reconstruction."""
import copy
import html
import json
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

import pytest

from inklet.experimental.browser import BrowserFigure, ScatterView, LineView, FacetView, RevisionOption
from inklet.experimental.browser.overrides import rebase_overrides
from inklet.experimental.selection import KeyedTable, SelectionState
from test_browser_switching import mark_geometry


def figures():
    table = KeyedTable('appearance', dict(id=['a','b','c'], x=[0,1,2], y=[1,3,2], group=['East','West','East']))
    views = [FacetView(ScatterView('points','x','y',(-1,3),(0,4)), 'group', ('East','West')),
             LineView('line','x','y',(-1,3),(0,4))]
    original = BrowserFigure(table, views)
    reordered = BrowserFigure(table, [FacetView(views[0].view,'group',('West','East')), views[1]], width=160)
    removed = BrowserFigure(table, [views[1]], width=160)
    return original, reordered, removed


def test_saved_overrides_are_independent_and_preserve_facet_identity():
    f, reordered, removed = figures()
    original = f.to_svg()
    value = f.overrides({'points':dict(color='#a03050',radius_mm=1.2), 'line':dict(line_width_mm=.9)})
    before = copy.deepcopy(value)
    edited = f.to_svg(overrides=value)
    assert f.to_svg() == original and value == before
    assert edited != original and edited == f.to_svg(overrides=json.loads(json.dumps(value)))
    assert rebase_overrides(value,reordered)[0] == value
    root = ET.fromstring(reordered.to_svg(overrides=value))
    circles = list(root.iter('{http://www.w3.org/2000/svg}circle'))
    assert len(circles) == 3 and all(float(c.attrib['r']) == 1.2 and c.attrib['fill']=='#a03050' for c in circles)
    with pytest.raises(ValueError,match='orphaned'): rebase_overrides(value, removed)
    kept, report = rebase_overrides(value, removed, missing='drop')
    assert set(kept['targets']) == {'line'} and report['orphaned_targets'] == ['points']
    changed_kind = BrowserFigure(f.table,[ScatterView('points','x','y',(-1,3),(0,4)), f._views[1]])
    with pytest.raises(ValueError,match='orphaned'): rebase_overrides(value,changed_kind)


@pytest.mark.parametrize('changes', [dict(radius_mm=True),dict(radius_mm=0),dict(radius_mm=float('nan')),
    dict(radius_mm=11),dict(color='red'),dict(color='</script>'),dict(unknown=1),dict(line_width_mm=.2)])
def test_invalid_or_unsupported_properties_fail(changes):
    with pytest.raises(ValueError): figures()[0].overrides({'points':changes})


def test_schema_and_project_boundaries():
    f = figures()[0]
    value = f.overrides({'points':dict(radius_mm=1)})
    for key, replacement in [('schema','inklet.visual-overrides/9'),('table','different'),('targets',[]),('unknown',1)]:
        bad = copy.deepcopy(value);bad[key] = replacement
        with pytest.raises(ValueError): f.to_svg(overrides=bad)
    with pytest.raises(ValueError): rebase_overrides(value,f,missing='ignore')


CHECKS = r"""
<script>
(async()=>{
  await inkletDocument.ready;
  const ok=(v,m)=>{if(!v)throw Error(m);},e=inkletDocument.editor,initial=e.overrides(),state=inklet.state();
  const geometry=()=>[...new DOMParser().parseFromString(inklet.exportSVG(),'image/svg+xml').querySelectorAll('circle,line')]
    .map(node=>[node.localName,...[...node.attributes].map(a=>[a.name,a.value])]);
  const before=JSON.stringify(geometry()),old=inklet;
  const edited=structuredClone(initial);edited.targets.points={kind:'FacetView/ScatterView',color:'#a03050',radius_mm:1.2};edited.targets.line={kind:'LineView',line_width_mm:.9};
  await e.apply(edited);
  ok(old.disposed&&!old.svg.isConnected,'old renderer not disposed');
  ok(JSON.stringify(inklet.state())===JSON.stringify(state),'editing changed interaction state');
  const paint=JSON.stringify(geometry());ok(paint!==before,'edit did not paint');
  await e.undo();ok(JSON.stringify(geometry())===before,'undo paint');
  await e.redo();ok(JSON.stringify(geometry())===paint,'redo paint');
  const copy=e.overrides();copy.targets.points.radius_mm=8;ok(e.overrides().targets.points.radius_mm===1.2,'override accessor aliases state');
  const stable=inklet;
  let failed=false;try{await e.apply({...edited,table:'wrong'});}catch{failed=true;}
  ok(failed&&inklet===stable,'invalid edit changed current renderer');
  const file=new File([JSON.stringify(initial)],'overrides.json',{type:'application/json'});
  let finishRead;Object.defineProperty(file,'text',{value:()=>new Promise(resolve=>{finishRead=resolve;})});
  const input={files:[file],value:'overrides.json'};
  const loading=document.getElementById('edit-load').onchange({target:input});
  failed=false;try{await inkletDocument.switchRevision(1);}catch{failed=true;}ok(failed,'revision raced file load');
  finishRead(JSON.stringify(initial));await loading;
  ok(input.value===''&&JSON.stringify(geometry())===before,'file did not restore original appearance');
  await e.undo();ok(JSON.stringify(geometry())===paint,'opening file was not undoable');
  const afterLoad=inklet;
  const NativeImage=window.Image;
  window.Image=function(){const image=new NativeImage();Object.defineProperty(image,'src',{set(){setTimeout(()=>image.onerror(new Event('error')),0);}});return image;};
  failed=false;try{await e.apply(initial);}catch{failed=true;}window.Image=NativeImage;
  ok(failed&&inklet===afterLoad&&e.overrides().targets.points.radius_mm===1.2,'failed render committed command');
  ok(!document.querySelector('.revision-staging'),'failed render leaked staging');
  // A delayed command must exclude concurrent edits, revision and file state operations.
  let release;window.Image=function(){const image=new NativeImage();Object.defineProperty(image,'src',{set(value){release=()=>Reflect.set(HTMLImageElement.prototype,'src',value,image);}});return image;};
  const pending=e.undo();await Promise.resolve();
  failed=false;try{await inkletDocument.switchRevision(1);}catch{failed=true;}ok(failed,'revision raced edit');
  failed=false;try{await e.apply(initial);}catch{failed=true;}ok(failed,'edit raced edit');
  window.Image=NativeImage;release();await pending;await e.redo();
  const exports=[{index:0,state:inklet.state(),overrides:e.overrides(),svg:inklet.exportSVG()}];
  await inkletDocument.switchRevision(1);
  ok(e.overrides().targets.points.radius_mm===1.2,'facet reordering lost authored styles');
  ok(document.getElementById('edit-undo').disabled,'revision retained stale undo history');
  exports.push({index:1,state:inklet.state(),overrides:e.overrides(),svg:inklet.exportSVG()});
  const previous=inklet;failed=false;try{await inkletDocument.switchRevision(2);}catch{failed=true;}
  ok(failed&&inklet===previous,'orphaned edit was silently removed');
  const report=await inkletDocument.switchRevision(2,{missing:'drop'});
  ok(JSON.stringify(report.visual_overrides.orphaned_targets)==='["points"]','orphan report missing');
  ok(!Object.hasOwn(e.overrides().targets,'points')&&e.overrides().targets.line.line_width_mm===.9,'drop discarded valid edits');
  exports.push({index:2,state:inklet.state(),overrides:e.overrides(),svg:inklet.exportSVG()});
  await inkletDocument.switchRevision(0);ok(!Object.hasOwn(e.overrides().targets,'points'),'dropped edit resurrected');
  // Actual inspector controls create an undoable command.
  document.getElementById('edit-target').value='points';document.getElementById('edit-target').dispatchEvent(new Event('change'));
  document.getElementById('edit-radius').value='1.7';await document.getElementById('edit-apply').onclick();
  ok(e.overrides().targets.points.radius_mm===1.7,'inspector did not commit');
  await document.getElementById('edit-undo').onclick();ok(!Object.hasOwn(e.overrides().targets,'points'),'inspector undo');
  return exports;
})().then(exports=>document.body.dataset.overrideTest=JSON.stringify({exports})).catch(e=>document.body.dataset.overrideTest=JSON.stringify({error:e.stack}));
</script>
"""


@pytest.mark.parametrize('renderer,backend', [('classic','svg'),('classic','canvas'),('classic','hybrid'),
    ('compiled','svg'),('compiled','canvas'),('compiled','webgl2')])
def test_browser_commands_revisions_and_python_exports(tmp_path, renderer, backend):
    browser = shutil.which('google-chrome') or shutil.which('chromium')
    if not browser: pytest.skip('Chrome/Chromium not installed')
    f, reordered, removed = figures()
    state = f.state(SelectionState.for_table(f.table,selected=['a'],visible=['a','b']))
    page = f.to_html(renderer=renderer,backend=backend,editor=True,state=state,
        revisions=[RevisionOption('Reordered',reordered,'same source'),RevisionOption('Removed',removed,'same source')])
    path = tmp_path/'index.html';path.write_text(page.replace('</html>',CHECKS+'</html>'))
    result = subprocess.run([browser,'--headless','--no-sandbox','--enable-unsafe-swiftshader',
        '--use-gl=angle','--use-angle=swiftshader','--dump-dom','--virtual-time-budget=12000',
        f'--user-data-dir={tmp_path}/profile',path.as_uri()],capture_output=True,text=True,timeout=40)
    match = re.search(r'data-override-test="([^"]+)"',result.stdout)
    assert match, result.stderr[-2000:]
    report = json.loads(html.unescape(match[1]));assert 'error' not in report,report
    for export in report['exports']:
        figure = (f,reordered,removed)[export['index']]
        assert mark_geometry(export['svg']) == mark_geometry(figure.to_svg(export['state'],overrides=export['overrides']))
