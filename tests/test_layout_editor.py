"""Local authoring commands use real compilation and immutable successful previews."""
import json
import urllib.request
import urllib.error

import pytest
import inklet as i
from inklet.experimental.layout_editor import LayoutEditor


def source():
    data=i.dataset({'x':[0,1,2],'y':[1,2,3]})
    recipe=i.composition(120,75)
    recipe.add('plot',i.plot_spec(x=(0,2),y=(0,5)).line(data.points('x','y')).axes(),
               x=13,y=8,anchor='area-nw',width=recipe.page_width-26,height=30)
    flow=i.composition(90,20);flow.add('label',i.module('Input'),x=5,y=2)
    recipe.add('flow',flow,y=55)
    return recipe,data


def test_edit_undo_redo_reset_and_reopen_match_python_exports():
    base,_=source();before=base.signature();editor=LayoutEditor(base)
    original=editor.figure.to_svg()
    result=editor.command('edit',{'path':'/plot','placement':{'height':35}},revision=0)
    changed=editor.figure.to_svg()
    assert changed!=original and result['undo'] and not result['redo']
    state=json.loads(json.dumps(editor.overrides()))
    restored,_=base.with_layout_overrides(state)
    doc=i.document(width=120,height=75,margin=0);doc.add('composition',restored)
    assert doc.compile().to_svg()==changed
    assert doc.compile().to_pdf()==editor.figure.to_pdf()
    editor.command('undo');assert editor.figure.to_svg()==original
    editor.command('redo');assert editor.figure.to_svg()==changed
    editor.command('reset','/plot');assert editor.overrides()['targets']=={}
    editor.command('load',state);assert editor.figure.to_svg()==changed
    assert base.signature()==before
    state['targets'].clear();assert editor.overrides()['targets']


def test_failed_build_invalid_load_and_stale_commands_leave_everything_unchanged():
    base,_=source();editor=LayoutEditor(base)
    editor.command('edit',{'path':'/plot','placement':{'height':35}})
    before=editor.snapshot();figure=editor.figure
    for action,value in [('edit',{'path':'/plot','placement':{'height':-2}}),
                         ('edit',{'path':'/plot','placement':{'anchor':'missing'}}),
                         ('edit',{'path':'/absent','placement':{'x':1}}),
                         ('load',{'schema':'unknown','targets':{}}),('unknown',None)]:
        with pytest.raises((ValueError,i.DiagramError)):editor.command(action,value)
        assert editor.snapshot()==before and editor.figure is figure
    with pytest.raises(ValueError,match='stale'):editor.command('undo',revision=0)
    assert editor.snapshot()==before


def test_refresh_retains_edits_rebuilds_data_and_reports_removed_paths():
    base,data=source();editor=LayoutEditor(base)
    editor.command('edit',{'path':'/flow/label','placement':{'x':10}})
    previous=editor.figure;svg=previous.to_svg()
    data.update(y=[2,3,4])
    assert editor.figure is previous
    refreshed=editor.command('refresh')
    assert editor.figure.to_svg()!=svg and previous.to_svg()==svg
    assert not refreshed['undo'] and editor.overrides()['targets']
    base.replace('flow',i.module('Replacement'))
    before=editor.snapshot()
    with pytest.raises(i.LayoutError,match='orphaned'):editor.command('refresh')
    assert editor.snapshot()==before
    refreshed=editor.command('refresh',missing='drop')
    assert refreshed['report']['orphaned_targets']==['/flow/label']
    assert editor.overrides()['targets']=={}


def test_noop_edits_and_branching_history():
    base,_=source();editor=LayoutEditor(base)
    assert not editor.command('edit',{'path':'/plot','placement':{'x':13}})['undo']
    editor.command('edit',{'path':'/plot','placement':{'x':14}})
    editor.command('edit',{'path':'/plot','placement':{'x':15}})
    assert editor.command('undo')['redo']
    assert not editor.command('edit',{'path':'/plot','placement':{'x':16}})['redo']
    with pytest.raises(ValueError,match='nothing'):editor.command('redo')


def test_http_commands_exports_host_checks_and_shutdown():
    base,_=source();editor=LayoutEditor(base)
    with pytest.raises(RuntimeError):_ = editor.url
    with editor:
        address=editor.url
        assert address.startswith('http://127.0.0.1:')
        page=urllib.request.urlopen(address).read().decode()
        assert 'Layout editor' in page
        import re
        token=re.search(r"const token='([^']+)'",page)[1]
        def post(body,**headers):
            req=urllib.request.Request(address+'/command',json.dumps(body).encode(),
                headers={'Content-Type':'application/json','X-Inklet-Token':token,**headers})
            return json.load(urllib.request.urlopen(req))
        first=post({'action':'edit','value':{'path':'/plot','placement':{'height':35}},'revision':0})
        assert first['revision']==1
        assert urllib.request.urlopen(address+'/figure.svg?revision=1').read().decode()==editor.figure.to_svg()
        assert urllib.request.urlopen(address+'/figure.pdf?revision=1').read()==editor.figure.to_pdf()
        assert json.load(urllib.request.urlopen(address+'/layout.json?revision=1'))==editor.overrides()
        for headers in ({'Origin':'https://example.com'},{'Host':'example.com'},{'X-Inklet-Token':'bad'}):
            with pytest.raises(urllib.error.HTTPError) as caught:
                post({'action':'undo','revision':1},**headers)
            assert caught.value.code==403
        for body in ({'action':'undo','revision':0},{'action':'undo'},{'action':'undo','revision':None}):
            with pytest.raises(urllib.error.HTTPError):post(body)
        with pytest.raises(urllib.error.HTTPError):urllib.request.urlopen(address+'/figure.svg?revision=0')
        assert editor.snapshot()['revision']==1
    with pytest.raises(RuntimeError):_ = editor.url
    assert editor.figure.to_pdf().startswith(b'%PDF')
    editor.close()


def test_browser_controls_apply_undo_reload_and_export(tmp_path):
    import html,re,shutil,subprocess
    chrome=shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:pytest.skip('Chrome/Chromium not installed')
    base,_=source();editor=LayoutEditor(base)
    page=editor._html()
    checks='''<script>
    (async()=>{const sleep=()=>new Promise(r=>setTimeout(r,30));async function ready(rev){for(let n=0;n<200;n++){if(state&&state.revision===rev&&!busy&&previewReady)return;await sleep();}throw Error('timeout '+rev);}
    try{await ready(0);byId('target').value='/plot';byId('target').dispatchEvent(new Event('change'));
    const height=document.querySelector('input[data-group="placement"][data-key="height"]');height.value=35;height.dispatchEvent(new Event('input'));byId('apply').click();await ready(1);
    if(state.targets['/plot'].placement.height!==35)throw Error('edit failed');
    const saved=await(await fetch(byId('save').href)).json();const exported=await(await fetch(byId('svg').href)).text();if(exported!==state.svg)throw Error('export mismatch');
    byId('undo').click();await ready(2);if(state.targets['/plot'].placement.height!==30)throw Error('undo failed');
    byId('redo').click();await ready(3);if(state.targets['/plot'].placement.height!==35)throw Error('redo failed');
    await request('load',saved);await ready(4);byId('reset').click();await ready(5);if(Object.keys(state.overrides.targets).length)throw Error('reset failed');
    document.body.dataset.editorTest=JSON.stringify({ok:true,svg:exported,saved});
    }catch(error){document.body.dataset.editorTest=JSON.stringify({error:error.message});}})();</script>'''
    editor._html=lambda:page.replace('</body>',checks+'</body>')
    with editor:
        result=subprocess.run([chrome,'--headless','--no-sandbox','--dump-dom','--virtual-time-budget=15000',
                               f'--user-data-dir={tmp_path}/chrome',editor.url],capture_output=True,text=True,timeout=40)
    match=re.search(r'data-editor-test="([^"]+)"',result.stdout)
    assert match,result.stderr[-2000:]
    report=json.loads(html.unescape(match[1]));assert report.get('ok'),report
    restored,_=base.with_layout_overrides(report['saved'])
    doc=i.document(width=120,height=75,margin=0);doc.add('composition',restored)
    assert doc.compile().to_svg()==report['svg']


def test_repeated_edits_and_reset_follow_shared_nested_definitions():
    base,_=source();base.add('alias',base['flow'],x=60,y=55)
    editor=LayoutEditor(base)
    for x in (8,10):
        state=editor.command('edit',{'path':'/flow/label','placement':{'x':x}})
        assert state['targets']['/alias/label']['placement']['x']==x
    state=editor.command('reset','/alias/label')
    assert state['targets']['/flow/label']['placement']['x']==5
    assert editor.overrides()['targets']=={}
    editor.command('edit',{'path':'/flow','page':{'height':25},'placement':{'y':50}})
    state=editor.command('reset','/alias')
    assert state['targets']['/flow']['page']['height']==20
    assert state['targets']['/flow']['placement']['y']==50


def test_page_size_is_physical_and_explicit_document_size_remains_authoritative():
    base,_=source();editor=LayoutEditor(base)
    editor.command('edit',{'path':'/','page':{'width':140}})
    assert editor.figure.root.width==140
    fixed=LayoutEditor(base,width=150)
    fixed.command('edit',{'path':'/','page':{'width':140}})
    assert fixed.figure.root.width==150


def test_concurrent_clients_cannot_overwrite_a_newer_revision():
    from concurrent.futures import ThreadPoolExecutor
    base,_=source();editor=LayoutEditor(base)
    def edit(value):
        try:return editor.command('edit',{'path':'/plot','placement':{'height':value}},revision=0)
        except ValueError as error:return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,[34,36]))
    assert sum(isinstance(result,dict) for result in results)==1
    assert any(isinstance(result,str) and 'stale' in result for result in results)
    assert editor.snapshot()['revision']==1
