"""Appearance, text and layout share an atomic, reproducible authoring state."""
import json
import pytest
import inklet as i
from inklet.experimental.layout_editor import LayoutEditor
from inklet.document.layout_overrides import SCHEMA


def source():
    data=i.dataset({'x':[0,1,2],'y':[1,3,2]})
    plot=i.plot_spec(x=(0,2),y=(0,4))
    plot.line(data.points('x','y'),stroke='#34786b',stroke_width=.4,key='line')
    plot.scatter(data.points('x','y'),color='#34786b',size=1.5,key='points').axes()
    plot.text(1,1,'Reference',key='note').annotate(1,3,'Peak',key='peak')
    group=i.composition(120,25)
    group.add('a',i.module('Input'),x=5,y=3)
    x,y=group.point('a','out');group.add('b',i.module('Output'),x=x+10,y=y,anchor='in')
    group.link('a:out','b:in')
    root=i.composition(150,110)
    root.add('heading',i.component(i.text,'Study',font_size=4),x=10,y=6,anchor='nw')
    root.add('plot',plot,x=15,y=25,anchor='area-nw',width=root.page_width-35,height=42)
    root.add('flow',group,x=5,y=80)
    root.annotate('heading:e','Supplied observations',name='caption',side='e',clear=3)
    return root,data


def edit(editor,path,key,**fields):
    kind=editor.snapshot()['targets'][path]['styles'][key]['kind']
    return editor.command('edit',{'path':path,'styles':{key:{'kind':kind,**fields}}})


def test_mixed_edit_is_one_undo_step_and_reopens_at_two_widths():
    base,_=source();editor=LayoutEditor(base);before=editor.snapshot();signature=base.signature()
    command={'path':'/plot','placement':{'height':45},
             'labels':{'peak':{'kind':'plot-annotate','text':'Reviewed peak'}},
             'styles':{'line':{'kind':'plot-line','stroke':'#aa5533','stroke_width':.8},
                       'points':{'kind':'plot-scatter','size':2.5,'opacity':.6}}}
    result=editor.command('edit',command);saved=json.loads(json.dumps(editor.overrides()))
    assert result['svg']!=before['svg'] and '#aa5533' in result['svg']
    assert base.signature()==signature
    editor.command('undo');assert editor.figure.to_svg()==before['svg'] and not editor.snapshot()['undo']
    editor.command('redo');assert editor.figure.to_svg()==result['svg']
    for width in (150,170):
        restored,_=base.with_layout_overrides(saved)
        doc=i.document(width=width,height=110,margin=0);doc.add('composition',restored)
        reopened=LayoutEditor(base,width=width);reopened.command('load',saved)
        assert reopened.figure.to_svg()==doc.compile().to_svg()
        assert reopened.figure.to_pdf()==doc.compile().to_pdf()


@pytest.mark.parametrize('path,key,fields',[
    ('/heading','text',{'size':6,'fill':'#991155'}),
    ('/flow/a','text',{'size':6,'fill':'navy'}),
    ('/flow/a','box',{'fill':'#ddeeff','stroke':'#223344','stroke_width':.8}),
    ('/plot','note',{'size':5,'fill':'#883311'}),
    ('/plot','peak',{'size':4,'fill':'#883311'}),
    ('/','caption',{'size':4,'fill':'#883311'}),
])
def test_supported_text_and_module_styles_change_real_exports(path,key,fields):
    root,_=source();editor=LayoutEditor(root);before=editor.figure.to_svg()
    result=edit(editor,path,key,**fields)
    assert result['svg']!=before
    saved=editor.overrides();restored=LayoutEditor(root);restored.command('load',saved)
    assert restored.figure.to_svg()==result['svg']
    for field,value in fields.items():assert result['targets'][path]['styles'][key][field]==value
    editor.command('reset',path);assert editor.figure.to_svg()==before


def test_text_size_remeasures_ports_and_removes_legacy_size_alias():
    root,_=source();editor=LayoutEditor(root);before=editor.snapshot();old=editor.figure
    edit(editor,'/heading','text',size=7)
    assert editor.snapshot()['geometry']['/heading']['box'][2]>before['geometry']['/heading']['box'][2]
    edit(editor,'/flow/a','text',size=8)
    assert editor.snapshot()['geometry']['/flow/b']['box'][0]>before['geometry']['/flow/b']['box'][0]
    assert old.to_svg()==before['svg']
    restored,_=root.with_layout_overrides(editor.overrides())
    assert 'font_size' not in restored['heading'].kwargs


def test_null_removes_explicit_style_and_source_revisions_keep_unedited_choices():
    root,data=source();editor=LayoutEditor(root);edit(editor,'/plot','line',stroke=None)
    assert editor.overrides()['targets']['/plot']['styles']['line']['stroke'] is None
    root['plot'].style('line',stroke='#aa5533',stroke_width=.9)
    data.update(y=[2,3,1]);refreshed=editor.command('refresh')
    assert refreshed['targets']['/plot']['styles']['line']['stroke'] is None
    assert refreshed['targets']['/plot']['styles']['line']['stroke_width']==.9
    editor.command('reset','/plot')
    assert editor.snapshot()['targets']['/plot']['styles']['line']['stroke']=='#aa5533'


def test_data_driven_marker_fields_are_not_constant_style_targets():
    root,_=source();root['plot'].style('points',size=[1,2,3],color=['red','green','blue'])
    editor=LayoutEditor(root);fields=editor.snapshot()['targets']['/plot']['styles']['points']
    assert set(fields)=={'kind','opacity'}
    with pytest.raises(i.LayoutError,match='/plot#style:points'):edit(editor,'/plot','points',size=2)
    edit(editor,'/plot','points',opacity=.5)
    assert editor.snapshot()['targets']['/plot']['styles']['points']['opacity']==.5


def test_revised_data_mapping_reports_style_and_preserves_labels_and_layout():
    root,_=source();editor=LayoutEditor(root)
    editor.command('edit',{'path':'/plot','placement':{'height':45},
        'labels':{'peak':{'kind':'plot-annotate','text':'Saved'}},
        'styles':{'points':{'kind':'plot-scatter','color':'#aa5533'}}})
    root['plot'].style('points',color=['red','green','blue'])
    before=editor.snapshot()
    with pytest.raises(i.LayoutError,match='#style:points'):editor.command('refresh')
    assert editor.snapshot()==before
    result=editor.command('refresh',missing='drop')
    assert result['report']['orphaned_targets']==['/plot#style:points']
    assert set(editor.overrides()['targets']['/plot'])=={'placement','labels'}


def test_shared_styles_merge_and_conflicting_saved_values_fail():
    root,_=source();root.add('alias',root['plot'],x=100,y=20,width=35,height=20)
    editor=LayoutEditor(root);edit(editor,'/plot','line',stroke='#991133');edit(editor,'/alias','line',stroke_width=.7)
    saved=editor.overrides();assert saved['targets']['/plot']['styles']==saved['targets']['/alias']['styles']
    saved['targets']['/alias']['styles']['line']['stroke']='#553399'
    with pytest.raises(i.LayoutError,match='conflicting'):root.with_layout_overrides(saved)
    editor.command('reset','/alias');assert editor.overrides()['targets']=={}


@pytest.mark.parametrize('fields',[
    {'kind':'plot-line','stroke':'url(https://invalid)'}, {'kind':'plot-line','stroke_width':True},
    {'kind':'plot-line','opacity':float('nan')}, {'kind':'plot-line','opacity':1.1},
    {'kind':'plot-line','stroke_width':-1}, {'kind':'plot-scatter','size':0},
    {'kind':'plot-line','marker':'circle'}, {'stroke':'red'}, {'kind':'plot-line'},
])
def test_bad_style_values_are_atomic_even_when_missing(fields):
    root,_=source();editor=LayoutEditor(root);before=editor.snapshot()
    with pytest.raises(ValueError):editor.command('edit',{'path':'/plot','styles':{'line':fields}})
    assert editor.snapshot()==before
    with pytest.raises(ValueError):root.with_layout_overrides({'schema':SCHEMA,'targets':{'/absent':{'styles':{'line':fields}}}},missing='drop')


def test_legacy_label_file_loads_but_cannot_claim_style_fields():
    root,_=source();editor=LayoutEditor(root)
    saved={'schema':'inklet.composition-layout/0.3','targets':{'/plot':{'labels':{'peak':{'kind':'plot-annotate','text':'Legacy'}}}}}
    editor.command('load',saved);assert editor.overrides()['schema']==SCHEMA
    saved['targets']['/plot']['styles']={'line':{'kind':'plot-line','stroke':'red'}}
    with pytest.raises(ValueError,match='schema 0.4'):editor.command('load',saved)


def test_style_key_survives_reordering_and_reports_changed_instruction_kind():
    root,_=source();editor=LayoutEditor(root);edit(editor,'/plot','line',stroke='navy')
    root['plot']._steps.reverse();editor.command('refresh')
    assert editor.snapshot()['targets']['/plot']['styles']['line']['stroke']=='navy'
    root['plot'].remove('line').scatter([(0,1),(1,2)],key='line')
    with pytest.raises(i.LayoutError,match='/plot#style:line'):editor.command('refresh')
    result=editor.command('refresh',missing='drop')
    assert result['report']['orphaned_targets']==['/plot#style:line']


def test_direct_recipe_capture_handles_removed_and_named_colour_styles():
    root,_=source();edited=root.copy()
    edited['plot'].style('line',stroke='navy')
    edited['plot']._steps[0][3].pop('stroke_width')
    saved=edited.layout_overrides(root);restored,_=root.with_layout_overrides(saved)
    assert restored['plot']._steps[0][3]['stroke']=='navy'
    assert 'stroke_width' not in restored['plot']._steps[0][3]
    assert LayoutEditor(restored).figure.to_svg()==LayoutEditor(edited).figure.to_svg()


def test_browser_sections_apply_layout_labels_and_style_together(tmp_path):
    import html,re,shutil,subprocess
    chrome=shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:pytest.skip('Chrome/Chromium not installed')
    root,_=source();editor=LayoutEditor(root);page=editor._html()
    checks='''<script>
    (async()=>{const sleep=()=>new Promise(r=>setTimeout(r,30));async function ready(rev){for(let n=0;n<250;n++){if(state&&state.revision===rev&&!busy&&previewReady)return;await sleep();}throw Error('timeout '+rev+': '+byId('status').textContent);}
    function section(group){byId('inspector').value=group;byId('inspector').dispatchEvent(new Event('change'));}
    function set(selector,value){const input=document.querySelector(selector);if(!input.getBoundingClientRect().height)throw Error('hidden control '+selector);input.value=value;input.dispatchEvent(new Event('input'));}
    try{await ready(0);const original=state.svg;byId('target').value='/plot';fields();
    set('[data-group="placement"][data-key="height"]',45);
    section('labels');set('[data-group="labels"][data-label="peak"][data-key="text"]','Reviewed peak');
    section('styles');set('[data-group="styles"][data-label="line"][data-key="stroke"]','#991133');set('[data-group="styles"][data-label="points"][data-key="size"]',2.5);
    byId('apply').click();await ready(1);if(state.targets['/plot'].placement.height!==45||state.targets['/plot'].labels.peak.text!=='Reviewed peak'||state.targets['/plot'].styles.line.stroke!=='#991133')throw Error('mixed edit');
    const saved=await(await fetch(byId('save').href)).json(),svg=await(await fetch(byId('svg').href)).text();if(svg!==state.svg)throw Error('export');
    byId('undo').click();await ready(2);if(state.svg!==original||state.undo)throw Error('one-step undo');
    await request('load',saved);await ready(3);if(state.svg!==svg)throw Error('reopen');
    section('styles');set('[data-group="styles"][data-label="line"][data-key="stroke"]','');byId('apply').click();await ready(4);if(state.targets['/plot'].styles.line.stroke!==null)throw Error('clear explicit style');
    document.body.dataset.styleTest=JSON.stringify({ok:true,saved,svg});
    }catch(error){document.body.dataset.styleTest=JSON.stringify({error:error.message});}})();</script>'''
    editor._html=lambda:page.replace('</body>',checks+'</body>')
    with editor:
        result=subprocess.run([chrome,'--headless','--no-sandbox','--dump-dom','--virtual-time-budget=18000',
            f'--user-data-dir={tmp_path}/chrome',editor.url],capture_output=True,text=True,timeout=45)
    match=re.search(r'data-style-test="([^"]+)"',result.stdout);assert match,result.stderr[-2000:]
    report=json.loads(html.unescape(match[1]));assert report.get('ok'),report
    reopened=LayoutEditor(root);reopened.command('load',report['saved'])
    assert reopened.figure.to_svg()==report['svg']
