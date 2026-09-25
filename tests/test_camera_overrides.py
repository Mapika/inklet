"""Camera edits follow native source revisions and the composition transaction."""
from dataclasses import replace
import json

import pytest
import inklet as i
from inklet.document.layout_overrides import SCHEMA
from inklet.editor import LayoutEditor
from inklet.three.camera import Camera
from inklet.three.linalg import Vec3


def source(view='three-quarter'):
    root=i.composition(100,70)
    root.add('model',i.component(i.solid,'cube',width=35,view=view,style='shaded'),x=15,y=15)
    return root


def edit(editor,**fields):
    kind=editor.snapshot()['targets']['/model']['cameras']['view']['kind']
    return editor.command('edit',{'path':'/model','cameras':{'view':{'kind':kind,**fields}}})


def test_camera_and_layout_share_history_and_reopen_at_two_widths():
    root=source();signature=root.signature();editor=LayoutEditor(root);before=editor.snapshot()
    result=editor.command('edit',{'path':'/model','placement':{'x':20},
        'cameras':{'view':{'kind':'native-orbit','azimuth':12,'elevation':18,'roll':8,'perspective':True}}})
    assert result['svg']!=before['svg'] and root.signature()==signature
    saved=json.loads(json.dumps(editor.overrides()))
    editor.command('undo');assert editor.figure.to_svg()==before['svg']
    editor.command('redo');assert editor.figure.to_svg()==result['svg']
    for width in (100,150):
        restored,_=root.with_layout_overrides(saved)
        doc=i.document(width=width,height=70,margin=0);doc.add('composition',restored)
        reopened=LayoutEditor(root,width=width);reopened.command('load',saved)
        assert reopened.figure.to_svg()==doc.compile().to_svg()
        assert reopened.figure.to_pdf()==doc.compile().to_pdf()
    editor.command('reset','/model');assert editor.figure.to_svg()==before['svg']


def test_geometry_replacement_and_unedited_camera_fields_remain_live():
    root=source();editor=LayoutEditor(root);old=editor.figure;svg=old.to_svg()
    edit(editor,azimuth=10)
    root.replace('model',i.component(i.solid,'cylinder',width=35,view=Camera(elevation=25,roll=7),style='shaded'))
    result=editor.command('refresh');camera=result['targets']['/model']['cameras']['view']
    assert camera['azimuth']==10 and camera['elevation']==25 and camera['roll']==7
    assert not result['report']['orphaned_targets'] and old.to_svg()==svg


def test_look_at_preserves_source_eye_target_and_up():
    camera=Camera.look_at(Vec3(3,-4,2),Vec3(0,0,0))
    root=source(camera);editor=LayoutEditor(root)
    controls=editor.snapshot()['targets']['/model']['cameras']['view']
    assert controls['kind']=='native-look-at' and 'azimuth' not in controls
    edit(editor,roll=12,perspective=True)
    restored,_=root.with_layout_overrides(editor.overrides())
    assert restored['model'].kwargs['view']==replace(camera,roll=12,perspective=True)


@pytest.mark.parametrize('changes',[
    {'azimuth':float('nan')},{'roll':True},{'fov':0},{'fov':180},
    {'perspective':1},{'elevation':91},{'eye':[1,2,3]},
])
def test_invalid_camera_edits_do_not_change_state(changes):
    editor=LayoutEditor(source());before=editor.snapshot()
    with pytest.raises(ValueError):edit(editor,**changes)
    assert editor.snapshot()==before


def test_changed_camera_kind_is_orphan_and_drop_keeps_layout():
    root=source();editor=LayoutEditor(root)
    editor.command('edit',{'path':'/model','placement':{'x':22},'cameras':{'view':{'kind':'native-orbit','azimuth':10}}})
    root['model'].kwargs['view']=Camera.look_at(Vec3(3,-4,2))
    before=editor.snapshot()
    with pytest.raises(i.LayoutError,match='/model#camera:view'):editor.command('refresh')
    assert editor.snapshot()==before
    result=editor.command('refresh',missing='drop')
    assert result['report']['orphaned_targets']==['/model#camera:view']
    assert result['targets']['/model']['placement']['x']==22


def test_shared_model_camera_conflicts_and_editor_aliases():
    root=source();root.add('other',root['model'],x=55,y=15);editor=LayoutEditor(root)
    edit(editor,azimuth=10)
    assert editor.snapshot()['targets']['/other']['cameras']['view']['azimuth']==10
    saved=editor.overrides();saved['targets']['/other']['cameras']['view']['azimuth']=20
    with pytest.raises(i.LayoutError,match='conflicting'):root.with_layout_overrides(saved)
    editor.command('reset','/other');assert not editor.overrides()['targets']


@pytest.mark.filterwarnings('ignore:composition layout schema')
def test_capture_records_camera_diff_and_legacy_style_schema_still_loads():
    root=source();changed=root.copy();changed['model'].kwargs['view']=Camera.named('three-quarter').turned(azimuth=10)
    saved=changed.layout_overrides(root)
    assert saved['targets']['/model']['cameras']['view']=={'kind':'native-orbit','azimuth':Camera.named('three-quarter').azimuth+10}
    restored,_=root.with_layout_overrides(saved);assert LayoutEditor(restored).figure.to_svg()==LayoutEditor(changed).figure.to_svg()
    saved['schema']='inklet.composition-layout/0.4'
    with pytest.raises(ValueError,match='schema 0.5'):root.with_layout_overrides(saved)
    old={'schema':'inklet.composition-layout/0.4','targets':{'/model':{'placement':{'x':20}}}}
    editor=LayoutEditor(root);editor.command('load',old);assert editor.overrides()['schema']==SCHEMA
