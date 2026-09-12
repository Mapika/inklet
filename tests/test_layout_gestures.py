"""Mouse transforms agree with nested physical coordinates and saved Python output."""
import json
import pytest
import inklet as i
from inklet.experimental.layout_editor import LayoutEditor
from inklet.document.layout_overrides import SCHEMA


def source():
    group=i.composition(120,50,unit=.5)
    group.add('input',i.module('Input',min_width=20,min_height=12,pad=1),x=10,y=8,anchor='in')
    x,y=group.point('input','out')
    group.add('output',i.module('Output'),x=x+12,y=y,anchor='in')
    group.link('input:out','output:in').port('exit','output:out')
    root=i.composition(160,100)
    root.add('group',group,x=15,y=25,scale=1.4)
    root.add('plot',i.plot_spec(x=(0,1),y=(0,2)).line([(0,0),(1,1)]).axes(),
             x=20,y=60,anchor='area-nw',width=60,height=25)
    return root


@pytest.mark.parametrize('path',['/plot','/group','/group/input','/group/output'])
def test_mouse_move_uses_world_mm_and_keeps_original_snapshot(path):
    root=source();editor=LayoutEditor(root);first=editor.figure;svg=first.to_svg()
    box=editor.snapshot()['geometry'][path]['box']
    result=editor.command('gesture',{'path':path,'dx':6,'dy':4},revision=0)
    moved=result['geometry'][path]['box']
    assert moved[:2]==pytest.approx([box[0]+6,box[1]+4])
    assert moved[2:]==pytest.approx(box[2:])
    assert first.to_svg()==svg and root.layout_overrides(source())['targets']=={}
    editor.command('undo');assert editor.figure.to_svg()==svg
    editor.command('redo');assert editor.snapshot()['geometry'][path]['box']==pytest.approx(moved)


@pytest.mark.parametrize('corner',['nw','ne','sw','se'])
@pytest.mark.parametrize('path',['/plot','/group','/group/input'])
def test_corner_scale_keeps_opposite_corner_fixed_with_registered_ports(path,corner):
    editor=LayoutEditor(source());before=editor.snapshot()['geometry'][path]['box']
    result=editor.command('gesture',{'path':path,'dx':0,'dy':0,'factor':1.3,'corner':corner})
    after=result['geometry'][path]['box']
    px=before[0]+(before[2] if 'w' in corner else 0)
    py=before[1]+(before[3] if 'n' in corner else 0)
    assert after==pytest.approx([px+(before[0]-px)*1.3,py+(before[1]-py)*1.3,before[2]*1.3,before[3]*1.3])
    # Reopen the actual saved decisions and export through the regular compiler.
    restored,_=editor.source.with_layout_overrides(json.loads(json.dumps(editor.overrides())))
    doc=i.document(width=160,height=100,margin=0);doc.add('composition',restored)
    assert doc.compile().to_svg()==editor.figure.to_svg()
    assert doc.compile().to_pdf()==editor.figure.to_pdf()


def test_movement_keeps_measured_relationships_and_folds_repeated_offsets():
    editor=LayoutEditor(source())
    initial=editor.snapshot()['geometry']['/group/output']['box']
    for _ in range(36):editor.command('gesture',{'path':'/group/output','dx':.1,'dy':0})
    actual=editor.snapshot()['geometry']['/group/output']['box']
    assert actual[0]==pytest.approx(initial[0]+3.6)
    moved=editor.overrides()['targets']['/group/output']['placement']['x']
    assert moved['op']=='+' and moved['args'][0]['op']=='point'
    # Growing the upstream module still moves its dependent output.
    editor.source['group']['input'].configure('A much longer input label')
    refreshed=editor.command('refresh')
    assert refreshed['geometry']['/group/output']['box'][0]>actual[0]


@pytest.mark.parametrize('value',[
    {'path':'/','dx':1,'dy':1}, {'path':'/missing','dx':1,'dy':1},
    {'path':'/plot','dx':float('nan'),'dy':0}, {'path':'/plot','dx':True,'dy':0},
    {'path':'/plot','dx':0,'dy':0,'factor':0}, {'path':'/plot','dx':0,'dy':0,'factor':-1},
    {'path':'/plot','dx':0,'dy':0,'corner':'se'},
    {'path':'/plot','dx':0,'dy':0,'factor':2,'corner':'bad'},
])
def test_bad_gestures_are_atomic(value):
    editor=LayoutEditor(source());before=editor.snapshot()
    with pytest.raises(ValueError):editor.command('gesture',value)
    assert editor.snapshot()==before


def test_scale_keeps_ports_and_downstream_links_attached():
    root=source();editor=LayoutEditor(root)
    before=editor.snapshot()['geometry']['/group/output']['box']
    editor.command('gesture',{'path':'/group/input','dx':0,'dy':0,'factor':1.5,'corner':'se'})
    after=editor.snapshot()['geometry']['/group/output']['box']
    assert after[0]>before[0]
    assert after[2:]==pytest.approx(before[2:])
    assert '<path' in editor.figure.to_svg()


def test_legacy_layouts_load_but_scale_requires_new_schema():
    root=source()
    legacy={'schema':'inklet.composition-layout/0.1','targets':{'/plot':{'placement':{'x':22}}}}
    restored,_=root.with_layout_overrides(legacy);assert restored._parts[1].x==22
    legacy['targets']['/plot']['placement']['scale']=1.2
    with pytest.raises(ValueError,match='schema 0.2'):root.with_layout_overrides(legacy)
    legacy['schema']=SCHEMA
    restored,_=root.with_layout_overrides(legacy);assert restored._parts[1].scale==1.2
    assert restored.layout_overrides(root)['schema']=='inklet.composition-layout/0.2'


def test_scale_validation_is_atomic_and_noop_gesture_creates_no_history():
    root=source();before=root.signature()
    for factor in (0,-1,float('nan'),True,'2'):
        with pytest.raises(ValueError):root.place('plot',scale=factor)
        assert root.signature()==before
    editor=LayoutEditor(root)
    assert editor.command('gesture',{'path':'/plot','dx':0,'dy':0})['revision']==0
    assert not editor.snapshot()['undo']


def test_browser_pointer_gestures_cancel_and_reopen_match_python(tmp_path):
    import html,re,shutil,subprocess
    chrome=shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:pytest.skip('Chrome/Chromium not installed')
    root=source();editor=LayoutEditor(root);page=editor._html()
    checks='''<script>
    (async()=>{const sleep=()=>new Promise(r=>setTimeout(r,30));async function ready(rev){for(let n=0;n<250;n++){if(state&&state.revision===rev&&!busy&&previewReady)return;await sleep();}throw Error('timeout '+rev);}
    // Synthetic pointer events do not activate native pointer capture. Exercise
    // the same handlers with a capture shim; real capture is reviewed in browser QA.
    let captured=false;overlay.setPointerCapture=()=>captured=true;overlay.hasPointerCapture=()=>captured;overlay.releasePointerCapture=()=>captured=false;
    function pointer(node,type,x,y){node.dispatchEvent(new PointerEvent(type,{bubbles:true,pointerId:7,isPrimary:true,button:0,clientX:x,clientY:y}));}
    function boxOf(selector){return document.querySelector(selector).getBoundingClientRect();}
    try{await ready(0);const original=state.svg;const target='/group/input';const old=state.geometry[target].box;
    let box=boxOf('.hit[data-path="'+target+'"]'),x=box.x+box.width/2,y=box.y+box.height/2;
    const scale=overlay.getScreenCTM().a;
    pointer(document.querySelector('.hit[data-path="'+target+'"]'),'pointerdown',x,y);pointer(overlay,'pointermove',x+6*scale,y+4*scale);pointer(overlay,'pointerup',x+6*scale,y+4*scale);await ready(1);
    if(Math.abs(state.geometry[target].box[0]-old[0]-6)>1e-6)throw Error('move coordinates');
    box=boxOf('.handle[data-corner="se"]');x=box.x+box.width/2;y=box.y+box.height/2;const before=state.geometry[target].box;
    pointer(document.querySelector('.handle[data-corner="se"]'),'pointerdown',x,y);pointer(overlay,'pointermove',x+before[2]*scale*.2,y+before[3]*scale*.2);pointer(overlay,'pointerup',x+before[2]*scale*.2,y+before[3]*scale*.2);await ready(2);
    if(Math.abs(state.geometry[target].box[2]/before[2]-1.2)>1e-6)throw Error('scale geometry');
    const saved=await(await fetch(byId('save').href)).json(),svg=state.svg;
    box=boxOf('.hit[data-path="'+target+'"]');x=box.x+box.width/2;y=box.y+box.height/2;
    pointer(document.querySelector('.hit[data-path="'+target+'"]'),'pointerdown',x,y);pointer(overlay,'pointermove',x+25,y+10);document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));pointer(overlay,'pointerup',x+25,y+10);
    if(state.revision!==2||state.svg!==svg||gesture!==null)throw Error('cancel mutated state');
    byId('undo').click();await ready(3);byId('undo').click();await ready(4);if(state.svg!==original)throw Error('undo original');
    await request('load',saved);await ready(5);if(state.svg!==svg)throw Error('reopen');
    document.body.dataset.gestureTest=JSON.stringify({ok:true,saved,svg});
    }catch(error){document.body.dataset.gestureTest=JSON.stringify({error:error.message});}})();</script>'''
    editor._html=lambda:page.replace('</body>',checks+'</body>')
    with editor:
        run=subprocess.run([chrome,'--headless','--no-sandbox','--dump-dom','--virtual-time-budget=18000',
                            f'--user-data-dir={tmp_path}/chrome',editor.url],capture_output=True,text=True,timeout=45)
    match=re.search(r'data-gesture-test="([^"]+)"',run.stdout)
    assert match,run.stderr[-2000:]
    report=json.loads(html.unescape(match[1]));assert report.get('ok'),report
    restored,_=root.with_layout_overrides(report['saved'])
    doc=i.document(width=160,height=100,margin=0);doc.add('composition',restored)
    assert doc.compile().to_svg()==report['svg']
