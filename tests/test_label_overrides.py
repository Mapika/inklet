"""Saved text decisions follow explicit identities through compilation and revisions."""
import json
import pytest
import inklet as i
from inklet.experimental.layout_editor import LayoutEditor
from inklet.document.layout_overrides import SCHEMA


def source():
    recipe=i.composition(140,100)
    recipe.add('heading',i.component(i.text,'Source heading',size=4),x=10,y=5,anchor='nw')
    chart=i.plot_spec(x=(0,2),y=(0,4)).line([(0,1),(1,3),(2,2)]).axes()
    chart.title('Response',key='title').annotate(1,3,'Peak',key='peak',side='s',clear=3)
    chart.text(1,1,'Reference',key='reference')
    recipe.add('chart',chart,x=15,y=25,anchor='area-nw',width=65,height=35)
    flow=i.composition(120,22)
    flow.add('input',i.module('Input'),x=5,y=4)
    x,y=flow.point('input','out')
    flow.add('output',i.module('Output'),x=x+10,y=y,anchor='in')
    flow.link('input:out','output:in')
    recipe.add('flow',flow,x=5,y=73)
    recipe.annotate('chart:e','Measured signal',name='signal',side='e',clear=4)
    return recipe


def edit(editor,path,key,**fields):
    kind=editor.snapshot()['targets'][path]['labels'][key]['kind']
    return editor.command('edit',{'path':path,'labels':{key:{'kind':kind,**fields}}})


def test_all_label_kinds_roundtrip_and_history_at_two_widths():
    base=source();editor=LayoutEditor(base);original=editor.figure.to_svg();signature=base.signature()
    cases=[('/heading','text','Revised heading'),('/chart','title','Edited response'),
           ('/chart','peak','Maximum'),('/chart','reference','Baseline'),
           ('/flow/input','label','Updated input'),('/','signal','Supplied measurements')]
    for path,key,text in cases:edit(editor,path,key,text=text)
    edit(editor,'/chart','peak',side='se',clear=5,leader=False)
    saved=json.loads(json.dumps(editor.overrides()))
    assert saved['targets']['/chart']['labels']['peak']['text']=='Maximum'
    assert base.signature()==signature
    for width in (140,160):
        restored=LayoutEditor(base,width=width);restored.command('load',saved)
        recipe,_=base.with_layout_overrides(saved)
        doc=i.document(width=width,height=100,margin=0);doc.add('composition',recipe)
        assert doc.compile().to_svg()==restored.figure.to_svg()
        assert doc.compile().to_pdf()==restored.figure.to_pdf()
    changed=editor.figure.to_svg()
    for _ in range(7):editor.command('undo')
    assert editor.figure.to_svg()==original
    for _ in range(7):editor.command('redo')
    assert editor.figure.to_svg()==changed
    editor.command('reset','/chart')
    assert '/chart' not in editor.overrides()['targets']


def test_label_growth_reflows_ports_and_old_snapshots_stay_unchanged():
    editor=LayoutEditor(source());before=editor.snapshot();old=editor.figure
    edit(editor,'/flow/input','label',text='Longer measurements input')
    after=editor.snapshot()
    assert after['geometry']['/flow/output']['box'][0]>before['geometry']['/flow/output']['box'][0]
    assert old.to_svg()==before['svg'] and after['svg']!=before['svg']


def test_source_updates_and_reordered_instructions_retain_only_authored_fields():
    base=source();editor=LayoutEditor(base)
    edit(editor,'/chart','peak',text='Authored peak')
    base['chart']._steps.reverse()
    base['chart'].replace('peak',1.5,2.5,'New source text',side='w',clear=6)
    base['heading'].configure('New source heading')
    result=editor.command('refresh')
    assert result['targets']['/chart']['labels']['peak']==dict(kind='plot-annotate',text='Authored peak',side='w',clear=6,leader=True)
    assert result['targets']['/heading']['labels']['text']['text']=='New source heading'
    assert not result['undo']


def test_removed_or_changed_kind_reports_label_and_preserves_other_edits():
    base=source();editor=LayoutEditor(base)
    edit(editor,'/chart','peak',text='Authored peak')
    editor.command('edit',{'path':'/chart','placement':{'x':18}})
    base['chart'].remove('peak').text(1,2,'Replacement',key='peak')
    before=editor.snapshot()
    with pytest.raises(i.LayoutError,match='/chart#peak'):editor.command('refresh')
    assert editor.snapshot()==before
    result=editor.command('refresh',missing='drop')
    assert result['report']['orphaned_targets']==['/chart#peak']
    assert editor.overrides()['targets']['/chart']=={'placement':{'x':18}}


def test_shared_definition_edits_merge_and_conflicts_are_atomic():
    base=source();base.add('alias',base['chart'],x=90,y=30,width=30,height=20)
    editor=LayoutEditor(base)
    edit(editor,'/chart','peak',text='Shared text')
    edit(editor,'/alias','peak',side='w')
    saved=editor.overrides()
    assert saved['targets']['/chart']['labels']==saved['targets']['/alias']['labels']
    saved['targets']['/alias']['labels']['peak']['text']='Conflict'
    with pytest.raises(i.LayoutError,match='conflicting'):base.with_layout_overrides(saved)
    editor.command('reset','/alias')
    assert editor.overrides()['targets']=={}


@pytest.mark.parametrize('fields',[
    {'kind':'plot-annotate','text':None}, {'kind':'plot-annotate','side':'wrong'},
    {'kind':'plot-annotate','clear':True}, {'kind':'plot-annotate','clear':float('nan')},
    {'kind':'plot-annotate','clear':-1}, {'kind':'plot-annotate','leader':1},
    {'kind':'plot-title','clear':4}, {'text':'No kind'}, {'kind':'plot-annotate'},
])
def test_invalid_label_edits_do_not_change_state(fields):
    editor=LayoutEditor(source());before=editor.snapshot()
    with pytest.raises(ValueError):editor.command('edit',{'path':'/chart','labels':{'peak':fields}})
    assert editor.snapshot()==before
    with pytest.raises(ValueError):editor.source.with_layout_overrides(
        {'schema':SCHEMA,'targets':{'/missing':{'labels':{'peak':fields}}}},missing='drop')


def test_legacy_files_load_and_reject_new_fields():
    base=source()
    for schema in ('inklet.composition-layout/0.1','inklet.composition-layout/0.2'):
        editor=LayoutEditor(base);editor.command('load',{'schema':schema,'targets':{'/chart':{'placement':{'x':18}}}})
        assert editor.overrides()['schema']==SCHEMA
        with pytest.raises(ValueError,match='schema 0.3'):
            editor.command('load',{'schema':schema,'targets':{'/chart':{'labels':{'peak':{'kind':'plot-annotate','text':'New'}}}}})


def test_keyword_text_empty_text_and_explicit_annotation_names():
    base=source();base.replace('heading',i.component(i.text,content='Keyword'))
    editor=LayoutEditor(base);edit(editor,'/heading','text',text='')
    assert editor.snapshot()['targets']['/heading']['labels']['text']['text']==''
    with pytest.raises(i.LayoutError,match='duplicate annotation'):base.annotate('chart','Duplicate',name='signal')
    with pytest.raises(ValueError):base.annotate('chart','Invalid',name='')


def test_browser_label_controls_save_undo_reopen_and_export(tmp_path):
    import html,re,shutil,subprocess
    chrome=shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:pytest.skip('Chrome/Chromium not installed')
    base=source();editor=LayoutEditor(base);page=editor._html()
    checks='''<script>
    (async()=>{const sleep=()=>new Promise(r=>setTimeout(r,30));async function ready(rev){for(let n=0;n<250;n++){if(state&&state.revision===rev&&!busy&&previewReady)return;await sleep();}throw Error('timeout '+rev+': '+byId('status').textContent);}
    try{await ready(0);byId('target').value='/chart';fields();
    function set(key,value){const input=document.querySelector('[data-label="peak"][data-key="'+key+'"]');if(input.type==='checkbox')input.checked=value;else input.value=value;input.dispatchEvent(new Event(key==='side'?'change':'input'));}
    set('text','Edited <peak> & signal');set('side','sw');set('clear',4);set('leader',false);byId('apply').click();await ready(1);
    const label=state.targets['/chart'].labels.peak;if(label.text!=='Edited <peak> & signal'||label.side!=='sw'||label.clear!==4||label.leader!==false)throw Error('label controls');
    const saved=await(await fetch(byId('save').href)).json(),svg=await(await fetch(byId('svg').href)).text();if(svg!==state.svg)throw Error('export mismatch');
    byId('undo').click();await ready(2);if(state.targets['/chart'].labels.peak.text!=='Peak')throw Error('undo');
    await request('load',saved);await ready(3);if(state.svg!==svg)throw Error('reopen');
    document.body.dataset.labelTest=JSON.stringify({ok:true,saved,svg});
    }catch(error){document.body.dataset.labelTest=JSON.stringify({error:error.message});}})();</script>'''
    editor._html=lambda:page.replace('</body>',checks+'</body>')
    with editor:
        result=subprocess.run([chrome,'--headless','--no-sandbox','--dump-dom','--virtual-time-budget=18000',
            f'--user-data-dir={tmp_path}/chrome',editor.url],capture_output=True,text=True,timeout=45)
    match=re.search(r'data-label-test="([^"]+)"',result.stdout);assert match,result.stderr[-2000:]
    report=json.loads(html.unescape(match[1]));assert report.get('ok'),report
    reopened=LayoutEditor(base);reopened.command('load',report['saved'])
    assert reopened.figure.to_svg()==report['svg']


def test_measured_annotation_clearance_remains_live_during_text_edits():
    base=source()
    base.annotate('flow','Measured clearance',name='measured',side='s',clear=base.measure('heading')/10)
    editor=LayoutEditor(base)
    assert 'clear' not in editor.snapshot()['targets']['/']['labels']['measured']
    edit(editor,'/','measured',text='Edited measured note')
    saved=editor.overrides()['targets']['/']['labels']['measured']
    assert saved=={'kind':'composition-annotation','text':'Edited measured note'}
    base['heading'].configure('Longer source heading')
    editor.command('refresh')
    assert editor.overrides()['targets']['/']['labels']['measured']==saved


def test_failed_text_compilation_keeps_history_and_preview():
    base=source();base['flow']['input'].configure(max_width=24)
    editor=LayoutEditor(base);before=editor.snapshot();old=editor.figure
    with pytest.raises(i.DiagramError):edit(editor,'/flow/input','label',text='Unbreakable'*25)
    assert editor.snapshot()==before and editor.figure is old


def test_shared_complementary_saved_label_fields_merge():
    base=source();base.add('alias',base['chart'],x=90,y=30,width=30,height=20)
    value={'schema':SCHEMA,'targets':{
        '/chart':{'labels':{'peak':{'kind':'plot-annotate','text':'Shared'}}},
        '/alias':{'labels':{'peak':{'kind':'plot-annotate','side':'w'}}}}}
    editor=LayoutEditor(base);editor.command('load',value)
    for path in ('/chart','/alias'):
        label=editor.snapshot()['targets'][path]['labels']['peak']
        assert label['text']=='Shared' and label['side']=='w'
