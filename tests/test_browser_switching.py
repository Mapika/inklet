"""Prepared revision switching must be atomic and match Python's rebase rules."""
import html
import json
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

import pytest

from inklet.experimental.browser import (
    BarView, BrowserFigure, LineView, RevisionOption, ScatterView,
)
from inklet.experimental.selection import KeyedTable, SelectionState


def scenes():
    views = [LineView('line', 'x', 'y', (-1, 5), (-3, 5)),
             ScatterView('points', 'x', 'y', (-1, 5), (-3, 5))]
    original = BrowserFigure(KeyedTable('switching', {
        'id': ['a', 'b', 'c', 'd'], 'x': [0, 1, 2, 3],
        'y': [1, 2, -1, None], 'label': ['Alpha', 'Beta', 'Gamma', 'Delta'],
    }), views, width=190, columns=2)
    # a changes only JSON number representation: 1 -> 1.0. JS cannot infer
    # that change after JSON.parse, so report metadata must come from Python.
    revised = BrowserFigure(KeyedTable('switching', {
        'id': ['c', 'a', 'e'], 'x': [2, 0, 4],
        'y': [-1, 1.0, 3], 'label': ['Gamma', 'Alpha', 'Epsilon'],
    }), views, width=120, columns=1)
    alternate = BrowserFigure(KeyedTable('switching', {
        'id': ['e', 'c', 'a'], 'x': [4, 2, 0], 'y': [3, -1, 1.0],
        'source': ['Third', 'Third', 'Third'],
    }), [BarView('bars', 'x', 'y', (-1, 5), (-3, 5))], width=140)
    return original, revised, alternate


def revision_options(revised, alternate):
    return [RevisionOption('Revised', revised, 'Revised source', ('label',)),
            RevisionOption('Third', alternate, 'Third source', ('source',))]


def test_revision_option_validation_and_script_safe_labels():
    original, revised, alternate = scenes()
    valid = revision_options(revised, alternate)
    page = original.to_html(revision_label='Original', revisions=valid)
    assert 'revision-target' in page and 'apply-revision' in page
    assert '<main id="app" inert aria-busy="true">' in page
    for options in ([valid[0], valid[0]], [RevisionOption('Original', revised, 'Credit')],
                    [RevisionOption(str(n), revised, 'Credit') for n in range(8)]):
        with pytest.raises(ValueError):
            original.to_html(revisions=options, revision_label='Original')
    for kwargs in ({'revision_label': ''}, {'revision_label': 3}, {'revisions': 'wrong'}):
        with pytest.raises((ValueError, TypeError)):
            original.to_html(**kwargs)
    unrelated = BrowserFigure(KeyedTable('unrelated', original.table.columns), original._views)
    changed_key = BrowserFigure(KeyedTable('switching', {
        'row': ['a'], 'x': [0], 'y': [1],
    }, key='row'), original._views)
    for figure in (unrelated, changed_key):
        with pytest.raises(ValueError):
            original.to_html(revisions=[RevisionOption('Other', figure, 'Credit')])
    with pytest.raises(ValueError):
        original.to_html(revisions=[RevisionOption('Other', revised, 'Credit', ('absent',))])
    malicious = '</script><script>window.injected=true</script> /*RUNTIME*/'
    page = original.to_html(revision_label=malicious, revisions=[
        RevisionOption('Revised', revised, malicious, ('label',))])
    assert '<script>window.injected=true</script>' not in page


CHECKS = r'''
(async()=>{
 const ok=(condition,message)=>{if(!condition)throw Error(message);};
 const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?
   Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
 const equal=(a,b,message)=>ok(JSON.stringify(canonical(a))===JSON.stringify(canonical(b)),message);
 const deadline=p=>Promise.race([p,new Promise((_,reject)=>setTimeout(()=>reject(Error('operation timed out')),3000))]);
 await deadline(inkletDocument.ready);
 const doc=inkletDocument, app=document.querySelector('main');
 ok(!app.inert,'page remains inert after initial readiness');
 ok(doc.revisionIndex===0&&doc.report()===null,'initial revision/report');
 equal(inklet.state(),INITIAL_STATE,'initial state restored before document readiness');
 const original=inklet;
 const snapshot=()=>({renderer:inklet,state:JSON.stringify(inklet.state()),report:JSON.stringify(doc.report()),
   credit:document.getElementById('attribution').textContent,headers:document.getElementById('headers').textContent,
   current:document.getElementById('revision-current').textContent,index:doc.revisionIndex});
 const unchanged=(before,message)=>{
   const after=snapshot();ok(after.renderer===before.renderer,message+' renderer');
   for(const key of ['state','report','credit','headers','current','index'])equal(after[key],before[key],message+' '+key);
   ok(!app.inert,message+' leaves page inert');
 };
 async function rejects(operation,message){let rejected=false;try{await deadline(operation());}catch(e){rejected=true;}ok(rejected,message);}
 const before=snapshot();
 await rejects(()=>doc.switchRevision(1),'removed selected/visible rows must require explicit drop');
 unchanged(before,'rejected removal');
 for(const [index,options] of [[-1,{}],[3,{}],[1.5,{}],[true,{}],[1,{missing:'ignore'}],[1,{viewport:'auto'}]]){
   await rejects(()=>doc.switchRevision(index,options),'invalid revision/options accepted');unchanged(before,'invalid options');
 }
 // Hold candidate image decoding so a second request reliably overlaps.
 const NativeImage=window.Image;let release;
 window.Image=function(){const image=new NativeImage();
   Object.defineProperty(image,'src',{set(value){release=()=>Reflect.set(HTMLImageElement.prototype,'src',value,image);}});
   return image;
 };
 let disconnected=0;const disconnect=original.resizeObserver.disconnect.bind(original.resizeObserver);
 original.resizeObserver.disconnect=()=>{disconnected++;disconnect();};
 const pending=doc.switchRevision(1,{missing:'drop',viewport:'preserve'});
 await Promise.resolve();
 ok(app.inert,'switch does not block page interaction');
 await rejects(()=>doc.switchRevision(2,{missing:'drop'}),'overlapping switches accepted');
 ok(inklet===original&&doc.revisionIndex===0,'candidate became current before ready');
 window.Image=NativeImage;ok(typeof release==='function','candidate frame not created');release();
 const first=await deadline(pending);
 equal(first,EXPECTED_REPORT,'report differs from Python, including integer/float change');
 equal(inklet.state(),EXPECTED_STATE,'revised state differs from Python');
 ok(inklet!==original&&original.disposed&&disconnected===1,'old renderer/observer not disposed once');
 ok(!original.svg.isConnected&&!original.canvas.isConnected,'old renderer DOM retained');
 ok(!app.inert&&doc.revisionIndex===1,'successful switch not ready');
 ok(inklet.backend===BACKEND,'switch changed selected rendering backend');
 ok(document.getElementById('attribution').textContent==='Revised source','new source credit missing');
 ok(document.getElementById('revision-current').textContent.includes('Revised'),'current revision label stale');
 ok(inklet.selected.has('c')&&!inklet.shown('c'),'hidden selection lost');
 first.changed_ids.length=0;const copy=doc.report();copy.removed_ids.length=0;
 equal(doc.report(),EXPECTED_REPORT,'report accessor aliases mutable caller data');
 const noop=snapshot();ok(await doc.switchRevision(1)===null,'same-index switch is not a no-op');unchanged(noop,'same-index no-op');
 await rejects(()=>inklet.loadState(INITIAL_STATE),'old revision state accepted');unchanged(noop,'stale saved state');
 // Hold an actual saved-view file read. Revision changes must not race the
 // asynchronous load or retarget that state to a different data revision.
 const savedFile=new File([JSON.stringify(inklet.state())],'view.json',{type:'application/json'});
 let finishRead;Object.defineProperty(savedFile,'text',{value:()=>new Promise(resolve=>{finishRead=resolve;})});
 const upload={files:[savedFile],value:'view.json'};
 const reading=document.getElementById('load').onchange({target:upload});
 ok(app.inert,'saved-view read leaves controls active');
 await rejects(()=>doc.switchRevision(2),'revision switched during saved-view read');
 finishRead(JSON.stringify(inklet.state()));await deadline(reading);
 unchanged(noop,'saved-view read');ok(upload.value==='','file input not cleared');
 const exports=[{index:1,state:inklet.state(),svg:inklet.exportSVG()}];
 // An image decode failure must roll back every observable part of the page.
 window.Image=function(){const image=new NativeImage();
   Object.defineProperty(image,'src',{set(){setTimeout(()=>image.onerror(new Event('error')),0);}});return image;};
 await rejects(()=>doc.switchRevision(2),'failed candidate frame accepted');window.Image=NativeImage;
 unchanged(noop,'frame failure');
 ok(!document.querySelector('.revision-staging'),'failed candidate staging container leaked');
 ok(document.querySelectorAll('#stage > svg').length===1&&document.querySelectorAll('#stage > canvas').length===1,
    'failed candidate DOM leaked into stage');
 // Invalid preserved geometry fails without discarding a valid current state.
 await doc.switchRevision(0);
 inklet.setViewport([0,0,inklet.scene.width*100,50]);const huge=snapshot();
 await rejects(()=>doc.switchRevision(1,{viewport:'preserve'}),'invalid preserved viewport accepted');unchanged(huge,'invalid viewport');
 await doc.switchRevision(1);
 equal(inklet.viewport,[0,0,inklet.scene.width,inklet.scene.height],'default viewport did not reset');
 // All, none and explicit visibility must keep distinct meanings for additions.
 for(const visible of [null,[],['a']]){
   await doc.switchRevision(0);inklet.setVisible(visible);inklet.select(['c']);
   await doc.switchRevision(1);equal(inklet.state().selection.visible_ids,visible,'visibility meaning changed');
   ok(inklet.selected.has('c'),'retained ID selection lost');
 }
 inklet.setVisible(null);await doc.switchRevision(2);
 ok(!document.getElementById('headers').textContent.includes('label')&&
    document.getElementById('headers').textContent.includes('source'),'headers not rebuilt for changed columns');
 ok(document.getElementById('attribution').textContent==='Third source','third source credit stale');
 const filter=document.getElementById('id-filter');filter.value='Third';filter.dispatchEvent(new Event('input',{bubbles:true}));
 equal(inklet.state().selection.visible_ids,['a','c','e'],'revision-specific search columns not applied');
 exports.push({index:2,state:inklet.state(),svg:inklet.exportSVG()});
 filter.value='';filter.dispatchEvent(new Event('input',{bubbles:true}));
 // Exercise the actual controls and ensure they use the active revision.
 const applyButton=document.getElementById('apply-revision');
 document.getElementById('revision-controls').open=true;
 document.getElementById('revision-target').value='0';applyButton.focus();applyButton.click();
 for(let n=0;n<100&&doc.revisionIndex!==0;n++)await new Promise(resolve=>setTimeout(resolve,10));
 ok(doc.revisionIndex===0,'revision UI did not switch back');
 ok(document.activeElement===applyButton,'revision UI lost keyboard focus after switching');
 // A failed asynchronous candidate must restore the same keyboard control.
 window.Image=function(){const image=new NativeImage();
   Object.defineProperty(image,'src',{set(){setTimeout(()=>image.onerror(new Event('error')),0);}});return image;};
 applyButton.focus();await rejects(()=>doc.switchRevision(1),'failed focus-check candidate accepted');
 window.Image=NativeImage;
 ok(document.activeElement===applyButton,'failed revision lost keyboard focus');
 for(let n=0;n<4;n++){
   const old=inklet;await doc.switchRevision(n%2?0:1);
   ok(old.disposed&&!old.svg.isConnected&&!old.canvas.isConnected,'repeat switch retained old renderer');
   ok(document.querySelectorAll('#stage > svg').length===1,'repeat switch leaked SVGs');
 }
 return {exports};
})().then(value=>document.body.dataset.switchTest=JSON.stringify(value))
 .catch(error=>document.body.dataset.switchTest=JSON.stringify({error:error.message,stack:error.stack}));
'''


def mark_geometry(svg):
    root = ET.fromstring(svg)
    marks = []
    for group in (root[1], root[-1]):
        for node in group.iter():
            tag = node.tag.rsplit('}', 1)[-1]
            if tag not in ('circle', 'line', 'rect') or not {'fill', 'stroke'} & node.attrib.keys():
                continue
            attrs = {}
            for name, value in node.attrib.items():
                try:
                    attrs[name] = float(value)
                except ValueError:
                    attrs[name] = value
            marks.append((tag, attrs))
    return tuple(map(float, root.attrib['viewBox'].split())), marks


@pytest.mark.parametrize('renderer,backend', [('classic', 'svg'), ('classic', 'canvas'), ('classic', 'hybrid'),
    ('compiled', 'svg'), ('compiled', 'canvas'), ('compiled', 'auto'), ('compiled', 'webgl2')])
@pytest.mark.parametrize('dpr', [1, 2])
def test_browser_revision_switching_is_atomic_and_matches_python(tmp_path, backend, dpr, renderer):
    browser = next((path for name in ('google-chrome', 'chromium', 'chromium-browser')
                    if (path := shutil.which(name))), None)
    if browser is None:
        pytest.skip('Chrome/Chromium not installed')
    original, revised, alternate = scenes()
    state = original.state(SelectionState.for_table(original.table,
        selected=['b', 'c'], visible=['a', 'b']), viewport=[4, 8, 85, 40])
    expected = original.replace_data(revised.table, state=state, views=revised._views,
        width=revised._width, columns=revised._columns, missing='drop', viewport='preserve')
    assert expected.report()['changed_ids'] == ['a']
    checks = CHECKS
    for token, value in {'INITIAL_STATE': state, 'EXPECTED_REPORT': expected.report(),
                         'EXPECTED_STATE': expected.state(), 'BACKEND': backend}.items():
        checks = checks.replace(token, json.dumps(value).replace('<', '\\u003c'))
    page = original.to_html(renderer=renderer, backend=backend, state=state, attribution='Original source',
        revision_label='Original', search_columns=('label',), revisions=revision_options(revised, alternate))
    path = tmp_path/'index.html'
    path.write_text(page.replace('</html>', '<script>'+checks+'</script></html>'), encoding='utf-8')
    result = subprocess.run([browser, '--headless', '--no-sandbox', '--disable-gpu', '--dump-dom',
        '--virtual-time-budget=15000', f'--force-device-scale-factor={dpr}',
        f'--user-data-dir={tmp_path}/profile', path.as_uri()],
        capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr[-2000:]
    match = re.search(r'data-switch-test="([^"]*)"', result.stdout)
    assert match, result.stdout[-3000:]
    report = json.loads(html.unescape(match[1]))
    assert 'error' not in report, report
    targets = [original, revised, alternate]
    for exported in report['exports']:
        assert mark_geometry(exported['svg']) == mark_geometry(
            targets[exported['index']].to_svg(exported['state']))


def test_revision_removed_unicode_ids_follow_python_report_order(tmp_path):
    browser = next((path for name in ('google-chrome', 'chromium', 'chromium-browser')
                    if (path := shutil.which(name))), None)
    if browser is None:
        pytest.skip('Chrome/Chromium not installed')
    # UTF-16 sorts the astral emoji before U+E000; Python sorts code points.
    # Both removed arrays must match the authoritative Python report even
    # when state() serialized them in a different order in the browser.
    views = [ScatterView('points', 'x', 'y', (0, 3), (0, 3))]
    original = BrowserFigure(KeyedTable('unicode', {
        'id': ['a', '\ue000', '😀'], 'x': [0, 1, 2], 'y': [1, 2, 1],
    }), views)
    revised = BrowserFigure(KeyedTable('unicode', {
        'id': ['a'], 'x': [0], 'y': [1],
    }), views)
    state = original.state(SelectionState.for_table(original.table,
        selected=['\ue000', '😀'], visible=['\ue000', '😀']))
    expected = original.replace_data(revised.table, state=state, missing='drop')
    assert expected.report()['removed_selected'] == ['\ue000', '😀']
    checks = '''
    (async()=>{await inkletDocument.ready;
      const report=await inkletDocument.switchRevision(1,{missing:'drop'});
      return {report,state:inklet.state()};
    })().then(value=>document.body.dataset.unicodeTest=JSON.stringify(value))
      .catch(error=>document.body.dataset.unicodeTest=JSON.stringify({error:error.message}));
    '''
    page = original.to_html(state=state,
        revisions=[RevisionOption('Revised', revised, 'Test fixture')])
    path = tmp_path/'index.html'
    path.write_text(page.replace('</html>', '<script>'+checks+'</script></html>'), encoding='utf-8')
    result = subprocess.run([browser, '--headless', '--no-sandbox', '--disable-gpu', '--dump-dom',
        '--virtual-time-budget=5000', f'--user-data-dir={tmp_path}/profile', path.as_uri()],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[-2000:]
    match = re.search(r'data-unicode-test="([^"]*)"', result.stdout)
    assert match, result.stdout[-3000:]
    report = json.loads(html.unescape(match[1]))
    assert 'error' not in report, report
    assert report['report'] == expected.report()
    assert report['state'] == expected.state()


def test_initial_frame_failure_leaves_readable_error_and_disables_actions(tmp_path):
    browser = next((path for name in ('google-chrome', 'chromium', 'chromium-browser')
                    if (path := shutil.which(name))), None)
    if browser is None:
        pytest.skip('Chrome/Chromium not installed')
    original, revised, alternate = scenes()
    setup = '''
    window.testUnhandled=[];
    window.addEventListener('unhandledrejection',event=>window.testUnhandled.push(String(event.reason)));
    const TestNativeImage=window.Image;
    window.Image=function(){const image=new TestNativeImage();
      Object.defineProperty(image,'src',{set(){setTimeout(()=>image.onerror(new Event('error')),0);}});
      return image;};
    '''
    checks = '''
    (async()=>{
      let rejected=false;try{await inkletDocument.ready;}catch(error){rejected=true;}
      await new Promise(resolve=>setTimeout(resolve,20));
      return {rejected,status:document.getElementById('status').textContent,
        error:document.getElementById('error').textContent,
        controls:[...document.querySelectorAll('#app button,#app input,#app select')].map(node=>node.disabled),
        stageInert:document.getElementById('stage').inert,appInert:document.getElementById('app').inert,
        unhandled:window.testUnhandled};
    })().then(value=>document.body.dataset.initialFailure=JSON.stringify(value))
      .catch(error=>document.body.dataset.initialFailure=JSON.stringify({testError:error.message}));
    '''
    page = original.to_html(revisions=revision_options(revised, alternate))
    # Install the fault before the production runtime creates its first Image.
    page = page.replace('<script>\'use strict\';', '<script>'+setup+'</script><script>\'use strict\';', 1)
    assert 'window.testUnhandled=[]' in page
    path = tmp_path/'index.html'
    path.write_text(page.replace('</html>', '<script>'+checks+'</script></html>'), encoding='utf-8')
    result = subprocess.run([browser, '--headless', '--no-sandbox', '--disable-gpu', '--dump-dom',
        '--virtual-time-budget=5000', f'--user-data-dir={tmp_path}/profile', path.as_uri()],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[-2000:]
    match = re.search(r'data-initial-failure="([^"]*)"', result.stdout)
    assert match, result.stdout[-3000:]
    report = json.loads(html.unescape(match[1]))
    assert 'testError' not in report, report
    assert report['rejected']
    assert report['status'] == 'Figure could not be loaded. Reload this page to try again.'
    assert 'Cannot rasterize' in report['error']
    assert report['controls'] and all(report['controls'])
    assert report['stageInert'] and not report['appInert']
    assert report['unhandled'] == []
