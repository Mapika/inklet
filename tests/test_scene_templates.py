"""Packaged template creation, authored metadata and failure-safe outputs."""
import json
from pathlib import Path
import subprocess
import threading

import pytest
import inklet as i
from inklet.three import templates
from inklet.three.blender import blender_available, BlenderError, discover


def test_catalogue_is_available_without_blender_and_returns_independent_data(monkeypatch):
    monkeypatch.setattr(discover,'find_blender',lambda *a:pytest.fail('Unexpected Blender lookup'))
    catalogue=i.scene_templates()
    assert set(catalogue)=={'laboratory','product','architecture'}
    catalogue['product']['parameters']['width']['default']=999
    assert i.scene_templates()['product']['parameters']['width']['default']==2.8
    for definition in i.scene_templates().values():
        assert 'Overview' in definition['cameras']
        assert definition['metres_per_unit']>0
        assert definition['landmarks']


@pytest.mark.parametrize('name,params',[
    ('missing',{}),('product',{'width':100}),('product',{'width':True}),
    ('product',{'width':float('nan')}),('product',{'width':'2'}),
    ('product',{'accent':'red'}),('product',{'unexpected':3}),
    ('laboratory',{'fill_fraction':0}),('architecture',{'height':None}),
])
def test_bad_parameters_fail_before_starting_blender(tmp_path,monkeypatch,name,params):
    monkeypatch.setattr(discover,'find_blender',lambda *a:pytest.fail('Unexpected Blender lookup'))
    with pytest.raises(ValueError):i.create_scene(name,tmp_path/'scene.blend',parameters=params)
    assert not list(tmp_path.iterdir())


def fake_worker(monkeypatch, action):
    from types import SimpleNamespace
    monkeypatch.setattr(discover,'find_blender',lambda *a:SimpleNamespace(path=Path('/blender')))
    def run(command,**kwargs):
        request=json.loads(Path(command[-1]).read_text())
        return action(request,kwargs)
    monkeypatch.setattr(templates,'run_process',run)


def test_atomic_creation_refuses_racing_destination_and_cleans_stage(tmp_path,monkeypatch):
    destination=tmp_path/'scene.blend'
    def action(request,kwargs):
        Path(request['output']).write_bytes(b'BLENDER-v420payload')
        destination.write_bytes(b'authored by someone else')
        return subprocess.CompletedProcess([],0,'')
    fake_worker(monkeypatch,action)
    with pytest.raises(FileExistsError):i.create_scene('product',destination)
    assert destination.read_bytes()==b'authored by someone else'
    assert list(tmp_path.iterdir())==[destination]


@pytest.mark.parametrize('failure',['exit','missing','invalid','cancel','timeout'])
def test_failed_generation_preserves_existing_scene(tmp_path,monkeypatch,failure):
    destination=tmp_path/'scene.blend';destination.write_bytes(b'original')
    cancel=threading.Event()
    def action(request,kwargs):
        if failure=='timeout':raise subprocess.TimeoutExpired([],1)
        if failure!='missing':Path(request['output']).write_bytes(b'bad' if failure=='invalid' else b'BLENDER-v420')
        if failure=='cancel':cancel.set()
        return subprocess.CompletedProcess([],1 if failure=='exit' else 0,'worker failed')
    fake_worker(monkeypatch,action)
    with pytest.raises((BlenderError,i.RenderCancelled,subprocess.TimeoutExpired)):
        i.create_scene('product',destination,overwrite=True,cancel=cancel)
    assert destination.read_bytes()==b'original'
    assert list(tmp_path.iterdir())==[destination]


def test_successful_creation_and_explicit_replace(tmp_path,monkeypatch):
    def action(request,kwargs):
        assert request['template']['parameters']['accent']=='#abcdef'
        Path(request['output']).write_bytes(b'BLENDER-v420payload')
        return subprocess.CompletedProcess([],0,'')
    fake_worker(monkeypatch,action)
    destination=tmp_path/'scene.blend'
    assert i.create_scene('product',destination,parameters={'accent':'#ABCDEF'})==destination
    with pytest.raises(FileExistsError):i.create_scene('product',destination)
    assert i.create_scene('product',destination,parameters={'accent':'#ABCDEF'},overwrite=True)==destination


@pytest.mark.parametrize('name',['laboratory','product','architecture'])
def test_actual_templates_are_portable_editable_and_renderable(tmp_path,name):
    if not blender_available():pytest.skip('Blender integration requires Blender 4.2+')
    definition=i.scene_templates()[name]
    overrides={'height':1.5} if name=='laboratory' else {'width':3.5 if name=='product' else 6.2}
    path=i.create_scene(name,tmp_path/(name+'.blend'),parameters=overrides)
    assert path.read_bytes().startswith(b'BLENDER')
    inventory=i.inspect_blend(path)['scenes'][0]
    assert {camera['name'] for camera in inventory['cameras']}==set(definition['cameras'])
    names={obj['name'] for obj in inventory['objects']}
    assert set(definition['landmarks'].values())<=names
    assert inventory['template']['parameters'].items()>=overrides.items()
    # Relocate the .blend without its staging folder or any asset directory.
    relocated=tmp_path/'moved'/'scene.blend';relocated.parent.mkdir();path.rename(relocated)
    rendered=i.render_blend(relocated,width=60,dpi=60,samples=2,device='CPU',
        engine='CYCLES',camera='Overview',passes=('depth',),landmarks=definition['landmarks'])
    assert rendered.diagram.prim.data.startswith(b'\x89PNG')
    assert rendered.metadata['template']['name']==name
    assert rendered.metadata['template']['metres_per_unit']==definition['metres_per_unit']
    assert [item['path'] for item in rendered.metadata['dependencies']]==[str(relocated)]
    assert all(item['in_frame'] for item in rendered.metadata['landmarks'].values())


def test_deep_architectural_room_fits_default_plan_frame(tmp_path):
    if not blender_available():pytest.skip('Blender integration requires Blender 4.2+')
    path=i.create_scene('architecture',tmp_path/'deep-room.blend',
                        parameters={'width':4,'depth':6,'height':4})
    points={str(n):(x,y,z) for n,(x,y,z) in enumerate(
        ( (x,y,0) for x in (-2,2) for y in (-3,3) ))}
    view=i.render_blend(path,width=60,height=45,dpi=60,samples=2,
        device='CPU',camera='Plan',landmarks=points)
    assert all(item['in_frame'] for item in view.metadata['landmarks'].values())
